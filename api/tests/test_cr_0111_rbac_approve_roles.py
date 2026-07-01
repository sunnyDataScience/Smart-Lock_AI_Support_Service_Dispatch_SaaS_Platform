"""CR-0111 — RBAC 權限矩陣補齊（service 層，無 DB）。

驗證權威來源（final-spec sheet 11 + M17 BR-M17-01「can-view/can-edit/can-approve」+
Q&A 具體規則）落地到 role_service._MATRIX：
  1. 權限維度含 approve（4 動作）
  2. 角色補齊至 12（含會計 / 主管 / 派工 / 稽核 / 家族覆核 / 經銷）
  3. owner 已確認規則：會計可核准退款、不可改工單狀態（Q113=No）
  4. approve 依角色分層（admin/reviewer/accounting 有；technician/line_user 無）
  5. 階層強制：admin 可授權所有新角色（tier 嚴格 >）

這些為純資料/純函式斷言，不連 DB。
"""

from services import role_service as r


def _perms(role_id: str) -> dict:
    """回傳 {resource: perm-dict} 方便查。"""
    row = r._role_to_dict(role_id, 0)
    return {p["resource"]: p for p in row["permissions"]}


def test_approve_is_fourth_dimension():
    assert r._ACTIONS == ("read", "write", "delete", "approve")
    # 每個 permission row 都帶 approve 欄
    for p in r._role_to_dict("admin", 0)["permissions"]:
        assert "approve" in p


def test_roles_completed_to_twelve():
    expected = {
        "admin", "reviewer", "technician", "brand_oem", "line_user",
        "accounting", "supervisor", "dispatcher", "customer_service",
        "auditor", "family_reviewer", "distributor",
    }
    assert expected <= set(r._ROLE_META.keys())
    assert set(r._MATRIX.keys()) == set(r._ROLE_META.keys())


def test_accounting_q113_workorder_readonly_but_approves_refund():
    """final-spec Q113：會計不可改工單狀態；但可核准退款/月結。"""
    acct = _perms("accounting")
    assert acct["work_orders"]["write"] is False   # Q113=No
    assert acct["work_orders"]["read"] is True
    assert acct["refunds"]["approve"] is True
    assert acct["accounting"]["approve"] is True


def test_approve_tiered_by_role():
    # admin：業務資源可核准
    assert _perms("admin")["refunds"]["approve"] is True
    # reviewer：退款/保固/爭議可核准
    rev = _perms("reviewer")
    assert rev["refunds"]["approve"] is True
    assert rev["disputes"]["approve"] is True
    # technician / line_user：無任何核准權
    tech = _perms("technician")
    assert all(p["approve"] is False for p in tech.values())
    line = _perms("line_user")
    assert all(p["approve"] is False for p in line.values())


def test_customer_service_cannot_approve_refund():
    """客服：可看退款、但高金額需主管/會計 → 無 approve。"""
    cs = _perms("customer_service")
    assert cs["refunds"]["read"] is True
    assert cs["refunds"]["approve"] is False


def test_hierarchy_admin_can_grant_new_roles():
    for role in ["accounting", "supervisor", "dispatcher",
                 "customer_service", "auditor", "family_reviewer", "distributor"]:
        assert role in r.ROLE_HIERARCHY
        assert r.can_grant("admin", role) is True
    # admin 仍不可改同階/更高階
    assert r.can_grant("admin", "admin") is False
    assert r.can_grant("admin", "super_admin") is False
