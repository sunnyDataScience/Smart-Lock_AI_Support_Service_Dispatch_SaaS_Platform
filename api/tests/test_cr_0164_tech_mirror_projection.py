"""CR-0164 B：tech_mirror users 投影最小化——不鏡射憑證/PII。

原 SELECT * 全欄鏡射技師 users（含 password_hash/email/phone/address）到品牌庫，
抵銷 CR-0112「憑證集中權威庫」。修：users 走欄位白名單。技師登入 lookup 改讀權威庫。
"""

from __future__ import annotations

import pytest

from core import tech_mirror

pytestmark = pytest.mark.component


def test_users_projection_excludes_credentials_and_pii():
    """users 投影白名單不含 password_hash/email/phone/address。"""
    cols = tech_mirror._USERS_PROJECTION_COLS
    for sensitive in ("password_hash", "email", "phone", "address"):
        assert sensitive not in cols, f"投影不應含憑證/PII 欄 {sensitive}"
    # 品牌側剛性依賴的欄須保留
    for needed in ("id", "tenant_id", "role", "is_active",
                   "failed_login_attempts", "locked_until", "password_changed_at"):
        assert needed in cols, f"投影應保留 {needed}（A1/A2/A3/FK 依賴）"


def test_select_cols_users_vs_other_tables():
    """users 走白名單、其他技師表仍全欄鏡射。"""
    users_sel = tech_mirror._select_cols("users")
    assert "password_hash" not in users_sel and "email" not in users_sel
    assert "id" in users_sel and "role" in users_sel
    # 非 users 表全欄（technicians 顯示名/證照等品牌側需要）
    assert tech_mirror._select_cols("technicians") == "*"
    assert tech_mirror._select_cols("technician_certification") == "*"


def test_login_lookup_routes_technician_to_authority():
    """_login_lookup_conn 對 role_in==['technician'] 走權威庫，其餘走主庫。"""
    import inspect

    from services import auth_service
    src = inspect.getsource(auth_service._login_lookup_conn)
    assert 'role_in == ["technician"]' in src
    assert "require_tech_conn" in src
