"""KYC 註冊文件靜態加密（沿 FR-API-08 的 core.media_crypto）。

2026-07-30 稽核發現：到府證據 media 早已 envelope 加密（media_service:184/297），
但 **KYC 註冊文件是唯一還在明文落盤的上傳路徑**——而它存的是身分證正反面，
敏感度高於工單照片。師傅站 UI 又已對師傅宣稱「文件加密環境保存」
（web/tech-portal/src/i18n/messages/zh-TW.json:2801），實作沒跟上宣稱。

本檔鎖住三件事：
1. 寫入落盤的位元組 != 明文（真的加密了）
2. 讀回來是明文（round-trip 正確）
3. **存量明文檔仍讀得回來**（dual-read fallback）——加密上線前上傳的檔案不能壞
"""

from __future__ import annotations

import uuid

import pytest

from core import media_crypto
from services import technician_kyc_service as kyc

_PNG = b"\x89PNG\r\n\x1a\n" + b"fake-id-card-bytes" * 8


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    async def fetchone(self):
        return self._row


class _FakeConn:
    """只回應本測試會走到的兩條 SQL：dedup 查詢（無既有列）與 INSERT。"""

    def __init__(self):
        self.inserted = None

    async def execute(self, sql, params=None):
        if sql.strip().upper().startswith("SELECT"):
            return _FakeCursor(None)          # dedup 未命中 → 走寫檔路徑
        self.inserted = (sql, params)
        return _FakeCursor(None)


@pytest.fixture
def kyc_env(tmp_path, monkeypatch):
    """把 MEDIA_ROOT 導到 tmp、繞過 token 解析與額度扣減（那些不是本檔的標的）。"""
    tech_id, tenant_id = str(uuid.uuid4()), str(uuid.uuid4())
    conn = _FakeConn()
    monkeypatch.setattr(kyc, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(kyc.db_module, "require_tech_conn", _async_return(conn))
    monkeypatch.setattr(kyc, "_resolve_token", _async_call(("tok-id", tech_id, tenant_id)))
    monkeypatch.setattr(kyc, "_claim_upload_slot", _async_call(None))
    return tmp_path, conn


def _async_return(value):
    async def _f(*a, **kw):
        return value
    return _f


def _async_call(value):
    async def _f(*a, **kw):
        return value
    return _f


@pytest.mark.asyncio
async def test_uploaded_file_is_encrypted_on_disk(kyc_env):
    """落盤位元組不得等於明文——這是本次修正的核心主張。"""
    tmp_path, conn = kyc_env
    await kyc.upload_registration_document(
        token="t", doc_type="id_front", file_bytes=_PNG,
        filename="id.png", content_type="image/png",
    )
    written = list(tmp_path.rglob("*.png"))
    assert len(written) == 1, "應該正好寫出一個檔"
    on_disk = written[0].read_bytes()
    assert on_disk != _PNG, "檔案仍是明文落盤（加密沒生效）"
    assert media_crypto.decrypt_bytes(on_disk) == _PNG, "解不回原始位元組"


@pytest.mark.asyncio
async def test_sha256_still_computed_on_plaintext(kyc_env):
    """sha256 必須算在明文上，否則同一張檔重傳會因密文不同而 dedup 失效。"""
    import hashlib
    _, conn = kyc_env
    await kyc.upload_registration_document(
        token="t", doc_type="id_front", file_bytes=_PNG,
        filename="id.png", content_type="image/png",
    )
    assert conn.inserted is not None
    assert hashlib.sha256(_PNG).hexdigest() in conn.inserted[1]


@pytest.mark.asyncio
async def test_read_back_returns_plaintext(tmp_path, monkeypatch):
    """新的加密檔讀回來要是明文。"""
    rel = "kyc-registration/x/doc.png"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(media_crypto.encrypt_bytes(_PNG))
    _patch_read(monkeypatch, tmp_path, rel)
    data, ct, name = await kyc.get_document_file(
        technician_id=str(uuid.uuid4()), document_id=str(uuid.uuid4()),
    )
    assert data == _PNG
    assert ct == "image/png"


@pytest.mark.asyncio
async def test_legacy_plaintext_file_still_readable(tmp_path, monkeypatch):
    """**存量明文檔零破壞**：加密上線前上傳的檔案 decrypt 失敗 → fallback 原位元組。

    漏了這條 dual-read，上線當下所有既有 KYC 文件會在審核頁變成亂碼／壞檔。
    """
    rel = "kyc-registration/x/legacy.png"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(_PNG)                      # 明文，就是舊檔的樣子
    _patch_read(monkeypatch, tmp_path, rel)
    data, _, _ = await kyc.get_document_file(
        technician_id=str(uuid.uuid4()), document_id=str(uuid.uuid4()),
    )
    assert data == _PNG


def _patch_read(monkeypatch, tmp_path, rel):
    conn = _FakeConn()

    async def _exec(sql, params=None):
        return _FakeCursor((rel, "image/png", "doc.png"))

    conn.execute = _exec
    monkeypatch.setattr(kyc, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(kyc.db_module, "require_tech_conn", _async_return(conn))
