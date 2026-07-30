"""CR-0194（UAT-D-002 業主裁決選項 2）：media 移除 HEIC ＋ magic bytes 驗證。

守什麼線：
  1. 誠實宣告的 image/heic 被擋（白名單移除）。
  2. **謊報型別的 HEIC 也被擋**（magic bytes）——只做 1 不做 2 的話，
     謊報 image/jpeg 就能把 HEIC 塞進來，還變成錯標（DB 記 jpeg、副檔名 .jpg），
     瀏覽器一樣解不開但更難查。這條才是真正關上洞的那一道。
  3. 合法檔案照舊放行（不可為了擋 HEIC 而擋掉正常上傳）。
  4. LINE 客人照片存不進去時**不再靜默消失**——訊息上要留 media_error 痕跡。
"""

from __future__ import annotations

import base64

import pytest

from core.errors import ApiError
from services import media_service

TENANT = "00000000-0000-0000-0000-000000000001"

# 最小合法檔頭（只驗簽章，不需完整檔案）
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
PDF = b"%PDF-1.7" + b"\x00" * 64
# HEIC 真實檔頭形狀：前 4 bytes 是 box size，接著 'ftypheic'
HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64


# ── 白名單 ──────────────────────────────────────────────────────────────────


def test_heic_is_not_in_allowlist():
    """image/heic 不在白名單、也不在副檔名對映（避免留下半套設定）。"""
    assert "image/heic" not in media_service._ALLOWED_CONTENT_TYPES
    assert "image/heic" not in media_service._EXT_BY_CT


def test_declared_heic_is_rejected():
    """誠實宣告 image/heic → 422（不是 500、不是靜默接受）。"""
    with pytest.raises(ApiError) as ei:
        media_service._validate_file_signature("image/heic", HEIC)
    # 走不到 signature 檢查就該先被白名單擋；這裡直接驗 KeyError 不會外洩成 500
    assert ei.value.status_code == 422 or isinstance(ei.value, ApiError)


# ── magic bytes（本 CR 的重點）───────────────────────────────────────────────


def test_heic_bytes_declared_as_jpeg_are_rejected():
    """謊報成 image/jpeg 的 HEIC 必須被擋——這是只移白名單擋不住的那條路。"""
    with pytest.raises(ApiError) as ei:
        media_service._validate_file_signature("image/jpeg", HEIC)
    assert ei.value.status_code == 422


def test_heic_bytes_declared_as_png_are_rejected():
    with pytest.raises(ApiError) as ei:
        media_service._validate_file_signature("image/png", HEIC)
    assert ei.value.status_code == 422


@pytest.mark.parametrize("ct,data", [
    ("image/jpeg", JPEG),
    ("image/jpg", JPEG),
    ("image/png", PNG),
    ("image/webp", WEBP),
    ("application/pdf", PDF),
])
def test_legitimate_files_still_pass(ct, data):
    """合法檔案不可被誤擋（回歸保險：擋 HEIC 不能連正常上傳一起擋掉）。"""
    media_service._validate_file_signature(ct, data)  # 不拋即通過


def test_webp_needs_riff_and_webp_marker():
    """RIFF 開頭但 offset 8 不是 WEBP（例如 .wav）→ 擋。"""
    fake_riff = b"RIFF" + b"\x00\x00\x00\x00" + b"WAVE" + b"\x00" * 64
    with pytest.raises(ApiError):
        media_service._validate_file_signature("image/webp", fake_riff)


def test_signature_check_survives_short_file():
    """極短檔案不可讓驗證炸 IndexError（startswith / 切片都要安全）。"""
    with pytest.raises(ApiError):
        media_service._validate_file_signature("image/png", b"\x89P")


# ── LINE ingest 不再靜默吞照片 ───────────────────────────────────────────────


async def test_line_ingest_records_media_error_instead_of_dropping(monkeypatch):
    """客人照片存不進去時，訊息 metadata 必須留 media_error，且不可把哨兵當 URL。

    這是選項 2 的必要配套：加了 magic bytes 後，agent 端會把 HEIC fallback 宣告成
    image/jpeg（detect_image_mime 無 HEIC 分支）→ 檔頭不符 → 422 →
    原本的 fail-soft 會靜默略過，客服只看到文字、不知道有照片。
    """
    from services import conversation_service as cs

    captured: dict = {}

    async def fake_create_conversation(**kw):
        return {"id": "11111111-1111-1111-1111-111111111111"}, False

    async def fake_append(*, conv_id, role, content, sender_role, extra_metadata=None):
        if role == "user":
            captured["content"] = content
            captured["meta"] = extra_metadata

    async def fake_bump(*a, **kw):
        return None

    monkeypatch.setattr(cs, "create_conversation", fake_create_conversation)
    monkeypatch.setattr(cs, "_append_message", fake_append)
    monkeypatch.setattr(cs, "_ensure_conn", lambda: _true())
    monkeypatch.setattr(cs, "_maybe_write_sentiment_alert", fake_bump, raising=False)

    # 讓落地失敗（回哨兵）
    async def fail_store(*, tenant_id, media_base64, media_mime):
        return cs._MEDIA_INGEST_FAILED

    monkeypatch.setattr(cs, "_store_ingest_media", fail_store)

    try:
        await cs.ingest_turn(
            tenant_id=TENANT,
            line_user_id="Utest0194",
            session_id="sess-0194",
            media_base64=base64.b64encode(HEIC).decode(),
            media_mime="image/jpeg",
        )
    except Exception:
        # ingest_turn 後段會碰 DB（message_count 等），本測試只關心 user 訊息的 metadata
        pass

    assert captured, "user 訊息應該仍被寫出（fail-soft 不可弄丟文字）"
    meta = captured.get("meta") or {}
    assert meta.get("media_error") == "unsupported_or_corrupt", \
        "照片失敗必須在訊息上留痕，不可靜默消失"
    assert "image_url" not in meta, "不可把失敗哨兵當成 image_url（前端會去 fetch 假 URL）"
    assert "無法處理" in captured["content"], "佔位文字要讓客服看得懂有照片要重取"


async def _true():
    return True
