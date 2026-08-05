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


# ── target_skill 不採信 LLM 回傳值（TC-REF-SPLIT-01 hardening）────────────
#
# 對話逐字稿是外部輸入，會一路進 LLM prompt。若模型被注入而在 target_skill
# 填了任意字串，原本會直接落進 draft payload → DB → 審核流程。行為草稿只有
# locksmith-cs-sop 一個合法標的，這個欄位不該由模型決定。


def _injected_generate(prompt: str, system_prompt: str, schema: dict) -> dict:
    """模擬被注入：target_skill 被塞成別的東西。"""
    base = _fake_generate(prompt, system_prompt, schema)
    base["behavior_candidates"][0]["target_skill"] = "../../etc/passwd"
    return base


def test_target_skill_is_coerced_not_taken_from_llm(capsys):
    drafts = refine_card(
        CARD, TRANSCRIPT, generate=_injected_generate,
        llm_model="fake/model", refined_at="2026-07-10T00:00:00+00:00",
    )
    bh = drafts[1]
    assert bh["draft_type"] == "behavior"
    # 收斂為常數，不採信模型輸出
    assert bh["payload"]["target_skill"] == "locksmith-cs-sop"
    # 提案本體保留（收斂而非丟棄——仍要送人工審核）
    assert bh["payload"]["proposal"] == "遇硬體脫落類,先確認型號,再走 L3 派工"
    # 異常必須看得見
    assert "target_skill 非預期值" in capsys.readouterr().out


def test_schema_pins_target_skill_enum():
    """schema 這層也釘住值域——雙保險，且讓支援 enum 的供應商在生成時就受限。"""
    props = REFINE_SCHEMA["properties"]["behavior_candidates"]["items"]["properties"]
    assert props["target_skill"]["enum"] == ["locksmith-cs-sop"]
