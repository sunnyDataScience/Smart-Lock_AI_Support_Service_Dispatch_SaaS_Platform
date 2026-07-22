"""BR-SETTLE-05 月結對帳閘門單元測試（0722 稽核缺口銷案）——不碰 DB/Kafka。

手法比照 test_cr_0132_pc_dual_gate.py：monkeypatch M18 config 開關 +
reconcile_commission 假結果，直測 `_assert_reconcile_gate`。
"""

import pytest

from core.errors import ApiError
from services import config_m18_service, event_reconcile_service, monthly_settlement_service

pytestmark = pytest.mark.asyncio


def _cfg(value):
    async def _read(*, namespace: str, key: str = "default"):
        assert namespace == "settlement_policy"
        return value
    return _read


def _reconcile(result: dict):
    async def _run(*, tenant_id: str):
        return result
    return _run


async def test_default_off_no_gate(monkeypatch):
    """config 未設（None）＝沿用現行行為：不檢查、不呼叫 reconcile。"""
    monkeypatch.setattr(config_m18_service, "read_global_value", _cfg(None))

    async def _boom(*, tenant_id):  # pragma: no cover — 不該被呼叫
        raise AssertionError("gate off 不應觸發對帳")

    monkeypatch.setattr(event_reconcile_service, "reconcile_commission", _boom)
    await monthly_settlement_service._assert_reconcile_gate("t-1")


async def test_enforced_mismatch_blocks(monkeypatch):
    monkeypatch.setattr(
        config_m18_service, "read_global_value", _cfg({"reconcile_gate_enforce": True}))
    monkeypatch.setattr(
        event_reconcile_service, "reconcile_commission",
        _reconcile({"gate_pass": False,
                    "mismatched": [{"settlement_id": "s-1"}], "missing": ["s-2"]}))
    with pytest.raises(ApiError) as ei:
        await monthly_settlement_service._assert_reconcile_gate("t-1")
    assert ei.value.error_code == "RECONCILE_GATE_UNMET"
    assert ei.value.status_code == 409


async def test_enforced_pass_proceeds(monkeypatch):
    monkeypatch.setattr(
        config_m18_service, "read_global_value", _cfg({"reconcile_gate_enforce": True}))
    monkeypatch.setattr(
        event_reconcile_service, "reconcile_commission",
        _reconcile({"gate_pass": True, "mismatched": [], "missing": []}))
    await monthly_settlement_service._assert_reconcile_gate("t-1")


async def test_enforced_kafka_off_skipped_passes(monkeypatch):
    """Kafka 未啟用＝reconcile 回 skipped/gate_pass=True → 不誤擋（fail-open by design）。"""
    monkeypatch.setattr(
        config_m18_service, "read_global_value", _cfg({"reconcile_gate_enforce": True}))
    monkeypatch.setattr(
        event_reconcile_service, "reconcile_commission",
        _reconcile({"checked": 0, "skipped": True, "gate_pass": True}))
    await monthly_settlement_service._assert_reconcile_gate("t-1")


async def test_config_read_failure_defaults_off(monkeypatch):
    async def _err(*, namespace, key="default"):
        raise RuntimeError("config 服務掛了")

    monkeypatch.setattr(config_m18_service, "read_global_value", _err)
    await monthly_settlement_service._assert_reconcile_gate("t-1")  # 不拋＝視同 off
