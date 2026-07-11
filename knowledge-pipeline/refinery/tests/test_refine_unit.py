"""提煉分流器單元測試(無 DB、fake LLM)。"""

from refinery.refine import REFINE_SCHEMA, draft_key, refine_card

CARD = {
    "id": "11111111-1111-4111-8111-111111111111",
    "conversation_id": "22222222-2222-4222-8222-222222222222",
    "brand": "Chatlock",
    "model": "A90",
    "symptoms": "門把掉了",
    "category": "hardware",
    "triage_tier": "L3",
    "resolution_channel": "onsite",
    "failure_mode": "handle_detached",
    "root_cause": "固定螺絲鬆脫",
    "corrective_action": "重鎖並上螺絲膠",
    "verification": True,
    "disposition": "repair",
}

TRANSCRIPT = [
    {"sender_role": "line_user", "content": "門把整個掉下來了", "created_at": None},
    {"sender_role": "ai", "content": "請問是哪個型號?", "created_at": None},
    {"sender_role": "agent_human", "content": "已為您安排師傅", "created_at": None},
]


def _fake_generate(prompt: str, system_prompt: str, schema: dict) -> dict:
    assert schema is REFINE_SCHEMA
    # 不得編造:prompt 必含 spine 與逐字稿素材
    assert "固定螺絲鬆脫" in prompt and "門把整個掉下來了" in prompt
    return {
        "case_entry": {
            "title": "Chatlock A90 門把脫落",
            "symptom": "門把鬆脫掉落",
            "resolution": "重鎖固定螺絲並上螺絲膠,現場驗證",
            "confidence": 0.9,
        },
        "behavior_candidates": [
            {
                "title": "硬體故障先問型號再派工",
                "proposal": "遇硬體脫落類,先確認型號,再走 L3 派工",
                "target_skill": "locksmith-cs-sop",
                "rationale": "對話展現的處理順序",
                "confidence": 0.6,
            }
        ],
    }


def test_refine_card_two_tracks_with_provenance():
    drafts = refine_card(
        CARD, TRANSCRIPT, generate=_fake_generate,
        llm_model="fake/model", refined_at="2026-07-10T00:00:00+00:00",
    )
    assert [d["draft_type"] for d in drafts] == ["case_entry", "behavior"]

    ce = drafts[0]
    assert ce["payload"] == {"symptom": "門把鬆脫掉落", "resolution": "重鎖固定螺絲並上螺絲膠,現場驗證"}
    assert ce["brand"] == "Chatlock" and ce["model"] == "A90"
    assert ce["source_problem_card_id"] == CARD["id"]

    # provenance 溯源完整(HITL 審計基礎)
    prov = ce["provenance"]
    assert prov["problem_card_id"] == CARD["id"]
    assert prov["conversation_id"] == CARD["conversation_id"]
    assert prov["message_count"] == 3
    assert prov["spine"]["root_cause"] == "固定螺絲鬆脫"
    assert prov["llm_model"] == "fake/model"

    bh = drafts[1]
    assert bh["payload"]["target_skill"] == "locksmith-cs-sop"


def test_draft_key_deterministic_and_content_sensitive():
    p1 = {"symptom": "a", "resolution": "b"}
    assert draft_key("cid", "case_entry", p1) == draft_key("cid", "case_entry", p1)
    assert draft_key("cid", "case_entry", p1) != draft_key("cid", "behavior", p1)
    assert draft_key("cid", "case_entry", p1) != draft_key("cid", "case_entry", {"symptom": "a", "resolution": "c"})
    assert len(draft_key("cid", "case_entry", p1)) == 16


def test_no_behavior_candidates_ok():
    def gen(prompt, system_prompt, schema):
        return {
            "case_entry": {"title": "t", "symptom": "s", "resolution": "r", "confidence": 0.5},
            "behavior_candidates": [],
        }

    drafts = refine_card(CARD, [], generate=gen)
    assert len(drafts) == 1 and drafts[0]["draft_type"] == "case_entry"
    assert drafts[0]["provenance"]["message_count"] == 0
