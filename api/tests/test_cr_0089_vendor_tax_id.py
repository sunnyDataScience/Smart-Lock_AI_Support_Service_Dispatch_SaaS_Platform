"""CR-0089 廠商統一編號 + 公司名必填 — VendorCreateBody 驗證單元測試。

原對象 VendorRegisterBody（公開自助註冊）已依 UAT R2 W3-2 裁決（2026-07-18）
移除；統編/公司名驗證語意由平台代建 body（routers/platform_vendors.py 的
VendorCreateBody）承接，本檔改驗之。純 Pydantic 驗證（無 DB）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from routers.platform_vendors import VendorCreateBody

pytestmark = pytest.mark.unit


def _base() -> dict:
    return dict(
        name="王經理",
        company_name="測試品牌股份有限公司",
        tax_id="12345678",
        phone="0912345678",
        email="v@example.com",
        password="vendorpass123",
        address="台北市信義區",
    )


def test_valid_vendor_body():
    b = VendorCreateBody(**_base())
    assert b.tax_id == "12345678"
    assert b.company_name == "測試品牌股份有限公司"
    assert b.vendor_type == "brand", "未帶 vendor_type 預設 brand"


def test_tax_id_required():
    d = _base()
    del d["tax_id"]
    with pytest.raises(ValidationError):
        VendorCreateBody(**d)


@pytest.mark.parametrize("bad", ["1234567", "123456789", "1234567a", "", "abcdefgh"])
def test_tax_id_must_be_8_digits(bad):
    d = _base()
    d["tax_id"] = bad
    with pytest.raises(ValidationError):
        VendorCreateBody(**d)


def test_company_name_required():
    d = _base()
    del d["company_name"]
    with pytest.raises(ValidationError):
        VendorCreateBody(**d)


def test_company_name_not_empty():
    d = _base()
    d["company_name"] = ""
    with pytest.raises(ValidationError):
        VendorCreateBody(**d)
