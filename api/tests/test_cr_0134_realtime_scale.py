"""CR-0134 即時通道多實例化（WBS 1.3.1 / SA-02）。

- cron 分散式鎖：PG advisory lock 領導者選舉——他 session 持鎖時 ensure_leader=False
  （不重跑）；釋放後可接手（failover）；同 session 冪等 True。
- WS hub Redis 橋：publish 本地即刻＋Redis 複寫（stub 驗證信封/自跳過）；
  未設 REDIS_URL＝單機行為不變。
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid

import pytest

import core.db as db_module
from core import distributed_lock as dl

TID = "00000000-0000-0000-0000-000000000001"

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_advisory_lock_mutual_exclusion_and_failover():
    """他 session 持鎖 → ensure_leader=False；他 session 釋放 → 本 session 接手。"""
    assert await db_module._ensure_conn()
    import psycopg

    job = f"testjob-{uuid.uuid4().hex[:8]}"
    key = dl._job_key(job)
    other = await psycopg.AsyncConnection.connect(os.environ["POSTGRES_URI"], autocommit=True)
    try:
        # 他實例（另一 session）先搶到
        cur = await other.execute("SELECT pg_try_advisory_lock(%s, %s)", (dl._LOCK_NS, key))
        assert (await cur.fetchone())[0] is True

        assert await dl.ensure_leader(job) is False, "他 session 持鎖時不可重跑"

        # 他實例讓出 → 本 session 接手（failover）
        await other.execute("SELECT pg_advisory_unlock(%s, %s)", (dl._LOCK_NS, key))
        assert await dl.ensure_leader(job) is True
        # 冪等（快取，不堆疊）
        assert await dl.ensure_leader(job) is True
    finally:
        await dl.release_leader(job)
        await other.close()


@pytest.mark.asyncio
async def test_leader_blocks_second_session():
    """本 session 為 leader 時，他 session 搶不到（cron 不重跑的另一向）。"""
    assert await db_module._ensure_conn()
    import psycopg

    job = f"testjob-{uuid.uuid4().hex[:8]}"
    key = dl._job_key(job)
    try:
        assert await dl.ensure_leader(job) is True
        other = await psycopg.AsyncConnection.connect(os.environ["POSTGRES_URI"], autocommit=True)
        try:
            cur = await other.execute("SELECT pg_try_advisory_lock(%s, %s)", (dl._LOCK_NS, key))
            assert (await cur.fetchone())[0] is False
        finally:
            await other.close()
    finally:
        await dl.release_leader(job)


# ── WS hub Redis 橋（stub） ──────────────────────────────────────────────────

class _StubRedis:
    def __init__(self):
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, data: str):
        self.published.append((channel, data))


class _StubWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, message):
        self.sent.append(message)


@pytest.mark.asyncio
async def test_hub_publish_local_plus_redis_envelope():
    """publish：本地連線即刻收到＋Redis 複寫信封帶 src/channel/message。"""
    from realtime.ws_hub import WSHub, _REDIS_BROADCAST_CHANNEL

    hub = WSHub()
    stub = _StubRedis()
    hub._redis = stub
    ws = _StubWS()
    await hub.subscribe("/realtime/sla-alerts", ws)

    sent = await hub.publish("/realtime/sla-alerts", {"type": "sla.alert", "payload": {"x": 1}})
    assert sent == 1 and ws.sent[0]["type"] == "sla.alert"
    assert len(stub.published) == 1
    ch, data = stub.published[0]
    env = json.loads(data)
    assert ch == _REDIS_BROADCAST_CHANNEL
    assert env["src"] == hub._instance_id and env["channel"] == "/realtime/sla-alerts"
    assert env["message"]["payload"] == {"x": 1}


@pytest.mark.asyncio
async def test_hub_without_redis_behaves_local_only():
    """未設 REDIS_URL：publish 純本地（單機行為不變、不觸碰 Redis）。"""
    from realtime.ws_hub import WSHub

    hub = WSHub()
    ws = _StubWS()
    await hub.subscribe("/realtime/pool/t1", ws)
    sent = await hub.publish("/realtime/pool/t1", {"type": "pool.update"})
    assert sent == 1 and hub._redis is None


@pytest.mark.asyncio
async def test_hub_redis_publish_failure_does_not_break_local(caplog):
    """Redis publish 失敗：本地照送＋[WS_BRIDGE_ALERT] 告警。"""
    from realtime.ws_hub import WSHub

    class _Boom:
        async def publish(self, *a, **k):
            raise ConnectionError("redis down")

    hub = WSHub()
    hub._redis = _Boom()
    ws = _StubWS()
    await hub.subscribe("/realtime/x", ws)
    sent = await hub.publish("/realtime/x", {"type": "t"})
    assert sent == 1, "本地 fanout 不受 Redis 故障影響"
