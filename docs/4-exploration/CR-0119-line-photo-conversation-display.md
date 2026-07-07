# CR-0119：LINE 客人照片顯示於對話管理（Change Impact Analysis）

- **日期**：2026-07-07
- **提出**：業主（「當用戶傳送照片時可以顯示出來嗎」→ 裁決「做」）
- **狀態**：approved（業主 2026-07-07 口頭裁決，見 §8）
- **範圍**：agent LINE gateway 旁路持久化 + API internal ingest + 對話管理前端

---

## 1. 變更摘要

客人在 LINE 傳照片時，品牌後台「對話管理」詳情頁（`/conversations/{id}`）目前只顯示文字標記「[照片]」，照片本體看不到。本 CR 把照片接進既有持久化管線，讓客服在對話 timeline 直接看到客人傳的照片。

## 2. 現況鏈路（2026-07-07 逐段查證）

| 環節 | 狀態 | 位置 |
|---|---|---|
| LINE 收照片 → 下載給 AI vision | ✅ 已有 | `agent/lockcore/channels/line_gateway.py:576-589`（VLN 2026-07-03） |
| 照片持久化到對話 | ❌ 斷點 | `_persist_turn_safe` 只送 `user_text="[照片]"`，照片本體未送 |
| API ingest 收 media | ❌ 斷點 | `IngestTurnRequest` 無 media 欄位 |
| API 讀取端映射 | ✅ 已備好 | `conversation_service._msg_row_to_dict` 已映射 `metadata.image_url → Message.media_url` |
| 前端泡泡渲染 | ✅ 已備好 | `ChatTimeline.tsx` CustomerMessage 已寫 `media_url → <img>`（但直連會 401，見 §5.3） |
| 媒體儲存服務 | ✅ 已有 | `media_service.upload_media` + `GET /api/v1/media/{id}`（tenant 隔離、FS 儲存、retention） |

結論：缺口只在中段（agent → ingest → metadata），兩端已在先前開發中備好。

## 3. 觸發面向（CIA gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| API contract | ✅ | `IngestTurnRequest`（internal 端點）新增選填欄位 `media_base64` / `media_mime` —— **additive、不破壞既有呼叫端**（未帶欄位行為完全不變） |
| DB schema | ❌ | 零變更。`messages.metadata` 為 jsonb；`media_files.purpose='other'` 已在既有 CHECK 白名單 |
| Domain model | ❌ | 復用既有 media_files 實體，無新 invariant |
| User/Business flow | ❌ | 客人傳照片的 LINE 側行為（AI vision、回覆）不變；僅後台呈現增強 |
| External integration | ❌ | LINE webhook 處理不變（照片本來就已下載） |
| Architecture boundary | ❌ | 依循方案 A「通道旁路持久化」既有邊界；agent 核心 / CS_TOOL_ALLOWLIST 不動（架構鎖） |

## 4. 設計

### 4.1 儲存與 URL

- 照片經 ingest 以 base64 傳入，API 端復用 `media_service.upload_media` 落地：
  - `purpose="other"`（既有 CHECK 白名單，**免 migration**，UAT 期間不動 DB）
  - `uploader_user_id=None`（LINE 客人非 users 表帳號；欄位本為 nullable）
  - 不掛 work_order / dispute（皆 nullable）
  - 沿用 20 MiB 上限、retention 1 年、tenant 隔離
- `messages.metadata.image_url = "/api/v1/media/{media_id}"` —— 與工單照片牆（MediaGallery）消費的 URL 格式完全一致。
- 雲端顧慮一併解決：agent（Cloud Run）檔案系統為暫時性，照片轉存 API 的 MEDIA_ROOT 後不因 agent 重啟遺失。

### 4.2 資料流（新增段以粗體標示）

```
LINE 客人傳照片
  → gateway Blob API 下載到 agent 本機（既有，vision 用）
  → **_persist_turn_safe 讀檔 base64 → ingest payload（media_base64/media_mime）**
  → **ingest_turn 解碼 → media_service.upload_media → metadata.image_url**
  → GET /conversations/{id}/messages 回 media_url（既有映射）
  → **ChatTimeline 帶 JWT fetch → blob URL → <img>**（比照 MediaGallery 模式）
```

### 4.3 Fail-soft 原則（對齊方案 A 既有設計）

- agent 端讀檔 / base64 失敗 → 略過 media，照舊送文字「[照片]」（持久化絕不影響回客人）。
- API 端 base64 解碼失敗 / upload_media 驗證失敗 → log warning、略過 media，文字訊息照寫（不 4xx，避免整輪對話流失）。

## 5. 影響清單

### 5.1 API（dispatch api:8001）

| 檔案 | 變更 |
|---|---|
| `api/models/internal.py` | `IngestTurnRequest` +`media_base64: str|None` +`media_mime: str|None`（選填） |
| `api/routers/internal_ingest.py` | `ingest_conversation_turn` 傳遞新欄位 |
| `api/services/conversation_service.py` | `ingest_turn` 收 media → 存檔 → user 訊息 metadata 帶 `image_url`；`_append_message` 支援 extra metadata |

### 5.2 Agent（LINE gateway，通道旁路層）

| 檔案 | 變更 |
|---|---|
| `agent/lockcore/channels/line_gateway.py` | `_persist_turn_safe` +選填 `media_paths`；兩個呼叫點（接管中 :628 / 一般 turn :650）帶入 |

### 5.3 Web（dispatch web:3000）

| 檔案 | 變更 |
|---|---|
| `web/src/components/conversations/ChatTimeline.tsx` | `media_url` 由 `<img src>` 直連改為帶 Bearer + X-Tenant-ID fetch → blob URL（媒體端點需認證，直連 401） |

### 5.4 測試

- 新增 `api/tests/test_cr_0119_line_photo_ingest.py`：ingest 帶照片 → messages 回 media_url、media 可下載（tenant 隔離）、壞 base64 fail-soft 只寫文字。
- `agent/tests/test_line_gateway.py` 補：persist payload 含 media_base64。

## 6. 風險與取捨

1. **payload 大小**：LINE 原圖可達 ~10MB，base64 膨脹 1.33 倍；ingest POST timeout 已是 20s（冷啟考量），本機/雲內網傳輸可承受。超過 20 MiB 由 media_service 既有驗證擋下（fail-soft 只留文字）。
2. **單張假設**：LINE 一則照片訊息恰一張圖；欄位採單張（`media_base64`）。日後多圖再 additive 擴充。
3. **隱私**：照片為客人家門/鎖具照，經 `GET /media/{id}` 需 JWT + tenant 隔離；不產生公開 URL。
4. **回填**：不回填歷史照片（agent 本機舊檔不可靠），僅新訊息生效。

## 7. 豁免確認

不適用豁免（命中 API contract 面向），故產出本 CIA。

## 8. Human Decisions Required

| # | 決策 | 裁決 |
|---|---|---|
| 1 | 是否實作照片顯示於對話管理？ | ✅ 業主 2026-07-07 裁決「做」 |
| 2 | 儲存策略：復用 media_service（FS + tenant 隔離）vs 另建儲存 | ✅ 復用 media_service（業主同意提案；零 schema 變更） |
| 3 | purpose 分類：沿用 `other` vs 新增 `conversation_image`（需 migration） | ✅ 沿用 `other`（UAT 期間不動 DB；日後需分類統計再開 CR） |
| 4 | 歷史照片回填 | ✅ 不回填（見 §6.4） |

### 進度

- ✅ S1 done（commit `e5012626`，本輪 `--no-ff` 併回 dev_new_arch）：三處接線全落地（agent `_encode_media_for_persist` + ingest `media_base64/media_mime` + 前端 `AuthChatImage` 帶認證 blob 載入）；順修 `NEXT_PUBLIC_API_BASE_URL` 空字串 `??` 漏接（ChatTimeline+MediaGallery）與 `Message.media_url` spec `uri→uri-reference`。驗證：api 新增 4 測 + 回歸 60 全綠（隔離 scratch DB）、agent 39 全綠（新增 3）、tsc 0、端到端截圖確認照片顯示（UAT 測試資料已清）。本機 dispatch api/web/agent 容器已重建。

## 9. Suggested Implementation Order

1. API：models/internal + internal_ingest + conversation_service（含 fail-soft）
2. Agent：line_gateway `_persist_turn_safe` + 呼叫點
3. Web：ChatTimeline 帶認證圖片載入
4. 測試：api scratch DB 跑新測試 + conversations/media 相關回歸；agent 跑 test_line_gateway
5. 驗證：本機重建 api/web 容器 → internal ingest 實測一張照片 → Playwright 檢視 :3000 對話頁 → 清除測試資料
6. 文件三同步：本 CR §進度、CHANGELOG、completion-status；docs_html regen
