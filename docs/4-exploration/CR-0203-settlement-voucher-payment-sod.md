---
id: CR-0203
title: 結算、傳票、金流與職責分離——退款生命週期缺半段、核准權限閘門零實作、金流子系統無入口
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, API contract, Domain model, External integration, Architecture boundary, Test plan]
related: [TC-SETTLE-01, TC-SETTLE-02, TC-SETTLE-04, TC-SETTLE-05, TC-SETTLE-08, TC-PAYMENT-01, FR-API-10, FR-API-11, FR-API-12, FR-TEC-06, FR-0011, FR-0012, FR-0014, FR-0046, BR-Set-001, BR-Set-002, BR-Set-003, BR-Set-005, ADR-0040, ADR-P014, CR-0070, CR-0166, CR-0189, CR-0198, OD-003, G-2]
---

# CR-0203 — 結算、傳票、金流與職責分離

## 1. 一句話

錢的那條路上，**「誰有權核准」與「錢什麼時候真的動」這兩件事在程式碼裡都沒有落地**：
退款的核准權限閘門（角色上限／自動升級）零實作、`create_refund_sod` 漏寫
`requires_dual_sign` 導致 20 萬退款一個人簽就終審、退款「執行」階段整段不存在、
金流子系統有骨架但**沒有任何 HTTP 入口**，而 `api/openapi.yaml` 卻已對外宣告了
5 支金流相關端點——**契約承諾了，實作沒跟上**。

---

## 2. 需求追溯

### 2.1 六支 TC 的正典出處

| TC | 判定基準（20_Test_Cases.md 原文） | 需求 ID | 正典行號 |
|---|---|---|---|
| TC-SETTLE-01 | 對帳單生成；佣金計費（per-job，品牌側）發 `commission.accrued` 事件 → 技師平台彙總結算（Billing/Settlement 分離，ADR-P014） | FR-0012 / FR-API-12 / FR-TEC-06 | `smartlock-docs/enterprise/20_Test_Cases.md:314`；`04_SRS.md:303`、`:356` |
| TC-SETTLE-02 | 200 + 完整 audit 事件鏈 | FR-0014 / FR-API-11 | `20_Test_Cases.md:316`；`04_SRS.md:302` |
| TC-SETTLE-04 | 拒絕並升級至上一層核准者；有效額度 = min(requested, `role_limit`) | FR-0014 / FR-API-11 | `20_Test_Cases.md:318` |
| TC-SETTLE-05 | 冪等回放（TTL 24h），不重複出帳 | FR-0014 / FR-API-11 | `20_Test_Cases.md:319` |
| TC-SETTLE-08 | 技師/vendor 僅見自己 scope；成本欄位對非授權角色遮蔽 | FR-0046 / FR-API-12 / FR-TEC-06 | `20_Test_Cases.md:321` |
| TC-PAYMENT-01 | 拒絕/timeout 不落成功帳；重送至多一筆收款與憑證；dispute 建立可稽核例外且不以重複扣款恢復 | FR-API-10 / FR-0011 | `20_Test_Cases.md:428`；`04_SRS.md:301` |

支撐業務規則：

- `04_SRS.md:483` **BR-Set-002**：append-only ledger；更正用 reversal entry
- `04_SRS.md:484` **BR-Set-003**：退款依責任歸屬 5×3=15 分層
- `04_SRS.md:486` **BR-Set-005**：佣金 Billing／Settlement 分離；`commission.accrued` 事件 + 期末 reconcile 閘門

### 2.2 🛑 正典本身的三處問題（這是要裁決的事，不是實作缺口）

**① `role_limit` 在正典中只出現在測試案例本身，沒有任何規格定義它。**

```
grep -rn "核准上限|role_limit|授權額度|核准額度" smartlock-docs/
→ 唯一命中：smartlock-docs/enterprise/20_Test_Cases.md:318（TC-SETTLE-04 自己）
```

`04_SRS.md:302`（FR-API-11）與 `:484`（BR-Set-003）都只寫「退款依 5×3 責任分層」，
**沒有一個字提到核准者的金額上限、也沒有提到自動升級**。
更關鍵的是 `04_SRS.md:586` 的**業主裁決 D1** 已經把「5×3」定義死了：

> 「5×3」＝5 層金額分層（1k/5k/30k/100k 門檻）× **SoD 三維**（initiator/approver/executor）
> ＝ADR-0040 v2 …… 實作完整落地（`refund_service.py` `resolve_tier`＋三維 SoD＋`refund_class` 5 類）

**依這條裁決，TC-SETTLE-04 要求的「角色上限 + 自動升級」根本不在 FR-API-11 的範圍內。**
TC-SETTLE-04 引入了一個正典沒有背書的第三個維度。這是規格內部矛盾，不是實作漏做。

**② `21_Traceability_Matrix.md:70` 把 FR-0014 標為 ✅，但 TC-SETTLE-02/04/05 都有實缺。**

```
| FR-0014 | 退款（L1–L5 分層 + SoD 三維）| api C-07；13_Security_Architecture | TC-SETTLE-02~05 | ✅ |
```

這個 ✅ 與本 CR §5 的證據直接衝突。追溯矩陣是 tier-5 view（`.claude/rules/context-stability.md`
判定「code wins」），但它現在正在對外宣稱一個未達成的覆蓋率。

**③ config 裡的 5 個核准角色不存在於 7 角色正典。**

`api/services/refund_service.py:450-455` 的 `approver_roles` 是
`supervisor / manager / finance_manager / director / cfo`；
`smartlock-docs/enterprise/13_Security_Architecture.md` 的 7 角色正典為
`platform_admin / admin / operations_manager / customer_service / reviewer / technician / dispatcher`。
**兩組零交集**——即使補上角色比對，也沒有任何使用者持有這些角色，結果會是恆拒。

### 2.3 正典已經自己承認的缺口（不要重複開卡）

| 正典條目 | 內容 | 對應 TC |
|---|---|---|
| `21_Traceability_Matrix.md:67` FR-0011 | 🔜 規劃中（**正式金流 provider 未接**，見 §4 gap）；驗證 TC 欄寫 `[待確認：依 04_SRS 定版]` | TC-PAYMENT-01 |
| `21_Traceability_Matrix.md:113` **G-2** | 付款 gate 控派工，P0，🔜 規劃中；**落地前派工段以業主豁免手動跳過，E2E 整鏈標 blocked** | TC-PAYMENT-01 |
| `21_Traceability_Matrix.md:68` FR-0012 | 🟡（非 ✅） | TC-SETTLE-01 |
| `21_Traceability_Matrix.md:98` FR-0046 | 🟡（非 ✅） | TC-SETTLE-08 |
| `14_ADR/open_decisions.yaml:110` **OD-003**（2026-07-28 業主已裁決） | 「程式有 Redis bridge 與 technician event consumer，但 **REDIS_URL/KAFKA_BOOTSTRAP 的 production 證據不存在**……兩者現皆為休眠 opt-in」 | TC-SETTLE-01 |

**這四條的意思是：TC-PAYMENT-01 與 TC-SETTLE-01 的主要缺口，正典早就寫明是「規劃中」。**
它們在 UAT 被判「部分實作」不是新發現，是既有共識的重述。真正需要裁決的只有
「本輪要不要提前做」以及「契約層的漂移要不要現在收」。

---

## 3. 歷史成因（為什麼會長成這樣，不是誰疏忽）

**退款有三條建立路徑，是分兩個時代長出來的。**

| 路徑 | 端點 | 建立函式 | `requires_dual_sign` |
|---|---|---|---|
| legacy flat | `POST /api/v1/refunds`（`api/routers/refunds.py:64-105`） | `create_refund_request` | ✅ 自動判定：`amount >= 100000`（`refund_service.py:258-262`） |
| **v2 SoD**（現行主線，brand-portal 在用） | `POST /tenants/{tid}/refunds`（`api/routers/refunds_v2.py:36-48`） | `create_refund_sod` | ❌ **INSERT 欄位清單裡沒有這欄**（`refund_service.py:643-646`） |
| agent 特例 | `POST /tenants/{tid}/refunds:agent-initiate`（`refunds_v2.py:156-204`） | 同上 | ❌ 同上 |

v2 SoD 路徑（ADR-0040 v2，2026-05-28 業主 PARTIAL_UPDATE 拍板）帶進了新的
「5-tier + `required_approvals`」模型，本意是要**取代**舊的單一門檻
`_DUAL_SIGN_THRESHOLD = 100000.0`（`refund_service.py:120`）。
但新模型只做到「算出 tier 並落庫」，**沒有把 tier 接回既有的雙簽開關**——
`required_approvals` 定義了 L1..L5 需 1/1/2/2/3 簽（`refund_service.py:458-464`），
在 `api/` 生產碼中**零消費**：

```
grep -rn "required_approvals" api
api/services/refund_service.py:458              ← config 宣告
api/tests/test_refund_sod_5tier.py:144,146,148  ← 只驗 config 結構單調性
```

結果是：舊路徑有雙簽保護、新路徑沒有。**這不是「功能還沒做」，是「換模型時斷了一條線」。**

**金流子系統則相反——它從第一天就明說自己是 mock。**
`api/services/payment_service.py:1-13` 與 `SQL/migrations/069-payments-mock.sql:31`
兩處白紙黑字：

> 會議決議 5 授權 mock-first…… 正式 provider（真 Line Pay / Apple Pay 簽章金鑰串接）
> 由 Sunny 下輪（決議 6）替換，DB schema 不變。

所以「沒有 HTTP 入口」在當時是**刻意的**。但 `api/openapi.yaml` 同時宣告了
`recordPayment`（`:1621-1633`）——契約層自己跑到實作前面去了，這一段不是刻意的。

---

## 4. 現況證據（逐 TC，回查證後的結論）

走查文件的引用經逐行複核，除以下標注外**行號全數正確**。

| TC | 走查判定 | 回查證判定 | 關鍵修正 |
|---|---|---|---|
| TC-SETTLE-01 | 部分實作 | **確認部分實作，但文件有一處實質證據錯誤** | 文件寫「`statement_generate_cron.run_once` 在 `api/tests/` 零命中」——**實際有 4 處命中**，`api/tests/test_cr_0117_data_wiring.py:349-377` 直接 import worker、跑兩次 `run_once()`、斷言 draft 產生（`gross_amount=1400.0`）且第二輪不重複產。文件把已被覆蓋的判定基準說成沒覆蓋。另：文件把「事件不由 cron 發出」列為落差，但判定基準原文自己寫「**per-job**」——per-job 與 cron 本來就是兩件事，**此處文件判重** |
| TC-SETTLE-02 | 部分實作 | 確認部分實作 | 引用無誤 |
| TC-SETTLE-04 | 不一致 | **比文件更嚴重** | 文件把 `requires_dual_sign` 記在「觀測到的其他事實」卻沒接到結論——那是本組唯一**活的**控制失效，見 §5.1 |
| TC-SETTLE-05 | 部分實作 | 確認部分實作，**但不該獨立計為一個工作項** | 缺口與 TC-SETTLE-02 是同一個（執行端點不存在）。冪等機制本身完整成立，文件引用逐行複核無誤 |
| TC-SETTLE-08 | 部分實作 | 確認部分實作 | 三處 ±3~5 行漂移（`api/core/deps.py` 的 `OPS_ROLES` 實為 `:295`、`FORBIDDEN` 403 實為 `:320-325`、角色群組實為 `:290-304`），**不影響結論** |
| TC-PAYMENT-01 | 部分實作 | **比文件更嚴重** | 文件引用逐行複核全數精準，但**沒去看 `api/openapi.yaml`**——契約層已宣告端點且詞彙與實作互斥，見 §5.3 |

---

## 5. 程式碼現狀

### 5.1 🔴 P0：`create_refund_sod` 不寫 `requires_dual_sign` → L5 單簽終審

**這是本組唯一「現行主線上活的控制失效」，其餘都是未建功能或契約漂移。**

證據鏈：

1. `api/routers/refunds_v2.py:36-48` 的 `createRefundSod` 已註冊上線
   （`api/main.py:359` `app.include_router(refunds_v2_router.router)`），brand-portal
   `web/brand-portal/src/app/admin/refunds/page.tsx:23`、`:124` 走的正是這條。
2. `api/services/refund_service.py:643-646` 的 INSERT 欄位清單：

   ```
   (work_order_id, requested_by, amount, reason, status,
    tier, refund_class, initiator_user_id, approver_user_ids,
    executor_user_id, audit_event_id, config_version_used)
   ```

   **沒有 `requires_dual_sign`。**
3. `SQL/Schema.sql:850`：`requires_dual_sign  BOOLEAN DEFAULT FALSE`。
4. `api/services/refund_service.py:340`：`requires_dual_sign = bool(row[3]) if row[3] is not None else False`
   → 讀到 FALSE。
5. `api/services/refund_service.py:372-381`：`approve` 且 `not requires_dual_sign`
   → `new_status = _FINAL_APPROVED_STATUS`（`approved`）。

**結論**：一筆 NTD 200,000（`resolve_tier` → L5，config 要求 3 簽）走 v2 SoD 路徑建立後，
**一位 `reviewer` 按一次 approve 就直接落 `approved`**。`:376` 的 `elif requires_dual_sign`
分支永遠走不到。

**為什麼 66 項綠測試抓不到**：`api/tests/test_refund_decision_v2_endpoint.py:84-86` 的
fixture 是**直接 INSERT** `requires_dual_sign`，繞過 `create_refund_sod`。
測試驗的是「給定 `requires_dual_sign=True` 時雙簽正確」，從沒驗過「建立時這欄會不會被設對」。

**嚴重度的誠實界定**：因為退款**沒有執行出款路徑**（§5.2），`approved` 不會自動動錢。
但 `api/services/refund_service.py:596` 的既有註解自述
「走完雙簽就重複出款」——顯示團隊認知中 `approved` **就是**線下財務出款的觸發訊號。
**「approved 是否等於實際出款」是營運事實，靜態無法確認**；若是，本項為 P0 需立即處理。

### 5.2 退款生命週期缺「執行」整段（TC-SETTLE-02 / TC-SETTLE-05）

| 階段 | 狀態寫入 | audit_events | 證據 |
|---|---|---|---|
| 建立 | `pending` | ✅ 一筆 `financial_action` / `refund.created`（含 hash chain） | `api/services/refund_service.py:630-638` |
| 核准 | `approved` / `csm_approved` / `rejected` / `escalated` | ❌ **只 append `approval_chain` JSONB** | `api/services/refund_service.py:383-400` |
| 執行 | ❌ **無任何程式碼** | ❌ | 全 repo `'executed'` 僅 3 處 enum/常數宣告：`api/models/generated.py:392`、`api/services/refund_service.py:61`、`:468` |

`api/services/refund_service.py` 全檔 `audit_log_service` **只有兩處**（`:615`、`:630`），
皆在 `create_refund_sod` 內。`approval_chain` JSONB **不進 hash chain**，
也不被 `api/routers/audit_v2.py:82-103` 的完整性驗證端點涵蓋——
TC-SETTLE-02 判定基準的「完整 audit 事件鏈」在核准與執行兩段皆不成立。

**TC-SETTLE-05 的冪等機制本身完整成立**（TTL 24h `api/config.toml:29-32`、
reserve-first `api/core/idempotency.py:241-244`、回放 `:273-275`、
異 body 409 `:266-271`、五個退款寫入端點全掛 guard）。
它的「不重複出帳」測不了，**純粹因為沒有出帳動作可測**——不該獨立計為一個缺口。
唯一自身缺口是「TTL 過期後接管路徑（`api/core/idempotency.py:74-86`）無測試覆蓋」。

**角色守衛的次要落差**：TC-SETTLE-02 步驟寫 `initiator=客服`，但端點守衛為
`REVIEW_ROLES`（`api/core/deps.py:301` = `admin` / `operations_manager` / `reviewer`），
**不含 `customer_service`**。`X-Initiator` header 與呼叫者 JWT 角色是兩個獨立值。

### 5.3 金流子系統：有骨架、沒入口、契約已對外承諾（TC-PAYMENT-01）

**成立的三件事**（可靜態確認）：

- webhook 先驗 HMAC（`hmac.compare_digest`，`api/services/payment_service.py:47`），
  失敗 401 且不寫任何 payment 狀態（`:121-122`）
- 同 `provider_txn_id` 重送直接回既有列不再 confirm（`:125-130`）
  ＋ DB 唯一索引 `uq_payments_provider_txn`（`SQL/migrations/069-payments-mock.sql:28-29`）
  → 「至多一筆收款」在資料層釘住
- `report_cash_dispute`（`:167-195`）**全函式無任何扣款/退款呼叫**；
  `confirm_payment` 對已 `failed`/`disputed` 的列回 409（`:105-108`），不會被推回成功

**不成立的四件事**：

1. **provider 拒絕沒有分支**。`handle_linepay_webhook`（`:116-134`）的簽章裡
   根本沒有 `status`/`result`/`return_code` 參數，`payload` 只當簽章輸入不解析（`:121`），
   **驗簽過就 confirm**。`failed` 的唯一寫入點在 `record_payment_fallback`（`:155`），
   由呼叫端顯式觸發而非 provider 驅動。
2. **「憑證」與 payment 零關聯**。`vouchers` 是**會計傳票**（借貸科目），
   其 `CHECK` 約束 `related_entity_type IN ('reconciliation','settlement','refund','invoice')`
   （`SQL/Schema_v2_extensions.sql:320-323`）**不含 payment**。
3. **整個子系統沒有 HTTP 入口**。`api/main.py` 全檔零 `payment` 命中；
   `api/routers/` 零 `payments` 字樣；`assert_payment_gate`（`:198-214`）也沒有呼叫端。
4. **零稽核留痕**。`payment_service.py` 全檔零 `audit_log_service`；
   `04_SRS.md:301` 要求的 `PaymentReceived/Failed/Disputed` 三個事件名全庫零命中。

**🔴 契約漂移（走查文件沒查到這層）**：

`api/openapi.yaml:1621-1633` 已宣告 `POST /tenants/{tenantId}/payments`（`operationId: recordPayment`），
而 `grep -rn recordPayment api --include="*.py"` 為 **0 筆**。而且契約詞彙與實作三方互斥：

| 概念 | `api/openapi.yaml` | `payment_service.py` | DB |
|---|---|---|---|
| method | `[onsite_cash, link, bank_transfer]`（`:6095`） | `{cash, apple_pay, line_pay}`（`:29`） | — |
| state | `[pending, paid, failed]`（`:6102`） | — | `pending/confirmed/failed/disputed`（`069-payments-mock.sql:15`） |

**而且這不是孤例。** 我對 `api/openapi.yaml` 的 189 個 `operationId` 與
`api/openapi-runtime.json` 的 503 個做了差集：**83 個 yaml-only**，其中金流相關 5 個
——`recordPayment` / `createRefund` / `getRefund` / `getVoucher` / `exportVouchers`
（逐一 `grep operation_id="<id>" api/routers/` 皆零命中；實作用的是不同名字：
`createRefundSod` / `getRefundSod` / `listVouchers` / `exportVoucher`）。

`api/openapi.yaml:1584-1607` 甚至把 `POST /tenants/{tenantId}/refunds` 宣告為
`operationId: createRefund` 回 **202**，而實作是 `createRefundSod` 回 **200**
（`api/routers/refunds_v2.py:36-48` 未設 `status_code`）——TC-SETTLE-02 的判定基準
「200」對的是實作，**不是對契約**。

**一處誠實修正**：一個直覺的擔憂是「前端會依 `openapi.yaml` 生型別而以為端點存在」。
**實查不成立**——`web/shared-contract/src/api-generated.ts:3448` 生的是 `createRefundSod`
（來自 runtime spec），`recordPayment` / `createRefund` 在該檔零命中。
所以真正的問題不是「前端被誤導」，而是
**`CLAUDE.md` 宣告「OpenAPI 機讀 SSOT = `api/openapi.yaml`」，但實際被機器消費的是
`api/openapi-runtime.json`——宣告的 SSOT 與真正的 SSOT 是兩份檔案**。

### 5.4 佣金／對帳單的 scope 隔離（TC-SETTLE-08）

**「成本欄位遮蔽」完全成立且是 server 端結構性不回 key**，這條無缺口：

- 三份同值常數 `_COST_VISIBLE_ROLES = {"admin", "operations_manager"}`
  （`api/routers/catalog_v2.py:20`、`quote_v2.py:24`、`work_orders_v2.py:68`）
- service 端 `api/services/payout_rule_service.py:44-46`：`if include_cost: out["base_payout"] = ...`
  （不回傳該 key，而非回 null）
- 客戶端硬編 `include_cost=False`（`api/routers/consumer_v2.py:284`）

**真正的缺口比走查文件的中性並陳更明確——那是一個壞掉的頁面，不是權限過寬**：

`web/tech-portal/src/app/account/statements/page.tsx:48-57` 的「我的月結對帳單」頁
先取 profile 拿 `technician_id`，再呼叫 `/tenants/{tid}/tech-statements`；
而該端點守衛是 `role_required(*OPS_ROLES)`（`api/routers/technician_statement_v2.py:96`）
→ **技師 token 必得 403 `FORBIDDEN`，這一頁對技師本人永遠讀不到資料**。

對照組是正確的：`web/tech-portal/src/app/account/commission-statements/page.tsx:50`
打 `/api/v1/technicians/me/commission-statements`（`api/routers/technicians.py:138-149`，
`role_required("technician")` + JWT `user_id` → `technicians.id` 反查，
`api/services/technician_commission_service.py:180-187`，**無 client 可控 id**）。
`api/routers/technicians.py` 全檔 11 支 `/technicians/me/*`，
**唯獨沒有 `/technicians/me/statements`**。

次要事實：
- `api/routers/technician_statement_v2.py:93` 的 `technician_id` 只是**選填 query filter**，
  不是伺服器端強制 scope。今天靠 `OPS_ROLES` 門檻擋住，若日後放寬角色門檻會直接變成越權讀取。
- `vendor` 在 `api/core/deps.py:290-304` 的**所有**角色群組中皆不出現，
  只有 `api/routers/vendors_v2.py:33-39` 的 `/vendors/me`——**是功能缺席，不是資料外洩**。
- 無「技師／vendor token 打 `dispatcher-commissions` / `tech-statements` 應 403」的負向測試。

### 5.5 月結與跨品牌彙總（TC-SETTLE-01）

**成立的兩段**：

- 「對帳單生成」：`api/realtime/job_registry.py:182-193` 的 `statement-generate` 是 14 個 job 中
  唯一 `schedule="monthly"`；`api/realtime/statement_generate_cron.py:118-173` 對上月有完工單
  且尚無 statement 的 (tenant, technician) 產 draft 並冪等。**有測試**
  （`api/tests/test_cr_0117_data_wiring.py:349-377`）。
- 「佣金計費 per-job 發 `commission.accrued`」：`api/services/reconciliation_service.py:222-240`
  同交易寫 outbox、`:270-291` commit 後即時 publish，topic 常數 `api/core/event_bus.py:27`。

**不成立／需裁決的三段**：

1. **月結批次無排程 job**。`JOB_SPECS`（`api/realtime/job_registry.py:83-254`）14 個 job 中
   沒有任何一個 `object_path` 指向 `monthly_settlement_service`；只能由端點觸發
   （`api/routers/settlements_v2.py:73-78` 顯式傳 `triggered_by="manual"`；
   `api/routers/monthly_settlements_v2.py:86-91` 為 `body.triggered_by or "manual"`），
   儘管 `api/services/monthly_settlement_service.py:104` 的預設值寫的是 `"cron"`。
2. **整條 Kafka 路徑 opt-in**。`api/core/event_bus.py:31-36`（`bootstrap_servers()` / `enabled()`）：`KAFKA_BOOTSTRAP` 未設即全 no-op；
   未啟用時 `technician_commission_projection` 不會有任何資料，
   `api/services/technician_commission_service.py:201-207` 以 fail-soft 回空清單。
   **這一條正典已裁決過**（OD-003，`open_decisions.yaml:110`：production 證據不存在、休眠 opt-in）。
3. **投影欄位最小化導致彙總失真**。`api/services/technician_commission_service.py:170-174`
   自述 `gross_amount` 以佣金累計代替、`status` 一律 `'accrued'`（`:212-214` 實作）。

**⚠️ 與 CR-0198 的邊界**：`docs/4-exploration/CR-0198-monthly-settlement-no-commission-event.md`
（status: `awaiting-decision`）**已經在問**「月結批次不發 `commission.accrued`」
與「`public.settlements` vs `saas.settlement` 表分裂」這兩件事。
**本 CR 不重複那兩題**，只補 CR-0198 沒問到的一題：**月結批次要不要有排程 job**（§8 D9）。

---

## 6. 影響評估

### 6.1 Rewrite vs Refactor 九維打分（`.claude/rules/change-governance.md`）

| # | 維度 | 分數 | 依據 |
|---|---|---|---|
| 1 | 產品目標是否改變？ | **0** | 沒變。結算/退款/金流的產品意圖與 `04_SRS.md:301-303`、`:356` 完全一致，缺的是落地 |
| 2 | 核心 User Flow 是否改變？ | **1** | 新增分支：退款生命週期補「執行」段（新狀態轉移）、技師自助對帳單新流程、金流補 HTTP 入口。主流程（建立→核准）不重寫 |
| 3 | Domain Model 是否改變？ | **1** | 新增概念：核准者權限額度（`role_limit`）、payment→voucher 關聯、`executed` 從 dead state 變成真狀態。核心概念（refund/settlement/voucher 三者的職責）不動 |
| 4 | API Contract 是否大量破壞？ | **1** | 多 endpoint 變動：新增 `:mark-executed`、`/technicians/me/statements`、payments 三支；`api/openapi.yaml` 5 個金流 op 需仲裁。**但無既有端點的破壞性變更**——都是新增或契約向實作對齊 |
| 5 | DB Schema 是否需重建？ | **1** | migration 可處理：`requires_dual_sign` 回填、`vouchers.chk_voucher_entity_type` 加 `'payment'`、`refund_requests` 執行欄位。無需重建任何表 |
| 6 | 模組邊界是否錯誤？ | **1** | 有些混亂但沒切錯：三條退款路徑（`refunds.py` / `refunds_v2.py` / `:agent-initiate`）、兩張 settlement 表（`public.settlements` / `saas.settlement`）、兩張 dispute 表（legacy `disputes` / `saas.dispute`）、`payment_service` 無 router 層。ADR-P014 的 Billing/Settlement 分離邊界本身是對的 |
| 7 | 測試是否可信？ | **1** | 部分可信。退款 66 項 + 結算 38 項 + 佣金 50 項全綠，**但沒有一項覆蓋本組任何一條判定基準**；更糟的是 `test_refund_decision_v2_endpoint.py:84-86` 的 fixture 繞過 `create_refund_sod`，**綠燈本身遮蔽了 §5.1 的缺陷** |
| 8 | 文件是否可信？ | **2** | **本組最高分**。`api/openapi.yaml` 83/189 op 無實作（金流佔 5）＋ `createRefund` 202 vs 實作 200；`21_Traceability_Matrix.md:70` FR-0014 標 ✅ 但三支 TC 有實缺；`role_limit` 在正典零定義卻是 P0 TC 的判定基準；config 的 5 個核准角色不在 7 角色正典 |
| 9 | 團隊/AI 是否還理解系統？ | **1** | 少數人懂。程式碼註解的誠實度其實很高（`refund_service.py:588-599`、`technician_commission_service.py:170-174`、`monthly_settlement_service.py:55-59` 都主動記載自身限制），但這些知識散在註解裡、沒有進正典 |
| | **總分** | **9 / 18** | |

### 6.2 判定：**7–12 分 → 架構重審 + 模組拆分（多 CR + 跨 sprint）**

**不建議一張 CR 一次做完**，理由有三：

1. **金流是本專案風險最高的面向**，而正典（G-2 / FR-0011 / OD-003）已明確把它標為
   「規劃中 + 業主豁免」。在業主沒有推翻那個豁免之前，動它是逆向操作。
2. **同一領域已經有一張 CR 在等裁決**（CR-0198）。在它裁決前動 settlement 事件流，
   會與它的方案 A/B/C 打架。
3. **§5.1 是唯一需要立刻處理的**，它小、獨立、且不需等任何其他決策。
   把它綁在一張 9 分的大 CR 裡等裁決，是拿一個 5 行的修補去換一個跨 sprint 的裁決週期。

### 6.3 🔻 誠實：以下項目我認為**不該修**，或應降級

| 項目 | 理由 |
|---|---|
| **TC-SETTLE-04 的「有效額度 = min(requested, `role_limit`)」** | 這個概念**在正典中零定義**（§2.2①），而 `04_SRS.md:586` 的業主裁決 D1 已經把「5×3」定義為「金額分層 × SoD 三維」，不含核准者額度。**應該改的是測試案例，不是程式碼。** 而且「截斷金額」在會計上與 BR-Set-002（append-only + reversal entry）衝突——一筆退款的金額被系統悄悄改小，帳本上會找不到差額的去向 |
| **TC-SETTLE-04 的「自動升級至上一層核准者」** | 同上，正典零背書。而且 `escalated` 不在 `_DECISION_FROM = {"pending","csm_approved"}`（`api/services/refund_service.py:289`）內——升級後根本沒有後續核准路徑，做了也是死路。要做就得先設計狀態機 |
| **config 的 5 個核准角色（supervisor/manager/finance_manager/director/cfo）** | 不在 7 角色正典。**不要為了讓 TC-SETTLE-04 通過而把這 5 個角色加進 RBAC 正典**——那會推翻 CR-0130 SA-01「死角色全面移除」的裁決。要做角色比對，就得用既有 7 角色重新定義映射 |
| **TC-SETTLE-05 獨立列為缺口** | 它與 TC-SETTLE-02 是同一個缺口（執行端點不存在）。應併入 D1，不開第二張卡 |
| **TC-SETTLE-01 的「事件該由月結 cron 發出」** | 判定基準原文自己寫「per-job」，**走查文件此處判重**。事件在對帳核准當下發出正是 per-job 的定義 |
| **TC-PAYMENT-01 的「provider 拒絕/timeout 真實行為」** | 屬執行期事實，靜態不可得；且正典已標 provider 未接。這部分走查文件的保留是對的 |
| **`vendor` 佣金端點** | 是功能缺席不是資料外洩。要不要做屬產品決策（§8 D8），不是缺陷修復 |

**扣掉以上，本組真正需要工程處理的只剩五件**：
①`requires_dual_sign`（P0，5 行）②退款執行階段 ③核准階段 audit
④技師自助對帳單端點 ⑤`openapi.yaml` 契約仲裁。

### 6.4 若不處理的風險

| 不處理 | 後果 |
|---|---|
| §5.1 `requires_dual_sign` | 任何金額的退款，**一位 `reviewer` 單簽即終審**。若線下財務以 `approved` 為出款依據，這就是實質的授權控制失效 |
| §5.2 核准階段 audit | `approval_chain` JSONB 不進 hash chain → **NFR-Aud-002 的 append-only 保證對退款核准不成立**，`GET /audit-logs` 的完整性驗證端點看不到核准動作 |
| §5.3 契約漂移 | 「Contract first」的宣稱失效。下一個讀 `api/openapi.yaml` 的人（含 AI）會以為 `recordPayment` 存在 |
| §5.4 tech-portal 對帳單頁 | 技師端一個**永遠 403 的頁面**留在正式站上 |

---

## 7. 可行路徑

### 7.1 立即可做、不需裁決（L0/L1）

- **P0 止血**：`create_refund_sod` 依 tier 從 `required_approvals` 推出 `requires_dual_sign`
  （`>= 2` 即 `True`）並寫入 INSERT（`api/services/refund_service.py:643-656`），
  配一支測試釘住「L5 走真實建立路徑後，單簽不得落 `approved`」。
  **不改任何契約、不改 schema、不改狀態機**。
  ⚠️ 但需先確認一件事：現行 prod 已存在的 `pending` 退款列若回填 `requires_dual_sign=true`，
  會讓它們**開始**需要雙簽（可能卡住既有流程）——是否回填屬 D2 的子問題。
- **契約仲裁**（純文件）：把 `api/openapi.yaml` 的 5 個金流幽靈 op 對齊或標記。

### 7.2 需裁決後才動（L2）

- 退款執行階段（新端點 + 狀態機 + SoD 第三維比對）
- 核准階段補 audit（新增 audit action 詞彙 → 改變 `GET /audit-logs` 輸出集合）
- 技師自助 `/technicians/me/statements`（新端點 + `openapi.yaml` 條目）
- 金流 router 曝露 + webhook 拒絕分支 + Secret Manager 金鑰 + voucher 關聯

### 7.3 應退回規格層處理（不寫 code）

- TC-SETTLE-04 的 `role_limit` 與自動升級 → 在正典標注（**不可改寫原文**）
- `21_Traceability_Matrix.md:70` 的 FR-0014 ✅ → 應降為 🟡

---

## 8. 🛑 Human Decisions Required

> 每題請以「D<N> 選 <選項>」回覆即可。D2 建議優先回答。

### D1：退款的「執行（executor）」階段要不要做？做成什麼？

現況：退款生命週期止於 `approved`，`executed` 是 dead state（`api/services/refund_service.py:468`
宣告它是終態，但無任何程式碼寫得進去）。TC-SETTLE-02 的「完整 audit 事件鏈」與
TC-SETTLE-05 的「不重複出帳」都卡在這裡。

- **(a) 系統執行出款** —— 接金流 provider，`approved` → 自動觸發退款交易 → `executed`
  代價：必須先完成 §D6 的正式金流串接；金流 provider 的退款 API 與收款 API 是兩套授權；
  失敗補償（退款打出去但狀態沒回寫）需要獨立的對帳修復流程。工作量最大、風險最高。
- **(b) 線下執行，系統只登記** —— 比照 `api/routers/monthly_settlements_v2.py:174-198` 的
  `markSettlementManualPaid` 既有樣板（`:186` `idempotency_guard` + `:185` `_require_initiator`
  + `:188` `_guard_tenant(write=True)`），新增 `POST /tenants/{tid}/refunds/{rid}:mark-executed`，
  寫 `status='executed'` + `executed_at` + 第三筆 audit + executor 與 initiator/approver 相異的 SoD 比對。
  代價：新端點 + 狀態機變更 + `openapi.yaml` 條目（API contract + Domain model + User flow）；
  但**不依賴任何外部 provider**，可獨立於 D6 完成。
- **(c) 不做，改規格** —— 承認 v1 退款止於 `approved`，出款完全線下；
  在正典標注「退款執行階段 v1 不納入系統」，並把 `executed` 從
  `_VALID_TERMINAL_REFUND_STATES` 與 `api/models/generated.py:392` 移除（消除 dead state）。
  代價：TC-SETTLE-02 / TC-SETTLE-05 的判定基準需同步修改；
  「誰執行了出款」永遠不在系統裡，SoD 三維只剩兩維有實效。

**我的建議：(b)。** 理由：(a) 綁死在 D6 上，而 D6 依正典（G-2）本來就是「規劃中」，
會把一個可以現在做的事拖到下一輪；(c) 會讓已經落庫的 `executor_user_id` 三維
SoD 欄位（`api/services/refund_service.py:649`）與 DB CHECK
（`SQL/migrations/002-refund-sod-5tier.sql:74-77`）變成純裝飾。
(b) 用既有樣板、零外部依賴，且把 SoD 三維真正閉環。

---

### D2：🔴 §5.1 的 `requires_dual_sign` 要不要立刻補？既有資料要不要回填？

現況：v2 SoD 路徑建立的退款，`requires_dual_sign` 永遠是 DB 預設的 `FALSE`
→ L3/L4/L5（config 要求 2/2/3 簽）全部單簽即終審。

- **(a) 立即補，依 `required_approvals` 推導，既有 pending 列不回填** ——
  `create_refund_sod` 依 tier 查 `required_approvals`，`>= 2` 即寫 `True`。
  新建的退款立刻受保護；既有 `pending` 列維持現況（避免卡住進行中的案子）。
  代價：既有 pending 的高額退款仍可單簽通過（需人工盤點）。
- **(b) 立即補 + 回填既有 `pending` 列** —— 同 (a)，另跑一次 migration 把
  `status='pending'` 且 tier ∈ {L3,L4,L5} 的列補為 `True`。
  代價：進行中的退款會突然多需要一簽，營運端需被通知；需先盤點筆數。
- **(c) 補，但沿用 legacy 的 `_DUAL_SIGN_THRESHOLD = 100000`** ——
  只有 L5 需雙簽，與 legacy flat 路徑行為一致。
  代價：與 config 的 `required_approvals`（L3/L4 也要 2 簽）**明確不一致**，
  等於承認 config 那段是死設定。
- **(d) 不補** —— 承認現行單簽即終審是可接受的營運模式，並把
  `required_approvals`（`api/services/refund_service.py:458-464`）刪除，避免它繼續假裝存在。

**我的建議：先回答「`approved` 是否等於線下出款依據」，若是 → (b)，若否 → (a)。**
理由：這是本組唯一可能有實際金錢後果的項目，且修補只有 5 行、不動任何契約。
(c) 是倒退——它讓 v2 的 5-tier 模型退化成 legacy 的單一門檻；
(d) 需要業主明確承擔「20 萬退款一人可決」的風險，我不建議，但這是業主的權力。

---

### D3：TC-SETTLE-04 的「核准者角色上限 + 自動升級」——是補 code 還是改規格？

現況：`role_limit` 概念全 repo 零命中；`approver_role_for_tier`（`refund_service.py:524-526`）
的回傳值唯一去處是 audit payload（`:628`），從不參與判斷；
`INSUFFICIENT_AUTHORITY` 只在 `api/openapi.yaml`（10 處）而 Python 零實作。
**且此要求在正典中零定義**（§2.2①），`04_SRS.md:586` 的業主裁決 D1 已把「5×3」定義為
「金額分層 × SoD 三維」不含此項。

- **(a) 補 code：完整實作** —— 把 5 個虛構角色映射到 7 角色正典、在 `submit_decision`
  加入 `decided_by` 角色 vs tier 比對並回 403 `INSUFFICIENT_AUTHORITY`、
  定義「升級至上一層」的狀態轉移（`escalated` 需納入 `_DECISION_FROM` 或另開 re-assign 路徑）。
  代價：需要新的角色→tier 授權矩陣（產品決策）；`escalated` 狀態機重新設計；
  且會與 D2 的 `required_approvals`（簽核**人數**）形成兩套並行的核准規則，語意需釐清。
- **(b) 補 code：只做角色比對，不做自動升級** —— 超上限直接 403 `INSUFFICIENT_AUTHORITY`
  （契約已宣告，實作即對齊），升級改由人工重新指派核准者。
  代價：仍需角色→tier 映射；但避開了 `escalated` 死路的重新設計。
- **(c) 改規格：TC-SETTLE-04 判定基準降為「`required_approvals` 簽核人數達標」** ——
  在 `smartlock-docs` 標注（不改寫原文）說明 FR-API-11 的核准控制以
  「金額分層決定簽核**人數**」實現，不採「角色額度上限」；`role_limit` 與自動升級移出 v1 範圍。
  代價：TC-SETTLE-04 需重寫；`api/openapi.yaml` 的 `INSUFFICIENT_AUTHORITY`
  在退款路徑上需一併移除或改標。

**我的建議：(c)。** 理由：這是規格內部矛盾，不是實作漏做——TC-SETTLE-04 引入了一個
FR-API-11 與業主裁決 D1 都沒有背書的維度。強行補 code 會把 5 個不存在的角色
塞進 RBAC 正典，直接推翻 CR-0130 SA-01「死角色全面移除」的裁決。
D2 的簽核人數控制已經能達成「高額退款需要更多人同意」的實質目的。
若業主堅持要角色維度，退而求其次選 (b)。

---

### D4：（僅當 D3 選 (a) 或 (b) 時需回答）「有效額度 = min(requested, role_limit)」是什麼意思？

- **(a) 截斷金額** —— 系統把退款金額改成核准者的上限值後放行
- **(b) 拒絕** —— 超上限直接 403，金額不動
- **(c) 從正典移除此句** —— 承認它是測試案例撰寫時的措辭，非業務規則

**我的建議：(b)，或隨 D3 選 (c) 一併移除。**
理由：(a) 與 **BR-Set-002**（`04_SRS.md:483`「append-only ledger；更正用 reversal entry」）
直接衝突——系統悄悄把一筆退款從 20 萬改成 3 萬，帳本上找不到那 17 萬的去向，
也沒有對應的 reversal entry。且 `api/services/refund_service.py:514-521` 的
`validate_amount` 目前只做 `> 0` 檢查，加入截斷會讓「客戶申請的金額」與
「系統記錄的金額」分岔，audit payload（`:622`）記的是哪一個也會變成新的爭議點。

---

### D5：`api/openapi.yaml` 的 5 個金流幽靈端點怎麼仲裁？誰才是機讀 SSOT？

現況：`api/openapi.yaml` 189 個 op 中 **83 個在實作端零命中**，金流佔 5 個
（`recordPayment` / `createRefund` / `getRefund` / `getVoucher` / `exportVouchers`）；
且 `createRefund` 宣告 202 而實作回 200。
同時 `CLAUDE.md` 宣告「OpenAPI 機讀 SSOT = `api/openapi.yaml`」，
但前端型別實際生自 `api/openapi-runtime.json`（`web/shared-contract/src/api-generated.ts:3448` 為證）。

- **(a) `openapi.yaml` 對齊實作** —— 本 CR 範圍內的 5 個金流 op：把名稱／status code
  改成實作的值（`createRefundSod` 200、`getRefundSod`、`listVouchers`、`exportVoucher`），
  `recordPayment` 依 D6 決定是刪除或標記。
  代價：只處理金流 5 個，其餘 78 個 yaml-only op 仍未盤點（需另開 CR）。
- **(b) 實作對齊 `openapi.yaml`** —— 把端點改名回契約宣告的名字。
  代價：`createRefundSod` → `createRefund` 會破壞 `web/shared-contract` 已生成的型別
  與所有前端呼叫點；純為對齊文件而做破壞性變更，不划算。
- **(c) 在 `openapi.yaml` 為未實作 op 加 `x-status: planned` 標記，並在 `CLAUDE.md`
  更正機讀 SSOT 指向 runtime spec** —— 保留契約作為「設計意圖」，但明示哪些還沒做。
  代價：需要一次全檔盤點（83 個）才有意義；`CLAUDE.md` 的 SSOT 宣告變更屬治理決策。
- **(d) 不處理** —— 代價：契約與實作繼續分岔，「Contract first」的宣稱（`api/openapi.yaml:1-40` header）失效。

**我的建議：(a) 先做金流 5 個（本 CR 範圍），(c) 的全檔盤點另開 CR。**
理由：(a) 成本低、立刻消除本組最容易誤導人的部分；(c) 是對的方向但範圍是 83 個 op，
塞進這張 CR 會失焦。(b) 為了文件去破壞已上線的實作，本末倒置。

---

### D6：正式金流本輪要不要做？

現況：正典已明確標為規劃中——`21_Traceability_Matrix.md:67`（FR-0011 🔜）、
`:113`（**G-2 P0，落地前派工段以業主豁免手動跳過，E2E 整鏈標 blocked**）；
`payment_service.py:1-13` 與 `069-payments-mock.sql:31` 都寫「正式 provider 由 Sunny 下輪（決議 6）」。

- **(a) 本輪全做** —— 接真實 provider、新增 router 曝露三支端點、
  webhook 從 Secret Manager 取 `LINE_PAY_CHANNEL_SECRET` 取代硬編的
  `_MOCK_LINEPAY_SECRET`（`payment_service.py:31-32`）、補 provider 拒絕分支、補 voucher、補 audit。
  代價：最大工作量 + 最高風險 + 需要 provider 商務帳號；且會推翻既有的業主豁免安排。
- **(b) 本輪只做「不需 provider 就能做的三件」** ——
  ①`handle_linepay_webhook` 補 provider 回應解析與拒絕分支（成功→confirm、失敗→標 `failed` + 記 provider 錯誤碼）；
  ②`payment_service` 全檔補 `audit_log_service`（目前金流動作零稽核留痕）；
  ③依 D7 決定憑證關聯。**仍不曝露 HTTP 入口，維持 mock-first**。
  代價：中等；TC-PAYMENT-01 仍無法整案驗收（無 HTTP 入口），但判定基準的第一條
  「拒絕不落成功帳」會從「無分支」變成「有分支」。
- **(c) 本輪不做** —— 正典既有標注即為答案；TC-PAYMENT-01 標 `blocked`，
  在走查文件加判定更正說明「此為已知規劃項，非新缺口」。
  代價：金流動作零稽核的狀態持續；但這本來就是既定安排。

**我的建議：(b)。** 理由：(c) 太保守——「金流動作零稽核留痕」這一條與
provider 串不串接無關，是獨立的稽核缺陷，`payment_service.py` 全檔零
`audit_log_service` 這件事不該等下一輪。(a) 直接推翻業主既有豁免，
且 §6.2 已論證金流是風險最高的面向，不宜在一張 9 分 CR 裡順手做掉。

---

### D7：「一筆收款一張憑證」的「憑證」是什麼？

現況：`vouchers` 是**會計傳票**（借貸科目 + `reason_code` + hash chain + 反向沖銷），
`CHECK` 約束 `related_entity_type IN ('reconciliation','settlement','refund','invoice')`
（`SQL/Schema_v2_extensions.sql:320-323`）**不含 payment**；
`payments` 與 `vouchers` 在 `api/` 中無任何 JOIN。

- **(a) 就是會計傳票** —— confirm 成功後開立 `vouchers` 列，
  `related_entity_type` CHECK 加 `'payment'` 值（DB schema 變更）。
  代價：一次 migration；需定義收款的借貸科目（借：現金/銀行存款，貸：應收帳款）。
- **(b) 是客戶收據** —— 全新概念，需新表 + PDF 產生 + 客戶端取用路徑。
  代價：最大；且與 `04_SRS.md:301` 的「voucher 開立」用詞不符。
- **(c) `payments` 列本身即憑證** —— 規格用詞改，不新增任何東西。
  代價：`04_SRS.md:301` 明寫「voucher 開立」，選 (c) 需在正典標注說明；
  且會讓「7 帳本」（BR-Set-001）少了 Cash 帳本的傳票來源。

**我的建議：(a)。** 理由：`04_SRS.md:303` 的 7 帳本明列 **Cash** 帳本，
而 `04_SRS.md:587` 的業主裁決 E1 已定「7 帳本語意由各域專表 + 傳票日記帳承載」。
收款不開傳票 = Cash 帳本沒有來源。(b) 的「客戶收據」是產品功能，
與「憑證」在會計語境下的意思不同，不該混為一談。

---

### D8：技師自助月結對帳單端點要不要補？vendor 佣金面要不要做？

現況：`web/tech-portal/src/app/account/statements/page.tsx:48-57` 打的是
OPS-only 的 `/tenants/{tid}/tech-statements`（`api/routers/technician_statement_v2.py:96`）
→ **技師必得 403，這一頁對技師永遠壞的**。`api/routers/technicians.py` 有 11 支
`/technicians/me/*`，獨缺 `statements`。vendor 在所有角色群組中皆不出現。

- **(a) 補技師端點，vendor 不做** —— 比照 `api/routers/technicians.py:137-149` 既有樣板，
  新增 `GET /technicians/me/statements`（`role_required("technician")`，
  scope 由 JWT `user_id` → `technicians.id` 反查，**禁止任何 client 可控的 technician 參數**），
  service 沿用 `technician_statement_service` 但強制 `technician_id` 由 token 決定；
  前端改打新端點、移除兩段式做法。vendor 佣金面標為未規劃。
  代價：新端點 + `openapi.yaml` 條目（API contract）；vendor 需求若存在則延後。
- **(b) 兩者都做** —— 另加 vendor 佣金/對帳單面。
  代價：vendor 的佣金模型目前不存在（無資料表、無 service），是全新功能而非補洞。
- **(c) 都不做，改前端** —— 從 tech-portal 移除 `/account/statements` 頁，
  技師只用既有的 `/account/commission-statements`。
  代價：零後端工作；但技師看不到月結對帳單（只看得到佣金 accrued 明細，
  且該投影 `status` 一律 `'accrued'`、`gross_amount` 是佣金累計代替——
  `technician_commission_service.py:170-174`），資訊確實不完整。

**我的建議：(a)。** 理由：這是本組唯一「使用者今天就看得到壞掉」的項目；
既有樣板現成，是複製而非設計。vendor 佣金屬產品決策不是缺陷，
不該混進本 CR 的工作量。
**無論選哪個，都應補負向 RBAC 測試**（技師/vendor token 打
`dispatcher-commissions` 與 `tech-statements` 應 403）——目前
`api/tests/test_dispatcher_commission.py` 與 `test_technician_statement.py`
皆無 technician/vendor fixture。

---

### D9：月結批次要不要有排程 job？

現況：`JOB_SPECS`（`api/realtime/job_registry.py:83-254`）14 個 job 無任何一個指向
`monthly_settlement_service`；`generate_monthly_batch` 的 `triggered_by` 預設值是
`"cron"`（`api/services/monthly_settlement_service.py:104`）但兩個呼叫端都傳 `"manual"`
——**這個預設值在暗示一個不存在的 cron**。

- **(a) 新增 `schedule="monthly"` job** —— 在 `JOB_SPECS` 加一個指向
  `monthly_settlement_service.generate_monthly_batch` 的 job。
  代價：**新增背景 job 屬 Architecture boundary**；且必須先確認 CR-0198 的
  對帳閘門問題——若 `reconcile_gate_enforce` 之後被打開而 CR-0198 未修，
  自動月結會**每次 409 且無人察覺**（手動觸發至少有人看到錯誤）。
- **(b) 維持手動觸發，把 `triggered_by` 預設值改為 `"manual"`** ——
  消除那個誤導性的預設值，並在 docstring 註明月結為人工發起。
  代價：月結需人工每月執行；但**有人按 = 有人負責**，對金流而言未必是缺點。
- **(c) 等 CR-0198 裁決後再議** —— 本 CR 只記錄事實，不動。

**我的建議：(b)，且明確 defer (a) 到 CR-0198 裁決之後。**
理由：把月結自動化的前提是對帳閘門可信，而那正是 CR-0198 在問的事。
在閘門能不能開都還沒定案之前，先讓月結自動跑，是把一個「有人看著的手動動作」
換成「沒人看著的自動失敗」。(b) 是零風險的誠實化。

---

## 9. Suggested Implementation Order（待 §8 裁決後）

### 階段 0 — 不需裁決，可立即並行（L0/L1）

| # | 工作 | 相依 | 驗證方式 |
|---|---|---|---|
| 0.1 | 在 `docs/uat/static-walkthrough-20260803/TC-SETTLE-01.md` 加「判定更正」標注：修正「無測試」誤述（實有 `api/tests/test_cr_0117_data_wiring.py:349-377`）與「事件該由 cron 發」判重 | 無 | 走查文件 diff review |
| 0.2 | 同上，為 TC-SETTLE-08 標注三處行號漂移（`api/core/deps.py` `:295`/`:320-325`/`:290-304`） | 無 | 同上 |

0.1 與 0.2 **可與階段 1 完全並行**。

### 階段 1 — P0 止血（依 D2）

| # | 工作 | 相依 | 驗證方式 |
|---|---|---|---|
| 1.1 | 先寫測試（RED）：透過 `POST /tenants/{tid}/refunds` **真實建立** L5 退款 → 單簽 approve → 斷言狀態**不是** `approved` | D2 | 該測試必須在改實作前紅，且紅在「狀態為 approved」這一條 |
| 1.2 | `api/services/refund_service.py:643-656` 補 `requires_dual_sign`（依 tier 查 `required_approvals`，`>= 2` 即 `True`） | 1.1 | 1.1 轉綠 |
| 1.3 | 對照基線重跑退款五檔（`test_refund_sod_5tier` / `test_refund_sod_endpoint` / `test_refund_dual_sign` / `test_create_refund_request` / `test_refund_decision_v2_endpoint`） | 1.2 | 66 項 → 67 項，**零新增失敗**。⚠️ 用本機 Docker 測試庫，**不可對 5433 UAT 庫跑** |
| 1.4 | （僅 D2 選 (b)）盤點 prod `status='pending'` 且 tier ∈ {L3,L4,L5} 的筆數 → 產 migration 回填 | 1.3 + 業主確認筆數 | migration 於 scratch + `lock_AI_data` 兩庫各連套兩次退出碼 0（冪等）；套用前後筆數比對 |

**階段 1 必須序列**，且 1.4 需業主看過盤點結果才執行。

### 階段 2 — 契約仲裁（依 D5，純文件，可與階段 1 並行）

| # | 工作 | 相依 | 驗證方式 |
|---|---|---|---|
| 2.1 | `api/openapi.yaml` 金流 5 個 op 對齊實作或標記 | D5、D6（`recordPayment` 的處置依賴 D6） | 重跑 op 差集腳本，金流 yaml-only 應歸零 |
| 2.2 | 在 `smartlock-docs` 標注（**不改寫原文**）：`21_Traceability_Matrix.md:70` FR-0014 應為 🟡；並記錄 §2.2 的三處正典矛盾 | D3 | 業主 review |

### 階段 3 — 退款生命週期補完（依 D1，L2）

| # | 工作 | 相依 | 驗證方式 |
|---|---|---|---|
| 3.1 | 核准階段補 audit：`api/services/refund_service.py:395-400` 的 UPDATE 之後補一筆 `financial_action` / `refund.approved`、`refund.rejected`，payload 帶 `decided_by` / `decision` / `stage` / `new_status` | 階段 1 完成 | `api/tests/test_refund_sod_endpoint.py` 補核准階段 audit 斷言；`GET /audit-logs` 完整性驗證端點（`api/routers/audit_v2.py:82-103`）仍綠 |
| 3.2 | （D1 選 (b)）新增 `POST /tenants/{tid}/refunds/{rid}:mark-executed` + `openapi.yaml` 條目 + 狀態機 `approved → executed` + executor 與 initiator/approver 相異的 SoD 比對 | 3.1 | 新測試：SoD 違反 403、非 approved 狀態 409、成功後 `executed_at` 落庫 |
| 3.3 | 補「同 `Idempotency-Key` 重送 `:mark-executed` 不重複寫 `executed_at`」測試（TC-SETTLE-05 的判定基準在此才變得可驗收） | 3.2 | 同 key 重送回放原 200，`executed_at` 不變 |
| 3.4 | 補 TTL 24h 接管測試：把 `idempotency_keys` 列 `created_at` 往前推 25 小時，驗證同 key 重送走 `_try_takeover`（`api/core/idempotency.py:74-86`）而非回放 | 無（可與 3.1~3.3 並行） | 新測試綠；不改任何行為 |

3.1 → 3.2 → 3.3 **必須序列**；3.4 可並行。

### 階段 4 — 技師自助對帳單（依 D8，L2，可與階段 3 並行）

| # | 工作 | 相依 | 驗證方式 |
|---|---|---|---|
| 4.1 | 新增 `GET /technicians/me/statements` + `openapi.yaml` 條目 | D8 | 新測試：技師 token 只回自己的期數；**無任何 client 可控 technician 參數** |
| 4.2 | `web/tech-portal/src/app/account/statements/page.tsx:44-60` 改打新端點，移除兩段式（先取 profile 再帶 query） | 4.1 | 技師帳號實際開頁不再 403 |
| 4.3 | 補負向 RBAC 測試：technician / vendor token 打 `/tenants/{tid}/tech-statements` 與 `/tenants/{tid}/dispatcher-commissions` 皆 403 | 無（可先做） | 新測試綠 |

4.3 **可最先做**（它驗的是現況行為，不需等 4.1）。

### 階段 5 — 金流（依 D6，L2）

| # | 工作 | 相依 | 驗證方式 |
|---|---|---|---|
| 5.1 | `payment_service` 全檔補 `audit_log_service`（intent / confirm / webhook / fallback / dispute 五個動作） | D6 | 新測試：五個動作各產一筆 `financial_action`；hash chain 驗證端點仍綠 |
| 5.2 | `handle_linepay_webhook` 補 provider 回應解析與拒絕分支（成功→confirm、失敗→標 `failed` 並記 provider 錯誤碼） | 5.1 | 新測試補「provider 拒絕」與「timeout」情境（目前 `api/tests/test_cr_0070_payment_mock.py` 的失敗情境只有壞簽章與 fallback） |
| 5.3 | （D7 選 (a)）migration：`vouchers.chk_voucher_entity_type` 加 `'payment'`；confirm 成功後開立傳票 | 5.2 + D7 | migration 兩庫各連套兩次退出碼 0；新測試驗一筆 confirmed payment 對一張 voucher |
| 5.4 | （僅 D6 選 (a)）新增 payments router + Secret Manager 取金鑰 | 5.3 | E2E；**需業主另行授權部署** |

### 階段 6 — 收尾

1. 更新 `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
2. 回寫本 CR §8 的裁決結果與各階段 `✅ Sx done（merge <sha>）`
3. 更新 `27_Roadmap` WBS 狀態欄（**只標已驗證項**）
4. 有架構決策則新開 ADR（append-only）

### 明確 defer（不在本 CR）

| 項目 | 去處 |
|---|---|
| 月結批次不發 `commission.accrued`；`public.settlements` vs `saas.settlement` 表分裂 | **CR-0198**（已 `awaiting-decision`） |
| Kafka / Redis 啟用 | **OD-003**（`open_decisions.yaml:110`，已裁決為休眠 opt-in，待 production 證據） |
| `openapi.yaml` 其餘 78 個 yaml-only op 的全檔盤點 | 另開 CR |
| `commission.accrued` payload 補工單毛額（讓 `gross_amount` 不再以佣金代替） | 隨 CR-0198 的事件 schema 決定一併處理 |
| vendor 佣金／對帳單面 | 產品決策，D8 選 (b) 才啟動 |

---

## 附錄 A：本 CR 的查證方式

- **未啟動任何服務、未連任何資料庫、未跑任何 pytest**（含 5433 UAT 庫）。全部為靜態閱讀。
- 走查文件引用的每個「檔案:行號」逐一開檔複核；§4 表列出所有偏差。
- `INSUFFICIENT_AUTHORITY` / `recordPayment` / `required_approvals` / `role_limit`
  的零命中為 `grep -rn ... api --include="*.py"` 實測結果，非推測。
- `openapi.yaml` vs 實作的 op 差集以腳本比對
  （`api/openapi.yaml` 189 op vs `api/openapi-runtime.json` 503 op，83 yaml-only），
  金流 5 個再逐一 `grep operation_id="<id>" api/routers/` 複驗。
- 「前端會被 `openapi.yaml` 誤導」這個直覺假設**經查不成立**，已在 §5.3 更正
  （`web/shared-contract/src/api-generated.ts:3448` 生的是 `createRefundSod`）。
- `requires_dual_sign` 的 DB 預設值以 `SQL/Schema.sql:850` 直接確認；
  legacy 路徑的自動判定以 `api/services/refund_service.py:258-262` 直接確認。
- 正典引用皆為唯讀；`smartlock-docs/` **未做任何修改**（§2.2 的矛盾在本 CR 內陳述，
  待裁決後才以「標注」方式回寫）。

## 附錄 B：靜態走查無法確認的事實

以下三項需執行期或營運確認，本 CR **不腦補**：

1. **`approved` 是否等於線下財務出款依據**——直接決定 §5.1 的嚴重度是 P0 還是 P2。
2. **prod 現存 `status='pending'` 且 tier ∈ {L3,L4,L5} 的退款筆數**——決定 D2 選 (a) 還是 (b)。
3. **prod 的 `KAFKA_BOOTSTRAP` 是否已設**——決定 TC-SETTLE-01 的第三段判定基準
   在生產上是否成立。`open_decisions.yaml:110`（2026-07-28）說「production 證據不存在」，
   但那是一週前的記載，需重新確認。
