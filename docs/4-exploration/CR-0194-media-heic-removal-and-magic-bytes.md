# CR-0194 — media 移除 HEIC ＋ magic bytes 驗證（UAT-D-002）

- **狀態**：✅ 實作完成，本機驗證通過（prod 待重佈）
- **觸發面向**：API contract（上傳型別白名單收窄＋新增檔頭驗證＝行為變更）
- **來源**：UAT 2026-07-29 TC-ONSITE 系列 → UAT-D-002
- **業主裁決（2026-07-30）**：選項 **2 — 移除 `image/heic` ＋ 補 magic bytes 驗證**（含配套修 LINE fail-soft）

---

## §1 為什麼不是「只移除白名單」

`media_service` **沒有** magic bytes 驗證（`technician_kyc_service` 當年 CR-0115 review 補了，一般 media 沒補）。所以它只信 client 自報的 Content-Type。

只移除 `image/heic` 的結果是：把 Content-Type 謊報成 `image/jpeg` 就照樣進得來，而且**變成錯標**——DB 記 `image/jpeg`、副檔名 `.jpg`、瀏覽器一樣解不開，但這次連「為什麼壞」都查不出來。等於用可見問題換不可見問題。

所以本 CR 兩件一起做：白名單擋誠實宣告，檔頭擋謊報。

## §2 為什麼一定要配套修 LINE 那條 fail-soft

`agent/lockcore/utils/helpers.py:161-171` 的 `detect_image_mime` **沒有 HEIC 分支**——HEIC 回 `None`，`channels/line_gateway.py:229` 再 fallback 成 `"image/jpeg"`。

也就是說加了檔頭驗證後，客人從 LINE 傳 HEIC 會走到「宣告 jpeg、檔頭是 heic」→ 422。而 `conversation_service._store_ingest_media` 是 `except Exception` + `return None` 的 fail-soft：

> **照片會憑空消失，客服只看到文字，沒人知道有照片要追。**

這比「存下一張看不到的破圖」更糟——破圖至少留了一列。所以本 CR 把該路徑從「靜默略過」改成「fail-soft 但留痕」。

---

## §3 變更

### S1 — `services/media_service.py`

`_ALLOWED_CONTENT_TYPES` 由 `set` 改為 `dict[str, tuple[bytes, ...]]`（型別 → 允許的檔頭前綴），移除 `image/heic`；`_EXT_BY_CT` 同步移除。新增 `_validate_file_signature(ct, file_bytes)`，於白名單檢查後呼叫。

前綴表與 `technician_kyc_service._KYC_CONTENT_TYPES` 刻意保持同一做法（jpeg `FFD8FF` / png 簽章 / webp `RIFF`+offset8 `WEBP` / pdf `%PDF-`）。

未知型別走 `.get()` + 422 **fail-closed**，不讓 `KeyError` 逃成 500（這是寫測試時發現的：直接呼叫該函式而未先過白名單會 KeyError）。

### S2 — `services/conversation_service.py`

新增哨兵 `_MEDIA_INGEST_FAILED`。`_store_ingest_media` 失敗時回哨兵而非 `None`（讓 caller 分得出「本來就沒照片」與「有照片但存不進去」），log 由 `warning` 升 `error`。

`ingest_turn` 收到哨兵時：
- **不**把哨兵當 `image_url`（否則前端會去 fetch 一個不存在的媒體）
- metadata 寫 `{"media_error": "unsupported_or_corrupt", "media_mime": ...}`
- 無文字時佔位文字寫「[客人傳了照片，但格式無法處理]」而非「[照片]」，客服才知道要向客人重取

仍維持 fail-soft：照片問題不可弄丟整輪對話文字。

### S3 — 前端（本輪之前已完成）

師傅端三處 `accept` 已收窄為 `image/jpeg,image/png,image/webp`。全 repo 已無任何站台收 `heic` 或 `image/*`。

---

## §4 影響面（實測，非推論）

| 項目 | 結果 |
|---|---|
| `api/openapi.yaml` | **未列允許型別** → 機讀 contract 零改動 |
| 前端 | 已無站台收 heic/`image/*`（brand `svg+jpeg+png`、tech `jpeg+png+webp`、KYC 再加 pdf）→ 零破壞 |
| 測試 | 唯一提 heic 的 `test_cr_0115:193` 斷言 **KYC 拒絕** heic，走自己的窄白名單 → 不受影響（實測仍過） |
| LINE 路徑 | 從不宣告 heic（magic-byte 偵測無 HEIC 分支）→ 加檔頭驗證後會被擋，故 §2 配套為必要 |
| 既有 6 筆 heic 完工證據 | **照樣破圖**。`routers/media.py:74` 是 `media_type=content_type`（讀 DB 存的值），本 CR 只影響未來上傳 |

## §5 驗證

**單元**：新增 `tests/test_cr_0194_media_heic_removal.py` 12 測（白名單/副檔名對映清乾淨、誠實 heic 擋、**真 HEIC 謊報 jpeg/png 皆擋**、5 種合法型別放行、webp offset8 驗、極短檔不炸 IndexError、LINE 失敗留痕不當 URL）。

**全套**：`2210 passed / 13 failed / 5 skipped`（scratch 庫）。那 13 支已在**乾淨基線**（stash 全部變更 + pre-migration DB）重跑確認同樣失敗＝既有問題，非本輪造成。

**端到端**（重建 image，真實 HEIC 檔取自容器 `399b4086….heic`，檔頭 `ftypheic` 已 xxd 確認）：

| 案例 | 結果 |
|---|---|
| ① 誠實宣告 `image/heic` | `422 VALIDATION_ERROR unsupported content_type 'image/heic'` |
| ② **真 HEIC 謊報 `image/jpeg`** | `422 檔案內容與宣告型別 'image/jpeg' 不符` ← 本 CR 重點 |
| ③ 合法 PNG | `200`，media id `05c3a82c…`（無回歸） |
| ④ 既有 heic 列 GET | `200 Content-Type: image/heic 1304846 bytes`（證實既有證據未被修好） |

測試全程走 scratch 庫；UAT 庫（`lock_AI_data`）複驗 `work_orders=4 problem_cards=19 events=0 audit=84 media=16 checkpoint=0`＝與本輪開始時一致，零污染。

---

## §6 仍待裁決（獨立於本 CR）

**既有 6 筆 heic 完工證據怎麼處理？** 全是 `completion_before/during/after`、全部綁工單、1.0–2.5 MB：

1. 請師傅重新補拍（證據鏈最乾淨，但要聯絡師傅回頭補件）
2. 伺服器端一次性轉檔為 JPEG（省事，但等於平台代為改動完工證據，稽核上要記轉檔事實）
3. 不處理，只在審核頁顯示「此證據為 HEIC 格式無法預覽」提示

附帶發現：磁碟 12 個 `.heic` 檔 vs DB 6 列 → **6 個孤兒檔**（另一 stack 或先前 reset 遺留），與本決策無關但已記錄。

---

## §7 進度

- 2026-07-30：S1/S2 完成，12 測 + 全套 2210 passed + 端到端 4 案通過。已重建本機品牌 API image。prod 重佈與 §6 裁決為後續。
