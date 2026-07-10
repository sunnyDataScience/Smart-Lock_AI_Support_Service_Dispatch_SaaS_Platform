"""汲取層 + Draft Queue 元件測試(需 POSTGRES_URI 指向 scratch 庫;未設即 skip)。

⚠ 絕不對 UAT 庫(5433)跑——測試會寫入 knowledge_drafts / problem_cards。
"""

import json
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_URI"), reason="需 POSTGRES_URI(scratch 庫)"
)

TID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture()
def conn():
    from refinery import db

    os.environ.setdefault("REFINERY_TENANT_ID", TID)
    with db.connect() as c:
        yield c


def _mk_card(conn, *, knowledge_ready=True, status="resolved", with_conv=True):
    """建 user → conversation → messages → problem_card 完整鏈,回 (card_id, conv_id)。"""
    uid = str(uuid.uuid4())
    conv_id = str(uuid.uuid4()) if with_conv else None
    card_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, tenant_id, email, role) VALUES (%s::uuid, %s, %s, 'line_user')",
            (uid, TID, f"kr-test-{uid[:8]}@example.com"),
        )
        if with_conv:
            cur.execute(
                "INSERT INTO conversations (id, user_id, session_id) VALUES (%s::uuid, %s::uuid, %s)",
                (conv_id, uid, f"kr-test:{uid}"),
            )
            for role, sr, content in (
                ("user", "line_user", "門把掉了"),
                ("assistant", "ai", "請問型號?"),
                ("assistant", "agent_human", "已安排師傅"),
                ("user", None, "好的(舊資料無 sender_role)"),
            ):
                cur.execute(
                    "INSERT INTO messages (conversation_id, role, content_type, content, metadata) "
                    "VALUES (%s::uuid, %s, 'text', %s, %s::jsonb)",
                    (conv_id, role, content,
                     json.dumps({"sender_role": sr}) if sr else "{}"),
                )
        cur.execute(
            "INSERT INTO problem_cards (id, conversation_id, tenant_id, brand, model, symptoms, "
            " status, knowledge_ready, root_cause, corrective_action) "
            "VALUES (%s::uuid, %s::uuid, %s, 'Chatlock', 'A90', %s::jsonb, %s, %s, '螺絲鬆脫', '重鎖')",
            (card_id, conv_id, TID, json.dumps(["門把掉了"], ensure_ascii=False), status, knowledge_ready),
        )
    conn.commit()
    return card_id, conv_id


def _cleanup(conn, card_ids):
    with conn.cursor() as cur:
        for cid in card_ids:
            cur.execute("DELETE FROM knowledge_drafts WHERE source_problem_card_id=%s::uuid", (cid,))
            cur.execute("DELETE FROM problem_cards WHERE id=%s::uuid", (cid,))
        cur.execute("DELETE FROM users WHERE email LIKE 'kr-test-%'")  # cascade 清 conversations/messages
    conn.commit()


def _fake_drafts(card_id, conv_id, suffix=""):
    from refinery.refine import draft_key

    payload = {"symptom": f"s{suffix}", "resolution": f"r{suffix}"}
    return [{
        "draft_key": draft_key(card_id, "case_entry", payload),
        "draft_type": "case_entry",
        "source_problem_card_id": card_id,
        "source_conversation_id": conv_id,
        "brand": "Chatlock", "model": "A90", "category": None,
        "title": f"測試草稿{suffix}",
        "payload": payload,
        "provenance": {"problem_card_id": card_id, "test": True},
        "confidence": 0.8,
    }]


def test_intake_picks_only_ready_cards_without_drafts(conn):
    from refinery import intake, store

    ready, _ = _mk_card(conn)
    not_ready, _ = _mk_card(conn, knowledge_ready=False)
    not_resolved, _ = _mk_card(conn, status="confirmed")
    try:
        ids = [c["id"] for c in intake.list_pending_cards(conn, TID, limit=100)]
        assert ready in ids and not_ready not in ids and not_resolved not in ids

        # 落 draft 後不再撿起(冪等)
        store.insert_drafts(conn, TID, _fake_drafts(ready, None))
        ids2 = [c["id"] for c in intake.list_pending_cards(conn, TID, limit=100)]
        assert ready not in ids2
    finally:
        _cleanup(conn, [ready, not_ready, not_resolved])


def test_transcript_sender_role_with_fallback(conn):
    from refinery import intake

    card_id, conv_id = _mk_card(conn)
    try:
        t = intake.fetch_transcript(conn, conv_id)
        assert [m["sender_role"] for m in t] == ["line_user", "ai", "agent_human", "line_user"]
        assert t[0]["content"] == "門把掉了"
    finally:
        _cleanup(conn, [card_id])


def test_insert_idempotent_and_rerefine_supersede(conn):
    from refinery import intake, store

    card_id, conv_id = _mk_card(conn)
    try:
        drafts = _fake_drafts(card_id, conv_id)
        assert store.insert_drafts(conn, TID, drafts) == 1
        assert store.insert_drafts(conn, TID, drafts) == 0  # 重跑冪等

        # 審核者退回重煉 → 卡重新可撿;重煉時舊 draft 標 superseded
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE knowledge_drafts SET status='re_refine' WHERE source_problem_card_id=%s::uuid",
                (card_id,),
            )
        conn.commit()
        ids = [c["id"] for c in intake.list_pending_cards(conn, TID, limit=100)]
        assert card_id in ids

        assert store.supersede_rerefine(conn, TID, card_id) == 1
        assert store.insert_drafts(conn, TID, _fake_drafts(card_id, conv_id, suffix="2")) == 1
        counts = store.queue_counts(conn, TID)
        assert counts.get("superseded", 0) >= 1 and counts.get("pending_review", 0) >= 1
    finally:
        _cleanup(conn, [card_id])


def test_tenant_default_deny(monkeypatch):
    from refinery import db

    monkeypatch.delenv("REFINERY_TENANT_ID", raising=False)
    with pytest.raises(RuntimeError, match="REFINERY_TENANT_ID"):
        db.tenant_id()
