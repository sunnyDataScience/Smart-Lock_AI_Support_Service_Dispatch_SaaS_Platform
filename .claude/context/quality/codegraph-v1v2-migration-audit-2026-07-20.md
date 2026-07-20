# v1 API 遷移就緒盤點（codegraph 掃描）

> 對應 roadmap WBS 2.5.1。本版為**完整版**，涵蓋全部 25 個 v1 router / 101 端點（取代前一版僅 18/25 router）。
> **統計權威來源**：`anchor_v1.txt`。**判定規則**：可安全移除只採「驗證 CONFIRMED」，不採信單一 finding 的樂觀 `status=safe_remove`（本輪 82 個端點掛 `safe_remove` 樂觀旗標，經驗證錨點對帳後僅 **39** 真正 CONFIRMED、**43** 被 REFUTED）。
>
> ⚠️ **資料完整性聲明（務必先讀）**：本輪壓縮資料集 `comp_v1.json` 的每個端點 `verified` 皆為 `null`、`found` 皆為 `[]`——per-endpoint 驗證旗標未隨壓縮攜帶。因此：
> - **每個 router 的 CONFIRMED/REFUTED 計數** = 錨點權威、精確，本報告全數對帳一致。
> - **分裂 router 內「哪一個端點是 CONFIRMED、哪一個是 REFUTED」** = 依 `sum` 敘述推斷，凡推斷處均標記「成員待回驗證日誌複查」。這類 member-level 分配不影響本輪波次結論（同一 router 的 CONFIRMED 與 REFUTED 走同一波、同一治理閘），但下架具體端點前應回源確認。

---

## 1. TL;DR

- **規模**：25 router / **101 端點**。
- **可安全移除（驗證 CONFIRMED）**：**39** 個。
- **REFUTED（樂觀 safe_remove 被駁回）**：**43** 個。細分：
  - 被**前端活 caller**（真流量）卡住：**0** 個 —— 全部 43 個 REFUTED 端點 `fe=[]`，無任何前端呼叫紀錄。
  - 被**後端 pytest / CI freeze baseline / deprecation-header 契約測試**卡住：**43** 個（純屬「連帶清測試」，非真流量阻擋）。
  - （真正的前端流量阻擋另計於 `blocked_frontend`，見下。）
- **blocked_frontend（前端活 caller 真阻擋）**：**4** 個 —— media `getMedia` ×1 + reconciliations ×3。
- **blocked_owner（§8 業主待決，純 owner 旗標）**：**0** 個（但 reconciliations 的解封與 work_orders 的下架**執行**受 owner 治理閘牽動，見 §7/§8）。
- **keep（刻意保留現行契約，非 cutover 對象）**：**15** 個 —— notifications push ×1 + technicians `me/*` ×11 + v1_inventory ×2 + cancellation ×1。
- 🔴 **高爆炸半徑警示**：`work_orders.py` 單檔 **11 CONFIRMED**，含 onsite 核心流程端點（complete / cancel / confirm / signature / reschedule / scope-change / delay 等技師站＋LINE 現場流程）。**即使掃描判 CONFIRMED，一律不得列入低風險 wave 1；每一端點下架前須先產 CIA + 人工複查技師站/LINE 呼叫路徑**（見 §4.3、§8 Wave 3）。

---

## 2. 共通前提

1. **這批全是 D3 雙掛 deprecation shim**：v1 flat `/api/v1/*` 與 v2 tenant-scoped `/tenants/{tenantId}/*` 平行雙掛，凍結於 **ADR-003 / CR-0145**。多數 v1 handler 為獨立實作（非 thin-shim 轉發 v2），但與 v2 共用同一 service 層；部分掛 `Deprecation` + `Link(successor-version)` header。
2. **移除觸及 API contract → 屬 CIA gate**：依 `.claude/rules/change-governance.md`，刪除/下架 endpoint 命中「API contract」觸發面向，**須先產出 CIA 至 `docs/4-exploration/CR-NNNN-*.md`、🛑 等業主裁決 §8 後才可實作**。本盤點是 CIA 的輸入，不是 CIA 本身。
3. **結構化掃描的盲區**：codegraph 只能看到 repo 內的 caller。**看不到未知的外部 v1 HTTP 消費者**（第三方整合、webhook、外部腳本、行動端舊版本）。因此即使某端點掃描判 CONFIRMED，**實際退場窗仍需業主確認無外部消費者**。
4. **Gate-1 v1-freeze 凍結**：`scripts/ci/v1-freeze-check.py`（baseline ~195 ops）+ 多支 surface allowlist 測試把整個 v1 面凍結為契約。這正是 43 個 REFUTED 的根源——移除任何端點都須同步更新 freeze baseline 與相關契約測試（連帶清測試）。

---

## 3. 總表（全 25 router，依 CONFIRMED 數降序）

| # | router | v2 覆蓋 | CONFIRMED 可移除 | REFUTED | 前端阻擋 (bf) | owner | keep | 建議動作 |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | work_orders.py | covers_all | **11** | 8 | 0 | 0 | 0 | 🔴 Wave 3：每端點須 CIA + 人工複查技師站/LINE |
| 2 | problem_cards.py | covers_all | 5 | 3 | 0 | 0 | 0 | Wave 2：端點級下架 + 連帶清測試 |
| 3 | conversations.py | covers_all | 3 | 2 | 0 | 0 | 0 | Wave 2 |
| 4 | data_corrections.py | covers_all | 3 | 1 | 0 | 0 | 0 | Wave 2 |
| 5 | disputes.py | covers_all | 3 | 0 | 0 | 0 | 0 | ✅ Wave 1：整檔可清 |
| 6 | pricing_rules.py | covers_all | 3 | 1 | 0 | 0 | 0 | Wave 2 |
| 7 | refunds.py | covers_all | 2 | 2 | 0 | 0 | 0 | Wave 2 |
| 8 | warranty_claims.py | covers_all | 2 | 2 | 0 | 0 | 0 | Wave 2 |
| 9 | dashboard.py | covers_all | 1 | 0 | 0 | 0 | 0 | ✅ Wave 1：整檔可清 |
| 10 | inventory.py | covers_all | 1 | 0 | 0 | 0 | 0 | ✅ Wave 1：整檔可清 |
| 11 | media.py | covers_all | 1 | 2 | 1 | 0 | 0 | Wave 2 + §6：`getMedia` 待前端切 v2 才可整檔下線 |
| 12 | notifications.py | **partial** | 1 | 3 | 0 | 0 | 1 | Wave 2（4 端點）；push 永久 keep，**不可整檔刪** |
| 13 | resolution.py | covers_all | 1 | 0 | 0 | 0 | 0 | ✅ Wave 1：整檔可清 |
| 14 | sentiment_alerts.py | covers_all | 1 | 1 | 0 | 0 | 0 | Wave 2 |
| 15 | settlements.py | covers_all | 1 | 0 | 0 | 0 | 0 | ✅ Wave 1：整檔可清 |
| 16 | customers.py | covers_all | 0 | 4 | 0 | 0 | 0 | Wave 2：清 D3/surface 測試後下架 |
| 17 | dispatch_logs.py | covers_all | 0 | 1 | 0 | 0 | 0 | Wave 2 |
| 18 | dispatch.py | covers_all | 0 | 3 | 0 | 0 | 0 | Wave 2：清 Deprecation-header 測試後下架 |
| 19 | invoices.py | covers_all | 0 | 2 | 0 | 0 | 0 | Wave 2 |
| 20 | reconciliations.py | **partial** | 0 | 0 | 3 | 0 | 0 | 🟠 Wave 4：前端活 caller + §8 platform v2 dual-sign owner-entangled |
| 21 | technicians.py | **partial** | 0 | 3 | 0 | 0 | 11 | Wave 2（3 admin 端點）；11 個 `me/*` 永久 keep |
| 22 | vouchers.py | covers_all | 0 | 2 | 0 | 0 | 0 | Wave 2 |
| 23 | v1_inventory.py | none | 0 | 0 | 0 | 0 | 2 | keep：P4 cutover 診斷元工具，非移除對象 |
| 24 | public.py | covers_all | 0 | 3 | 0 | 0 | 0 | Wave 2：前端已遷 `/consumer/*` |
| 25 | cancellation.py | covers_all | 0 | 0 | 0 | 0 | 1 | keep：**本即 v2**（非 v1 router，任務前提誤標） |
| | **合計** | | **39** | **43** | **4** | **0** | **15** | 總計 101 |

---

## 4. 可安全移除清單（39 個 CONFIRMED）

驗證依據通用型樣（除另註）：**前端全部經 `lib/api.ts:241 tenantPath()` 產出 `/tenants/{tenantId}/…` 命中 v2，v1 flat 路徑無任何前端 caller；`codegraph_callers` 對 v1 handler 回報 No callers（僅 `main.py` HTTP 掛載，無後端內部呼叫）；v2 `covers_all`。**

### 4.1 完全確定的 CONFIRMED（7 個，來自「零 REFUTED」router）

這 7 個所屬 router 的 CONFIRMED 數 = 該 router 全部 safe_remove 端點數（無 REFUTED、無 bf、無 keep），故成員無歧義。

| router | method + path | 對應 v2 | 驗證依據 |
|---|---|---|---|
| disputes | `GET /api/v1/disputes` | `GET /tenants/{tid}/disputes` (listDisputesV2) | 前端 admin/disputes 頁全走 v2；handler 無 caller |
| disputes | `GET /api/v1/disputes/{id}` | `GET /tenants/{tid}/disputes/{disputeId}` (getDisputeV2) | 同上 |
| disputes | `POST /api/v1/disputes/{id}/decision` | v2 雙簽 `:review` + `:co-sign`（escalate 走 `:escalate`）取代單次 decision | 前端走 v2 雙簽；⚠️ 單次仲裁→雙簽屬刻意契約行為升級，需業主知悉 |
| dashboard | `GET /api/v1/dashboard/stats` | `GET /tenants/{tid}/dashboard/stats` (getDashboardStatsV2) | 前端 dashboard/page.tsx:147 用 `tenantPath('/dashboard/stats')`→v2 |
| inventory | `GET /api/v1/inventory/items` | `GET /tenants/{tid}/inventory/items` (listInventoryItemsV2，8 端點超集) | 前端 admin/inventory:44-45→v2；勿與 `v1_inventory.py` 混淆 |
| resolution | `POST /api/v1/resolve` | `POST /tenants/{tid}/problem-cards/{id}:resolve-suggest` (resolveProblemSuggestV2) | v2 docstring 明列此為 v1-cutover P4 退場對象；前端無 flat caller |
| settlements | `GET /api/v1/accounting/settlements` | `GET /tenants/{tid}/settlements` (listSettlementsV2) | 前端 accounting/page.tsx:139 `tenantPath('/settlements')`→v2 |

### 4.2 分裂 router 的 CONFIRMED（21 個，跨 8 個 router）

> ⚠️ 下列每個 router 的 **CONFIRMED 計數為錨點權威**，但因壓縮資料未攜帶 per-endpoint `verified` 旗標，**確切「哪幾個端點是 CONFIRMED、哪幾個被 REFUTED」需回驗證日誌複查**。REFUTED 成員數對應列於 §5。以下列出各 router 全部 safe_remove 候選端點。

**problem_cards.py — 8 safe_remove（anchor：5 CONFIRMED / 3 REFUTED）**
`GET /problem-cards`、`GET /problem-cards/{id}`、`POST /problem-cards`、`GET /problem-cards/{id}/export`、`PATCH /problem-cards/{id}`、`POST /problem-cards/{id}/confirm`、`POST /problem-cards/{id}/resolve`、`POST /problem-cards/{id}/convert-to-work-order`（F-002）→ 各對應 `…_v2` 1:1；前端裸 `/problem-cards` 皆 Next.js href 非 API。

**conversations.py — 5 safe_remove（anchor：3 CONFIRMED / 2 REFUTED）**
`GET /conversations`、`POST /conversations`（F-001）、`GET /conversations/{id}`、`GET /conversations/{id}/messages`、`POST /conversations/{id}/messages` → 對應 `…V2`。⚠️ agent `line_gateway.py` 打的是 `/api/v1/internal/conversations/ingest`（不同 router），不受影響。

**data_corrections.py — 4 safe_remove（anchor：3 CONFIRMED / 1 REFUTED）**
`GET /data-corrections`、`GET /data-corrections/{id}`、`POST …/{id}/approve`、`POST …/{id}/reject` → v2 tenant-scoped（approve/reject 升為 admin-only + cross-tenant guard + idempotency）。

**pricing_rules.py — 4 safe_remove（anchor：3 CONFIRMED / 1 REFUTED）**
`GET /pricing/rules`、`POST /pricing/rules`、`PUT /pricing/rules/{id}`、`POST /pricing/calculate` → `pricing_rules_v2` + `pricing_v2`。⚠️ 資料面：v1 讀 legacy `public.price_rules`、v2 讀 `saas.*`；router 移除安全，但 legacy 表殘留資料的 parity 屬 data migration 另議。

**refunds.py — 4 safe_remove（anchor：2 CONFIRMED / 2 REFUTED）**
`GET /refunds`、`POST /refunds`（F-014 雙簽）、`GET /refunds/{id}`、`POST /refunds/{id}/decision` → `refunds_v2`（5-tier 金額 + 三維 SoD）。agent 自動退款已於 CR-0009/ADR-0106 遷 v2 `:agent-initiate`。

**warranty_claims.py — 4 safe_remove（anchor：2 CONFIRMED / 2 REFUTED）**
`GET /warranty-claims`、`POST /warranty-claims`（F-015）、`GET /warranty-claims/{id}`、`POST /warranty-claims/{id}/decision` → `…V2`。

**media.py — 3 safe_remove（anchor：1 CONFIRMED / 2 REFUTED；另 1 bf 見 §6）**
`POST /media`、`GET /work-orders/{id}/media`、`GET /disputes/{id}/media` → `…V2`。⚠️ **整檔不可刪**：`GET /media/{id}` 為 blocked_frontend（§6），須先解阻擋。

**notifications.py — 4 safe_remove（anchor：1 CONFIRMED / 3 REFUTED；另 1 keep push）**
`GET /notifications`、`PATCH /notifications/{id}`、`POST /notifications:bulk`、`POST /notifications:mark-all-read` → `…V2`（openapi 明寫「取代 legacy」）。⚠️ **整檔不可刪**：`POST /notifications/push` 永久 keep（§7）。partial 覆蓋風險。

**sentiment_alerts.py — 2 safe_remove（anchor：1 CONFIRMED / 1 REFUTED）**
`GET /sentiment/alerts`、`PATCH /sentiment/alerts/{alert_id}` → `…V2`。

### 4.3 🔴 work_orders.py — 高爆炸半徑（anchor：11 CONFIRMED / 8 REFUTED，全 19 端點掛 safe_remove）

**掃描結論**：19 端點目前**零活躍 caller**（前端全走 `tenantPath()`→v2 三支 router：`work_orders_v2` / `work_orders_ops_v2` / `cancellation.py`；後端僅 `main.py:36/345` 掛載），程式碼層面全判 safe_remove。**易混淆點已驗證**：`delay`→前端打 v2 `notify-delay`、`dispatch-queue`→打 v2 `/dispatch/queue`、`cancel`→打 v2 `cancellation.py`。

**但建議動作一律為：「須先產 CIA + 人工複查技師站/LINE 呼叫路徑後才可下架」，不得列入低風險 wave 1。** 理由：以下端點屬技師站/LINE onsite 現場流程，結構化掃描看不到 LINE Flex webhook 與外部行動端消費者：

| 端點 | v2 對應 | 現場流程風險 |
|---|---|---|
| `POST …/{id}/complete` | `:complete` (work_orders_v2:462) + onsiteCompletion(:829) | 完工回報核心 |
| `POST …/{id}/cancel` | cancellation.py:30（v2 6 階段） | 取消工單 |
| `POST …/{id}/confirm` | `:confirm` (:500) | 客戶確認結案 + 評分 |
| `POST …/{id}/signature` | `/signature` (:631) | 雙方電子簽章 |
| `POST …/{id}/reschedule` | `/reschedule:propose` (ops_v2:421) | 改期請求 |
| `POST …/{id}/scope-change` | `/scope-change` (:665, T5) | 範圍變更 |
| `POST …/{id}/delay` | `/notify-delay` (ops_v2:229, T7) | 延遲通知 |
| `POST …/{id}/reschedule/customer-confirm` | `:customer-confirm` (ops_v2:465, **Flow 11 LINE Flex**) | 客戶 LINE 選改期時段 |
| `POST …/{id}/reschedule/customer-reject` | `:customer-reject` (ops_v2:492, **Flow 11 LINE Flex**) | 客戶 LINE 拒改期 |
| 其餘 | list / dispatch-queue / pool / {id} / accept / assign / escalate / material-request(T6) / door-check(T8) / events | 技師站派工/接單/現場作業 |

> per-endpoint 的 11/8 CONFIRMED/REFUTED 分配對本輪不改變結論——整支 router 皆走 Wave 3 CIA 閘，任一端點都不可進 Wave 1。移除**執行**另受 CR-0145 §8 v1-cutover 5-gate 業主裁決 + Gate-1 freeze 管控。

---

## 5. REFUTED 分析（43 個）

**關鍵發現**：43 個 REFUTED 端點**全部 `fe=[]`（無任何前端活 caller 紀錄）**。也就是說——

- 被「**前端活 caller**」（真流量）卡住的 REFUTED：**0 個**。真正的前端流量阻擋另歸類為 `blocked_frontend`（4 個，見 §6）。
- 被「**後端 pytest / CI freeze baseline / deprecation-header 契約測試**」卡住的 REFUTED：**43 個**——這些只是「連帶清測試」，非真流量阻擋。移除時同步更新/刪除對應測試與 freeze baseline 即可解封。

### 5A. 有具體 file:line 證據的 REFUTED（narrative 明列）

| router | REFUTED 數 | 卡在哪（file:line） |
|---|---:|---|
| notifications | 3 | `scripts/ci/smoke-api.sh:76/81/85`、`scripts/ci/v1-freeze-baseline.json:51/105/152/153`、`.github/workflows/mock-smoke.yml:46`、`api/tests/test_cr_0131_surface_failclosed.py:147`（surface 白名單） |
| dispatch | 3 | `test_dispatch_v2_endpoint`（驗 Deprecation header）、`test_manual_dispatch`、`test_api_surface`、`test_platform_surface`、`test_cr_0131`、`test_cr_0092` |
| conversations | 2 | `api/tests/test_create_conversation.py`、`test_api_surface.py`、`test_cr_0130/0131`、CI `mock-smoke.yml` |
| work_orders | 8 | `scripts/ci/v1-freeze-check.py`（Gate-1 freeze，baseline 195 ops）——全 19 端點在凍結面內 |

### 5B. 僅通用 Gate-1 freeze / surface allowlist 卡住（`sum` 未列具體行號，需回源複查）

這些 router 的 finding 自陳「無前端/後端活躍 caller」，卻仍被錨點判 REFUTED——阻擋來自通用的 v1-freeze baseline + surface allowlist 契約測試（`test_cr_0131_surface_failclosed` / `test_api_surface` / `test_platform_surface`）+ D3 `Deprecation` header 契約，以及移除時需同步下架的 `openapi.yaml` operationId 與四站台 `api.generated.ts` 型別產物。

| router | REFUTED 數 | 卡住性質（連帶清測試） |
|---|---:|---|
| customers | 4 | D3 Deprecation header 端點；surface/freeze + openapi/api.generated.ts operationId（listCustomers/createCustomer/getCustomer/updateCustomer） |
| public | 3 | 前端已全遷 `/consumer/*`；v1 operationId 仍在 freeze/surface（getWorkOrderPublicStatus / getScopeChangeProposalPublic / respondScopeChangePublic） |
| problem_cards | 3 | freeze baseline + surface allowlist（8 端點皆在凍結面） |
| invoices | 2 | freeze/surface（listInvoices / getInvoice） |
| vouchers | 2 | freeze/surface（listVouchers / exportVoucher） |
| refunds | 2 | freeze/surface（4 端點分裂 2C/2R，成員待回源） |
| warranty_claims | 2 | freeze/surface（4 端點分裂 2C/2R，成員待回源） |
| media | 2 | freeze/surface（POST /media、work-orders/{id}/media、disputes/{id}/media 中 2 個） |
| technicians | 3 | 3 admin 端點（listTechnicians / getTechnician / getTechnicianWorkloadHeatmap）——前兩者掛 D3 Deprecation header；第三者無 v2 直接對應（資料改由 `/dispatch:candidate-detail` 內嵌），建議業主確認 |
| data_corrections | 1 | freeze/surface（4 端點分裂 3C/1R，成員待回源） |
| pricing_rules | 1 | freeze/surface（4 端點分裂 3C/1R，成員待回源） |
| dispatch_logs | 1 | freeze/surface（listDispatchLogs） |
| sentiment_alerts | 1 | freeze/surface（2 端點分裂 1C/1R，成員待回源） |

> ⚠️ 誠實標註：5B 各 router 的 REFUTED **數量**是錨點權威；但「哪一具體端點被 REFUTED」在分裂 router（refunds/warranty/media/data_corrections/pricing/sentiment）中無法由本壓縮資料判定，需回驗證日誌。全 REFUTED 皆屬「連帶清測試」型，解封路徑一致（清 freeze baseline + surface/deprecation 契約測試），故此不確定性不影響 Wave 2 執行策略。

---

## 6. 被前端 caller 真正卡住（blocked_frontend，4 個）

這 4 個是**唯一有活前端 caller 的真流量阻擋**——移除前必須先改前端（或改資料驅動的 url 生成）。

| 端點 | 前端 caller（file:line） | 應改成的 v2 路徑 | 阻擋性質 |
|---|---|---|---|
| `GET /api/v1/media/{id}` (getMedia) | `web/brand-portal/src/components/work-orders/MediaGallery.tsx:66`、`…/conversations/ChatTimeline.tsx:35` | `GET /tenants/{tid}/media/{mediaId}` (getMediaV2, media_v2.py:100) | **資料驅動**：`media_service.py:215/286/351` 與 `conversation_service.py:277` 對所有媒體（含 v2 回應）產出 `url=/api/v1/media/{id}`，前端直接 fetch 後端回傳的相對路徑。務實順序＝**先把 service 的 url 生成切到 v2 tenant-scoped 路徑 + 回歸測試 → getMedia 才轉 CONFIRMED → 屆時 media.py 四端點連檔一併下線**。另 `main.py:673 _TECH_SURFACE_PREFIXES` 含 `/api/v1/media`（師傅站顯圖同依賴） |
| `GET /api/v1/accounting/reconciliations` | `web/brand-portal/src/app/accounting/page.tsx:189-190` | `GET /tenants/{tid}/accounting/reconciliations` (listReconciliationsV2) | v2 讀 `saas.reconciliation`，前端註解明載該表**目前為空、尚未遷移**——list 有功能對應但資料 parity 未就緒 |
| `POST /api/v1/accounting/reconciliations/{id}/approve` | `…/accounting/page.tsx:245-246` | **無 drop-in**：v2 改 dual-sign 兩步（`:review`→`:co-sign`，兩個不同 user） | 單簽 approve 無等價端點；前端 `P3.5-KEEP` 註解明載需 dual-sign UX rework（產品工作） |
| `POST /api/v1/accounting/reconciliations/{id}:reject` | `…/accounting/page.tsx:277-278` | **無 v2 對應**（v2 router 無 reject 端點） | 完全無覆蓋，需 v2 補端點或保留 legacy |

---

## 7. 業主待決 / keep（15 個 keep + 3 個 owner-entangled bf）

錨點 `blocked_owner` 純旗標 = **0**；但下列項目的解封/下架涉及業主層裁決或屬永久保留：

- **reconciliations ×3（blocked_frontend，owner-entangled）**：三端點在 accounting 頁有活前端 caller（§6）。這批 `P3.5-KEEP` 決策的解封涉及 **v2 dual-sign UX rework + `saas.reconciliation` seed 對齊**，與 **CR-0145 §8 platform v2 待決同源**，屬 owner 層裁決 → 歸 Wave 4。
- **notifications `POST /notifications/push` ×1（keep 永久）**：v2 刻意不覆蓋（`notifications_v2.py:13-14`：push 為平台級操作、非 tenant-scoped 查詢）。前端四站台皆無呼叫，為現行唯一手動推播契約。**push handler（含 PushBody model 與 role_required 授權）須保留，notifications.py 不可整檔刪。**
- **technicians `me/*` ×11（keep 永久）**：v2 docstring 明言 `/technicians/me/*` 自助端點屬 mobile 端範疇、刻意保留 legacy。全部有 tech-portal 活前端 caller。清單：`GET me/dashboard-summary`(CR-0088)、`GET me/workload-heatmap`(修 A37 IDOR)、`GET me`、`PATCH me`、`GET me/availability`、`GET me/commission-statements`(UAT P2-5)、`PATCH me/availability`、`GET me/schedule`、`POST me/schedule/leave-request`、`POST me/schedule/standby-request`、`DELETE me/schedule/request/{request_id}`。
- **v1_inventory `admin/v1-inventory` + `…/no-traffic` ×2（keep）**：**任務前提誤標**——此檔非庫存 router，而是 **P4 Cutover 規劃元工具**（動態掃 `app.routes` 列出 mounted v1 端點、供人工盤點刪除候選）。無 caller 是這類 admin 診斷端點常態，非死碼；且它正是用來決定其他 v1 能否移除的儀器。無 v2 版本。若退場須待 P4 cutover 全程結束後連同 `test_v1_inventory.py` 另議。
- **cancellation `POST /tenants/{tid}/work-orders/{woId}/cancel` ×1（keep）**：**任務前提反了**——此檔**本身即 v2** spec-aligned tenant-scoped router（`cancellation_service.cancel_work_order_6stage`，ADR-0102 / FR-0052），刻意無 `/api/v1` 前綴，**沒有 v1 端點可移除**。有 2 個活前端 caller（work-orders/[id]:1362、dispatch-manual:286）。真正的 legacy v1 取消端點在 `work_orders.py:248` 的 `POST /api/v1/work-orders/{id}/cancel`（已納 §4.3）。

---

## 8. 建議遷移波次

**Wave 1 — 真正低風險、整檔可清（5 router / 7 端點，排除 work_orders）**
零 REFUTED、零 bf、零 keep 的全 CONFIRMED router，前端已全遷 v2、handler 無 caller、v2 covers_all：
**`disputes.py`（3）、`dashboard.py`（1）、`inventory.py`（1）、`resolution.py`（1）、`settlements.py`（1）。**
動作：產一份合併 CIA → 業主確認退場窗（無外部消費者）→ 移除 router + `main.py` import/include_router + `openapi.yaml` operationId + 重生 `api.generated.ts`。
⚠️ disputes decision 的「單簽→雙簽」契約行為變更需在 CIA 標註。

**Wave 2 — 端點級下架 + 連帶清測試（14 router）**
所有「CONFIRMED 端點可移除，但同 router 有 REFUTED 需先清測試/CI」或「純 REFUTED（清測試即解封）」者：
`problem_cards`、`conversations`、`data_corrections`、`pricing_rules`、`refunds`、`warranty_claims`、`sentiment_alerts`、`customers`、`dispatch`、`dispatch_logs`、`invoices`、`vouchers`、`public`、`technicians`（僅 3 admin 端點）。
以及**部分檔**（保留 keep/bf 部分）：`media`（3 端點，`getMedia` 除外，須先完成 §6 url 切換）、`notifications`（4 端點，`push` 除外）。
動作：先更新 `scripts/ci/v1-freeze-baseline.json` + `v1-freeze-check.py` + surface allowlist 測試（`test_cr_0131_surface_failclosed` / `test_api_surface` / `test_platform_surface`）+ deprecation-header 契約測試（`test_dispatch_v2_endpoint` 等）+ `smoke-api.sh` / `mock-smoke.yml` → 再逐端點下架。**回源確認分裂 router 的 CONFIRMED/REFUTED 成員後再動刀。**

**Wave 3 — 需 CIA + 人工複查（1 router / 19 端點）**
🔴 `work_orders.py` 全 19 端點。逐端點產 CIA、人工複查技師站 + LINE Flex webhook（Flow 11）+ 外部行動端呼叫路徑，並過 CR-0145 §8 v1-cutover 5-gate 業主裁決 + Gate-1 freeze。**任一端點皆不得降級進 Wave 1/2。**

**Wave 4 — owner 待決 / 永久保留（不在 cutover 主線）**
- `reconciliations`（3 bf）：待 v2 dual-sign UX rework + `saas.reconciliation` seed 對齊 + §8 platform v2 業主裁決；其中 `:reject` 需 v2 先補端點。
- 永久 keep（不退場）：`notifications/push`、`technicians/me/*` ×11、`v1_inventory` ×2（P4 工具）、`cancellation`（本即 v2）。

---

### 需人工複查/回源的資料不足處（誠實標註）

1. **分裂 router 的 per-endpoint CONFIRMED/REFUTED 成員**（work_orders 11/8、problem_cards 5/3、conversations 3/2、data_corrections 3/1、pricing 3/1、refunds 2/2、warranty 2/2、media 1/2、notifications 1/3、sentiment 1/1）：壓縮資料 `verified=null`/`found=[]` 未攜帶，**計數權威、成員需回驗證日誌**。
2. **§5B 各 REFUTED 的具體卡點 file:line**：`sum` 未逐一列出，僅可歸因於通用 Gate-1 freeze + surface/deprecation 契約，實際行號需回源。
3. **外部未知 v1 HTTP 消費者**：結構化掃描的根本盲區，任一「CONFIRMED」的實際退場窗仍須業主確認無第三方/舊行動端消費。
4. `technicians` 第三個 admin 端點 `getTechnicianWorkloadHeatmap` 無 v2 直接對應（資料改由 `/dispatch:candidate-detail` 內嵌），下架前建議業主確認。
