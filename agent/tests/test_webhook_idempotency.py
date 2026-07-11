"""CR-0166 R1：PostgresWebhookIdempotencyStore 去重語意（LINE webhook 重送防護）。

需 POSTGRES_URI 指向有 webhook_idempotency 表的庫（scratch）。無則 skip。
"""

from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_URI"), reason="需 POSTGRES_URI（scratch webhook_idempotency 表）"
)


def _store():
    from lockcore.agent.user_memory.postgres_store import PostgresWebhookIdempotencyStore

    return PostgresWebhookIdempotencyStore(os.environ["POSTGRES_URI"])


def test_first_seen_false_repeat_true():
    """首見回 False（放行）；同 event_id 再見回 True（重複，caller skip）。"""
    store = _store()
    eid = f"evt-{uuid.uuid4().hex}"
    try:
        assert store.mark_seen(eid, tenant="default") is False  # 首見放行
        assert store.mark_seen(eid, tenant="default") is True   # 重送擋下
        assert store.mark_seen(eid, tenant="default") is True   # 再送仍擋
    finally:
        store._db.conn().execute(
            "DELETE FROM webhook_idempotency WHERE event_id=%s", (eid,))
        store.close()


def test_distinct_events_both_pass():
    """不同 event_id 各自首見皆放行。"""
    store = _store()
    e1, e2 = f"evt-{uuid.uuid4().hex}", f"evt-{uuid.uuid4().hex}"
    try:
        assert store.mark_seen(e1) is False
        assert store.mark_seen(e2) is False
    finally:
        store._db.conn().execute(
            "DELETE FROM webhook_idempotency WHERE event_id = ANY(%s)", ([e1, e2],))
        store.close()


def test_empty_event_id_fail_open():
    """空 event_id → 回 False（不去重、放行；不寫庫）。"""
    store = _store()
    try:
        assert store.mark_seen("", tenant="default") is False
        assert store.mark_seen(None, tenant="default") is False  # type: ignore[arg-type]
    finally:
        store.close()
