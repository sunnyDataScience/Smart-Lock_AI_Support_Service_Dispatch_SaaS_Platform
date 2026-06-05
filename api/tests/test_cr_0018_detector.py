"""CR-0018 Stage 3 — ReconExceptionDetector cron worker tests (DB mocked)。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from realtime.reconciliation_exception_detector import ReconExceptionDetector


@pytest.mark.asyncio
async def test_run_once_db_unavailable_returns_skipped(monkeypatch):
    """_ensure_conn 回 False → 直接 return {'skipped'}。"""
    import realtime.reconciliation_exception_detector as det_mod

    async def fake_ensure():
        return False

    monkeypatch.setattr(det_mod, "_ensure_conn", fake_ensure)
    w = ReconExceptionDetector()
    result = await w.run_once()
    assert result == {"skipped": "db_unavailable"}


@pytest.mark.asyncio
async def test_run_once_aggregates_three_detectors(monkeypatch):
    """三 detector 各回 N 個 row，run_once 應加總到 summary。"""
    import realtime.reconciliation_exception_detector as det_mod

    async def fake_ensure():
        return True

    monkeypatch.setattr(det_mod, "_ensure_conn", fake_ensure)

    # fake amount_mismatch 回 3, orphan 回 1, missing 回 2
    async def fake_am():
        return 3

    async def fake_orphan():
        return 1

    async def fake_missing():
        return 2

    w = ReconExceptionDetector()
    w._detect_amount_mismatch = fake_am
    w._detect_orphan_settlement = fake_orphan
    w._detect_missing_invoice = fake_missing

    summary = await w.run_once()
    assert summary == {
        "amount_mismatch": 3,
        "orphan_settlement": 1,
        "missing_invoice": 2,
        "errors": 0,
    }


@pytest.mark.asyncio
async def test_run_once_per_detector_error_isolated(monkeypatch):
    """一個 detector 拋例外不該阻斷其他兩個。"""
    import realtime.reconciliation_exception_detector as det_mod

    async def fake_ensure():
        return True

    monkeypatch.setattr(det_mod, "_ensure_conn", fake_ensure)

    async def fake_am():
        raise RuntimeError("query failed")

    async def fake_orphan():
        return 5

    async def fake_missing():
        return 4

    w = ReconExceptionDetector()
    w._detect_amount_mismatch = fake_am
    w._detect_orphan_settlement = fake_orphan
    w._detect_missing_invoice = fake_missing

    summary = await w.run_once()
    assert summary["amount_mismatch"] == 0  # not bumped
    assert summary["orphan_settlement"] == 5
    assert summary["missing_invoice"] == 4
    assert summary["errors"] == 1


@pytest.mark.asyncio
async def test_detect_amount_mismatch_calls_service_with_delta(monkeypatch):
    """SQL row mismatch → 呼 detect_exception 帶正確 delta。"""
    import realtime.reconciliation_exception_detector as det_mod

    captured = []

    class FakeCur:
        async def fetchall(self):
            return [
                # (recon_id, tenant_id, payout, settled, sid)
                ("recon-1", "tenant-1", 1000.0, 950.0, "set-1"),
                ("recon-2", "tenant-1", 500.0, 700.0, "set-2"),
            ]

    class FakeConn:
        async def execute(self, sql, *args):
            return FakeCur()

    det_mod.db_module._conn = FakeConn()

    # Patch service.detect_exception
    from services import reconciliation_exception_service as exc_svc

    async def fake_detect(**kwargs):
        captured.append(kwargs)
        return {"id": "e1"}

    monkeypatch.setattr(exc_svc, "detect_exception", fake_detect)

    w = ReconExceptionDetector()
    count = await w._detect_amount_mismatch()
    assert count == 2
    assert captured[0]["amount_delta"] == -50.0  # 950 - 1000
    assert captured[1]["amount_delta"] == 200.0  # 700 - 500
    assert captured[0]["exception_kind"] == "amount_mismatch"
    assert captured[0]["detected_by"] == "cron_daily"


@pytest.mark.asyncio
async def test_detector_default_interval_one_day():
    """sanity: 預設 interval 是一天（86400 秒），對齊 HD-5 (b) 日跑。"""
    w = ReconExceptionDetector()
    assert w._interval == 86400


@pytest.mark.asyncio
async def test_detector_start_stop_idempotent():
    """重複 start 不該炸；stop 後沒 start 也不該炸。"""
    w = ReconExceptionDetector()
    # 不 actually 跑 task — patch run 為 no-op
    w._run = lambda: None  # type: ignore[assignment]
    # stop 沒 task 應安全
    await w.stop()
    # start 兩次第二次應 no-op
    w._task = MagicMock()
    w._task.done.return_value = False
    w.start()  # second call short-circuits
