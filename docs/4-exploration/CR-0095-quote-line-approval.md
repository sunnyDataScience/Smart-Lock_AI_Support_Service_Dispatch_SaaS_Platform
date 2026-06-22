---
id: CR-0095
title: "初始報價 LINE 送單 + 客戶同意 + 同意才派工（quote-approval gate）"
status: implemented
tier: 4-exploration
owner: 業主
created: 2026-06-22
decided: 2026-06-22
target-release: dev_new_arch
related: [CR-0027, CR-0028, CR-0032, CR-0033, CR-0034, CR-0042]
---

# CR-0095: 初始報價 LINE 送單 + 客戶同意 + 同意才派工

> **Mandated by**: 業主要求的派工流程 ——「開單 → 內部估價 → 外部報價 → **傳報價單給客戶 LINE** → **客戶 LINE 同意/拒絕** → **同意後才排單派工**」。
> **狀態**: 🛑 **CIA gate — 等業主裁決 §8 後才實作。**

---

## 1. 背景：要的流程只做了一半

業主要的完整流程逐步查證（workflow `quote-approval-flow-trace` 對抗式覆核）結果：

| 步驟 | 狀態 |
|---|---|
| ①LINE→問題卡 ②確認→開單 ③內部估價 ④外部報價 | ✅ 已做 |
| **⑤ 報價單推 LINE 給客戶** | ❌ 缺 |
| **⑥ 客戶 LINE 同意/拒絕** | ❌ 缺（只有網頁版） |
| **⑦ 同意才派工（gate）** | ❌ 缺（派工完全不檢查報價狀態） |
| ⑧排單 ⑨派工 ⑩接單 ⑪完工 | ✅ 已做 |

## 2. 觸發面向（為何要 CIA）

| 面向 | 命中 |
|---|---|
| User/Business flow | ✅ 新增「客戶同意」關卡，改變派工前置流程 |
| API contract | ✅ quote `:send` 行為變更 + 新增客戶回覆路徑 + assign 前置條件 |
| Domain model | ✅ 工單派工生命週期新增「報價已同意」前置不變式 |
| DB schema | ⚠️ 預期**無新表/欄**（quote 狀態機 draft→sent→accepted/rejected/expired 已存在）|
| External integration | ✅ LINE（新增報價 Flex 推送；可能新增 agent postback 接收端）|
| Test plan | ✅ 新增 gate / 推送 / 同意路徑測試 |
| Architecture boundary | ⚠️ 視 §8-D1 而定：若做真 LINE postback → agent gateway 新增事件處理（架構面）|

## 3. 現狀（重要發現）

- **報價引擎完整**：`quote` 主表狀態機（draft→pending_approval→approved→sent→accepted/rejected/expired）、`quote_line_items` 雙欄（`unit_price` 內部成本 / `customer_price` 對客價）、catalog mock seed、RBAC 成本遮蔽、公開連結 `mint_view_token` → `/quotes/{token}`、發票自動開立。（CR-0032/0034/0035）
- **`:send` 只凍結快照 + 產網頁 token**，`api/services/quote_engine_service.py:224-225` **不 enqueue 任何 LINE 推送**；`PushKind` 列舉（`line_push_outbox_service.py:33-43`）**無報價類型**；`builders.py` 無報價 Flex。
- **客戶同意只有網頁**：`POST /consumer/quotes/{token}`（token-based 網頁），`:accept`（`quote_v2.py:123`）需 OPS_ROLES（僅員工）。
- **派工零 gate**：`assign_order`（`work_order_service.py`）只查 `_ASSIGN_FROM={created,assigned}`，**完全不檢查 quote 狀態**。
- **🔴 關鍵發現**：scope_change（追加報價）的 LINE Flex 用 **postback 按鈕**（`s:a|`/`s:r|`，`builders.py:170-185`），**但 agent `line_gateway.py` callback 只處理 `MessageEvent`+文字、`continue` 掉所有非訊息事件（agent 無 PostbackEvent 處理器）** → **連 scope_change 的「LINE 點按同意」都是死的**，目前真正能用的只有那顆 URI 按鈕「查看詳情」→ 開網頁。換言之：**全系統目前沒有任何「LINE 點按 → 後端接收」的運作中路徑。**

## 4. 提案範圍

把 scope_change 已有的「LINE 提案 + 同意」模式補完並接到**初始報價**，並加上派工 gate：
1. **S5**：`:send` 時 enqueue LINE 報價 Flex（含項目摘要 + 對客總價 + 同意/拒絕 + 網頁 fallback）；新 `quote_proposal` push_kind + builder；worker `_resolve_line_uid` 支援 quote → work_order → conversation → line_user_id。
2. **S6**：客戶同意/拒絕的接收端（依 §8-D1 決定：純網頁 or 真 LINE postback）。
3. **S7**：`assign_order` 加前置 gate（依 §8-D2 決定 hard/soft）。

## 5. 影響面（per-layer）

| 層 | 變更 |
|---|---|
| 後端 service | `quote_engine_service.transition(send)` enqueue 推送；`assign_order` 加 quote-gate；（D1-B）新報價回覆 service |
| 後端 router | `quote_v2`（送單行為）；consumer 報價回覆端點（已有 web；D1-B 加 agent 用內部端點）|
| LINE 推送 | `PushKind +quote_proposal`；`builders.py +render_quote_proposal`；`BUILDERS` dispatch；worker quote reference 解析 |
| agent（僅 D1-B）| `line_gateway.py` callback 新增 `PostbackEvent` 處理，路由 `q:a|`/`q:r|`（順帶救活 `s:a|`/`s:r|`）→ 打 api |
| 前端 | `/admin/quotes` 送單按鈕文案/狀態（「已推 LINE」）；`/quotes/{token}` 網頁同意頁（已存在，確認 OK）|
| DB | 預期無（quote 狀態機已足）；若要記「派工被 gate 擋」事件可用既有 work_order_events |
| 測試 | gate 409、送單 enqueue、同意→可派工、拒絕→不可派工、過期→不可派工 |

## 6. API contract 變更摘要

- `POST /tenants/{tid}/quotes/{id}:send`：行為新增「enqueue LINE 推送」（回應不變）。
- `POST .../work-orders/{id}:assign`：**新增前置條件** —— 若工單有未同意的 active 報價 → `409 QUOTE_NOT_ACCEPTED`（依 §8-D2/D3）。
- （D1-B）新增 agent→api 內部回覆端點 或 複用 `/consumer/quotes/{token}`。

## 7. 風險

- **改 `assign` 前置條件 = 既有派工流程行為變更**：若 prod 既有「無報價直接派工」的工單，gate 太硬會擋住 → 需 §8-D2 界定「無報價時是否放行」。
- **D1-B 動 agent gateway** = 架構面，須確保 postback 不影響既有文字訊息流（fail-soft）。
- LINE 推送 best-effort（同 CR-0027/0028）：送單失敗不可阻斷後台流程。

---

## 8. ✅ Human Decisions（業主已裁決 2026-06-22）

| 決策 | 裁決 |
|---|---|
| **D1 同意方式** | **真 LINE 點按 + 網頁 fallback** → 報價 Flex 含 postback 同意/拒絕；agent 新增 PostbackEvent 處理器（順帶救活 scope_change 死按鈕）；保留 URI 網頁 fallback |
| **D2 派工 gate** | **硬擋（一律需報價同意）** → 任何工單 `assign` 前都須有 `accepted` 報價，否則 `409 QUOTE_NOT_ACCEPTED`。附**主管 override**（admin/ops + reason，audited，沿用 CR-0042 開單 override 模式，作急修安全閥）|
| **D3 拒絕後** | **保留工單** → quote→rejected，工單留 created，客服改報價重送新版本（不自動關單）|
| **D4 過期** | 過期視同未同意 → 一樣擋派工，客服重送 |

> 下方為裁決前的原始選項，保留供追溯。

### （原始）Human Decisions Required

### D1：客戶「同意」方式 —— 網頁 vs 真 LINE 點按

| 選項 | 做法 | 成本 / 取捨 |
|---|---|---|
| **A. 網頁同意**（較省） | LINE 推一則報價訊息，含一顆「查看並同意報價」**URI 按鈕** → 開 `/quotes/{token}` 網頁，客戶在網頁按同意/拒絕 | 不動 agent；最穩；**但不是「LINE 內直接點同意」** |
| **B. 真 LINE 點按**（你原話「LINE 快速回覆」）（推薦但較大）| 報價 Flex 含 postback「同意/拒絕」按鈕，客戶**在 LINE 內直接點** → agent 新增 postback 處理器路由到 api；保留 URI 網頁 fallback | 需動 agent gateway（目前無 postback 處理）；**順帶救活 scope_change 死掉的 postback** |

> 我的建議：**B（含網頁 fallback）** —— 因為你明確要「LINE 快速回覆」，且這會一併修好 scope_change 的死按鈕。若想先快出 MVP 再說，選 A。

### D2：派工 gate 硬度

| 選項 | 做法 |
|---|---|
| **A. 硬擋（推薦）** | 工單有 active 報價但未 accepted → `assign` 回 409，不准派工 |
| **B. 軟提醒** | 允許派工但標警告/記事件 |

並附帶：**無報價的工單是否放行派工?** 建議 **放行**（有些簡單案件不需報價；gate 只在「有報價且未同意」時生效）+ 保留主管 override（沿用開單完整度的 override 模式）。

### D3：客戶「拒絕」報價後

| 選項 | 做法 |
|---|---|
| **A. 保留工單（推薦）** | quote → rejected，工單留 created，客服改報價重送新版本 |
| **B. 自動取消工單** | 拒絕即關單 |

### D4：報價過期（expiry_at，已存在 14d/3d）

建議：**過期 = 視同未同意 → 一樣擋派工**，客服重送新報價。（確認採用即可。）

---

## 9. Suggested Implementation Order（待 §8 核准後）

1. 後端：`PushKind +quote_proposal` + `render_quote_proposal` builder + `:send` enqueue + worker quote 目標解析。
2. 後端：`assign_order` 加 quote-gate（依 D2/D3/D4）+ 409 錯誤碼。
3. （若 D1-B）agent：`line_gateway` 加 PostbackEvent 處理（`q:a|`/`q:r|` + 救 `s:a|`/`s:r|`）→ api 回覆端點。
4. 前端：`/admin/quotes` 送單按鈕狀態/文案；確認 `/quotes/{token}` 網頁同意頁可用。
5. 測試：gate 409 / 同意→可派 / 拒絕→不可派 / 過期→不可派 / 送單 enqueue / postback 路由。
6. i18n + CHANGELOG + 本 CR 標 implemented + regen docs_html。
7. 部署 prod + 實測完整流程。

## 9.5 實作結果（2026-06-22）

| 層 | 落地 |
|---|---|
| 推送 | `PushKind +quote_proposal`；`render_quote_proposal`（postback `q:a|`/`q:r|` + URI fallback）+ BUILDERS；`quote_engine_service.transition(send)` enqueue；worker `_resolve_line_uid` 加 `quote` 路徑 |
| gate | `work_order_service._assert_quote_accepted`（無 accepted 報價 → 409 `QUOTE_NOT_ACCEPTED`；過期不算 accepted）+ assign_order 整合 + 主管 override（`assignWorkOrderV2` query `override_reason`，audited）|
| 客戶回覆 | `quote_engine_service.customer_respond_to_quote`（驗 line_user 擁有權 → 403 不符）+ internal 端點 `POST /internal/quotes/{id}:customer-respond` |
| agent | `line_gateway` 加 `PostbackEvent` 處理 → `_route_quote_postback_safe`（`q:a|`/`q:r|` → 內部端點 + reply_token 即時回覆）|
| 前端 | `/admin/quotes` 送單按鈕文案「送出並推 LINE」+ lineApprovalHint + i18n（中英）|
| 測試 | `test_cr_0095` 8/8（builder postback / gate 409 / accepted 放行 / override / 擁有權 403 / accept→accepted）+ 全套件 1403 passed / 0 回歸 + agent 120 passed + tsc 0 |

### 🔴 連帶修復 runtime 斷鏈（重大）

實作時發現 **`api/templates/line_flex/__init__.py` 未匯出 `build_messages`**，而 worker 以
`from templates.line_flex import build_messages` 取用 → **ImportError → outbox worker render 全失敗** →
**所有 LINE 推送（CR-0028 assign/accept、CR-0027 完工 PDF、scope_change_result）從未真正送達**。
此即會議「LINE 公單回傳斷鏈」(Action Item #6) 的真實 runtime 根因，先前 code-review 標 met 但 live 從未驗證。
本 CR 補匯出修復，所有 LINE 推送（含本 CR 報價推送）方能運作。

## 11. Out of Scope / Follow-up

- **scope_change（追加報價）postback 救活**：CIA D1 提及「順帶救活」，但為控制風險與聚焦初始報價流程，
  本 CR 只接初始報價 `q:a|`/`q:r|`。scope_change 的 `s:a|`/`s:r|` postback 仍未接收端（其 URI 網頁 fallback 可用，不退步）；
  agent `_route_quote_postback_safe` 對非 `q:` 前綴回 None。下一 CR 比照本 CR 模式接 scope_change 內部端點即可。
- 報價同意後是否自動排單（目前仍人工排單→派工）。

## 10. Sign-off

| Role | Date | Approved? |
|---|---|---|
| Product / 業主 | 2026-06-22 | ✅ 裁決 D1=真LINE點按+網頁fallback / D2=硬擋+主管override / D3=保留工單重送 / D4=過期擋派工 |
