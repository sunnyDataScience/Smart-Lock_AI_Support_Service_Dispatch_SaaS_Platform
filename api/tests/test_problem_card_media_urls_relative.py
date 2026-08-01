"""問題卡 media_urls 必須收得下相對路徑（業主 2026-08-01 回報：對話卡死）。

事故：品牌後台「對話管理」→「關聯問題卡」顯示「載入失敗：系統發生問題，請稍後再試」，
業主因此無法處理該對話、帳號卡住不能繼續測。

Root cause 鏈（prod 實證）：
  1. CR-0179 起 AI 建卡會自動掛上該對話近 24h 的照片（`_conversation_media_urls`），
     存的是 `messages.metadata.image_url` 的值 —— **相對路徑** `/api/v1/media/{id}`。
  2. `_coerce_media_urls` 只把它轉成 `list[str]`，**不會**補成絕對 URL（本來就不該補，見下）。
  3. 但回應模型 `ProblemCard.media_urls` 宣告 `list[AnyUrl]`，pydantic 的 AnyUrl 要求
     絕對 URL（需有 scheme）→ `ProblemCard(**_pc_row_to_dict(row))` 拋 ValidationError
     → 端點 **500** → 前端 `apiError.ts` 把 5xx 對到「系統發生問題，請稍後再試」。

為什麼是放寬型別而不是改資料：相對路徑**才是正確的存法**。前端用 `AuthImage` 帶認證去取
（`problem-cards/[id]/page.tsx:928` 註解明載「/api/v1/media/{id} 需認證，裸連結點擊 401」），
走同源 proxy；改存絕對 API URL 反而會打壞認證流程。

為什麼以前沒被發現：prod 全庫**唯一一張**帶 media_urls 的問題卡，就是 CR-0179 在 prod
第一次觸發產生的那張 —— 這個欄位從未被真實資料走過，一走就炸。

測試取徑刻意走 `_pc_row_to_dict` → `ProblemCard(**dict)` 這條**真實失敗路徑**，
而不是直接構造模型：初版測試直接塞 DB 原生狀態 `incomplete`，結果紅在
`ProblemCardStatus` 而非 media_urls —— 那是誤報，因為 `_coerce_status` 本來就會把
`incomplete` 對映成 API 的 `draft`。走完整路徑才不會把自己的測試錯誤當成產品缺陷。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from models.generated import (
    ProblemCard,
    ProblemCardCreateRequest,
    ProblemCardUpdateRequest,
)
from services.problem_card_service import _pc_row_to_dict

pytestmark = pytest.mark.unit

#: prod 實測值（problem_cards 305c19b3… 的 media_urls，全庫唯一一筆）
RELATIVE_MEDIA = "/api/v1/media/d0dd4ca1-1a6f-4c17-8109-c12421e7665f"


def _row(media, db_status: str = "incomplete") -> tuple:
    """組一列對齊 _PC_SELECT 的 row（欄位順序見 _pc_row_to_dict）。"""
    now = datetime.now(timezone.utc)
    return (
        "305c19b3-ee9f-4d5d-9ed1-19b963ec2c13",   # 0 id
        "e20b4b82-a7ca-4f31-bc8a-2be65a832b6c",   # 1 conversation_id
        "Yale",                                    # 2 brand
        "未知",                                     # 3 model
        ["外部無法解鎖"],                            # 4 symptoms
        "其他",                                     # 5 category
        "normal",                                  # 6 urgency
        db_status,                                 # 7 status（DB 原生值）
        media,                                     # 8 media_urls
        now,                                       # 9 created_at
        now,                                       # 10 updated_at
        "ai_line",                                 # 11 source
        None,                                      # 12 ai_missing_fields
    )


def test_relative_media_survives_full_serialization_path():
    """事故本身：DB 相對路徑 → row→dict → 回應模型，全程不得爆掉。"""
    card = ProblemCard(**_pc_row_to_dict(_row([RELATIVE_MEDIA])))
    assert card.media_urls == [RELATIVE_MEDIA], "值要原封不動帶出去，前端拿它去 AuthImage"
    # 順帶確認狀態對映沒被我改壞（DB incomplete → API draft）
    assert card.status.value == "draft"


def test_absolute_url_still_works():
    """放寬型別不得把原本能用的絕對 URL 弄壞。"""
    absolute = "https://smart-lock-api-sjmxp23sqq-de.a.run.app/api/v1/media/abc"
    card = ProblemCard(**_pc_row_to_dict(_row([absolute])))
    assert card.media_urls == [absolute]


def test_empty_and_null_media():
    """空與 None 都要能過 —— 解卡時把值清成 [] 走的就是這條。"""
    assert ProblemCard(**_pc_row_to_dict(_row([]))).media_urls is None
    assert ProblemCard(**_pc_row_to_dict(_row(None))).media_urls is None


def test_serialization_roundtrip_keeps_relative_path():
    """model_dump(mode="json") 是回傳前最後一步，不可在此變形或爆掉。"""
    card = ProblemCard(**_pc_row_to_dict(_row([RELATIVE_MEDIA])))
    assert card.model_dump(mode="json")["media_urls"] == [RELATIVE_MEDIA]


def test_create_request_accepts_relative_media_path():
    """建卡請求要收得下（symptom / urgency 為必填，一併給）。"""
    # urgency enum 是 low/medium/high；DB 的 'normal' 由 _coerce_urgency 對映成 medium
    req = ProblemCardCreateRequest(
        symptom="外部無法解鎖", urgency="medium", media_urls=[RELATIVE_MEDIA]
    )
    assert req.media_urls == [RELATIVE_MEDIA]


def test_update_request_accepts_relative_media_path():
    """客服在 UI 補附照片走的是這支——被 422 擋掉就等於附不了證據照。"""
    assert ProblemCardUpdateRequest(media_urls=[RELATIVE_MEDIA]).media_urls == [RELATIVE_MEDIA]
