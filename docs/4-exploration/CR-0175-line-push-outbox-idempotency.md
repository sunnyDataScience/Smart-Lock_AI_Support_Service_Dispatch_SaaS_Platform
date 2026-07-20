---
id: CR-0175
title: 客戶推播 outbox 冪等（enqueue 去重 + 送出 retry key）
status: in-progress
type: change-impact-analysis
date: 2026-07-20
related-findings: R13, R19（codegraph LINE 推播稽核）
source-report: .claude/context/decisions/codegraph-tech-line-push-trace-2026-07-20.md
---

# CR-0175 客戶推播 outbox 冪等（enqueue 去重 + 送出 retry key）

## 1. 背景與動機（WHY）

2026-07-20 codegraph LINE 推播全鏈路稽核（來源報告見 frontmatter）在客戶推播 outbox 路徑（S4 enqueue + S5 worker）確認兩處冪等缺口，皆有 code 證據（confirmed，非臆測）：

- **R13 — enqueue 無去重（`api/services/line_push_outbox_service.py:87-95`）**：`enqueue()` 為無條件 `INSERT INTO line_push_outbox (...) VALUES (...) RETURNING id`，對 `(reference_id, push_kind)` 完全無去重。schema（`SQL/Schema_v2_extensions.sql:421-457`）上 `line_push_outbox` 僅有三個**普通** index（`idx_outbox_pending_next` / `idx_outbox_tenant_kind` / `idx_outbox_reference`），`(reference_id, push_kind)` 上**沒有 UNIQUE 約束**，唯二的 CONSTRAINT 是 `chk_push_status` 與 `chk_push_attempts_nonneg`。因此同一 `(reference_id, push_kind)` 被 caller 呼叫兩次 → 落兩筆 pending row → worker 各推一次 → **客戶收到重複推播**。

- **R19 — 送出兩步非原子（`api/realtime/line_push_outbox_worker.py:142-144` 呼叫 `_push_to_line:232` 成功後於 `:282` `_mark_sent`）**：`_process_row` 先 `_push_to_line`（內部 `AsyncMessagingApi.push_message` @ `:272`）成功、**才** `_mark_sent`。兩步之間無原子性、無 idempotency key。若 push 已送達 LINE 但 worker 在 `_mark_sent` 前 crash / DB 斷線，該 row 仍為 `pending`，下一輪 `_poll_once`（`:99` `WHERE status='pending' AND next_attempt_at<=NOW()`）會再取出重推。這是 at-least-once 佇列無收斂點；`_push_to_line` 的 `push_message`（`:272`）也**未帶 `X-Line-Retry-Key`**，LINE 端無從對「同一 row 的重推」去重。

**現況痛點**：客戶在正常運維（上游重入、worker crash/重啟、DB 抖動）下可能收到重複的改期提案 / 報價 / 完工通知 LINE 訊息，直接損及客戶體驗與品牌信任；且缺口在「正常錯誤路徑」即可觸發，非極端邊界。

**不做的後果**：缺口長期潛伏，隨推播量成長重複率上升；且因兩處必須合修（見下），單獨補任一處都不能閉合，拖延只會累積技術債與客訴。

## 2. 變更範圍（WHAT）

一次收斂客戶推播 outbox 冪等，四項合修（來源報告建議做法 A/B/C/D）：

- **A（DB schema）**：`line_push_outbox` 加 partial unique index，於 `(reference_id, push_kind)` 建立唯一性（dedup 視窗定義待 §8 裁決），阻擋並發雙插（擋住 TOCTOU race，非應用層 SELECT-then-INSERT 可比）。
- **B（enqueue 冪等回傳）**：`enqueue()` 的 INSERT 尾加 `ON CONFLICT DO NOTHING`（配合 A 的 unique index）＋衝突時改查既有 row `id` 回傳，明確定義「重複 enqueue 回既有 outbox_id」為冪等回傳語意，記入 contract。
- **C（送出 retry key）**：`_push_to_line` 對 `push_message` 傳 `x_line_retry_key`（以 `outbox_id` 這個穩定 UUID 當 key），讓 LINE 端對「同一 row 24h 內重推」去重；上線前先確認 `line-bot-sdk` 版本簽章。
- **D（測試）**：補雙 enqueue 只落一筆、push 後 crash 重跑不產生第二次送達的測試。

## 3. CIA 觸發面向

| 面向 | 命中 | 說明 |
|---|---|---|
| **DB schema** | ✅ | A 新增 partial unique index，屬 schema 變更且需 migration（本輪 defer 的主因）；且 unique 條件（dedup 視窗）需依業務語意定義。 |
| **External integration** | ✅ | C 觸及 LINE retry 語意——傳 `X-Line-Retry-Key` 改變對 LINE Messaging API 的呼叫契約，且需驗 SDK 實際簽章（版本破壞風險）。 |
| **API contract** | ✅ | B 改變 `enqueue()` 回傳語意（重複時回既有 id vs 新 id），所有 service-layer caller 需知 enqueue 已變冪等回傳。 |
| **Domain model** | ➖ 局部 | 不新增 entity；但為 `line_push_outbox` 引入「`(reference_id, push_kind)` 在 dedup 視窗內唯一」這條新 invariant。 |
| **Test plan** | ✅ | 新增冪等專項測試類別（雙 enqueue / crash-replay）。 |
| **User/Business flow** | ➖ | 不改主流程；改的是既有推播的重複收斂，對合法重推語意有影響（見 §8）。 |
| **Architecture boundary** | ➖ | 不移動 module 邊界，沿用既有 outbox + worker 架構。 |

## 4. API contract 影響

- **內部 service API `enqueue()`（`line_push_outbox_service.py:51`）簽章不變**（`*, tenant_id, push_kind, payload, target_line_id=None, reference_id=None, reference_table=None, max_attempts=5) -> str`），但**回傳語意變更**：由「永遠回新插入 row 的 id」改為「若 `(reference_id, push_kind)` 已存在（dedup 視窗內）則回既有 row 的 id」。屬**行為契約變動**，需記入 contract。
- **受影響呼叫端**（皆需知 enqueue 變冪等回傳、勿假設每次回不同 id）：
  - `propose_reschedule_v2` → `reschedule_proposal`
  - `record_scope_change` → `scope_change_proposal`
  - `_detect_schedule_conflict_and_publish` → `schedule_conflict`
  - CR-0028 `work_order_assigned` / `work_order_accepted` / `scope_change_result`
  - CR-0027 `work_order_document`
  - CR-0095 `quote_proposal`
- **HTTP endpoint 層無新增/刪除**；outbox enqueue 為 service-internal，無對外 REST 契約破壞。若 `enqueue` 需回傳「是新建還是命中既有」的旗標給呼叫端判斷，屬 §8 待裁決（是否擴充回傳為 `(id, created: bool)`）。

## 5. Domain model / DB schema 影響

- **entity**：`line_push_outbox`（`SQL/Schema_v2_extensions.sql:421-457`）。
- **新 migration（A）**：新增 partial unique index，形如
  `CREATE UNIQUE INDEX uq_outbox_ref_kind ON line_push_outbox (reference_id, push_kind) WHERE reference_id IS NOT NULL AND status <> 'dead';`
  實際 `WHERE` 條件（dedup 視窗）待 §8 裁決——`status <> 'dead'` 只是候選之一。
- **新 invariant**：dedup 視窗內同一 `(reference_id, push_kind)` 至多一筆。
- **回填 / 既有資料風險**：建立 unique index **前**須先確認**存量資料無違反該唯一條件的重複 row**，否則 index 建立失敗。需先跑一支盤點查詢（`GROUP BY reference_id, push_kind HAVING COUNT(*)>1`，套上選定的 `WHERE` 條件），若有重複則需先決定清理策略（保留最新 / 合併）——此為 migration 前置步驟，屬 §8 待裁決之一。
- `reference_id IS NULL` 的 row（呼叫端未帶 reference 時）**不受** partial unique 約束，維持可多筆，符合現況（worker 靠 `target_line_id` 直送）。

## 6. External integration 影響

- **LINE Messaging API（C）**：`_push_to_line`（`worker:232-280`）的 `push_message`（`:272`）改帶 `x_line_retry_key=outbox_id`。LINE 對相同 retry key 的重送在 24h 內去重，可閉合「同一 row 重推」。
  - **版本破壞風險（confirmed）**：本 env 未裝 `linebot`，無法驗 `line-bot-sdk>=3.0` 之 `AsyncMessagingApi.push_message` 是否接受 `x_line_retry_key` kwarg（或需透過 header/`PushMessageRequest` 傳遞）。簽章不符會 `TypeError` 直接打斷推播——**上線前必須先在裝有 SDK 的環境確認實際簽章**（§8 / §9 前置）。
- **跨 service**：本變更僅在客戶推播 outbox 路徑，不涉技師派工同步 HTTP 鏈（S3），無跨 deployment token 影響。
- **token**：不動 `LINE_CHANNEL_ACCESS_TOKEN` 讀取；缺 token 時 `_push_to_line:242` 現有結構化錯誤字串回傳行為維持（保本地可用性，本輪不改為 hard fail）。

## 7. 測試計畫影響

新增「outbox 冪等」測試類別，關鍵案例：

- **enqueue 去重**：對同一 `(reference_id, push_kind)` 連呼兩次 `enqueue()` → DB 只落一筆 row，兩次回傳同一 `outbox_id`（驗 B + A）。
- **並發雙插**：兩並發 `enqueue()` 同 key → unique index 擋下，僅一筆存活（驗 A 擋 TOCTOU，非只靠應用層）。
- **crash-replay 不重送**：模擬 `_push_to_line` 成功後、`_mark_sent` 前 crash → 下輪 `_poll_once` 重取同 row → 帶相同 `x_line_retry_key` → 不產生第二次「有效送達」（驗 C；LINE 端去重以 mock/契約驗證）。
- **合法重推**（依 §8 裁決結果）：若某些 push_kind 允許合法重發（如報價修改後再推 quote_proposal），需有測試證明該情境**不被** unique 誤擋。
- **既有測試回歸**：`api/tests/test_cr_0017_outbox_worker.py`、`api/tests/test_cr_0028_wo_push.py`、`api/tests/test_cr_0095_quote_line_approval.py` 需檢查是否依賴「每次 enqueue 回新 id」的舊語意，若有則同步調整。
- ⚠️ **pytest 污染 UAT 庫注意**：本 repo 已知 pytest 單庫 fallback 會直打 5433 UAT 庫；UAT 期間勿對 5433 跑全套（見專案記憶），冪等測試須確保 DB 隔離。

## 8. 🛑 Human Decisions Required（待業主裁決）

實作前必須由業主回答以下問題（此為 gate）：

1. **各 push_kind 的 dedup 視窗語意——哪些允許合法重推？**
   稽核明確標示風險：若合法情境需對同一 `reference_id` 重發（例：報價修改後再推 `quote_proposal`、改期提案更新後再推 `reschedule_proposal`），過嚴的 unique 會**誤擋合法重推**。
   - 選項 A（全域嚴格）：所有 push_kind 都以 `(reference_id, push_kind)` 唯一，一律不准重推。
   - 選項 B（per-kind 白名單）：僅對「事件型、天生不該重複」的 kind（如 `work_order_assigned` / `work_order_document`）套唯一；對「可更新後再推」的 kind（如 `quote_proposal` / `reschedule_proposal` / `scope_change_proposal`）**放行重推**。
   - 選項 C（帶版本欄位）：對允許更新的 kind 引入版本/序號，dedup 以 `(reference_id, push_kind, version)`。
   - **建議**：選項 B——逐一確認每個 push_kind 的重發語意後定義白名單，兼顧去重與合法更新。**需業主逐 kind 給出「可否重推」清單**：`reschedule_proposal` / `scope_change_proposal` / `schedule_conflict` / `work_order_assigned` / `work_order_accepted` / `scope_change_result` / `work_order_document` / `quote_proposal`。

2. **partial unique index 的 `WHERE` 條件（dedup 視窗邊界）？**
   - 選項：`WHERE reference_id IS NOT NULL AND status <> 'dead'`（dead 後允許重試新 row）／ 或含 `sent` 也擋（sent 過就永不重推）／ 或加時間窗（如 24h 內才擋，之後允許重推）。
   - **建議**：先採 `reference_id IS NOT NULL AND status <> 'dead'`，時間窗留待有明確重推需求時再加。**與問題 1 的答案綁定**。

3. **存量重複資料的清理策略（migration 前置）？**
   若既有 `line_push_outbox` 已有違反選定唯一條件的重複 row，index 無法建立。
   - 選項：保留最新一筆刪其餘 / 保留最早 / 保留 status 最進展者（sent > failed > pending）。
   - **建議**：保留 `created_at` 最新一筆、其餘軟性標記後刪除，並先跑盤點查詢確認實際重複量（雲端與本機各跑一次）。**[待確認]** 生產庫實際重複筆數。

4. **`enqueue()` 回傳是否需擴充以區分「新建 vs 命中既有」？**
   - 選項 A：維持 `-> str`（只回 id，呼叫端不需知是否新建）。
   - 選項 B：改 `-> tuple[str, bool]`（id + created 旗標），供呼叫端做「已推過就不再送提醒」之類判斷。
   - **建議**：選項 A（最小破壞）——除非有呼叫端明確需要 created 旗標。**[待確認]** 是否有呼叫端需此旗標。

5. **`X-Line-Retry-Key` 上線的 SDK 驗證前置由誰執行？**
   本 env 未裝 `linebot`，無法驗 `push_message` 是否接受 `x_line_retry_key`。
   - **建議**：C 的落地以「先在裝有 `line-bot-sdk` 的環境（或雲端 staging）確認簽章通過」為硬性前置，未確認前 C 不隨 A/B 上線（可灰度分離，見 §9/§10）。**[待確認]** 生產所用 `line-bot-sdk` 精確版本。

## 9. Suggested Implementation Order

每步可獨立 review / revert：

1. **盤點（唯讀）**：跑存量重複查詢（本機 + 雲端），量化重複筆數，回填問題 3 的 `[待確認]`。
2. **SDK 簽章確認（唯讀）**：在裝有 `line-bot-sdk` 的環境確認 `push_message` 的 `x_line_retry_key` 傳法，回填問題 5 的 `[待確認]`。
3. **Migration A（schema）**：依 §8 裁決的 `WHERE` 條件與 push_kind 白名單，先清理存量重複（若有），再建 partial unique index。單獨 commit、單獨可 revert（drop index）。
4. **enqueue B（去重回傳）**：`enqueue()` INSERT 加 `ON CONFLICT DO NOTHING` + 衝突查既有 id 回傳；依問題 4 決定回傳型別。含單元測試（雙 enqueue / 並發雙插）。
5. **worker C（retry key）**：`_push_to_line` 傳 `x_line_retry_key=outbox_id`，前置為步驟 2 已確認簽章。含 crash-replay 測試。
6. **測試 D 補齊 + 既有測試回歸**：三個既有測試檔（`test_cr_0017_outbox_worker` / `test_cr_0028_wo_push` / `test_cr_0095_quote_line_approval`）調整為新冪等語意。
7. **文件同步**：更新 CR-0175 §8 進度區塊、`CHANGELOG.md [Unreleased]`、必要時新開 ADR（記 outbox 冪等 invariant 決策）。

## 10. 風險與回退

- **破壞性**：
  - 步驟 3（unique index）若存量有重複且未先清理 → migration 失敗（已由步驟 1 盤點 + 步驟 3 前置清理緩解）。
  - 步驟 4 若過嚴 unique 誤擋合法重推 → 合法更新推播消失（由 §8 問題 1 的 per-kind 白名單緩解）。
  - 步驟 5 若 SDK 不接受 `x_line_retry_key` kwarg → `TypeError` 打斷推播（由步驟 2 前置驗證緩解；未驗證不上線）。
- **灰度**：A/B（去重）與 C（retry key）**可分離上線**。A/B 先上（純 DB + service 內，無外部 SDK 依賴、風險可控）；C 待 SDK 簽章確認後獨立上，降低外部整合破壞面。
- **回退開關**：
  - A：`DROP INDEX uq_outbox_ref_kind_strict`（純加法索引，drop 即回退，不動資料）。
  - B：`ON CONFLICT DO NOTHING` 移除即回無條件 INSERT（回舊語意）。
  - C：`x_line_retry_key` 傳參以 feature flag / env 包裹，異常時可關閉退回不帶 key 的 `push_message`（維持現況 at-least-once，不惡化）。
- **對齊原則備註**：技師 webhook 側已 fail-closed，但本客戶 outbox 側的正確對齊方向是「冪等閉合」而非 fail-fast，故本 CR 不加 startup hard fail、不動 `_push_to_line:242` 缺 token 的結構化錯誤回傳（保本地可用性）。

## 11. 進度（實作記錄）

- **§8 決策（業主 2026-07-20 拍板，照建議全採）**：
  - 問題 1 白名單：🔒 去重＝`work_order_assigned` / `work_order_accepted` / `work_order_document` / `scope_change_result`；🔓 允許重推＝`quote_proposal` / `reschedule_proposal` / `scope_change_proposal` / `schedule_conflict`。
  - 問題 2 dedup 視窗：`reference_id IS NOT NULL AND status <> 'dead' AND push_kind IN (4 strict)`。
  - 問題 3 存量清理：migration 內先 DELETE 重複（保留 `(created_at, id)` 最大者）再建 index；生產實際重複量待 DB up 時盤點（乾淨庫＝DELETE 0）。
  - 問題 4 enqueue 回傳：維持 `-> str`（8 個呼叫端全未接回傳值，驗證無需 created 旗標）。
  - 問題 5 SDK：`line-bot-sdk 3.23.0` 之 `AsyncMessagingApi.push_message(..., x_line_retry_key=...)` **原生支援**，C 可行零版本風險。
- **實作（branch `feat/cr-0175-outbox-idempotency`）**：
  - A/B：migration `SQL/migrations/111-line-push-outbox-idempotency.sql`（partial unique index **`uq_outbox_ref_kind_strict`** ＋存量清理）；`enqueue()` strict kind 走 `ON CONFLICT (reference_id, push_kind) WHERE <predicate> DO NOTHING`，撞既有回既有 id（冪等回傳）。
  - C：`_push_to_line(..., retry_key)` → `push_message(req, x_line_retry_key=outbox_id)`。
- **驗證**：unit 18 passed（`test_cr_0175_outbox_idempotency.py` enqueue 分支×4 ＋ `test_cr_0017_outbox_worker.py` retry_key×1 ＋既有回歸）；**拋棄式 Postgres 16 實測** migration 套用＋ON CONFLICT 推斷＋去重/放行全綠（strict 同 ref 第二次 `INSERT 0 0`、`quote_proposal` 兩次都落）。
- **剩餘（deploy 時）**：migration 111 套用生產庫前先跑存量重複盤點（§9-1）；真 DB 整合測試（雙 enqueue／crash-replay）於有 DB 環境補跑；C 可與 A/B 分離灰度。