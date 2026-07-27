# CR-0185 — 問題卡新增 `dismissed` 作廢終態（＋師傅站本月毛額口徑、MCP 白名單條文補正）

- **日期**：2026-07-27
- **觸發**：0727 稽核輪三件待業主裁決事項，業主指示「都照你的建議開發完」＝授權由 Claude 依建議裁決並實作
- **觸發面向（CIA gate）**：Domain model（問題卡狀態機新增終態）、DB schema（新增欄位＋改 partial index）、API contract（新增端點）

---

## §1 根因

### A. 問題卡無作廢終態

`ProblemCardStatus` 只有 `draft / confirmed / resolved`。LINE agent 轉真人時會自動建**草擬卡**
（`escalation_to_draft_pc`），誤判或重複進線就會產生垃圾卡，但**沒有任何乾淨的關閉途徑**：

- 標記「已解決」→ 需先 confirm 再 resolve，且 `resolve_card` 會寫 `resolution_layer` 等欄
  → **污染解決率統計**，更嚴重的是 refinery 的 `_PENDING_CARDS_SQL` 只吃
  `status='resolved' AND knowledge_ready=TRUE`，垃圾卡會被**汲取成知識**。
- 留在 draft → 永遠佔住待確認佇列。

實例：0727 handoff 兜底誤判產生的 `630d9160`（品牌型號皆空、症狀是客人訊息串接）。

### B. 師傅站「本月毛額」含跨月未完工工單

`get_my_dashboard_summary` 的 pending 聚合欄**無任何日期條件**，`month_gross_est` ＝
本月完工 ＋ **全歷史**未完工。線上實測本月 0 單仍顯示 NT$31,617。

### C. CLAUDE.md 工具白名單條文不完整

第 4 條寫「工具白名單只能在 `CS_TOOL_ALLOWLIST` 統一控」，但 MCP 工具**不受該白名單約束**
（時序：白名單剝離在建構期、MCP 註冊在事件迴圈啟動後，`tools/mcp.py` 無 allowlist 檢查）。
實測：建構後 6 工具 → RAG MCP 註冊後 8 工具，`names ⊆ CS_TOOL_ALLOWLIST` = False。
此為 ADR-010 / CR-0125 的**刻意設計**，但條文未載明，且無測試守著。

---

## §2 設計（Claude 依授權裁決）

### A-1 命名：採用新 token `dismissed`（非沿用 `cancelled` / `rejected`）

全 repo 狀態命名慣例調查（106 個列舉）：`rejected` 19、`closed` 9、`cancelled` 6、
`retired` 3、`voided` 1、`superseded` 1、`terminated` 1；**`dismissed` 零出現**。

不沿用既有 token 的理由：

| 候選 | 既有語意 | 不採用原因 |
|---|---|---|
| `rejected` | 審核否決（申請類） | **相鄰工單域已用 `reject` 代表「技師拒單」**（`work_order_service._REJECT_FROM`），復用會混淆 |
| `cancelled` | 流程實例中止 | 工單的 `cancelled` **綁 6 階段取消費用機制**（`cancellation_service`），語意帶「真實案件被喊停」，與「這張卡本來就不該存在」不同 |
| `voided` | 發票作廢 | 樣本僅 1，且與會計憑證強綁 |

`dismissed` 語意精確＝「經客服審視，判定非真實案件／誤建／重複」，與上述三者可清楚區隔。
沿用 `voided` 的欄位慣例：`dismissed_at` ＋ `dismiss_reason`。

### A-2 合法轉移：`_DISMISS_FROM = {incomplete, confirmed}`

- 允許 `incomplete`（草擬卡誤建，主要情境）與 `confirmed`（客服確認後才發現是重複）
- **不允許 `resolved` → dismissed**：已結案卡可能已被 refinery 汲取成知識，回頭作廢會使知識來源失去依據
- **不允許 dismissed → 任何狀態**（終態）

### A-3 必須連帶處理的四類副作用

1. **`_DB_STATUS_TO_API` 對映**（`problem_card_service.py:45`）— 未加對映時 `_coerce_status`
   的未知值 fallback 會把作廢卡顯示成 `draft`，**直接回到待確認佇列**（此修復自我廢除）。
   且**絕不可**映射到 `resolved`（會進 refinery 知識汲取）。
2. **三處「active 卡」判定**（`:654` / `:915` / `:931`，predicate 均為
   `status NOT IN ('resolved','escalated') AND converted_at IS NULL`）＋ migration 077 的
   partial unique index `uniq_pc_conversation_active` — 不排除 dismissed 的話，作廢卡會
   **永遠佔住該對話的唯一 active 名額**，同對話開不了新卡、24h 冪等 dedup 會回傳作廢卡、
   新訊息會被併進作廢卡。
3. **統計扭曲點**：`kpi_service._funnel_counts`（漏斗第二階段 EXISTS 完全不看 status →
   作廢卡留在 PC→WO 轉換率分母壓低轉換率）、`dashboard_service.hot_topics` / `top_brands`
   （全表 COUNT 不濾 status → 誤建卡的 category/brand 進「熱門議題／熱門品牌」）。
   *不受影響*：`ai_resolution_rate` 實際算 `conversations.resolution_layer`，不吃 PC status。
4. **對話交還 AI**：escalation 會把 conversation 翻 `escalated`（AI 靜音），目前**只有工單
   結案**會翻回 active（`work_order_service.py:1199`）。作廢 PC 若不比照，該 LINE 客人的
   AI 會**永久靜音**——這正是 0727 查到 `14ef5e2f` 的成因。

### A-4 端點

新增 **v2 專用** `POST /tenants/{tenantId}/problem-cards/{id}/dismiss`
（`role_required(*BACKOFFICE_ROLES)` ＋ `idempotency_guard` ＋ cross-tenant guard，比照
confirm/resolve）。**不加 legacy `/api/v1` 孿生**——CR-0183 的教訓是雙掛端點守衛易失步，
新功能不應擴大已標 Deprecation 的舊面。

### B 師傅站本月毛額

pending 聚合加月份窗，錨點 `COALESCE(scheduled_at, created_at)`：已排程者以排程月為準
（跨月承接的工作算在實際要做的那個月），未排程者退回建立月。前月逾期未完工者不計入本月
毛額（另有「逾時工單」指標追蹤）。同時移除 status 白名單中 `scheduled` / `en_route` /
`arrived` 三個死值（API 層 enum，`work_orders.status` 正典狀態機不含，永遠 match 不到）。

### C CLAUDE.md 條文

補「MCP 例外」說明並指出**工具入口有兩條**（內建走白名單常數、MCP 走 config.toml 的
`[mcp_servers.*]`），兩者新增皆須走 CIA。**不動 code**（RAG 需要那些工具；改成事後套用
白名單會讓 RAG 靜默失效）。新增 `agent/tests/test_mcp_allowlist_boundary.py` 釘住時序。

---

## §3 驗證

- 測試庫＝`scripts/db/make-test-db.sh` 產生的 scratch 庫（UAT 庫零接觸）
- 基準：修改前 api 全套 **2091 passed / 13 failed**（13 支為既有 seed 依賴，非回歸）
- B 已完成：新增 3 案（SQL 形狀 2 ＋ 真 DB 行為 1）→ **2094 passed / 13 failed**（失敗清單不變）
- C 已完成：`test_mcp_allowlist_boundary.py` 3 案 ＋ 既有 `test_tool_allowlist.py` → 6 passed
- A 待驗：轉移合法性、對映不落 draft/resolved、三處 active 判定排除、統計排除、對話交還

---

## §8 Human Decisions Required

業主 2026-07-27 指示「都照你的建議開發完」＝**授權 Claude 依上述建議裁決**。以下為已代為
裁決、業主可事後推翻的項目：

1. **A-1 命名採 `dismissed`**（而非 D 調查建議的 `cancelled`）—— 理由見 §2 A-1 表格
2. **A-2 不允許 `resolved` → dismissed** —— 保護 refinery 知識來源可追溯性
3. **A-3(4) 作廢時連帶把 conversation 交還 AI** —— 若業主認為作廢後仍應維持人工接管，此項需改
4. **A-4 不加 legacy 孿生端點** —— 若外部整合仍依賴 `/api/v1`，需補（並比照守衛強度）
5. **B 錨點採 `COALESCE(scheduled_at, created_at)`** —— 若業主認為「逾期未完工仍屬本月預期收入」，改為不設上界即可

---

## §9 Implementation Order

1. ✅ C：CLAUDE.md 條文 ＋ `test_mcp_allowlist_boundary.py`
2. ✅ B：`technician_service` pending 月份窗 ＋ `test_cr_0185_month_gross_scope.py`
3. A-1：migration（`dismissed_at` / `dismiss_reason` ＋ 重建 partial unique index）
4. A-2：`generated.py` enum ＋ `_DB_STATUS_TO_API` ＋ `_DISMISS_FROM` ＋ `dismiss_card()`
5. A-3：三處 active 判定 ＋ kpi/dashboard 統計排除 ＋ 對話交還
6. A-4：v2 router 端點 ＋ openapi.yaml
7. 前端：問題卡明細「作廢」操作 ＋ 狀態標籤 i18n
8. 測試 ＋ 全套回歸 ＋ 部署
