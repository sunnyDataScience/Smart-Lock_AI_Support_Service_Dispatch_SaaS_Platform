# CR-0179 — CIA：AI 主動丟樣本圖＋引導客人拍照回傳（UAT-0720-13）

- **日期**：2026-07-22
- **來源**：20260720 三方會議 §六（Action 4，spec 遺漏項，業主會議拍板要做）；Plane UAT-0720-13（seq 53）
- **狀態**：🛑 **CIA 產出，停在 §8 等業主裁決**（觸發 Architecture boundary：agent 工具白名單）

## §1 需求

客服流程：客人「門打不開」→ AI 判斷鎖具問題 → **AI 反向丟樣本圖**（鎖具壞掉樣本 or 標示鎖具位置/測量項目示意圖）→ 引導客人拍自家門鎖照片回傳 → 照片進到後台供客服/技師評估。

素材：Mira 的 Google Drive 樣本圖；本地已有兩張（`meetings/20260720 資料/`：施工前評估 6 項測量、電子鎖預約安裝流程圖）。

## §2 現況（codegraph 稽核 2026-07-22）

| 能力 | 現況 |
|---|---|
| 接收客人照片 | ✅ 已有：LINE gateway 用 Blob API 下載 → 餵 vision 管線給 LLM → base64 旁路持久化到**對話**訊息（客服對話管理頁看得到） |
| AI 主動發送圖片 | ❌ 無：outbound 全程只送 TextMessage，全 repo 無 ImageMessage；工具白名單（`CS_TOOL_ALLOWLIST`）無任何發訊/發圖工具 |
| 回傳照片掛回問題卡 | ❌ 無：escalation 建草擬卡不帶 media；`problem_cards.media_urls` 只有人工建卡會填 |
| 樣本圖存放/服務 | ❌ 無：無樣本圖資產目錄與公開 URL（LINE ImageMessage 需可公開存取的 HTTPS URL） |

## §3 觸發面向

- **Architecture boundary**：若走新 agent 工具（send_image）→ 動 `CS_TOOL_ALLOWLIST`，CLAUDE.md 硬性約束 4 明定屬 architecture change
- **User/Business flow**：客服引導流程新增「丟圖→收圖」段
- **External integration**：LINE ImageMessage（原僅 Text）
- **API contract / Domain**：escalation ingest payload 增 media；問題卡 media_urls 寫入路徑

## §4 方案選項

### 方案 A：新 agent 工具 `send_sample_image`（LLM 自主決定何時丟圖）
- lockcore 新增工具（傳入圖類別，gateway 轉 LINE ImageMessage）＋ `CS_TOOL_ALLOWLIST` 加一項
- ✅ 最靈活，AI 依對話情境挑圖；❌ 動白名單（架構變更）、LLM 可能濫發、需圖庫索引給 LLM 選

### 方案 B：gateway 確定性夾圖（不動白名單）⭐ 建議
- SOP 話術讓 AI 在「請客人拍照」時輸出固定標記（如 `[[photo-guide:pre-install]]`）；gateway 偵測標記 → 剝除文字 → 附發對應 ImageMessage
- 樣本圖放 brand-portal/api 靜態資產（或 GCS 公開 bucket），映射表在 config
- ✅ 不動白名單（免架構變更）、確定性可稽核、濫發風險=0；❌ 圖類別固定（初期 2-3 張夠用）

### 方案 C：只做「拍照回傳掛問題卡」，丟圖延後
- escalation payload 帶本輪照片 → `problem_cards.media_urls`；丟樣本圖不做
- ✅ 最小；❌ 會議 Action 4 的「AI 丟樣本圖」沒交付

**共同必做（A/B 皆含 C 的掛卡）**：`_forward_escalation_safe` payload 帶本輪 media → `escalation_to_draft_pc` 寫進 `problem_cards.media_urls`。

## §8 Human Decisions Required ✅（業主 2026-07-22 裁決「2-B」）

**選方案 B：gateway 確定性夾圖**（SOP 標記→gateway 偵測附發 ImageMessage，不動白名單）；含共同段（回傳照片掛回問題卡）。樣本圖初期用會議兩張 JPG 起步；存放採可公開 HTTPS URL（實作定案：優先 brand-portal 靜態資產或 GCS，以 config 映射解耦）。

### 進度
- ✅ 實作完成（branch `feat/uat-0720-round-b`）：
  - **共同段（照片掛卡）**：採 api 端自查（gateway 不動、零 contract 變更）——`escalation_to_draft_pc` 反查該對話近 24h 照片（`messages.metadata.image_url`，CR-0119 管線既有 URL）→ 新卡 INSERT `media_urls`／併卡 append-only 聯集（沿 TI-M03-07 不覆蓋客服手附）；`_conversation_media_urls`（LIMIT 5＋24h 窗防 session 終身舊照）＋`_merge_media_urls` 皆 fail-soft。
  - **夾圖段**：`_extract_photo_guides`（剝 `[[photo-guide:key]]` 標記→URL、未知 key 只剝不夾、截斷殘尾防外洩、上限 4 圖）＋`_send_text` 支援 ImageMessage 多則＋`build_webapp(photo_guides=)` kwarg（None=關閉、行為不變）＋`AppConfig.photo_guides`／config.toml `[photo_guides]` 段＋樣本圖上架 `web/brand-portal/public/photo-guides/`（pre-install/booking-install，會議兩張 JPG）。
  - **SOP**：SKILL.md v1.5.0→1.6.0「樣本圖引導」話術（文末標記、至多一個、key 白名單）。
  - 測試：`test_photo_guide.py` 12 案（純函式＋webhook 整合＋SKILL 守線）全綠；agent 全套 231 passed。
- 遺留：①SkillSync 已 publish 環境需品牌後台重發佈 SOP v1.6.0 才生效 ②照片掛卡 component 測試（需真 DB）待安全窗補 ③問題卡詳情頁 media_urls 為裸連結（點擊 401 既有限制），可另卡搬 ChatTimeline AuthChatImage 縮圖 pattern。

## §8 原裁決選項（存檔）

1. **丟圖機制選 A（LLM 工具）或 B（gateway 確定性夾圖，建議）或 C（先只做掛卡）？**
2. 樣本圖初期集合與存放：用會議兩張 JPG（施工前評估測量／預約安裝）起步？放 GCS 公開 bucket 或 api 靜態目錄？
3. Mira GDrive 的其餘樣本圖是否納入第一批（bronze-only 規則不適用——樣本圖是發給客人的引導素材，非產品知識）？

## §9 建議實作順序（裁決後）

1. 共同段：escalation media → problem_cards.media_urls（含 ingest schema 擴充）
2. 樣本圖資產上架＋公開 URL
3. 依裁決實作丟圖機制（B：gateway 標記偵測＋SOP 話術補「請提供照片時附樣本圖標記」）
4. e2e：LINE 收圖→問題卡看得到；AI 引導拍照→客人收到樣本圖
