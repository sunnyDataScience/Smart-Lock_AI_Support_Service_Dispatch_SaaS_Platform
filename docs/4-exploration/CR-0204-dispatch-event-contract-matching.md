---
id: CR-0204
title: 派工事件契約與媒合演算法 —— 六支 TC 的契約 drift、演算法空轉與規則缺口
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [API contract, User/Business flow, Domain model, DB schema, External integration, Architecture boundary, Test plan]
related: [TC-DISPATCH-01, TC-DISPATCH-02, TC-DISPATCH-03, TC-DISPATCH-04, TC-DISPATCH-07, TC-DISPATCH-09, FR-API-05, FR-API-06, FR-API-07, FR-TEC-03, FR-TEC-04, FR-TEC-07, BR-Disp-001, BR-Disp-002, BR-Quote-003, CR-0095, CR-0150, CR-0152, CR-0166, CR-0172, CR-0175, CR-0197]
---

# CR-0204 — 派工事件契約與媒合演算法

**查證基準 commit：`01114100`（2026-08-05）**。本文所有 `檔案:行號` 皆於此 commit 逐一開檔覆核；
與 2026-08-03 走查文件（基準 `c8687f5d`）的行號差異已就地更新，不沿用舊值。

---

## 1. 一句話

派工這條線上，**「文件說的名字」「程式做的事」「機讀契約 `api/openapi.yaml` 裡有的東西」三者互不相同**——
現在要裁決的是：**哪一邊才是正典**（改文件對齊實作，還是改實作對齊文件），
以及**四條從沒被實作過的派工業務規則**（接單 SLA、空池 dispatch_pending、急件權重、建案分類）V1 到底做不做。

---

## 2. 需求追溯

### 2.1 每支 TC 的需求 ID 與正典出處

| TC | 需求 ID | 正典出處（檔案:行號） | 正典原文（節錄） |
|---|---|---|---|
| TC-DISPATCH-01 | FR-API-05 / FR-TEC-03 | `smartlock-docs/enterprise/04_SRS.md:296`、`:353` | 「候選池（5→10→20km 擴大）→ 5 因子權重（distance+skill+rating+load+fairness）→ tie-breaker → top-1 通知」／「`POST /technicians:match`（技能/地區/品牌授權/可用性）→ 排序候選」 |
| TC-DISPATCH-01 | 端點契約 | `smartlock-docs/enterprise/16_API_Spec.yaml:342`（tag `ohs`） | `/technicians:match` post，`security: ohsServiceCredential` |
| TC-DISPATCH-01 | 事件契約 | `smartlock-docs/enterprise/17_AsyncAPI.yaml:111-116` | `dispatchAssigned: address: dispatch.assigned` |
| TC-DISPATCH-02 | FR-API-06 | `04_SRS.md:297` | 「小編指定技師覆寫自動建議｜**覆寫必留 audit（who/why）**」 |
| TC-DISPATCH-03 | FR-TEC-04 / FR-WEB-03 | `04_SRS.md:354` | 「接單 / 拒單 + 即時推播｜前置＝**`dispatch.assigned` 消費**｜→ `technician.assignment_accepted/rejected` 回品牌」 |
| TC-DISPATCH-03 | 事件契約 | `17_AsyncAPI.yaml:96-103`、`:347` | channel `technician.status-changed`（**自帶 `[待確認] 精確 topic 命名`**），enum 含 `assignment_accepted` |
| TC-DISPATCH-04 | FR-API-07 / BR-Disp-001 / BR-Disp-002 | `04_SRS.md:298`、`:462`、`:463` | 「一般 10min / 急件 5min 接單 SLA（per-brand override）；**30min 無人接 → 擴大範圍 + 通知客服**」 |
| TC-DISPATCH-07 | FR-TEC-07 / BR-Quote-003 | `04_SRS.md:357`、`:450`、`:142` | 「保固期內 / **建案案件** quote：AI 永禁觸發 LIFF send；server-side enforce 403 `AI_FORBIDDEN_WARRANTY_PROJECT`」 |
| TC-DISPATCH-09 | FR-API-05 | `04_SRS.md:296` | 「**候選池空 → dispatch_pending + alert**；**急件覆寫權重（distance↓ rating↑）**」 |

### 2.2 正典本身的三處問題（這些本身就是要裁決的事）

**(A) `17_AsyncAPI.yaml` 自承未定。**
`:97` 與 `:106` 兩條 channel 的 address 後面直接寫著 `# [待確認] 精確 topic 命名（事件族 technician.*）`，
`:54` 的 broker host 也標 `[待確認]`，`:57` 更寫明整個 Kafka 骨幹是「ADR-P005 / ADR-P007 **Phase 2 🔜 規劃中**」。
**所以 TC-DISPATCH-03 拿一個正典自己標為「待確認 + 規劃中」的事件名當判定基準，這個判定基準本身不成立。**

**(B) `16_API_Spec.yaml:342` 的 `/technicians:match` 是 `ohs` tag，不是品牌 api 的端點。**
它的 security 是 `ohsServiceCredential`，配合 `04_SRS.md:353` 的「品牌 api 持服務憑證」與
「**品牌不直連技師庫**」——正典設計的是「品牌 api → OHS 同步契約 → 技師平台」。
實作走的是完全不同的路：`api/services/dispatch_service.py:419-423` 的 `_fetch_tenant_technicians`
直接 `await db_module.require_tech_conn()` 對技師庫下 SQL。
**`/technicians:match` 找不到，不是因為漏做端點，是因為整條 OHS ACL adapter 這一層根本沒建。**

**(C) `04_SRS.md:296`「急件覆寫權重（distance↓ rating↑）」語意歧義。**
「distance↓」可讀成「距離權重調降」也可讀成「以更短距離為優先（＝權重調升）」；
「rating↑」同理。這句話**無法直接翻成係數**，必須業主定義（見 §8 D5）。

**(D) `04_SRS.md:71` 定義了 `Site` entity 帶 `site_group_id`（建案），但該 entity 在 code 中不存在。**
全庫 grep `site_group_id` 零命中；唯一相關的是 `SQL/migrations/003-warranty-5mode.sql:76-78`
在 `warranty_claims` 上加的 `warranty_inherit_from_site_group BOOLEAN NOT NULL DEFAULT TRUE`，
而 `api/routers/device_warranty.py:71` 明寫 `TODO(P3): 由 device_warranty + device 表載入真實
mode / anchor 日期 / site_group 繼承`。**建案在 domain 層完全沒有載體。**

---

## 3. 歷史成因（不是疏漏，是階段性選擇）

| 現象 | 成因 | 證據 |
|---|---|---|
| 事件名叫 `work_order.assigned` 不叫 `dispatch.assigned` | CR-0166 R4 建事件骨幹時採「少 topic、以 `event_type` 欄位判別」的設計，把 dispatch 事件折進 `workorder.lifecycle` | `api/core/event_bus.py:11-13` docstring 只列三個 topic；`:26-28` 三個常數 |
| 預設環境下**根本沒發事件** | 骨幹刻意 opt-in | `api/core/event_bus.py:6-7`「**opt-in**：`KAFKA_BOOTSTRAP` 未設 → producer no-op」、`:36-37` `enabled()` |
| `technician.lifecycle` 有常數沒 publisher | 同上，技師事件族列在 Phase 2 | `event_bus.py:28` 定義；全庫 grep `TOPIC_TECHNICIAN_LIFECYCLE` 僅該一處 |
| 品牌直讀技師庫 | 單庫 fallback 是刻意設計，OHS 契約層延後 | `dispatch_service.py:420-423` 註解「CR-0114 R4：師傅身分讀共用師傅庫 authority（require_tech_conn;單庫 fallback 同顆連線,SQL 不變 → 行為不變）」 |
| `levels` 收下不生效 | 2026-08-02 已刻意留白，等業主定語意 | `dispatch_service.py:509-516` 一整段註解自述「刻意**不猜語意**直接實作」 |
| 接單 SLA 從沒做 | TC 原文自帶「🔜 SLA 引擎自動改派規劃中，上線前列 gap 追蹤」 | `docs/uat/static-walkthrough-20260803/TC-DISPATCH-04.md:15` |
| 建案判定缺 | 實作時已知並留註記 | `api/services/quote_engine_service.py:508`「（fail-closed：未知/未帶角色一律擋；**建案判定記遺留**）」 |

**這一節的重點：上面沒有一項是「寫錯」。全部是「當時決定先不做，但正典沒有跟著標注」。**
真正的債不在 code，在**正典與 as-built 之間沒有標注機制**——所以每一輪稽核都會重新把它們當成新發現的缺口。

---

## 4. 現況證據（逐 TC 查證結論）

回查證把 6 支 TC 的走查結論逐條拿回 code 覆核。**走查文件引用的行號全部對得上**（僅 ±1~3 的區塊邊界差），
但有 3 支的**判定輕重需要修正**。

| TC | 走查判定 | 回查證判定 | 修正理由 |
|---|---|---|---|
| TC-DISPATCH-01 | 不一致 | **確認部分實作** | 能力等價（top 候選確實回得出來），純命名/契約不符；但走查**漏掉**兩個更重的事實（見 §5.2、§5.1） |
| TC-DISPATCH-02 | 部分實作 | **確認部分實作，但缺口不是走查說的那個** | 「非 dispatcher → 403」判重（見 §4.1）；真缺口是 override 死參數（§5.4） |
| TC-DISPATCH-03 | 不一致 | **比走查更嚴重** | 走查把判定基準②③記成「有」，實際上預設配置下三條**一條都不會發生**（§5.1） |
| TC-DISPATCH-04 | 不一致 | **確認部分實作** | 「通知客服」判重——`dispatch_delay` 告警的 WS 白名單**含** `customer_service`（§4.1） |
| TC-DISPATCH-07 | 部分實作 | **確認部分實作，但缺口不是走查說的那個** | warranty gate 落在 `:send` 是**正確位置**（判重，§4.1）；真缺口是建案（§5.6） |
| TC-DISPATCH-09 | 部分實作 | **比走查更嚴重** | 「急件規則」走查判輕——boost 對全體等比相乘，**數學上不改變任何排序**（§5.3） |

### 4.1 三個判重項（確認後不該修 code）

**① TC-DISPATCH-02「非 dispatcher 角色 → 403」。**
判定基準若照字面讀，連 `admin` 都要被擋。實際白名單是
`admin / operations_manager / dispatcher / customer_service`（`api/routers/dispatch_v2.py:40-44`、
`api/routers/dispatch.py:26-34`），這是 ADR-0045 §4 / PM Q6=A 的刻意設計（客服繞過須留稽核）。
測試已釘住真正該擋的角色：`api/tests/test_manual_dispatch.py:151-167`（technician→403）、
`:394-416`（brand_oem→403）。**判定基準寫法有瑕疵，不是 code 有瑕疵。**

**② TC-DISPATCH-04「通知客服」。**
走查在事件風暴表寫「**找不到**逾時通知客服」。實際上 `dispatch_delay` 告警經 WS `/realtime/sla-alerts` 推播，
角色白名單 `api/main.py:463` 的 `_SLA_ALERT_ROLES = {"admin","operations_manager","dispatcher","customer_service"}`
**明確含 `customer_service`**；前端 `web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:69-74`
有 `dispatch_delay` 紅色樣式並深連結 `/admin/dispatch-manual?work_order_id={id}`（＝人工擴大候選的入口）。
「逾時 → 客服看得到 → 可人工改派」這條鏈是**通的**。缺的是起算點與門檻（§5.5）與「自動」。

**③ TC-DISPATCH-07「warranty gate 落錯位置」。**
判定基準寫的是「保固/建案案件**自動送出** → 403」。送出＝`:send`，建 v+1 draft 不是送出。
`api/services/quote_engine_service.py:509-527` 擋在**正確位置**，且
`api/tests/test_cr_0152_ai_quote_gate.py::test_warranty_case_fail_closed_for_non_staff` 有覆蓋。

---

## 5. 程式碼現狀（把 6 支 TC 收斂成 6 個議題）

### 5.1 議題 A —— 事件骨幹：預設是關的，且投影表沒有讀取端（TC-01 + TC-03）

三層事實，一層比一層嚴重：

**第一層（走查已抓到）：事件名不符。**

| 判定基準要的 | 實際 | 落點 |
|---|---|---|
| `dispatch.assigned` | `work_order.assigned` @ topic `workorder.lifecycle` | `api/services/work_order_service.py:2337`、`api/core/event_bus.py:26` |
| `technician.assignment_accepted` | `work_order.accepted` @ 同 topic；DB 事件流寫 `event_type="accepted"` | `work_order_service.py:1326`、`:1293` |

全庫 grep `dispatch.assigned` / `assignment_accepted`（另試 `dispatch_assigned` / `technicians_match` /
`techniciansMatch`）於 `api web agent SQL` **零命中**。命中的 `tech_dispatch_assigned` 是 outbox push_kind，語意不同。

**第二層（走查沒點破）：預設配置下事件根本不發。**
`api/core/event_bus.py:36-37` 的 `enabled()` 讀 `KAFKA_BOOTSTRAP`，未設即 `publish_event` 全 no-op。
`api/realtime/event_consumer.py:27-28` 同樣 opt-in。
`docs/system-completion-status.md` 亦載明 3.1.1 Kafka 骨幹「opt-in `KAFKA_BOOTSTRAP` 未設＝runtime 休眠」。
**→ 在目前的部署環境下，TC-DISPATCH-03 的三條判定基準一條都不會發生。這支 TC 現在測不出東西。**

**第三層（最嚴重）：投影表是寫入即墳墓。**
`technician_workorder_projection` 全 repo 只有三種命中：
- 寫入：`api/realtime/event_consumer.py:78`
- 讀取：**只有** `api/tests/test_cr_0166_event_backbone.py:63/74/94`
- DDL：`SQL/tech_authority/Schema_cqrs_projection.sql:10`

`api/routers/` **零命中**。師傅端實際是直讀 `work_orders`。
**→「師傅工作台投影同步」即使把 Kafka 打開也沒有下游在用。CQRS 讀側從未接上。**

**第四層：事件發布無 outbox 保底。**
`work_order_service.py` 的發布為 fail-soft（失敗只記 log）。既有 outbox 只有
`commission_event_outbox`（`SQL/migrations/119`）與 LINE push outbox（`SQL/migrations/111`），
**不涵蓋工單/技師生命週期**。若正式啟用 Kafka，事件會靜默遺失。

### 5.2 議題 B —— 兩個生產端點不在機讀 SSOT 裡（TC-01，走查漏抓）

```
grep -c "auto-match"        api/openapi.yaml  → 0
grep -c "dispatch:candidates" api/openapi.yaml → 0
```

`api/openapi.yaml` 共 167 條 path，**dispatch 相關只有 `:1458` 的 `/tenants/{tenantId}/dispatch:plan`**。
而 code 有三條：

| code 端點 | code operation_id | openapi.yaml |
|---|---|---|
| `GET /tenants/{tenantId}/dispatch:candidates` | `listDispatchCandidatesV2`（`api/routers/dispatch_v2.py:49-50`） | **不存在** |
| `POST /tenants/{tenantId}/dispatch:auto-match` | `planDispatchAutoMatchV2`（`:113-114`） | **不存在** |
| `POST /tenants/{tenantId}/dispatch:plan` | `planDispatchV2`（`:149`） | 有，但 `operationId: planDispatch`（`api/openapi.yaml:1463`）——**operationId 也對不上** |

**這是硬傷，與命名之爭無關：媒合端點在機讀契約上根本不存在，任何以 openapi 為準的下游（SDK、契約測試、
API gateway 白名單）都不知道它們存在。**

另有兩個相關事實：
- `auto_match_dispatch` 的輸入是 **`problem_card_id`** 不是工單 id（`api/routers/dispatch_v2.py:136-141`、
  `dispatch_service.py:577`）；只有 `list_dispatch_candidates`（`:499`）吃 `work_order_id`。
  **正典 FR-API-05 的前置條件寫「WO created」，實作的自動媒合根本不需要工單存在。**
  這直接影響 §5.3 的 dispatch_pending 該掛在誰身上。
- `_apply_progressive_radius` **只在** `auto_match_dispatch` 呼叫（`dispatch_service.py:632`），
  `list_dispatch_candidates`（`:499`）不呼叫 → **兩條媒合路徑行為不一致**（一條有 5→10→20km 漸進擴池、一條沒有）。

### 5.3 議題 C —— 媒合演算法的兩個空轉（TC-01 + TC-09）

**① `levels` 參數是假契約。**
`api/routers/dispatch_v2.py:59-62` 的 Query description 已自承「⚠ 尚未實作：目前收下但不生效」；
`dispatch_service.py:509-516` 一整段註解解釋為何刻意不猜語意；`:520-523` 只印 warning。
可用的資料其實已經有了：`SQL/migrations/063-*.sql:12` 的 `technician_skill.level_id VARCHAR(10) DEFAULT 'LV-B' -- A/B/C（對齊 payout rule level）`。
**→ 資料在、語意缺。**

**② 急件 boost 在數學上不做事（走查判輕）。**

```python
# api/services/dispatch_service.py:634-637
boost = 1.05 if urgency == "emergency" else 1.0
for c in scored[:max_candidates]:
    s_norm = min(1.0, (c["score"] / 100.0) * boost)
```

`boost` 是**在排序完成之後、對所有候選一致相乘**的。`_W_DISTANCE` / `_W_RATING`（`:40-44`）
是模組層常數，無任何 urgency 分支。
**→ 急件與非急件選出來的 top-N 完全相同，只有回傳的 score 數字不同。**
相對 `04_SRS.md:296`「急件覆寫權重」，這是**未實作**而非部分實作。

**③ 空候選池完全沒有處置。**
`dispatch_pending` 全 repo 零命中（另試 `dispatchPending` / `dispatch-pending` / `待派工`）。
`auto_match_dispatch`（`:577-647`）在 `scored` 為空時，迴圈不執行，直接 `return {"candidates": []}`（`:647`）——
無 raise、無 alert、無狀態變更。`_apply_progressive_radius`（`:92`）在 `not candidates` 時原樣回傳。
另注意 `:111-112`「三級皆不足 → `selected = list(candidates)` 全納」，所以「擴到 20km 還是不夠」
也不會被判定為空池，只會靜靜地全納。

### 5.4 議題 D —— override_reason 在兩條路上是死參數（TC-02，安全相關）

`DispatchAssignRequest.override_reason` 是**活的契約欄位**（`api/models/generated.py` 有此屬性，
`api/openapi-runtime.json` components.schemas 有），被 `/dispatch/assign` 與 `dispatch:plan` 兩條路引用。
但：

```python
# api/services/dispatch_service.py:650-668
async def assign_dispatch(*, tenant_id, work_order_id, technician_id,
                          override_reason: str | None = None) -> dict:
    from services.work_order_service import assign_order
    return await assign_order(
        tenant_id=tenant_id, wo_id=work_order_id, technician_id=technician_id,
        reason_code="other",
        reason_text=override_reason,      # ← 只塞進 reason_text
    )                                      #   actor_role / actor_user_id / override_reason 全不傳
```

而 `assign_order` 的三道 gate 的 override 分支都要求 `actor_role in _QUOTE_GATE_OVERRIDE_ROLES
and override_reason and override_reason.strip()`（`work_order_service.py:2080` 定義；
`:2092` 報價 gate、`:2132` 品牌授權 gate、`:2241` 熔斷 gate 使用）。

**→ 兩者恆為 `None`，三道 gate 的 override 在這兩條路上恆不成立。**

實際後果有二：
1. **功能**：主管走 `dispatch:plan` 帶 override 會被 409 `QUOTE_NOT_ACCEPTED` 擋死。
2. **合規**：這兩條路**不寫 `quote_gate_override` audit**——`api/routers/dispatch_v2.py:181-195`
   與 `api/routers/dispatch.py:121-135` 只有 `customer_service` 的 `manual_dispatch_bypass` 分支。
   **直接違反 FR-API-06「覆寫必留 audit（who/why）」（`04_SRS.md:297`）。**

對照組是完整的：`api/routers/work_orders_v2.py:521-529` 有傳 `actor_role`/`actor_user_id`/`override_reason`，
`:531-541` 有寫 `quote_gate_override` audit。**三個入口只有一個做對。**

**測試盲區**：`api/tests/` 全域 grep `quote_gate_override` 零命中；
`test_manual_dispatch.py:73/78` 雖在 body 帶 `override_reason`，但 `assign_dispatch` 被 mock，參數被丟掉看不出來。

附帶：`dispatch_logs` 的 INSERT 只有 4 欄（`work_order_service.py:2276-2281`），
表 schema（`SQL/Schema.sql:807-818`）本就無 actor 欄位；`work_order_events` 的 actor 在這兩條路上為 NULL。

### 5.5 議題 E —— 接單 SLA 從零（TC-04）

| BR | 正典要求 | 實作 |
|---|---|---|
| BR-Disp-001 | 接單 SLA 一般 10min / 急件 5min + per-brand override | **零實作**。`git grep "BR-Disp" -- api web SQL agent` 無輸出 |
| — | 以「指派時刻」起算 | **不可能**——`assigned_at` 欄位全 repo 不存在（grep `assigned_at` 於 `api/ SQL/` 零命中） |
| BR-Disp-002 | 30min 無人接 → 擴大範圍 + 通知客服 | 只有**告警**：`api/realtime/sla_monitor.py:53` `DISPATCH_DELAY_MINUTES=30`（起算 `created_at`）、`:159-177` 掃描條件 `status IN ('created','assigned')`——**不分「未指派」與「已指派未接」** |
| — | 逾時後處置 | **無**。`:290-297` 只有 `arrival_overdue` / `audit_overdue` 兩型有額外處置；`sla_monitor.py` 全檔未 import `dispatch_service` / `work_order_service` / `notification_service` |
| — | 拒單後擴大候選 | **無**。`work_order_service.py:1372-1384` 只把工單退回 `created`（`_REJECT_FROM = {"assigned"}`，`:926`），無候選重算 |

**唯一可免 migration 的起算點**：`dispatch_logs` 有 `created_at`（`SQL/Schema.sql:817`），
且 CR-0165 F9 後手動派工一定寫 `action='assign'` 一筆（`work_order_service.py:2276-2281`）。
但這條路只覆蓋手動派工——若未來有自動指派，需確認同樣寫得出這筆 log。

### 5.6 議題 F —— 建案案件無 domain 載體，但錯誤訊息宣稱有（TC-07）

```python
# api/services/quote_engine_service.py:517-527（節錄）
wc = await (await conn.execute(
    "SELECT 1 FROM warranty_claims WHERE work_order_id = %s::uuid LIMIT 1", (wo_row[0],))).fetchone()
if wc and (actor_role or "") not in _HUMAN_STAFF_SEND_ROLES:
    raise ApiError("AI_FORBIDDEN_WARRANTY_PROJECT",
                   "保固／建案案件僅人類客服／主管可送出報價（BR-QUOTE-03／ADR-025）", 403)
```

判定式**只查 `warranty_claims`**。程式自己在 `:508` 註明「建案判定記遺留」。
可用的分類欄位盤點結果（全部查過，全部不可用）：

| 候選載體 | 實況 |
|---|---|
| `work_orders.service_category` | `SQL/Schema.sql:492` 註解僅 `install/warranty_in/warranty_out/repair`，**無 project** |
| `saas.intake_case` | `SQL/migrations/085-intake-case.sql:10-28` 只有 `source_channel`（line/phone/web/referral）與 `status`（open/in_progress/closed）——**是「通路」與「狀態」，不是案件類型**。（此處推翻回查證初稿「可用 intake_case 既有分類回填」的說法） |
| `Site` / `site_group_id` | `04_SRS.md:71` 有定義，**code 零命中**。唯一相關是 `warranty_claims.warranty_inherit_from_site_group`（`SQL/migrations/003-warranty-5mode.sql:76-78`，**`DEFAULT TRUE`**）——用它判建案會把**所有**保固單都判成建案 |

**→ 錯誤碼與訊息宣稱涵蓋建案、行為沒有。這比命名差異嚴重：營運看到 `AI_FORBIDDEN_WARRANTY_PROJECT`
會以為建案已受控。**

**附帶死角（非 bug，是 RBAC 收斂造成）**：CR-0150 分層核可只有 `>2000` 一條有 enforcement
（`quote_engine_service.py:534-545`）。`501-2000` 那層依註解「由 router RBAC 承載」，
但 `:send` 的 RBAC 是 `OPS_ROLES = (admin, operations_manager)`（`api/routers/quote_v2.py:217-221`
＋ `api/core/deps.py:295`），`customer_service` **根本送不出去**。
`api/tests/test_cr_0150_tiered_approval.py:61-64` 自述此事。**現況比規格嚴，安全方向正確。**

### 5.7 議題 G —— 派工推播無投遞端冪等（TC-09）

`tech_dispatch_assigned` **不在** `_STRICT_DEDUP_KINDS`（`api/services/line_push_outbox_service.py:58-63`），
所以 enqueue 走無條件 INSERT。投遞側：

```python
# api/realtime/line_push_outbox_worker.py:211-215
if push_kind in _TECH_DISPATCH_ENDPOINT:
    ok, err = await self._dispatch_to_tech(push_kind, payload)
    if ok:
        await self._mark_sent(outbox_id)        # ← POST 成功後才標記
```

`_dispatch_to_tech` 打的是 `/api/v1/internal/technicians/notify-assign`（`worker.py:97` 對映表），
該端點（`api/routers/technician_line.py:170-190`）**無任何冪等鍵**；
`x_line_retry_key`（CR-0175 C，`worker.py:246`、`:384`）只用於 LINE 直推分支，**不適用此 kind**。
**→ POST 成功但 `_mark_sent` 前 crash ＝ 師傅收到兩次派單推播。**

最小修法要注意一個雷：把 kind 加進 `_STRICT_DEDUP_KINDS` 必須**同步**改
`_DEDUP_INDEX_PREDICATE`（`:67-73`）與 `SQL/migrations/111-*.sql:36-42` 的 partial unique index，
三者註明須**逐字對齊**，不一致會 `InvalidColumnReference`。

---

## 6. 影響評估

### 6.1 rewrite vs refactor 九維打分（依 `.claude/rules/change-governance.md`）

| # | 維度 | 分 | 依據 |
|---|---|---|---|
| 1 | 產品目標是否改變？ | **0** | 沒變。派工要做的事（找到最合適的技師並派出去）從頭到尾一致 |
| 2 | 核心 User Flow 是否改變？ | **1** | 主流程（建單→媒合→指派→接單）不動；但要**新增分支**：接單逾時自動處置（BR-Disp-001/002）、空池 dispatch_pending。皆為新增，非重寫 |
| 3 | Domain Model 是否改變？ | **1** | **新增概念**：`dispatch_pending`（派工待處理）、建案案件分類、接單時限。核心概念（WorkOrder / Technician / Dispatch）不動 |
| 4 | API Contract 是否大量破壞？ | **1** | 兩個生產端點缺 SSOT 定義（§5.2）＋ `planDispatch` vs `planDispatchV2` operationId 不符 ＋ `levels` 假契約 ＋ `override_reason` 死參數。**多 endpoint 變動**，但無全面不相容；若 D1/D3 選「改 code 對齊契約」則升為 2 |
| 5 | DB Schema 是否需重建？ | **1** | migration 可處理：`assigned_at` 欄（或改用 `dispatch_logs.created_at` 免 migration）、`service_category` 加 `project`、outbox partial unique index 重建、（若選 D2(b)）`status` 加 `dispatched`。**沒有一項是痛的 migration** |
| 6 | 模組邊界是否錯誤？ | **1** | **有些混亂**。正典 FR-TEC-03 明寫「品牌不直連技師庫」，實作 `dispatch_service.py:419-423` 直連。邊界在部署層存在（`TECH_POSTGRES_URI` 可分庫），但 OHS 同步契約層（`/technicians:match` + ACL adapter）從未建立。**若 D3 選 (b) 全面對齊 ADR-P004，此維度升為 2、總分升為 9** |
| 7 | 測試是否可信？ | **1** | **部分可信**。派工八檔 52 項全綠（走查第二輪實跑），但綠的是「現行實作」不是「規格」。零覆蓋項：空候選池、接單逾時、`quote_gate_override` audit、事件名、建案。且 `test_manual_dispatch.py` mock 掉 `assign_dispatch` → §5.4 的死參數測試看不出來 |
| 8 | 文件是否可信？ | **2** | **大量矛盾**。`04_SRS.md`（FR-API-05/06/07）、`16_API_Spec.yaml:342`、`17_AsyncAPI.yaml:97/111` 三份正典同時與實作不符；機讀 SSOT `api/openapi.yaml` **缺兩個生產端點**；且 AsyncAPI 自帶 `[待確認]` 與「Phase 2 🔜」，正典自己也不確定 |
| 9 | 團隊/AI 是否還理解系統？ | **0** | **理解**。程式碼有密集的 CR 註解（CR-0051/0060/0061/0095/0114/0117/0150/0152/0165/0166/0172/0175/0197/0199），本輪查證能逐行對上，`levels` 與「建案判定記遺留」都是實作者主動留白並註明 |
| | **總分** | **8 / 18** | |

### 6.2 判定

**7–12 分 → 架構重審 + 模組拆分（多 CR + 跨 sprint）。**

具體含意：**不要試圖用一張 CR、一個 sprint 把這六支 TC 補完。**
理由是這六支背後其實是**三個獨立的子系統**，各有各的相依與風險等級：

| 子系統 | 涵蓋 | 為什麼要拆 |
|---|---|---|
| **① 契約對帳**（低風險，可立刻做） | TC-01 的 openapi 缺漏、operationId drift、正典標注 | 不動 runtime 行為，純契約補登；**唯一不需等裁決的部分** |
| **② 派工安全與冪等**（中風險，獨立） | TC-02 override 死參數、TC-09 推播去重 | 兩者都是「既有行為有洞」，與事件骨幹、SLA 引擎零相依，可平行做 |
| **③ 派工業務規則引擎**（高風險，需設計） | TC-04 接單 SLA、TC-09 空池 + 急件權重、TC-07 建案 | 都要先定義業務語意才能寫 code，且彼此有相依（空池判定要接 SLA 告警通道） |
| **④ 事件骨幹 Phase 2**（阻塞於基礎設施） | TC-03 全部、TC-01 事件名 | `KAFKA_BOOTSTRAP` 未設就測不出來；投影讀側從未接上。**這不是補一行 code 的事，是一個獨立的 Phase 2 專案** |

### 6.3 誠實聲明：這些其實不該修 code

依「誠實優先於完整」，下列項目查證後我認為**正確處置是改規格/標注，不是改 code**：

1. **TC-DISPATCH-02「非 dispatcher → 403」**（§4.1①）——判定基準寫法有瑕疵。改 code 會擋掉 admin。
2. **TC-DISPATCH-04「通知客服」**（§4.1②）——已通。要修的是起算點與門檻，不是「加通知」。
3. **TC-DISPATCH-07 warranty gate 位置**（§4.1③）——落在 `:send` 是對的。
4. **TC-DISPATCH-07 分層核可 501-2000**（§5.6 附帶）——現況比規格嚴。放寬 RBAC 是**擴權**，
   在沒有明確營運需求前不該做。
5. **TC-DISPATCH-03 全部**——判定基準引用的是正典自己標 `[待確認]` + 「Phase 2 🔜 規劃中」的事件名
   （§2.2 A）。**在 `KAFKA_BOOTSTRAP` 未設的環境下，這支 TC 不該排進 UAT——測不出東西。**
6. **TC-DISPATCH-04 整支**——TC 原文自帶「🔜 SLA 引擎自動改派規劃中，上線前列 gap 追蹤」，
   正典 `20_Test_Cases.md` 亦同。**若 V1 不做，正確處置是標 deferred + 留 gap 記錄，
   而不是硬塞一個半套 timer。**

### 6.4 三個「無論如何都該修」的硬傷

與上述相反，下列三項**不論 §8 怎麼裁決都成立**：

| 硬傷 | 為什麼不受裁決影響 |
|---|---|
| `api/openapi.yaml` 缺 `auto-match` / `candidates`（§5.2） | 端點確實在生產跑，機讀契約卻不知道它存在。無論端點叫什麼名字，SSOT 都該有它 |
| `override_reason` 死參數不寫 audit（§5.4） | 違反 FR-API-06 明文驗收條件，且是**合規**問題（覆寫無 who/why） |
| `AI_FORBIDDEN_WARRANTY_PROJECT` 訊息宣稱涵蓋建案但行為沒有（§5.6） | 無論建案怎麼實作，訊息與行為不符本身就是誤導 |

### 6.5 不做的代價

| 不做 | 代價 |
|---|---|
| 契約缺漏 | 每一輪稽核都會重新把 `/technicians:match` 當「缺的端點」重查一次（本次已是第二輪——`docs/system-completion-status.md` 已記為「待業主裁決」）|
| override 死參數 | 主管急修派工被 409 擋死，且覆寫無稽核軌跡（合規風險）|
| 急件權重空轉 | **急件與非急件派給同一個人**。這是營運會直接感受到的 |
| 空池無 alert | 沒有技師可派時，系統靜靜回空陣列，沒有人知道 |
| 推播無冪等 | worker crash 時師傅收到重複派單推播 |
| 事件骨幹不接 | 技師平台 CQRS 讀側永遠不成立；`technician_workorder_projection` 持續是寫入即墳墓 |

---

## 7. 可行路徑

### 路徑 1：契約對帳優先（建議先做，不等裁決）

只補契約、不動 runtime：`api/openapi.yaml` 補兩個端點 + 修 operationId；
在 `smartlock-docs/` 對應條文旁**加標注**（不改寫原文）記錄 as-built。
成本：小（半天）。風險：零。價值：止住重複稽核。

### 路徑 2：安全與冪等補洞（與路徑 1 平行）

`assign_dispatch` 補傳三個參數 + 兩個 router 補 audit + outbox 去重。
成本：中（跨 3~4 檔 + 1 migration + 新測試）。風險：中（改變既有端點在相同輸入下的行為）。

### 路徑 3：業務規則引擎（需先裁決語意）

接單 SLA、空池、急件權重、建案分類。
成本：大（跨模組 + 需設計 + 至少 2 個 migration）。**每一項都卡在「業主定義」而非「技術難度」。**

### 路徑 4：事件骨幹 Phase 2（另開 CR，不在本 CR 範圍）

啟用 Kafka + 接上投影讀側 + 工單事件 outbox。
**建議：本 CR 只做「決定契約名字」與「標注 as-built」，實作另立 CR。**

---

## 8. 🛑 Human Decisions Required

> 每題請回「Dn 選 x」即可。標「**建議**」的是我的傾向與理由。

---

### D1：事件名 `dispatch.assigned` / `technician.assignment_accepted` —— 改文件還是改 code？

(a) **改文件對齊 code**——在 `17_AsyncAPI.yaml:111`（`dispatch.assigned`）與 `:96-103`
（`technician.status-changed`）旁**加標注**：as-built 為 `workorder.lifecycle` topic，
以 payload 的 `event_type` 欄位判別（`work_order.assigned` / `work_order.accepted`）；
TC-DISPATCH-01/03 的判定基準同步改以實作名為準。
- 代價：正典的「事件族分 topic」設計意圖被稀釋；未來若真要拆 topic 要再改一次。

(b) **改 code 對齊契約**——新增 `dispatch.assigned` 與 `technician.*` topic publisher。
- 代價：`api/core/event_bus.py` + `api/realtime/event_consumer.py:22` 的 `_TOPICS` 都要動；
  consumer 要同時訂閱新舊 topic 過渡；**且在 `KAFKA_BOOTSTRAP` 未設的環境下做完也驗不了**。

(c) **折衷**——現階段選 (a) 標注 as-built，但在 AsyncAPI 明確補上「`event_type` 判別欄」的
schema 定義，讓契約可讀可驗；把「拆 topic」列入事件骨幹 Phase 2 的範圍。
- 代價：多一次文件工。

> **建議 (c)。** 理由：正典自己在 `:97` 寫著 `[待確認] 精確 topic 命名`、`:57` 寫著
> 「Phase 2 🔜 規劃中」——**拿一個自承未定的契約去要求 code 對齊，方向是反的**。
> 但單純選 (a) 又會讓契約失去「可判別」的資訊（下游不知道怎麼從一個 topic 裡分出 dispatch 事件），
> 所以要補 `event_type` 的 schema。

---

### D2：工單狀態 `dispatched` 要不要成為真的狀態值？

現況：DB 寫 `assigned`（`work_order_service.py:2267`），`SQL/Schema.sql:467-469` 列舉無 `dispatched`；
`dispatched` 只是前端分組標籤（`web/brand-portal/src/components/work-orders/statusGroup.ts:13/20-23`，
把 `accepted/scheduled/dispatching/assigned` 四值全歸為 `dispatched`）。

(a) **不加**——TC 判定基準改以 `assigned` 為準，前端分組維持不變，正典標注 as-built。
- 代價：TC 文字與 DB 值不同名，需標注說明。

(b) **加 `dispatched` 狀態值**——migration 改狀態列舉、狀態機轉移集合
（`_ASSIGN_FROM` / `_REJECT_FROM` / `_COMPLETE_FROM`…，`work_order_service.py:926-929`）、
`statusGroup.ts` 對映、所有 `status IN (...)` 查詢（含 `sla_monitor.py:161-163`）。
- 代價：狀態機是派工流程的核心，改列舉會波及所有查詢與既有資料回填；**這是本 CR 裡風險最高的單一項目**，
  換來的只是名字對齊。

> **建議 (a)。** 理由：`assigned` 與 `dispatched` 是**同一個狀態的兩個名字**，前端已經把四個後端狀態
> 折成一個顯示分組——這正是分組標籤該做的事。為了名字對齊去動狀態機，投報比極差。

---

### D3：OHS 契約 `/technicians:match` 與「品牌不直連技師庫」的邊界

現況：正典設計「品牌 api → OHS 服務憑證 → 技師平台 `/technicians:match` → ACL adapter」
（`16_API_Spec.yaml:342` tag `ohs`、`04_SRS.md:353`）；
實作是品牌 code 直接 `require_tech_conn()` 對技師庫下 SQL（`dispatch_service.py:419-423`）。

(a) **不建 OHS 端點**——正典標注 as-built＝「單體階段品牌直讀技師庫（單庫 fallback 同顆連線）」，
`/technicians:match` 標為 Phase 2。同時**補齊 `api/openapi.yaml` 的 `dispatch:auto-match` / `dispatch:candidates`**，
operationId 以 code 為準（`planDispatchAutoMatchV2` / `listDispatchCandidatesV2`），
並把 `api/openapi.yaml:1463` 的 `planDispatch` 改為 `planDispatchV2` 對齊 `dispatch_v2.py:149`。
- 代價：ADR-P004 的模組邊界持續只存在於文件。

(b) **建立 OHS 契約層**——在 tech-api 實作 `/technicians:match`，品牌側改走 ACL adapter，
`dispatch_service` 不再直連技師庫。
- 代價：**這是本 CR 裡最大的一項**（新服務端點 + ACL adapter + 品牌側媒合邏輯搬家 + 效能驗證
  p95 < 300ms）；且會把 `_brand_authorized_ids`（CR-0197 剛落地的閘門）一起搬。跨 sprint。

(c) **先補 openapi 缺漏 + 標注，OHS 契約另立 CR 排入 Phase 2 roadmap。**
- 代價：等於 (a) 但明確承諾未來會做。

> **建議 (c)。** 理由：openapi 缺漏是**硬傷**（§6.4），不該跟邊界之爭綁在一起等。
> 而 (b) 的價值只在真正要分離部署技師平台時才兌現——那是 ADR-P004 的階段目標，不是這輪 UAT 的範圍。
> 註：無論選哪個，**openapi 補齊都要做**；(a) 與 (c) 的差別只在「有沒有承諾 Phase 2」。

---

### D4：`levels` 參數的語意（`technician_skill.level_id` 已有 A/B/C 資料）

程式碼在 `dispatch_service.py:509-516` 已明白把這題留給業主：
`levels=['A']` 是指「持有**任一** A 級技能」還是「**指定技能**達 A 級」？

(a) **移除參數**——`dispatch_v2.py:59-62` 刪掉 Query，service 簽名移除。
- 代價：API contract 變更（雖然目前無呼叫端傳它——FastAPI 對未宣告的 query 參數是忽略而非 422，
  所以移除後舊呼叫端不會壞）。

(b) **實作為「持有任一該等級技能」**——`levels=['A']` → 該技師的 `technician_skill` 中
存在任一 `level_id='LV-A'` 的列即通過。
- 代價：語意最寬鬆，可能選到「A 級開鎖但 C 級電子鎖」的人去修電子鎖。

(c) **實作為「指定技能達該等級」**——需與 `skills` 參數交叉：
`skills=['electronic_lock'] & levels=['A']` → 該技師的 electronic_lock 技能須為 LV-A。
- 代價：`skills` 為空時語意退化成什麼？需再定義。實作較複雜。

> **建議 (c)，若要快則 (a)。** 理由：(b) 的語意在派工現場幾乎沒有用（派工在意的是「修這個東西夠不夠格」，
> 不是「他有沒有某個 A 級技能」）。但 (c) 需要多定義一條規則（`skills` 空時的行為），
> 若業主現在不想定義，(a) 移除比留一個假契約誠實——**現況（收下不生效）是三者中最差的**。

---

### D5：急件權重 —— `04_SRS.md:296`「急件覆寫權重（distance↓ rating↑）」的具體係數

先說清楚：**這句話本身有歧義。**「distance↓」可讀成「距離權重調降」，也可讀成
「以更短距離為優先（＝距離權重調升）」。從派工常識推，急件應該是「近的優先、評分次要」，
所以我讀作「distance 權重↑、rating 權重↓」——但這是我的推測，需要你確認。

(a) **維持現況**（`boost = 1.05`，等同不實作）——在 `04_SRS.md:296` 旁標注「急件權重 v1 不實作」。
- 代價：急件與非急件派給同一個人。這是營運會直接感受到的。

(b) **急件專用權重組**——我提議的預設值（總和仍為 1.0）：

| 因子 | 一般（現行 `dispatch_service.py:40-44`） | 急件（提議） |
|---|---|---|
| skill | 0.35 | 0.30 |
| **distance** | 0.25 | **0.40** |
| **rating** | 0.20 | **0.15** |
| load | 0.10 | 0.10 |
| fairness | 0.10 | 0.05 |

- 代價：需把 `urgency` 傳進 `_score_rows`（`dispatch_service.py:622`）；係數需業主確認。

(c) **不改權重，改排序策略**——急件時直接以 `availability_eta_minutes` 升冪取 top-1。
- 代價：完全忽略技能匹配度，急件可能派給不會修的人。

> **建議 (b)，用上表的係數。** 理由：急件的本質是「時間」，distance 是最直接的時間 proxy；
> fairness（雨露均霑）在急件情境下應該讓位。(c) 太激進——急件也不能派給不會修的人。
> **若你對係數有不同想法，直接回「D5 選 b，distance 改 X / rating 改 Y」即可。**

---

### D6：空候選池 `dispatch_pending` 的載體

先說一個影響選項的事實（§5.2）：`auto_match_dispatch` 的輸入是 **`problem_card_id`**，
不是工單 id——**這條路上根本沒有工單可以標狀態**。只有 `list_dispatch_candidates` 吃 `work_order_id`。

(a) **以工單為主體**——只在 `list_dispatch_candidates` 空池時把工單標 `dispatch_pending` + 發 alert；
`auto_match_dispatch`（PC 階段）只發 alert 不改狀態。
- 代價：要在 `work_orders.status` 加值（回到 D2 的狀態機問題），且兩條路行為不對稱。

(b) **獨立 pending 佇列表**——新建 `dispatch_pending_queue`（PC 與 WO 皆可入列），不動狀態機。
- 代價：多一張表與一套生命週期（誰清除？何時清除？）。

(c) **只發 alert，不落狀態**——`sla_monitor` 新增 `dispatch_no_candidate` 告警型別，
沿用既有 WS 通道（`_SLA_ALERT_ROLES` 已含 `customer_service`，`api/main.py:463`）與紅色橫幅
（`SlaAlertBanner.tsx` 加一個型別即可），深連結到人工派工頁。
- 代價：正典字面寫的 `dispatch_pending` 沒有實體，需標注。

> **建議 (c)。** 理由：**空池要解決的問題是「沒有人知道派不出去」，不是「需要一個新狀態值」。**
> (c) 用既有通道（WS 白名單、紅色橫幅、深連結到人工派工頁）幾天就能上，且不動狀態機、不建新表。
> 若日後發現需要「待派工佇列」的批次處理視角，再升級到 (b) 不遲。

---

### D7：`override_reason` 死參數與 dispatcher 的覆寫權（§5.4）

(a) **只修傳參**——`assign_dispatch`（`dispatch_service.py:650`）增加 `actor_role` / `actor_user_id`
參數並原樣轉傳給 `assign_order`（`override_reason` 傳 `override_reason` 而非只當 `reason_text`）；
兩個 router（`dispatch_v2.py:174-179`、`dispatch.py:115-120`）補傳 `user.role` / `user.user_id`，
並比照 `work_orders_v2.py:531-541` 在 `override_reason` 非空時寫 `quote_gate_override` audit。
**`_QUOTE_GATE_OVERRIDE_ROLES` 維持 `{admin, operations_manager}` 不變**——dispatcher 帶 override
仍不生效（會被 409 擋），但**該次嘗試會留 audit**。
- 代價：改變既有端點在相同輸入下的行為（admin/ops 的 override 從無效變有效）。

(b) **同 (a)，另把 `dispatcher` 加入 `_QUOTE_GATE_OVERRIDE_ROLES`。**
- 代價：**擴權**。報價 gate（「派工前須有已同意報價」）是 CR-0095 D2 業主親自裁決的規則，
  放寬覆寫角色等於放寬那條規則。

(c) **反向處理**——承認這兩條路的 `override_reason` 只是備註，把它從
`DispatchAssignRequest` 移除或改名為 `reason_text`。
- 代價：契約破壞（欄位已在 `api/openapi-runtime.json` 對外）；且主管在這兩條路上永遠無法急修覆寫。

> **強烈建議 (a)。** 理由：這是**三個入口只有一個做對**的傳參 bug，
> 且缺 audit 直接違反 FR-API-06 明文驗收條件（`04_SRS.md:297`）。
> (b) 是另一件事（要不要給派工小編覆寫權），**不該搭這班車**——若真需要，另開 CR 單獨裁決。
> **這題是本 CR 最需要你優先回答的一題**：它同時是功能 bug、合規缺口，且修法明確、範圍小。

---

### D8：接單 SLA（BR-Disp-001 / BR-Disp-002）V1 做不做？

(a) **V1 不做**——TC-DISPATCH-04 標 `deferred`，在 `04_SRS.md:298`/`:462-463` 旁標注
「接單 SLA v1 不實作，現行以 `dispatch_delay` 30 分告警（起算 `created_at`）替代」，
並在 completion-status 留 gap 記錄。
- 代價：與正典不符，需標注；派工逾時仍靠客服看紅色橫幅人工處理。

(b) **完整三層**——① `assigned_at` 欄位（migration 128）② `sla_monitor` 新增 `accept_timeout` 告警型別
（門檻讀 M18 config 支援 per-brand override，對齊 BR-Disp-001）③ 逾時自動擴池改派
（複用 `_apply_progressive_radius` 的 5→10→20km）。
- 代價：**自動改派是高風險功能**——判斷錯了會把單從正在路上的技師手上搶走。
  且 `sla_monitor.py` 目前刻意零業務相依（全檔未 import `dispatch_service`/`work_order_service`），
  接上去等於讓 SLA 引擎變成派工決策者，是架構邊界變更。

(c) **折衷**——做 ①（起算點）+ ②（`accept_timeout` 告警 + 通知客服），**不做**③（自動改派）。
起算點可先用 `dispatch_logs.created_at`（`action='assign'` 那筆，`SQL/Schema.sql:817`）**免 migration**，
但要先確認自動指派路徑也一定寫得出這筆 log。
- 代價：仍需人工改派（但客服本來就有紅色橫幅 + 深連結入口）。

> **建議 (c)。** 理由：現行 `dispatch_delay` 的問題是**起算點錯**（用 `created_at` 而非指派時刻）
> 與**不分未指派/已指派未接**（`sla_monitor.py:161` 的 `status IN ('created','assigned')`），
> 這兩點修掉，告警就準了——而告警準了，人工處置鏈（§4.1②已證通）就成立。
> **自動改派是另一個量級的功能，且 TC 原文自己寫「🔜 規劃中」**，不該在 UAT 補洞輪硬塞。

---

### D9：建案案件的 domain 載體（§5.6）

盤點結果：`service_category` 無 `project`、`saas.intake_case` 只有通路與狀態、
`Site`/`site_group_id` 在 code 不存在、`warranty_inherit_from_site_group` 預設 TRUE 不可用。
**建案在 domain 層真的沒有任何載體。**

(a) **擴 `work_orders.service_category` 加 `'project'`**——migration 128 + 更新
`_map_service_category`（`api/services/work_order_service.py`）+ 把
`quote_engine_service.py:517-521` 的判定式改成「`warranty_claims` 存在 OR `service_category='project'`」。
- 代價：`service_category` 目前混雜了「服務類型」（install/repair）與「保固狀態」（warranty_in/out），
  再塞「案件性質」（project）會讓這個欄位承載三種語意。

(b) **建 `Site` entity**（對齊 `04_SRS.md:71`）——新表 `site` + `site_group_id`，
`work_orders` 加 FK；建案＝有 `site_group_id`。
- 代價：這是一個完整的 domain 擴充（建案主檔、批次工單、保固繼承），
  遠超本 CR 範圍。`device_warranty.py:71` 的 `TODO(P3)` 也在等它。

(c) **V1 不做建案判定，先修訊息**——把 `quote_engine_service.py:524-525` 的錯誤碼與訊息
改成只講保固（或保留錯誤碼但訊息加「（建案判定 v1 未實作）」），
並在 `04_SRS.md:450` BR-Quote-003 旁標注。
- 代價：建案案件的 AI 送出防護持續不存在。**但現在也不存在，差別只在不再誤導。**

> **建議 (c) 立刻做 + (a) 排入下一輪。** 理由：(c) 是零成本止血（§6.4 硬傷之一）；
> (b) 是 P3 級的 domain 擴充不該搭這班車；(a) 是務實的中間解，但**前提是業主先回答
> 「建案在營運上怎麼認定」**——是接單時客服標記？還是同一 `site_group` 有 N 張單自動判定？
> 這題沒答案前，(a) 也做不了。

---

### D10：分層核可 501-2000 的 RBAC 死角（§5.6 附帶）

現況：`:send` 的 RBAC 是 `admin/operations_manager`（`quote_v2.py:217-221`），
`customer_service` 送不出去 → CR-0150 設計的「501-2000 由小編核可」那層在 API 面不存在。
`test_cr_0150_tiered_approval.py:61-64` 自述此事。

(a) **不放寬**——現況比規格嚴，安全方向正確。在 `16_API_Spec.yaml` 與 TC 標注
「501-2000 層 v1 不可行使（`:send` RBAC 已收斂）」。
- 代價：小編每一張 501-2000 的修正報價都要找主管送出。

(b) **放寬 `:send` RBAC 加入 `customer_service`**——`>2000` 仍需主管
（`_REQUOTE_SUPERVISOR_ROLES` 不變），501-2000 由小編執行送出即視為核可。
- 代價：**擴權**。`:send` 是「對客戶送出報價」這個動作本身，放寬影響的不只 requote 分層，
  是所有報價送出的角色範圍。

> **建議 (a)。** 理由：這不是 bug，是兩個規則（CR-0150 分層 vs `:send` RBAC 收斂）
> 的交集造成的死角，而**收斂的那一邊是後來為了安全刻意做的**。
> 若營運真的因此卡住（小編頻繁找主管），那是營運回饋驅動的擴權需求，該另案評估而非在此順手放寬。

---

### D11：派工推播的重複投遞防護（§5.7）

(a) **把 `tech_dispatch_assigned` 加進 `_STRICT_DEDUP_KINDS`**——同步改
`_DEDUP_INDEX_PREDICATE`（`line_push_outbox_service.py:67-73`）與新 migration 128 重建
`uq_outbox_ref_kind_strict`（原定義 `SQL/migrations/111-*.sql:36-42`）。三者須**逐字對齊**。
- 代價：擋的是 **enqueue 重複**（同一工單重複派工不會重複入列）；
  **擋不到** worker「POST 成功 → crash → `_mark_sent` 未執行 → 重推」那個窗口。
  另外要確認：assign 與 reassign 共用此 kind（`line_push_outbox_service.py:45-47` 註明 HD-B），
  加嚴格去重後**改派給另一位技師會不會被誤擋**（`reference_id` 是 wo_id，同一張單第二次派工會撞 unique）。
  **這是 (a) 的真風險，必須先驗。**

(b) **在 `/api/v1/internal/technicians/notify-assign`（`technician_line.py:170-190`）加冪等鍵**——
worker 傳 `outbox_id` 當 Idempotency-Key，端點側去重。
- 代價：要在技師平台側加冪等儲存（可複用 `core/idempotency.py`）。
  但**這才是真正擋住 crash-replay 的做法**，且不影響合法改派。

(c) **兩者都做。**

> **建議 (b)。** 理由：(a) 看起來最小，但**有誤擋改派的實質風險**（同一 `reference_id` + 同一 kind）——
> 而改派重推是合法行為。(b) 針對的正是實際的失效模式（worker crash window），
> 且與「同一張單可以派給不同技師」的業務語意不衝突。
> **若你要保險，選 (c)，但 (a) 上線前務必先驗改派情境。**

---

## 9. Suggested Implementation Order

### 相依關係

```
S0 契約補登 ──────────────┐（不等裁決，可立即開工）
                          │
S1 override 修復 ─────────┤（等 D7）      ← 這三步可平行
S2 推播冪等 ──────────────┤（等 D11）
                          │
S3 訊息止血 ──────────────┘（等 D9）
                          ↓
S4 levels 處置（等 D4）
S5 急件權重（等 D5）        ← S4/S5 可平行，皆在 dispatch_service.py 內
                          ↓
S6 空池 alert（等 D6，依賴 S5 完成後的 scored 流程理解）
S7 接單 SLA 起算點＋告警（等 D8）  ← S6/S7 共用 sla_monitor 告警機制，建議序列
                          ↓
S8 正典標注（等 D1/D2/D3/D8/D9/D10 全部裁決後一次做完）
                          ↓
S9 事件骨幹 Phase 2 → **另立 CR，不在本 CR 範圍**
```

### 逐步說明

| # | 步驟 | 前置 | 平行 | 驗證方式 |
|---|---|---|---|---|
| **S0** | `api/openapi.yaml` 補 `dispatch:auto-match`（`planDispatchAutoMatchV2`）與 `dispatch:candidates`（`listDispatchCandidatesV2`）；`:1463` 的 `planDispatch` → `planDispatchV2` | **無**（§6.4 硬傷） | 與所有步驟平行 | openapi lint 通過；與 `api/openapi-runtime.json` 的 operationId 對照零差異；既有 drift check 綠 |
| **S1** | `dispatch_service.assign_dispatch`（`:650`）加 `actor_role`/`actor_user_id` 參數並轉傳；`dispatch_v2.py:174-179` 與 `dispatch.py:115-120` 補傳 `user.role`/`user.user_id`；兩處補 `quote_gate_override` audit（比照 `work_orders_v2.py:531-541`） | D7 | 與 S2/S3 平行 | 新增 `test_manual_dispatch.py` 三案例：① admin 帶 override 走 `dispatch:plan` 應繞過報價 gate ② 應寫 `quote_gate_override` audit ③ dispatcher 帶 override 不繞過但仍留 audit（或明確 409）。**注意現有測試 mock 掉 `assign_dispatch`，新測試不可沿用該 mock** |
| **S2** | 依 D11 實作推播冪等 | D11 | 與 S1/S3 平行 | 若選 (a)：**先寫「改派重推不被誤擋」的測試**再改 index；migration 128 於 scratch 庫連套兩次退出碼 0（冪等）。若選 (b)：worker crash-replay 模擬測試（同 `outbox_id` 送兩次，端點只處理一次） |
| **S3** | `quote_engine_service.py:524-525` 錯誤訊息止血 | D9 | 與 S1/S2 平行 | `test_cr_0152_ai_quote_gate.py` 既有 5 測不得紅；訊息字串斷言更新 |
| **S4** | `levels` 依 D4 處置（移除或實作） | D4 | 與 S5 平行 | 若實作：新增 `test_dispatch_v2_endpoint.py` 案例覆蓋 A/B/C 三級過濾；若移除：確認 `web/` 無呼叫端傳此參數 |
| **S5** | 急件權重：把 `urgency` 傳進 `_score_rows`（`dispatch_service.py:622`），以急件權重組取代 `boost` 乘數（`:634-637`） | D5 | 與 S4 平行 | **關鍵驗證＝「急件與非急件的 top-N 排序必須不同」**（現況相同，這正是缺陷）。純函式測試，無需 DB |
| **S6** | 空池處置依 D6（建議 (c)：`sla_monitor` 新增 `dispatch_no_candidate` 告警型別 + `SlaAlertBanner.tsx` 加樣式與深連結） | D6、S5 | 序列 | 新增空候選池情境測試（`api/tests/` 目前**零覆蓋**）；前端型別對映測試 |
| **S7** | 接單 SLA 依 D8（建議 (c)：起算點改指派時刻、新增 `accept_timeout` 告警型別、門檻讀 M18 config 支援 per-brand override） | D8、S6 | 序列（與 S6 共用告警機制） | ① 起算點：驗「已指派未接 10 分」觸發、「未指派 10 分」不觸發（現況兩者不分）② per-brand override 讀 config ③ **確認自動指派路徑也寫 `dispatch_logs(action='assign')`**（若用該表當起算點） |
| **S8** | `smartlock-docs/` 標注（**只加標注，絕不改寫原文**）：`04_SRS.md:296/297/298/353/450/462-463`、`16_API_Spec.yaml:342`、`17_AsyncAPI.yaml:97/111`；`docs/uat/static-walkthrough-20260803/` 對應 TC 補判定更正 | D1/D2/D3/D8/D9/D10 全裁決 | 最後 | 標注後重跑一次 §5 的 grep 清單，確認無新的零命中項；更新 `docs/system-completion-status.md` 的「命名/契約 drift 待業主裁決」條目為已裁決 |
| **S9** | 事件骨幹 Phase 2（啟用 Kafka、接上 `technician_workorder_projection` 讀側、工單事件 outbox） | — | **另立 CR** | 不在本 CR 範圍。**在 `KAFKA_BOOTSTRAP` 未設前，TC-DISPATCH-03 不應排進 UAT** |

### 全程共通的驗證守則

- **不對 5433 埠的 UAT 庫跑 pytest**（會污染業主驗收資料）。用本機 Docker 測試庫。
- 每個 migration 於 scratch 庫**連套兩次退出碼 0**（冪等），並登記 `SQL/migrations/MIGRATION_REGISTRY.md`
  （不登記 drift check 會紅）。下一個可用編號＝**128**（現有最大為 127）。
- 全套跑完對照 scratch 基線，**零新增失敗**才算過。
- 每完成一步依 `CLAUDE.md` 同步三處：本 CR §8 進度區塊、`CHANGELOG.md` `[Unreleased]`、
  有架構決策則新開 ADR。

---

## 附錄：本 CR 的查證方式

- 走查文件引用的每個 `檔案:行號` 逐一開檔覆核，並在 HEAD `01114100` 重新定位（走查基準為 `c8687f5d`）。
- 宣稱「零命中」的識別碼以多種命名寫法重跑 grep：
  `dispatch.assigned` / `dispatch_assigned` / `technicians:match` / `technicians_match` / `techniciansMatch` /
  `assignment_accepted` / `dispatch_pending` / `dispatchPending` / `dispatch-pending` / `待派工` /
  `assigned_at` / `BR-Disp` / `site_group_id`。
- 三處推翻了初版回查證的說法，已在正文標明：
  ① `saas.intake_case` **沒有**可用的案件分類欄（§5.6）；
  ② `Site`/`site_group_id` 在 code 完全不存在，唯一相關欄位預設 TRUE 不可用（§5.6）；
  ③ `_STRICT_DEDUP_KINDS` 最小修法**有誤擋合法改派的風險**，不是無痛選項（§8 D11）。
- 未啟動任何服務、未連外網、未對 UAT 庫執行任何操作；`smartlock-docs/` 全程唯讀。
