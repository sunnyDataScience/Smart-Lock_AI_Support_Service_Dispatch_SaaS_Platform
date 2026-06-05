"""CR-0018 Stage 3 — router 結構 smoke tests (不啟 lifespan / 不打 DB)。

策略：
- HTTP integration（含 cross-tenant / X-Initiator / voucher_void 連動）走
  conftest.py 既有 client fixture 需 POSTGRES_URI；本檔不重複那層。
- 改為純 router 結構驗證：
  - operationId 唯一性對齊 OpenAPI 規範
  - body schema 欄位齊全
  - 8 endpoints 全部註冊
  - dispatch 表（router_mod 引用 svc & voucher_void_service）就位
- 真實 HTTP+DB 整合留給 dev 環境 / CI 跑（同 reconciliations_v2 pattern）。
"""

from __future__ import annotations

from routers import reconciliation_exceptions_v2 as router_mod


# ----------------------------- 結構檢查 -----------------------------

def test_router_has_8_endpoints():
    """detect / list / get / advance / propose / approve / apply / close。"""
    routes = router_mod.router.routes
    assert len(routes) == 8


def test_router_operation_ids_unique():
    ids = [getattr(r, "operation_id", None) for r in router_mod.router.routes]
    ids = [i for i in ids if i]
    assert len(ids) == len(set(ids)), f"duplicate operationIds: {ids}"


def test_router_expected_operation_ids():
    """對齊 spec — operation_id 必須穩定（破壞性變更觸發 contract 變動）。"""
    ids = {getattr(r, "operation_id", None) for r in router_mod.router.routes}
    expected = {
        "detectReconciliationException",
        "listReconciliationExceptions",
        "getReconciliationException",
        "advanceReconciliationException",
        "proposeReconciliationExceptionFix",
        "approveReconciliationExceptionFix",
        "applyReconciliationExceptionFix",
        "closeReconciliationException",
    }
    assert ids == expected


def test_router_paths_tenant_scoped():
    """所有路徑都應在 /tenants/{tenantId}/... 下（ADR-0030 tenant scoping）。"""
    for r in router_mod.router.routes:
        path = getattr(r, "path", "")
        assert path.startswith("/tenants/{tenantId}/accounting/"), (
            f"non-tenant path: {path}"
        )


# ----------------------------- service 依賴 -----------------------------

def test_router_imports_required_services():
    """svc + voucher_void_service 必須在 router_mod 可見（連動點）。"""
    assert hasattr(router_mod, "svc")
    assert hasattr(router_mod, "voucher_void_service")
    assert hasattr(router_mod.voucher_void_service, "void_voucher")


# ----------------------------- body schema -----------------------------

def test_propose_fix_body_required_field():
    """ProposeFixBody.fix_path 必填。"""
    from pydantic import ValidationError

    with __import__("pytest").raises(ValidationError):
        router_mod.ProposeFixBody()


def test_apply_fix_body_optional_fields_default_correct():
    """ApplyFixBody.void_reason 預設 'error_correction'。"""
    body = router_mod.ApplyFixBody()
    assert body.void_reason == "error_correction"
    assert body.voucher_id is None
    assert body.invoice_id is None


def test_detect_body_required_fields():
    """DetectBody.reconciliation_id / exception_kind / description 必填。"""
    from pydantic import ValidationError

    with __import__("pytest").raises(ValidationError):
        router_mod.DetectBody()


def test_detect_body_default_detected_by():
    body = router_mod.DetectBody(
        reconciliation_id="r1", exception_kind="amount_mismatch", description="x",
    )
    assert body.detected_by == "manual"
