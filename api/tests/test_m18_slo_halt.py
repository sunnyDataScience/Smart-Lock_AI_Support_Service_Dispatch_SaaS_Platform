"""M18 SLO halt decision — admin manual trigger model (HD-: WBS §8 P1 解 DEFERRED)。"""

from __future__ import annotations

import pytest

from services import config_m18_service as svc


class FakeCur:
    def __init__(self, row=None):
        self._row = row

    async def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    async def execute(self, sql, *args):
        result = self._results[self._idx] if self._idx < len(self._results) else FakeCur()
        self._idx += 1
        return result


# ----------------------------- happy path -----------------------------

@pytest.mark.asyncio
async def test_slo_check_under_threshold_no_halt(monkeypatch):
    """error_rate 0.5% < 1% threshold → should_halt=false。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    async def fake_audit(**kwargs):
        pass

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    monkeypatch.setattr(svc, "_append_audit", fake_audit)

    db_module._conn = FakeConn([
        FakeCur(row=(
            "rollout-1", "5%", "v1", "tenant-1", "ns", "key",
        )),
    ])

    result = await svc.check_slo_halt(
        tenant_id="t1", rollout_id="rollout-1",
        error_rate_pct=0.5, p99_latency_ms=500,
    )
    assert result["decision"]["should_halt"] is False
    assert result["decision"]["exceeded"] == []
    assert result["current_stage"] == "5%"
    assert "SLO 通過" in result["recommendation"]


@pytest.mark.asyncio
async def test_slo_check_error_rate_breach(monkeypatch):
    """error_rate 2% > 1% → should_halt + exceeded 列原因。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    async def fake_audit(**kwargs):
        pass

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    monkeypatch.setattr(svc, "_append_audit", fake_audit)

    db_module._conn = FakeConn([
        FakeCur(row=("rollout-1", "50%", "v1", "tenant-1", "ns", "key")),
    ])

    result = await svc.check_slo_halt(
        tenant_id="t1", rollout_id="rollout-1",
        error_rate_pct=2.0, p99_latency_ms=500,
    )
    assert result["decision"]["should_halt"] is True
    assert any("error_rate" in s for s in result["decision"]["exceeded"])
    assert "立即呼 rollback" in result["recommendation"]


@pytest.mark.asyncio
async def test_slo_check_latency_breach(monkeypatch):
    """p99 latency 1500ms > 1000ms → should_halt。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    async def fake_audit(**kwargs):
        pass

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    monkeypatch.setattr(svc, "_append_audit", fake_audit)

    db_module._conn = FakeConn([
        FakeCur(row=("rollout-1", "5%", "v1", "tenant-1", "ns", "key")),
    ])

    result = await svc.check_slo_halt(
        tenant_id="t1", rollout_id="rollout-1",
        error_rate_pct=0.5, p99_latency_ms=1500,
    )
    assert result["decision"]["should_halt"] is True
    assert any("p99_latency" in s for s in result["decision"]["exceeded"])


@pytest.mark.asyncio
async def test_slo_check_custom_strict_threshold(monkeypatch):
    """自訂門檻 0.1% → error_rate 0.5% breach。"""
    import core.db as db_module

    async def fake_ensure():
        return True

    async def fake_audit(**kwargs):
        pass

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    monkeypatch.setattr(svc, "_append_audit", fake_audit)

    db_module._conn = FakeConn([
        FakeCur(row=("rollout-1", "5%", "v1", "tenant-1", "ns", "key")),
    ])

    result = await svc.check_slo_halt(
        tenant_id="t1", rollout_id="rollout-1",
        error_rate_pct=0.5, error_rate_slo_pct=0.1,
    )
    assert result["decision"]["should_halt"] is True


@pytest.mark.asyncio
async def test_slo_check_rollout_not_found(monkeypatch):
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn([FakeCur(row=None)])

    with pytest.raises(ApiError) as e:
        await svc.check_slo_halt(
            tenant_id="t1", rollout_id="nope", error_rate_pct=0.5,
        )
    assert e.value.error_code == "CONFIG_NOT_FOUND"


@pytest.mark.asyncio
async def test_slo_check_already_100_rejects(monkeypatch):
    """rollout 已 100% → 409 不需 halt 決策。"""
    from core.errors import ApiError
    import core.db as db_module

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    db_module._conn = FakeConn([
        FakeCur(row=("rollout-1", "100%", "v1", "tenant-1", "ns", "key")),
    ])

    with pytest.raises(ApiError) as e:
        await svc.check_slo_halt(
            tenant_id="t1", rollout_id="rollout-1", error_rate_pct=0.5,
        )
    assert e.value.status_code == 409


@pytest.mark.asyncio
async def test_slo_check_negative_error_rate_rejected(monkeypatch):
    from core.errors import ApiError

    async def fake_ensure():
        return True

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)

    with pytest.raises(ApiError) as e:
        await svc.check_slo_halt(
            tenant_id="t1", rollout_id="rollout-1", error_rate_pct=-1,
        )
    assert e.value.error_code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_slo_check_writes_audit_trail(monkeypatch):
    """每次 check 都應寫 audit row (slo_check trail)，不論 should_halt。"""
    import core.db as db_module

    captured = []

    async def fake_ensure():
        return True

    async def fake_audit(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(svc, "_ensure_conn", fake_ensure)
    monkeypatch.setattr(svc, "_append_audit", fake_audit)

    db_module._conn = FakeConn([
        FakeCur(row=("rollout-1", "5%", "v1", "tenant-1", "ns", "key")),
    ])

    await svc.check_slo_halt(
        tenant_id="t1", rollout_id="rollout-1",
        error_rate_pct=0.5, p99_latency_ms=500,
        actor_user_id="admin-1",
    )
    assert len(captured) == 1
    audit_call = captured[0]
    assert audit_call["actor_user_id"] == "admin-1"
    assert audit_call["diff"]["slo_check"] is True
    assert audit_call["diff"]["should_halt"] is False
    assert audit_call["diff"]["observed"]["error_rate_pct"] == 0.5


# ----------------------------- router -----------------------------

def test_router_endpoint_registered():
    from routers import config_m18 as mod
    ids = {getattr(r, "operation_id", None) for r in mod.router.routes}
    assert "checkConfigRolloutSlo" in ids
