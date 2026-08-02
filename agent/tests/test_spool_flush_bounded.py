"""spool 補送不可拖住 turn（2026-08-02 掃描）。

**原問題**：`_flush_persist_spool` 在**每一輪 turn 的路徑上**執行，且持有
process 全域鎖（`_get_spool_lock()`），原本一次序列重送整個 spool
（上限 `PERSIST_SPOOL_MAX=500` 筆，每筆最多 `_PERSIST_TIMEOUT_SEC`）。

API 掛過一段時間累積出 spool 之後，下一個客人的 turn 會拿著全域鎖把整批送完——
期間**所有其他客人的下一輪全部卡死**。500 筆 × 20s 就是數小時。

**修法**：每輪只送一小批（`_SPOOL_FLUSH_MAX_PER_TURN`）且有總時間預算
（`_SPOOL_FLUSH_BUDGET_SEC`），剩下的原封留待下輪。

這是刻意的部分完成：spool 是 at-least-once 的補送佇列，晚幾輪送到不影響正確性；
把 turn 拖死才會影響所有客人。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from lockcore.channels import line_gateway as gw

pytestmark = pytest.mark.asyncio


@pytest.fixture
def spool(tmp_path, monkeypatch):
    p = tmp_path / "persist_spool.jsonl"
    monkeypatch.setattr(gw, "_PERSIST_SPOOL_PATH", str(p))
    return p


def _write(spool, n: int) -> None:
    spool.write_text(
        "\n".join(json.dumps({"tenant_id": "t", "line_user_id": f"U{i}"}) for i in range(n)) + "\n",
        encoding="utf-8",
    )


async def test_flush_stops_at_batch_limit(spool, monkeypatch):
    """spool 遠大於批次上限時，單輪只送 _SPOOL_FLUSH_MAX_PER_TURN 筆。"""
    _write(spool, 50)
    calls = 0

    async def fake_post(base, token, payload):
        nonlocal calls
        calls += 1
        return True

    monkeypatch.setattr(gw, "_post_ingest", fake_post)
    monkeypatch.setattr(gw, "_SPOOL_FLUSH_MAX_PER_TURN", 5)

    await gw._flush_persist_spool("http://x", "tok")

    assert calls == 5, f"單輪送了 {calls} 筆，超過批次上限"
    remaining = [ln for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(remaining) == 45, f"剩餘筆數不對：{len(remaining)}（應為 45）"


async def test_flush_respects_time_budget(spool, monkeypatch):
    """每筆都很慢時，總時間預算要能中斷，不可送完整批。"""
    _write(spool, 50)
    calls = 0

    async def slow_post(base, token, payload):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(gw, "_post_ingest", slow_post)
    monkeypatch.setattr(gw, "_SPOOL_FLUSH_MAX_PER_TURN", 1000)   # 讓時間預算成為唯一限制
    monkeypatch.setattr(gw, "_SPOOL_FLUSH_BUDGET_SEC", 0.15)

    await gw._flush_persist_spool("http://x", "tok")

    assert calls < 50, f"時間預算沒生效，送了 {calls} 筆"
    remaining = [ln for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert remaining, "時間預算中斷後，未送出的項目必須保留"


async def test_nothing_is_lost_when_cut_short(spool, monkeypatch):
    """被批次上限截斷時，未處理的項目一筆都不能掉。"""
    _write(spool, 20)
    monkeypatch.setattr(gw, "_SPOOL_FLUSH_MAX_PER_TURN", 3)

    async def ok(base, token, payload):
        return True

    monkeypatch.setattr(gw, "_post_ingest", ok)
    await gw._flush_persist_spool("http://x", "tok")

    remaining = [json.loads(ln) for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [r["line_user_id"] for r in remaining] == [f"U{i}" for i in range(3, 20)], (
        "截斷後剩餘內容與預期不符——可能掉了項目或順序錯亂"
    )


async def test_failed_items_are_kept(spool, monkeypatch):
    """送失敗的項目仍要留在 spool（at-least-once）。"""
    _write(spool, 3)

    async def always_fail(base, token, payload):
        return False

    monkeypatch.setattr(gw, "_post_ingest", always_fail)
    await gw._flush_persist_spool("http://x", "tok")

    remaining = [ln for ln in spool.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(remaining) == 3, "送失敗的項目被丟掉了"
