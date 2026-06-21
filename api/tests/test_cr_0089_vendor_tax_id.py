"""CR-0089 廠商註冊統一編號 + 公司名必填 — VendorRegisterBody 驗證單元測試。

純 Pydantic 驗證（無 DB）：統編 8 碼必填、公司名必填。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from routers.auth import VendorRegisterBody

pytestmark = pytest.mark.unit


def _base() -> dict:
    return dict(
        vendor_type="brand",
        name="王經理",
        company_name="測試品牌股份有限公司",
        tax_id="12345678",
        phone="0912345678",
        email="v@example.com",
        password="vendorpass123",
        address="台北市信義區",
    )


def test_valid_vendor_body():
    b = VendorRegisterBody(**_base())
    assert b.tax_id == "12345678"
    assert b.company_name == "測試品牌股份有限公司"


def test_tax_id_required():
    d = _base()
    del d["tax_id"]
    with pytest.raises(ValidationError):
        VendorRegisterBody(**d)


@pytest.mark.parametrize("bad", ["1234567", "123456789", "1234567a", "", "abcdefgh"])
def test_tax_id_must_be_8_digits(bad):
    d = _base()
    d["tax_id"] = bad
    with pytest.raises(ValidationError):
        VendorRegisterBody(**d)


def test_company_name_required():
    d = _base()
    del d["company_name"]
    with pytest.raises(ValidationError):
        VendorRegisterBody(**d)


def test_company_name_not_empty():
    d = _base()
    d["company_name"] = ""
    with pytest.raises(ValidationError):
        VendorRegisterBody(**d)
