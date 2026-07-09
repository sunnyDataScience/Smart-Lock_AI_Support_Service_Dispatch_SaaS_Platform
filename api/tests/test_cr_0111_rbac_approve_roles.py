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


def test_roles_canon_seven_after_sa01():
    """SA-01（CR-0130）：矩陣收斂 7 角色正典＋line_user 通道行（legacy 6 行移除）。"""
    expected = {
        "admin", "operations_manager", "reviewer", "customer_service",
        "dispatcher", "technician", "line_user",
    }
    assert set(r._ROLE_META.keys()) == expected
    assert set(r._MATRIX.keys()) == set(r._ROLE_META.keys())


def test_reviewer_workorder_readonly_but_approves_refund():
    """SA-01 後會計職能由 reviewer 承接：不可改工單狀態；但可核准退款/爭議。"""
    rev = _perms("reviewer")
    assert rev["work_orders"]["write"] is False
    assert rev["work_orders"]["read"] is True
    assert rev["refunds"]["approve"] is True
    assert rev["disputes"]["approve"] is True


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


def test_hierarchy_admin_can_grant_canon_roles():
    """SA-01：admin 可授權 7 正典中的下階角色；死角色/legacy 階層 0 一律拒。"""
    for role in ["operations_manager", "reviewer", "customer_service", "dispatcher", "technician"]:
        assert role in r.ROLE_HIERARCHY
        assert r.can_grant("admin", role) is True
    # admin 不可改同階
    assert r.can_grant("admin", "admin") is False
    # 死角色/legacy 由 ALLOWED_TARGET_ROLES 阻擋（不可作為授權目標）
    assert "super_admin" not in r.ALLOWED_TARGET_ROLES
    assert "accounting" not in r.ALLOWED_TARGET_ROLES
