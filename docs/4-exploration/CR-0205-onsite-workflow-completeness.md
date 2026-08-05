---
id: CR-0205
title: 現場作業流程完整性——「施工中」狀態不可達，加價流有兩套並存路徑
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, API contract, Domain model, DB schema, Test plan]
related: [TC-ONSITE-01, TC-ONSITE-02, TC-ONSITE-03, TC-ONSITE-04, TC-ONSITE-05, TC-ONSITE-06, TC-ONSITE-07, FR-0006, FR-0008, FR-0010, FR-API-08, FR-API-18, FR-TEC-07, BR-Onsite-001, BR-Onsite-004, ADR-027, CR-0038, CR-0049, CR-0053, CR-0144, CR-0150, CR-0197]
---

# CR-0205 — 現場作業流程完整性（抵達、施工、驗收、簽名）

## 1. 一句話

師傅端主要價值流的 7 支 P1 測試案例全數不合格，但**根因只有一個**：正常工單從
`accepted` 直接跳到 `completed`，**`in_progress`（＝規格說的 `on_site`／「施工中」）
在產品上根本不會發生** —— 於是所有掛在「施工中」上的功能（現場報價修正、技師可派工
計數、施工中統計）全部靜默失效；其餘落差有一半是規格側已被業主裁決推翻或本就排到
階段二，本 CR 要業主裁決的是「補哪些、砍哪些、標注哪些」。

---

## 2. 需求追溯

### 2.1 每支 TC 的需求 ID 與正典出處

| TC | 判定基準（`20_Test_Cases.md` 原文） | 需求 ID | 正典出處 |
|---|---|---|---|
| TC-ONSITE-01 | 工單 `on_site`；evidence 入庫帶 purpose 分類 | **FR-0006** | `smartlock-docs/enterprise/20_Test_Cases.md:301`；`04_SRS.md:299`（FR-API-08，前置寫「WO `in_progress`」）|
| TC-ONSITE-02 | 師傅自確 + 客戶簽名 + 照片三件套即通過 | **FR-0008** | `20_Test_Cases.md:302`；`04_SRS.md:189`、`:464`（BR-Onsite-001）；`02_BRD.md:286`；`15_SDS.md:244`；`03_PRD.md:158`（FR-D02）；`08_User_Flow.md:307` |
| TC-ONSITE-03 | 自動建 quote v+1 → 客戶 LIFF 確認後才可續作 | **FR-0008** | `20_Test_Cases.md:303`；`04_SRS.md:178`、`:181`、`:189`；`02_BRD.md:219`；`15_SDS.md:245`；`08_User_Flow.md:308` |
| TC-ONSITE-04 | 強制主管覆核；三件套（影音+文字+before/after 照）必齊 | **FR-0008** | `20_Test_Cases.md:304`；`04_SRS.md:189`；`15_SDS.md:246`；`08_User_Flow.md:309` |
| TC-ONSITE-05 | fallback 鏈完成；audit 標 `consent_method=paper` + evidence FK | **FR-0008** | `20_Test_Cases.md:305`；`04_SRS.md:191`、`:467`（BR-Onsite-004）；`02_BRD.md:291`；`15_SDS.md:248`；`03_PRD.md:159`（FR-D03）|
| TC-ONSITE-06 | 工單轉入例外流程（改期／取消分流）；不得直接結案 | **FR-0010** | `20_Test_Cases.md:306`；`04_SRS.md:176`（`arrived --> customer_not_onsite`）、`:309`（FR-API-18）|
| TC-ONSITE-07 | 工單 `on_site → quoted`；建 quote v+1（`supersedes_quote_id` 串鏈）→ 客戶 LIFF 確認 → `approved` 續工；拒絕 → 按原報價完工或走取消分流 | **FR-TEC-07** | `20_Test_Cases.md:307`；`04_SRS.md:357`；`15_SDS.md:210-217`、`:258`（§4.4）；`ADR-027` |

> 走查文件的「TC 原文」段把 TC-ONSITE-01～05、07 的需求欄一律寫成 `FR-API-08`。
> 那是走查作者的二次對映；`20_Test_Cases.md:301-307` 的**對應 FR 欄**寫的是
> FR-0006 / FR-0008 / FR-0010 / FR-TEC-07。本 CR 以正典欄位為準。

### 2.2 🛑 正典衝突一：業主已裁決過 `on_site` / `quoted`，但測試案例未同步

`smartlock-docs/enterprise/15_SDS.md:221` 有一則**業主 2026-07-10 裁決標注**：

> 〔標注 2026-07-10 業主裁決——階段一 as-built 對映：本節 flow DSL 值域
> （dispatched／on_site／quoted／approved／settled）依 18_DB「status 值域由 flow DSL
> 定義」與 WBS 4.1，屬 **M4 flow DSL 引擎 to-be**；階段一實作值域＝created／assigned／
> accepted／in_progress／completed／confirmed／cancelled（api/services/work_order_service.py），
> 全值域切換隨 M4 落地。現行對映：**on_site≡in_progress**（現場作業）、
> **quoted→approved 修正輪發生在 quote 層狀態機**（工單停留 in_progress，CR-0144／ADR-027）、
> settled≡confirmed＋月結鏈。〕

這則裁決直接處置了兩件事：

- **TC-ONSITE-01 的「工單 `on_site`」** → 讀作「工單 `in_progress`」。**這不是缺口，是用詞。**
- **TC-ONSITE-07 的「`on_site → quoted` → `approved` 續工」** → 已明文裁決「發生在 quote 層
  狀態機，工單停留 `in_progress`」。**這兩條判定基準已被業主裁決 supersede，不該再算缺口。**

`20_Test_Cases.md:301` 與 `:307` 未同步這則裁決，是走查判「不合格」的直接原因。
**M4 屬階段二**（`27_Product_Roadmap_WBS.md:70`、`:168` WBS 4.1），且
`27_Product_Roadmap_WBS.md:129` 明寫「階段二在階段閘（§5）通過前**只做設計不動工**」。

### 2.3 🛑 正典衝突二：BRD 自己前後矛盾（≤500 師傅自確 vs 技師零定價權）

| 出處 | 條文 |
|---|---|
| `02_BRD.md:111` | 痛點 **P-5**：「現場加價『**師傅說了算**』，客訴與呆帳高」→ 解法「加價三段式金額分層 + 簽名／照片／稽核三件套」|
| `02_BRD.md:286` | 「**≤ 500 元**：師傅自確，三件套（客戶簽名 + 照片 + audit log）齊備後續工」|
| `ADR-027`（2026-07-07 業主裁決，Accepted，`14_ADR/00_INDEX.md:92`）| 技師平台只發 command、品牌 api 為報價唯一權威——**技師零定價權** |
| `api/services/requote_service.py:22`（實作註解） | 「工單狀態機無 on_site(ADR-027 語彙)——現場作業對映 in_progress」|
| `web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx:1-5` | 「本頁原為 scope-change 自填單價流，**與 ADR-027 相悖**，2026-07-10 原地改造」|

**「≤500 師傅自確」與「技師零定價權」不可能同時成立。**
ADR-027（07-07）晚於 BRD 基線（07-07 凍結的 00–26 文件集），且前端已於 07-10 依 ADR-027
改造。但 BRD/SRS/SDS/PRD/User_Flow **五處**「≤500 師傅自確」的條文一字未動。
這是 §8 D2 要裁決的核心。

### 2.4 🛑 正典衝突三：「三件套」定義有一處孤例

| 出處 | 三件套定義 |
|---|---|
| `02_BRD.md:111`、`:286` | 簽名 + 照片 + audit log |
| `04_SRS.md:180`、`:464`（BR-Onsite-001）| 簽名 + 照片 + audit |
| `15_SDS.md:244` | 客戶簽名 + 照片證據 + audit log |
| `08_User_Flow.md:307` | 師傅簽名 + 照片 + audit 留痕 |
| `03_PRD.md:158` | 三件套（未展開，承 FR-D02）|
| `api/openapi.yaml:278` | `Scope change with 三件套 (signature + photo + audit)` |
| **`20_Test_Cases.md:304`（TC-ONSITE-04 唯一出處）** | **影音 + 文字 + before/after 照** |

六處對一處。走查文件依 TC 原文去找「影音類別」，結論是
`api/services/media_service.py:31-41` 九個 purpose 全為影像／簽名類、
`:54-60` 的 `_ALLOWED_CONTENT_TYPES` 只收 jpeg/png/webp/pdf——**這個「缺口」是照孤例定義
量出來的**。§8 D8 要裁決以哪個定義為準。

### 2.5 追溯矩陣的假綠

`smartlock-docs/enterprise/21_Traceability_Matrix.md`：

| 行 | 內容 | 本輪走查實測 |
|---|---|---|
| `:63` | FR-0006 到場存證（GPS + 照片）→ TC-ONSITE-01 → **✅** | 部分實作；GPS proof 恆 `None`、到場不觸發狀態轉移 |
| `:64` | FR-0008 現場加價三段式 → TC-ONSITE-02/03/04/05 → **✅** | 四支全部部分實作；分級結果是死資料 |
| `:66` | FR-0010 改期／例外回報 → TC-WO-11、TC-ONSITE-06 → **✅** | 部分實作；技師無法自行開異常 |

三個 ✅ 都是假綠。`smartlock-docs/` 只可標注不可改寫——處置方式見 §9 S0。

---

## 3. 歷史成因（不是疏漏，是三批工作沒收尾）

### 3.1 `in_progress` 從一開始就沒有進入的動作

`api/services/work_order_service.py:915-923` 的 `_WO_TRANSITIONS` 有
`"accepted": {"assigned", "in_progress", "completed", "cancelled"}`——**`accepted → in_progress`
是一條合法邊**。但同檔 `:927` 的 `_COMPLETE_FROM = {"accepted", "in_progress"}`
讓完工**可以直接從 `accepted` 發生**。於是這條合法邊從來沒有業務動作去走它，
而 happy path（`assigned → accepted → completed → confirmed`）照樣端到端可跑，
所以沒有任何測試會紅。

CR-0053（到場事件）修的是「`onsite_arrival` 誤用 `record_door_check` 寫 `event_type='door_check'`」
與「`started_at` 未落」兩個 bug（`work_order_service.py:3245-3250` docstring 自述），
**沒有把狀態轉移一併補上** —— 但同期寫的 `api/routers/work_orders_v2.py:862` docstring
已經寫著「到場後…狀態機推至 `in_progress`」。契約敘述先行、實作沒跟上。

### 3.2 ADR-027 引入 requote 時沒有處置舊的 scope-change 路徑

CR-0038（2026 桶 4）建了 `_classify_scope_tier` 金額分級與 M18 config 門檻
（`SQL/migrations/053-scope-tier-autoconfirm-config.sql:19-24` seed
`{"minor_max":500,"standard_max":2000,"major_pct":0.5}`）。
CR-0049 建了 `PENDING_SCOPE_CHANGE` 完工閘。

CR-0144（2026-07-10，ADR-027）另建 requote command 通道，並把技師端 scope-change 頁
**原地改造**成打 `/requote-requests`。改造後：

- 舊端點 `POST /tenants/{t}/work-orders/{id}/scope-change`（`api/routers/work_orders_v2.py:773`
  `operation_id="recordScopeChangeV2"`）**失去所有前端呼叫者**
- `_classify_scope_tier` 的唯一入口就是那個端點 → **整段分級邏輯成為死碼**
- CR-0049 的 `PENDING_SCOPE_CHANGE` 閘查 `scope_changes.status='pending'`，
  requote 路徑不建 `scope_changes` 列 → **這道閘對新路徑不成立**

`27_Product_Roadmap_WBS.md:118` 把 WBS 2.4.3 標為 ✅ 並註「技師 UI 入口＋cs_fallback 代發起
已補（scope-change 舊頁原地改造去定價）」—— 改造做了，**舊路徑的下架沒做**。

### 3.3 fallback 鏈只做了資料模型層

`api/services/signature_service.py:47` 註解自陳「TI-M08-03：簽名擷取通道 fallback 鏈——
LIFF 初始化失敗 → QR code → 紙本。`fallback_method` 記錄『這份簽名實際是怎麼取得的』，
供結案稽核（紙本 fallback 須留痕）」。service 層完整（`:48` 白名單、`:60` 預設、
`:69-73` 422、`:134`/`:153` 寫 JSONB）—— 但 HTTP 面從未接上。

---

## 4. 現況證據（回查證後的分流）

**本節結論全部逐一開檔覆核過**（走查文件的 36 處引用錯誤已在回查證階段修正）。

### 4.1 A 類 — 真缺陷，與規格之爭無關，必須修

| # | 缺陷 | 證據 |
|---|---|---|
| **A1** | **到場不觸發任何狀態轉移** —— `record_arrival`（`api/services/work_order_service.py:3237-3287`）只寫 `arrival` 事件 + `COALESCE` 補 `started_at`（`:3264-3267`），全程不動 `status` | 全 repo `UPDATE work_orders SET status = 'in_progress'` 只有兩處：`api/services/scope_change_service.py:190`（客戶核可加價）與 `:336`（admin override）。`_assert_transition_applied` 的 15 個呼叫點（`work_order_service.py:1289/1379/1819/1953/2274/2442/2520/2617/2751/3268/3606/3834/3958`）涵蓋接單／拒單／完工／取消／指派／改派／升級／客戶確認／改期／到場，**沒有一個目標是 `in_progress`** |
| **A2** | **技師可派工計數失準** —— 正在現場施工的師傅仍被算成 online/dispatchable | `api/services/technician_service.py:512-518`：`NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.technician_id = t.id AND wo.status = 'in_progress')`；`:527` 直接 `"dispatchable_count": online_count` |
| **A3** | **施工中統計桶恆為 0** | `api/services/technician_service.py:590-604` 的 daily bucket `if status == "in_progress"` 永不成立 |
| **A4** | **requote 入口實質不可達** —— 技師端「現場報價修正」頁到場後固定吃 403 | `api/services/requote_service.py:23` `_ALLOWED_WO_STATUS = {"in_progress"}`；`:72-74` 403；前端 `web/tech-portal/src/app/my-orders/[id]/scope-change/page.tsx:61-64` 打的正是 `/requote-requests` |
| **A5** | **一張工單這輩子只能成功 requote 一次** —— `requote_requests.status` CHECK 含 `closed`（`SQL/migrations/097-requote-requests.sql:21-22`）但**全 repo 對該表零 UPDATE**（只有 `requote_service.py:56` SELECT 冪等、`:78` SELECT open、`:107` INSERT 固定 `'quoted'`）；`:77-82` 對同工單已有 `received`/`quoted` 一律 409 | 已用 `grep -rn "UPDATE requote_requests"` 全庫確認零命中 |
| **A6** | **GPS 到場 proof 恆為 `None`** —— `compute_arrival_gps_proof`（`work_order_service.py:3211-3217`）需要 `ref_lat`/`ref_lng`，前端只送 `lat`/`lng`（`my-orders/[id]/page.tsx:283-289`），且無服務地址地理編碼來源 → 這段是死碼 | `work_order_service.py:3271-3273` 從 `gps.get("ref_lat")` 取值 |
| **A7** | **紙本／QR 簽名經 HTTP 不可達** —— `signature_service` 支援 `paper`（`:48`、`:60`、`:69-73`），但兩個端點都不透傳（`api/routers/work_orders_v2.py:753-761`、`api/routers/work_orders.py:344-352`），`SignaturePayload`（`api/models/generated.py:492-497`）無此欄位 → **經 API 進來的簽名恆為 `liff`** | 唯一能寫入 `paper` 的方式是直呼 service，`api/tests/test_cr_0066_coverage_batch4.py:121-143` 就是這麼測的——**測到的是產品上不可達的路徑** |
| **A8** | **簽名成功不寫 audit** —— `submit_work_order_signature` 全函式（`signature_service.py:51-180`）零 `audit_log_service` 呼叫 | `grep -n "audit" api/services/signature_service.py` 零命中（已實測）|
| **A9** | **技師不能回報「客戶未到場」** —— `openExceptionCase` 的 RBAC 是 `role_required("admin","operations_manager","dispatcher","customer_service")`（`api/routers/exception_cases_v2.py:24-26`，`:57` 使用），**不含 technician**；技師端六個 subflow CTA（`my-orders/[id]/page.tsx:565-602`）無此入口 | `api/core/deps.py:304` 的 `TECH_ACTION_ROLES` 有 technician，但這支端點沒用它 |
| **A10** | **「不得直接結案」形同虛設** —— `open_exception` 的 `severity` 預設 `"medium"`（`api/services/exception_service.py:69`、`api/routers/exception_cases_v2.py:37`），而 `_HIGH_RISK = {"high","critical"}`（`exception_service.py:24`）才設 `high_risk_hold`（`:96-100`）→ 以預設值開 `customer_absent`，完工照樣過 | 完工側 `work_order_service.py:1765` → `_assert_not_high_risk_hold`（`:2061-2075`）確實會擋，前提是 hold 有被設 |
| **A11** | **孤兒 UI 分支** —— `reschedule/page.tsx:319-328` 有 `?from=no_show` 提示分支，全 tech-portal 找不到產生該 query 的連結來源 | 走查步驟 3 已重掃確認 |
| **A12** | **`ensure_evidence` 只檢查非空** —— `customer_not_onsite` 宣告 `evidence_required: ["gps","timestamp"]`（`api/services/cancellation_service.py:73-76`），但 `:214-222` 只驗 `evidence_ids` 非空，不逐項比對 → 存證要求形同宣告 | — |

### 4.2 B 類 — 規格 vs ADR 衝突，要裁決不是要修

| # | 事項 | 證據 |
|---|---|---|
| **B1** | **`_classify_scope_tier` 產出的 `tier` / `requires_supervisor` 沒有任何執行期讀取者** —— 產生點 `work_order_service.py:2920`，只被寫進 `:3005` 的 `new_scope` JSONB 與事件 payload；全庫消費者僅 `:2900` docstring、`:2988` 註解、`api/tests/test_cr_0038_bucket4.py:26/34/42/50` 四個測試斷言 | 已用 `grep -rn "requires_supervisor" api web` 實測 |
| **B2** | **`record_scope_change` 對所有 tier 處理完全相同** —— `:2992-3009` 的 INSERT 是 **SQL 字面 `'pending'`**（`:2996`），無參數化無分支；`:3054-3071` 的 LINE 推播亦無 tier 分支 | minor 提案照樣擋完工（`:1585-1591` 的 `PENDING_SCOPE_CHANGE` 只查 `status='pending'`，`:1471-1477` 的 SQL 不含 tier 或金額）|
| **B3** | **「師傅自確」0% 實作** —— `scope_changes` 無 self-approve 欄或狀態；`self_approve`／`selfApprove`／`自確`／`auto_approve` 全庫零命中（命中的 `auto_confirm` 全屬 Q063「completed 逾期自動結案」）| 走查步驟 4 + 回查證重掃 |
| **B4** | **「501–2000 自動建 quote v+1」不存在** —— `record_scope_change` 全函式（`:2924-3075`）零 quote 表操作；唯一建 v+1 的路徑是 requote command（`requote_service.py:84-104`），其入參（`:39-43`）**根本沒有金額欄位**，對任何金額都建 v+1 | — |
| **B5** | **「>2000 強制主管覆核」的強制點不在 scope change** —— 真正的 403 落在**報價送出**：`api/services/quote_engine_service.py:531-546` 的 `REQUOTE_SUPERVISOR_REQUIRED`，觸發條件是 `quote.supersedes_quote_id` 非空且 `abs(v+1.total − prev.total) > 2000`（`_REQUOTE_TIER_EDITOR_MAX = 2000.0` `:453`、`_REQUOTE_SUPERVISOR_ROLES = ("operations_manager","admin")` `:454`）—— **與現場加價金額、與發起時點都不是同一件事** | `scope_change_service` 的 `admin_override` 用 `_DISPATCH_ALLOWED_ROLES`（`work_orders_v2.py:70-75`，含 dispatcher/customer_service），**比 `_REQUOTE_SUPERVISOR_ROLES` 寬，形同旁路** |
| **B6** | **「501–2000 小編核可」不可能行使** —— `:send` 端點的 RBAC 是 `OPS_ROLES`＝`(admin, operations_manager)`（`api/routers/quote_v2.py:217-221`、`api/core/deps.py:293-295`），`customer_service` 連送出都不行 | `quote_engine_service.py:450-453` 註解宣稱的分層與實際 RBAC 不符 |
| **B7** | **`pct` 優先於金額** —— `work_order_service.py:2910` 的 `if delta > standard_max or pct >= major_pct`，原價 600 加價 400（≤500）會被判 **major**，與規格「≤500 = minor」的直覺相悖 | 無測試覆蓋這個交叉案例 |
| **B8** | **`total_estimate` 為空時 tier 恆 `minor`** —— `new_price=None` → `delta=0`（`:2976-2977`），但仍照樣建 pending 卡 | — |
| **B9** | **`consent_method` 值域無 `paper`** —— 欄位只存在於 `appearance_change_consents`（`SQL/Schema.sql:930`，三值 `digital_signature`/`line_confirmation`/`verbal_recorded`）與 `api/openapi.yaml:5809`、`:5827`（`QuoteCustomerConfirm` 必填，enum `[liff_full, flex_simple_fallback]`）—— **全庫沒有任何地方能記錄「紙本同意」**。程式用的是 `fallback_method` 不是 `consent_method` | `work_order_consents`（`SQL/migrations/043-work-order-consents.sql:16-26`）無 method 欄 |
| **B10** | **evidence 對簽名無 FK** —— `digital_signatures`（`SQL/Schema_v2_extensions.sql:179-195`）無 media 欄，`media_files`（`SQL/Schema_media.sql:18-24`）無指向它的 FK；照片只透過 `work_order_id` 與工單間接關聯 | — |
| **B11** | **拒絕加價無分流** —— `decline` 只把 quote 打成 `rejected`（`quote_engine_service.py:36`），無「按原報價完工」或 `customer_disagreed_partial` 的表達方式 | accept 側只回寫 `estimated_price`（`:580-592`）＋ best-effort 開發票（`:596-616`），**不改工單 status、不解除任何 gate、不回寫 `requote_requests`** |

### 4.3 契約漂移（設計稿宣告、實作未落地）

`api/openapi.yaml` 是**設計期契約**，不是型別 SoT
（`scripts/ci/generate-api-types.sh:5-8`：「型別 SoT＝runtime export…設計稿 `api/openapi.yaml`
仍為設計期契約（spec-lint / mock-smoke / contract-check 對象），但**不是**型別來源」）。
以下三處是設計稿承諾但 runtime 不存在：

| 位置 | 宣告內容 | 實作狀態 |
|---|---|---|
| `api/openapi.yaml:273-287` | `## --- Onsite (scope change 三件套) ---`；`POST /work-orders/{id}/onsite/scope-change`（`operationId: onsiteScopeChange`），responses 明列 `'422': missing one of signature/photo/audit`、`'403': amount tier violation (per ADR-0049)` | `grep -rn "onsiteScopeChange" api --include="*.py"` **零命中**（已實測）；`api/openapi-runtime.json` 無此 path |
| `api/openapi.yaml:6027-6032` | `Onsite.state` enum `[arrived, working, scope_change, pending_quote_v2, completed, customer_not_onsite, customer_disagreed_partial]` | 七值中只有 `arrived` 以字面字串出現在回應（`api/routers/work_orders_v2.py:928` `"state": "arrived"`，**不寫入 DB**）；其餘六值全庫零實作 |
| `api/openapi.yaml:1521` | 到場端點 `'201'` 回應 `$ref: '#/components/schemas/Onsite'` | 實作回的是 `_publish_and_return` 的工單 dict + 硬寫 `"state": "arrived"` |
| `api/routers/work_orders_v2.py:862` | docstring：「到場後以 record_door_check 寫入結構化事件，**狀態機推至 in_progress**」 | 實作不推（見 A1）；且「以 `record_door_check` 寫入」也是 CR-0053 修掉的舊行為 —— **整段 docstring 過期** |

### 4.4 測試現況：六批全綠，對本組判定基準零守線

走查步驟 6 的實跑結果（本機 Docker 測試庫，**未碰 5433 UAT 庫**）：
到場／門檢 11 綠、分級／pending gate 7 綠、requote 相關 16 綠、分層核可 9 綠、
簽名 fallback 5 綠、異常框架／取消 38 綠。**但**：

| 測試 | 測了什麼 | 沒守到什麼 |
|---|---|---|
| `api/tests/test_cr_0053_arrival_doorcheck.py:50-62` | 409 前置閘、`actual_arrival` 非空 | **零 `status` 斷言** → A1 永遠不會被測出來 |
| `api/tests/test_cr_0038_bucket4.py:26/34/42/50` | `_classify_scope_tier` 回傳值 | 沒斷言分級**被消費** → B1/B2 永遠不會紅 |
| `api/tests/test_cr_0066_coverage_batch4.py:121-143` | `fallback_method="paper"` 落 JSONB | **直呼 service，測的是產品不可達路徑**（A7）—— 這已經是誤報等級 |
| `api/tests/test_cr_0041_exception_framework.py:77/174` | high 設 hold、resolve 解 hold | 兩檔都以**後台身分**開異常，無 technician 開立、無「medium 不設 hold」的守線（A9/A10）|
| `api/tests/test_cr_0144_requote_channel.py:86-102` | v+1 supersedes 串鏈 | **沒有第二次 requote 的案例** → A5 永遠不會紅 |

這是典型的「CI 綠＝OK 的謊言」：測試本身沒寫錯，**是覆蓋面沒對到需求**。

---

## 5. 程式碼現狀速查（給實作者的座標）

```
狀態機          api/services/work_order_service.py:915-923  _WO_TRANSITIONS（七值）
                                                   :925  _ACCEPT_FROM = {"assigned"}
                                                   :927  _COMPLETE_FROM = {"accepted","in_progress"}  ← 讓 in_progress 可跳過
                                                  :2836  _SUBFLOW_FROM = {"assigned","accepted","in_progress"}
到場            api/services/work_order_service.py:3237-3287  record_arrival（不改 status）
                                                 :3211-3234  compute_arrival_gps_proof（座標缺漏回 None）
                api/routers/work_orders_v2.py     :897-935   onsiteArrival（:862 docstring 過期）
門檢            api/services/work_order_service.py:3332-3345  無 arrival 事件 → 409
加價（舊路徑）  api/services/work_order_service.py:2890-2895  _SCOPE_TIER_DEFAULTS
                                                 :2898-2921  _classify_scope_tier（:2920 requires_supervisor）
                                                 :2924-3075  record_scope_change（:2996 字面 'pending'，零 quote 操作）
                api/routers/work_orders_v2.py     :773        recordScopeChangeV2（無前端呼叫者）
                api/services/scope_change_service.py:171-190  客戶決議 CAS + accept → in_progress
                                                     :336     admin_override → in_progress
加價（新路徑）  api/services/requote_service.py   :22-23      _ALLOWED_WO_STATUS = {"in_progress"}
                                                  :77-82      同工單已有 open → 409（無收斂者 ⇒ 一次性）
                                                  :84-113     建 v+1 + supersedes + INSERT 'quoted'
                api/services/quote_engine_service.py:29-42    _TRANSITIONS（accept: sent→accepted）
                                                    :450-454  _REQUOTE_TIER_EDITOR_MAX / _SUPERVISOR_ROLES
                                                    :531-546  REQUOTE_SUPERVISOR_REQUIRED 403
                                                    :580-616  accept 回寫 estimated_price + 開票（不改 WO status）
完工閘          api/services/work_order_service.py:1551-1576  照片張數 / 簽名 / 序號
                                                 :1585-1591  PENDING_SCOPE_CHANGE 409（只對舊路徑成立）
                                                 :1605-1618  QUOTE_NOT_CONFIRMED_FOR_CLOSE 422
                                                 :1765 → :2061-2075  high_risk_hold 422
簽名            api/services/signature_service.py :48/:60/:69-73/:134/:153  fallback_method（HTTP 不可達）
                api/models/generated.py           :492-497   SignaturePayload（缺欄位）
例外            api/services/exception_service.py :18-28     類型/嚴重度/return_path
                                                  :69        severity 預設 "medium"
                                                  :96-100    high/critical → high_risk_hold
                api/routers/exception_cases_v2.py :24-26     RBAC（不含 technician）
媒體            api/services/media_service.py     :31-41     _ALLOWED_PURPOSES（九值，無影音）
                                                  :54-60     _ALLOWED_CONTENT_TYPES（jpeg/png/webp/pdf）
```

---

## 6. 影響評估

### 6.1 「補洞」還是「本來就沒做完」？—— 三者都有，比例如下

| 分類 | 支數 | 判斷 |
|---|---|---|
| **真缺陷（必修）** | A1–A12，橫跨 7 支 TC | **一個根因（A1）撐起 A2/A3/A4 四項可觀測後果**。A5/A7/A8/A9/A10 是各自獨立的半成品。這些與規格之爭無關，無論 §8 怎麼裁都要修 |
| **規格已被裁決推翻／排到階段二** | TC-ONSITE-01 的 `on_site` 用詞、TC-ONSITE-07 的 `on_site → quoted` / `approved` 用詞、TC-ONSITE-03/07 的 `pending_quote_v2` / `customer_disagreed_partial` 子狀態 | 15_SDS.md:221 業主 0710 裁決 + WBS 4.1（M4 階段二）+ `27_Product_Roadmap_WBS.md:129`「階段二只做設計不動工」。**這幾條不該在階段一 UAT 判為缺口** |
| **規格自相矛盾，要先裁決才知道要不要做** | TC-ONSITE-02（≤500 師傅自確 vs ADR-027 零定價權）、TC-ONSITE-04 的三件套定義孤例 | 見 §2.3、§2.4 |

**結論：這條線不是「整段沒做」，是「做了兩套、只接了一套、而且兩套都缺一個必要前置狀態」。**

### 6.2 rewrite vs refactor 九維打分

| 維度 | 分 | 理由 |
|---|---|---|
| 產品目標是否改變？ | **0** | 到場存證、加價分層管控、例外分流三個目標從 `02_BRD.md:111`（P-5 痛點）起未動。UAT 只是發現實作沒跟上 |
| 核心 User Flow 是否改變？ | **2** | SC-07（現場加價）目前有兩套實作（`scope_changes` 提案 vs requote command），規格只描述一套。§8 D2 的裁決會決定技師與客戶實際走哪條——「≤500 師傅自確」與「一律走品牌定價引擎」是**完全不同的操作體驗**，屬主流程層級改變 |
| Domain Model 是否改變？ | **1** | 最小路徑：只補 `accepted → in_progress` 轉移（沿用既有合法邊 `:917`）＋ `requote_requests` 補 `closed` 收斂（值已在 CHECK 內）＝新增概念少。若 D2 選 (b)（規格為正典）則要引入 Onsite 子狀態機與 `scope_changes.self_approved`＝**2 分** |
| API Contract 是否大量破壞？ | **1** | 四處要動：`SignaturePayload` 加 optional 欄位、`openExceptionCase` RBAC 放寬、`onsiteScopeChange` 設計稿處置、`Onsite` schema 處置。全部是**新增或收斂，無既有 runtime endpoint 破壞**，但 `web/shared-contract` 型別要重生（`scripts/ci/generate-api-types.sh`）→ 屬「多 endpoint 變動」 |
| DB Schema 是否需重建？ | **1** | 最小路徑不用（`fallback_method` 走 `signature_data` JSONB、狀態轉移不改 schema、`closed` 已在 CHECK 內）。D6 若選 M18 config 需比照 CR-0197 migration 127 註冊 namespace；D2 選 (b) 需加 `scope_changes` 欄位、D8 選 (b) 需改 `media_files.purpose` CHECK。**migration 可處理，不痛** |
| 模組邊界是否錯誤？ | **2** | 同一業務動作（現場加價）有**兩套 service**（`work_order_service.record_scope_change` + `scope_change_service` vs `requote_service` + `quote_engine_service`）、**兩張表**（`scope_changes` vs `requote_requests`+`quote`）、**兩道完工閘**（`PENDING_SCOPE_CHANGE` vs `QUOTE_NOT_CONFIRMED_FOR_CLOSE`），而且**互不知情**——走 requote 路徑時 CR-0049 的閘不成立。ADR-027 引入新邊界時沒有下架舊邊界，這是切割的實質錯誤，不只是混亂 |
| 測試是否可信？ | **2** | 六批 86 個測試全綠，**對本組 7 支 TC 的判定基準零守線**（詳 §4.4）。`test_cr_0066_coverage_batch4.py:121-143` 更是直呼 service 測產品上不可達的路徑——那已經超過「覆蓋不足」，是**誤報** |
| 文件是否可信？ | **2** | `21_Traceability_Matrix.md:63/64/66` 三個假 ✅；`20_Test_Cases.md:304` 三件套孤例；`work_orders_v2.py:862` docstring 過期；`api/openapi.yaml:273-287`/`:6032` 宣告未實作；`15_SDS.md:221` 有裁決標注但 §4.2 pack 子狀態機（`:242-248`）**沒有對應標注**，同一份文件兩段的效力不明 |
| 團隊/AI 是否還理解系統？ | **1** | 走查＋回查證能把每條路徑追到 `file:line`，程式碼註解品質高（`requote_service.py:22` 自陳語彙差異、`scope_change_service.py:186-192` 解釋為何條件式寫事件）。但「技師端 scope-change 頁其實 POST 到 `/requote-requests`」與「`_classify_scope_tier` 是死碼」都要開檔才知道，直到這輪走查才被發現 |
| **總分** | **12 / 18** | |

### 6.3 行動建議

**12 分 → 落在「7–12 分：架構重審 + 模組拆分（多 CR + 跨 sprint）」，且是這個區間的上緣，離 13 分（考慮新主幹）只差 1 分。**

但**不建議**開新主幹，理由：拉高分數的三項（模組邊界 2 / 測試 2 / 文件 2）都是**ADR-027 遷移沒收尾的後遺症，不是原始設計錯誤**。
`02_BRD.md:111` 的產品目標（0 分）與 domain model（1 分）都健康。這是「換軌換到一半停在中間」，
不是「地圖描述的世界已經不存在」。

**具體建議：拆成三張卡，不要當一張補洞單處理。**

| 卡 | 範圍 | 為什麼要拆 |
|---|---|---|
| **本 CR（CR-0205）** | A1–A12 的真缺陷 + 全部文件／契約標注 | 與規格之爭無關，裁決成本低，可立刻開工 |
| **另開一張（加價路徑收斂）** | §8 D2 的裁決落地：廢止或實作 | 跨 sprint、動 domain model、要新 ADR（supersede 或補強 ADR-027）。混進本 CR 會讓 A1 這種一行修的東西被綁在架構討論後面 |
| **階段二 backlog（不是卡）** | Onsite 子狀態機（`arrived`/`working`/`pending_quote_v2`/`customer_disagreed_partial`）| 屬 M4 flow DSL（WBS 4.1），`27_Product_Roadmap_WBS.md:129` 明寫階段閘前不動工 |

### 6.4 誠實聲明：本 CR 認為**不該修**的項目

依「誠實優先於完整」，以下項目查證後認為不應列為工作項：

1. **TC-ONSITE-01 的「工單 `on_site`」** —— 業主 `15_SDS.md:221` 已裁決 `on_site≡in_progress`。
   **要修的是轉移不是命名**（A1）。應在 `20_Test_Cases.md:301` 加標注同步該裁決。
2. **TC-ONSITE-07 的「`on_site → quoted`」與「`approved` 續工」** —— 同一則裁決明寫
   「quoted→approved 修正輪發生在 **quote 層狀態機**（工單停留 `in_progress`）」。
   **這兩條判定基準已被業主裁決 supersede**，不該再算缺口。TC-ONSITE-07 真正剩下的只有
   A5（`closed` 無寫入者）與 B11（拒絕無分流）。
3. **TC-ONSITE-04 的「影音」類別** —— 三件套定義六處對一處（§2.4）。為了 `20_Test_Cases.md:304`
   的孤例去加影音 purpose、放寬 content-type、改 DB CHECK、改前端上傳，**代價與收益不成比例**。
   建議改文件不改 code（D8）。
4. **`pending_quote_v2` / `customer_disagreed_partial` 子狀態** —— 屬 M4 flow DSL 值域
   （WBS 4.1，階段二）。應在 `api/openapi.yaml` 標注為 to-be，不在階段一實作。
5. **B10「evidence FK 指向簽名」** —— `20_Test_Cases.md:305` 的「evidence FK」字面上要
   `media_files → digital_signatures` 的外鍵。但簽名與照片透過 `work_order_id` 已可關聯，
   加 FK 的稽核價值有限而 schema 成本實在。建議降級為「在 `signature_data` 記 `evidence_ids`」，
   或直接在正典標注此要求不採納。

---

## 7. 可行路徑（供 §8 參考）

### 7.1 A1（開工轉移）的三條路

| | 做法 | 代價 |
|---|---|---|
| (a) | `record_arrival` 內把 `accepted → in_progress`（沿用 `_WO_TRANSITIONS:917` 既有合法邊）| 最小；但「到場」與「開工」被綁成一個動作，與 SRS `:175` 的 `arrived --> working` 兩段語意不同 |
| (b) | 新增獨立「開工」動作（技師按「開始施工」）| 貼近規格；但階段一沒有 `arrived`/`working` 兩層狀態可對映，新端點＋新 UI＋新 CTA，成本三倍 |
| (c) | 不修狀態，改把 `requote_service._ALLOWED_WO_STATUS` 放寬到 `_SUBFLOW_FROM`，並修 `technician_service` 的 online 判定 | 治標；`in_progress` 永遠是死值、統計桶繼續恆 0、`_WO_TRANSITIONS:917` 那條邊永遠沒人走 |

### 7.2 D2（加價路徑）的三條路

若選「ADR-027 為正典」，需處置的資產清單：

- 廢止端點 `api/routers/work_orders_v2.py:771-798`（`recordScopeChangeV2`）
- 廢止 `_classify_scope_tier`（`work_order_service.py:2898-2921`）與 `_SCOPE_TIER_DEFAULTS`（`:2890-2895`）
- 處置 M18 config namespace `scope_change_policy`（`SQL/migrations/053`）
- **保留** `PENDING_SCOPE_CHANGE` 閘（`:1585-1591`）—— 存量 `scope_changes` 列仍需能被解除
- `smartlock-docs` 五處加標注（**不改寫**）：`02_BRD.md:286`、`04_SRS.md:189`、
  `15_SDS.md:244`、`03_PRD.md:158`、`08_User_Flow.md:307`
- `api/openapi.yaml:273-287` 的 `onsiteScopeChange` 一併處置

若選「規格為正典」，需新開 ADR supersede ADR-027，並實作 §4.2 B3/B4/B5 三段——
**這一條會把 `02_BRD.md:111` 標為 P-5 痛點的「師傅說了算」風險放回來**。

---

## 8. 🛑 Human Decisions Required

> 業主只需回「D1 選 a」這樣的形式即可。
> **優先序：D1 > D2 > D3 = D4 = D5 = D6 > D7 = D8。**
> D1 不依賴任何其他決策，且是 A2/A3/A4 的共同前置——**建議先回 D1，實作可立刻開工，不必等 D2 的長討論。**

---

### D1：`in_progress`（＝規格的 `on_site`／「施工中」）要怎麼進入？

現況：正常工單 `assigned → accepted → completed`，`in_progress` 永遠不會發生
（`_COMPLETE_FROM = {"accepted","in_progress"}`，`work_order_service.py:927`）。
到場（`record_arrival`，`:3237-3287`）不改 status。

- **(a)** 在 `record_arrival` 內把 `accepted → in_progress`，沿用 `_WO_TRANSITIONS:917` 既有合法邊
  （`assigned` 狀態下到場則維持不動，另議）
  - 代價：「到場」與「開工」綁成一個動作，與 `04_SRS.md:175` 的 `arrived --> working` 兩段語意不同
- **(b)** 新增獨立「開工」動作（技師按「開始施工」），到場與開工分離
  - 代價：階段一無 `arrived`/`working` 兩層可對映，需新端點 + 新 UI CTA + 新測試，約 (a) 的三倍工
- **(c)** 不動狀態機，改放寬 `requote_service._ALLOWED_WO_STATUS`（`:23`）到 `_SUBFLOW_FROM`，
  並修 `technician_service.py:512-518` 的 online 判定
  - 代價：`in_progress` 永遠是死值、`:590-604` 統計桶恆 0、`_WO_TRANSITIONS:917` 那條邊永遠沒人走

**我的建議：(a)。** 理由：`15_SDS.md:221` 業主已裁決 `on_site≡in_progress`，
「到場即施工中」是對這則裁決最直接的落地；(b) 更貼近 SRS 但階段一沒有可對映的兩層狀態，
等於為了一個階段二才會用到的粒度先付三倍成本；(c) 把可觀測的資料錯誤（A2/A3）留在原地。

---

### D2：現場加價要收斂成一條路徑，還是兩條並存？

現況：`scope_changes` 提案路徑（端點無前端呼叫者、分級是死碼）與 requote command 路徑
（技師端實際走的）並存，且 CR-0049 的 `PENDING_SCOPE_CHANGE` 閘對 requote 路徑不成立。
`02_BRD.md:286`「≤500 師傅自確」與 ADR-027「技師零定價權」直接衝突（§2.3）。

- **(a)** 認定 **ADR-027 為正典**：requote 為唯一路徑，廢止 `scope-change` 端點與 `_classify_scope_tier`，
  在 BRD/SRS/SDS/PRD/User_Flow 五處加標注（不改寫）說明「≤500 師傅自確」經 ADR-027 廢止
  - 代價：`02_BRD.md:286`、`04_SRS.md:189`、`15_SDS.md:244`、`03_PRD.md:158`（FR-D02）、
    `08_User_Flow.md:307` 五處要標注；`_classify_scope_tier` 與 migration 053 的 config namespace 要下架；
    存量 `scope_changes` 列的解除路徑要保留
- **(b)** 認定 **規格為正典**：實作「≤500 師傅自確」「501–2000 自動建 v+1」「>2000 主管覆核」，
  新開 ADR supersede ADR-027
  - 代價：把 `02_BRD.md:111` 自己標為 **P-5 痛點**的「現場加價師傅說了算，客訴與呆帳高」放回來；
    要加 `scope_changes.self_approved` 狀態與欄位（migration）、三件套齊備的聚合判定、
    tier 分支的 LINE 推播；跨 sprint
- **(c)** 兩條並存但明確分工（例如 `scope-change` 只記非金額的範圍異動，requote 專責金額）
  - 代價：維持兩套完工閘的認知負擔，且要補一道「兩閘語意一致」的守線測試；
    下一個讀 code 的人（含 AI）仍會搞錯走哪條

**我的建議：(a)。** 理由：ADR-027 是 2026-07-07 業主裁決且狀態 Accepted
（`14_ADR/00_INDEX.md:92`），前端已於 07-10 依它改造完畢（`scope-change/page.tsx:1-5` 自陳）。
「技師零定價權」是**刻意的風險控制**，而 BRD 在同一份文件裡既把「師傅說了算」列為痛點（`:111`）
又寫「≤500 師傅自確」（`:286`），這個矛盾應該由較晚且較具體的 ADR 收斂。
選 (b) 等於把已裁決的風控拿掉，需要業主明確承擔。

---

### D3：`requote_requests` 一單只能改一次報價，要解嗎？

現況：`status` CHECK 含 `closed`（migration 097:21-22）但**全庫零 UPDATE**；
`requote_service.py:77-82` 對同工單已有 `received`/`quoted` 一律 409 →
**一張工單第二次發起現場報價修正永遠失敗**。

- **(a)** 在 quote `accept`/`decline` 時回寫 `requote_requests.status='closed'`（最小修）
  - 代價：`quote_engine_service.transition` 要新增一段跨表回寫，需比照 `:580-592` 的
    fail-soft + tenant 雙重限定寫法；補一支「第二次 requote 應成功」的測試
- **(b)** 放寬 409 條件為「同 `reason` 才擋」
  - 代價：治標；`closed` 仍無寫入者，資料層永遠看不出修正輪何時收斂
- **(c)** 維持現狀（認定「一單只能改一次報價」是刻意的業務規則）
  - 代價：需在正典明文寫下這條規則；且要解釋為何 CHECK 裡有一個永不使用的 `closed`

**我的建議：(a)。** 理由：migration 097 的 CHECK 已含 `closed` 表示原設計就打算收斂，
沒有任何程式碼寫它是**漏做不是刻意**。這是本組唯一「單一函式內、無契約影響」接近 CIA 豁免的項目，
但因為它改變「同工單可否再次 requote」這條業務規則，仍當 User/Business flow 面向處理。

---

### D4：QR／紙本簽名 fallback 要不要接到 API 面？

現況：`signature_service` 支援 `paper`（`:48`/`:60`/`:69-73`），但兩個端點都不透傳、
`SignaturePayload` 無此欄位 → 經 API 進來的簽名**恆為 `liff`**；且簽名成功不寫 `audit_events`。
唯一的「證據」是 `test_cr_0066_coverage_batch4.py:121-143` 直呼 service ——**測到的是不可達路徑**。

- **(a)** 全接：`SignaturePayload` 加欄位 → 重生 `generated.py` → 兩端點透傳 →
  `signature_service` 補 `audit_log_service.log_event` → tech-portal 加
  「LIFF 失敗 → 出示 QR → 紙本簽 + 拍照」三段 UI
  - 代價：跨 API + 前端，含 QR 產生與紙本分支的強制拍照，約 2–3 天
- **(b)** 只補後端（欄位 + 透傳 + audit 留痕），UI 留待技師端下一輪
  - 代價：能力仍無使用者入口，但至少契約與稽核鏈完整、測試改走 HTTP 就不再測不可達路徑
- **(c)** 不接：把 `_VALID_FALLBACK_METHODS`（`:48`）收斂成只有 `liff`，
  並在 `04_SRS.md:191` / `02_BRD.md:291`（BR-ONSITE-04）旁標注「fallback 鏈階段一不做」
  - 代價：LIFF 授權失敗時現場沒有退路，客戶簽不了名＝完工硬閘（`:1561-1563` `SIGNATURE_REQUIRED`）過不了

**我的建議：(b) 先做，(a) 排入技師端下一輪。** 理由：現狀最糟——service 有能力、契約無入口、
測試測不可達路徑，是「看起來有做」的假象。(b) 是可獨立驗證的低風險段，且能立刻把那支誤報測試改對。
(c) 不建議：`04_SRS.md:191` 的 fallback 是為了處理現場真實故障，砍掉等於接受「LIFF 掛了就無法結案」。

---

### D5：技師能不能自己開「客戶未到場」異常？

現況：`openExceptionCase` RBAC 不含 technician（`exception_cases_v2.py:24-26`），
技師端無此 CTA；最接近的是延誤頁的理由選項「客戶尚未到場」（`delay/page.tsx:39`），
送到 `notify_delay` 後只落一筆 `delay` 事件。`20_Test_Cases.md:306` 的步驟明寫「**師傅**回報客戶未到場」。

- **(a)** 放寬 `openExceptionCase` 的 RBAC 含 technician，service 層再限「只能對自己 assignee 的工單、
  只能開 `no_show`/`customer_absent`/`delay_severe`」
  - 代價：先開門再補鎖——RBAC 層一旦放行，任何遺漏的 service 層檢查都是越權；
    且 `exception_cases_v2.py` 的其他端點（resolve 等）共用 `_resolve_roles`，要小心不要一起放寬
- **(b)** 另開技師專用端點 `POST /tenants/{t}/work-orders/{id}/report-absent`，
  內部呼叫 `exception_service.open_exception` 並帶 assignee 驗證
  - 代價：多一支端點與 openapi 條目，約多半天工
- **(c)** 維持現狀（技師打電話給客服，客服代開）
  - 代價：與 `20_Test_Cases.md:306` 的步驟不符，需在正典標注；現場即時性差

**我的建議：(b)。** 理由：(a) 會讓技師拿到「開任意型別、任意工單異常」的能力，
service 層收窄是防禦縱深不是授權邊界；(b) 的端點語意窄、RBAC 清楚、audit 能辨識來源，
而且順便可以把 `reschedule?from=no_show` 那個孤兒 UI 分支（A11）接上來源。

---

### D6：`customer_absent` 的嚴重度預設要不要提高？

現況：`open_exception` 的 `severity` 預設 `"medium"`（`exception_service.py:69`、
`exception_cases_v2.py:37`），而只有 `high`/`critical` 才設 `high_risk_hold`（`:96-100`）→
**以預設值開 `customer_absent`，完工照樣過**，`20_Test_Cases.md:306`「不得直接結案」形同虛設。

- **(a)** 技師開立 `customer_absent`/`no_show` 時在 code 中強制 `high`
  - 代價：政策寫死，日後調整要改 code + 重佈
- **(b)** 由 M18 config 決定 `exception_type → severity` 對映（比照 CR-0197 的 `dispatch_policy` 前例）
  - 代價：需新 migration 註冊 config namespace ——
    **注意 CR-0197 §8 的教訓：`config_version.namespace` 有 FK 指向 `config_namespace(code)`，
    namespace 沒註冊開關就永遠開不了**；且 config 讀取失敗時的 fallback 要明確定義
- **(c)** 維持 `medium`（「不得直接結案」改由別的機制達成，例如在完工閘直接查 open exception）
  - 代價：`_HIGH_RISK` 這條路徑對現場最常見的異常型別永遠不成立；
    但完工閘改查 open exception 反而更直接（`auto_confirm_stale_completed`，`:4269`，已經是這麼做的）

**我的建議：(b)。** 理由：型別→嚴重度屬營運可調政策，本專案已有 M18 config 的成熟前例
（CR-0197 migration 127）。若業主要更快落地可先選 (a)，但要在 code 註解寫明「暫時寫死，
待 M18 namespace 註冊後遷移」，避免下一輪又被當成刻意設計。

---

### D7：`api/openapi.yaml` 裡宣告未實作的 Onsite 設計稿怎麼處置？

現況：`:273-287` 的 `onsiteScopeChange`（含 `'422': missing one of signature/photo/audit`、
`'403': amount tier violation`）與 `:6027-6032` 的 `Onsite.state` 七值 enum
（`arrived`/`working`/`scope_change`/`pending_quote_v2`/`completed`/`customer_not_onsite`/
`customer_disagreed_partial`）在 runtime 皆不存在。
`api/openapi.yaml` 是**設計期契約**、spec-lint / mock-smoke / contract-check 的對象
（`scripts/ci/generate-api-types.sh:5-8`），不是型別 SoT。

- **(a)** 保留設計意圖，加階段標記（如 `x-stage: phase-2` 或 description 前綴「⚠️ 設計稿，階段一未實作」），
  讓 contract-check / mock-smoke 與讀 code 的人（含 AI）知道它不是 as-built
  - 代價：要確認 spec-lint 是否接受該擴充欄位
- **(b)** 直接刪除 `onsiteScopeChange`（`:274-287`）與 `Onsite.state` 的六個未實作值（`:6032`）
  - 代價：丟失 M4 的設計素材；`:1521` 的到場端點回應 `$ref` 要一併改
- **(c)** 依 D2 結果實作
  - 代價：等同 D2 選 (b)

**我的建議：(a)。** 理由：這些是 M4 flow DSL 的設計素材（WBS 4.1），有保留價值；
但**必須讓它看得出來不是 as-built**，否則下一輪走查會再判一次「契約漂移」。
同時 `api/routers/work_orders_v2.py:862` 的過期 docstring 應一併修（依 D1 結果決定寫什麼）。

---

### D8：`20_Test_Cases.md:304` 的「三件套 = 影音 + 文字 + before/after 照」孤例怎麼處理？

現況：六處正典（`02_BRD.md:111`/`:286`、`04_SRS.md:180`/`:464`、`15_SDS.md:244`、
`08_User_Flow.md:307`、`api/openapi.yaml:278`）一致寫「簽名 + 照片 + audit」，
只有 `20_Test_Cases.md:304` 寫「影音 + 文字 + before/after 照」。

- **(a)** 以多數定義為準（簽名 + 照片 + audit），在 `20_Test_Cases.md:304` 加標注更正
  - 代價：無；只是文件標注
- **(b)** 以 TC 定義為準 → 加影音 purpose（`media_service.py:31-41`）、放寬
  `_ALLOWED_CONTENT_TYPES`（`:54-60`）、改 `SQL/Schema_media.sql:24-35` 的 purpose CHECK、
  改前端上傳、處理影音儲存與頻寬成本
  - 代價：DB schema + API contract + 前端 + 儲存成本，且與 CR-0194 剛收窄 content-type 的方向相反
- **(c)** 兩者都要（三件套維持簽名+照片+audit，另加 before/after 成對檢核）
  - 代價：完工閘（`work_order_service.py:1551-1559`）目前只數張數，要改成分類計數；中等

**我的建議：(a)。** 理由：六處對一處，且 `api/openapi.yaml:278` 的 summary 也寫
`signature + photo + audit`。為孤例去動 DB schema 與媒體儲存，代價與收益不成比例。
若業主認為 before/after 成對確實有稽核價值，可單獨選 (c) 但要另開卡（那是完工閘的改動，不是三件套定義）。

---

## 9. Suggested Implementation Order

> **可平行 ‖ / 必須序列 →**
> A 類真缺陷（S1–S4）與 B 類裁決（S5）刻意分開，避免一行修的東西被綁在架構討論後面。

### S0 — 文件標注（**不等裁決，可立即做**）

只寫標注、不改寫原文（`smartlock-docs/` 為業主規格正典）。

1. `21_Traceability_Matrix.md:63/64/66` —— FR-0006 / FR-0008 / FR-0010 三個 ✅ 旁加標注，
   註明 2026-08-03 走查實測為部分實作 + 指向本 CR
2. `20_Test_Cases.md:301` / `:307` —— 加標注同步 `15_SDS.md:221` 的業主 0710 裁決
   （`on_site≡in_progress`、`quoted→approved` 在 quote 層）
3. `15_SDS.md:242-248`（§4.2 Onsite 三段式）—— 加標注說明其階段歸屬
   （§4.1 已有 0710 標注，§4.2 沒有 → 效力不明，見 §6.2 文件維度）

**驗證**：人工複審標注未改動原文語句；`git diff` 只有新增行。

---

### S1 — D1：開工轉移（**所有後續的前置，必須最先**）

1. 依 D1 裁決實作狀態轉移
2. 同步修 `api/routers/work_orders_v2.py:862` 的過期 docstring（依 D7 一併處理）
3. 補測試：`api/tests/test_cr_0053_arrival_doorcheck.py` 加「到場後 `status == 'in_progress'`」斷言
4. 回歸：確認 `test_cr_0128` 狀態機對帳測試不被破壞
5. 檢查 `api/services/technician_service.py:512-518` 的 online 判定在轉移修好後是否仍符合業務語意
   （修好後「在現場的師傅」會被正確排除，這是**行為改變**，要確認營運端預期）

**驗證**：`cd api && pytest tests/test_cr_0053_arrival_doorcheck.py tests/test_work_orders_onsite_v2_endpoint.py`；
再對 scratch 庫跑全套比對基線（**不得對 5433 UAT 庫跑**）。

---

### S2 ‖ S3 ‖ S4 — 可平行開發（**驗收需序列於 S1**）

#### S2 — D3：requote 收斂
- `quote_engine_service.transition` 的 `accept`/`decline` 分支回寫 `requote_requests.status='closed'`，
  比照 `:580-592` 的 fail-soft + tenant 雙重限定寫法
- 補測試：第二次 requote 應成功（`test_cr_0144_requote_channel.py` 現無此案例）
- ⚠️ **端到端驗收必須等 S1** —— requote 需要 `in_progress` 可達（A4）

#### S3 — D4：簽名 fallback + audit
- `api/openapi.yaml` 的 `SignaturePayload` 加 `fallback_method`（enum `[liff, qr, paper]`，default `liff`）
- 重生 `api/models/generated.py` 與 `web/shared-contract`（`scripts/ci/generate-api-types.sh`）
- `api/routers/work_orders_v2.py:753-761` 與 `api/routers/work_orders.py:344-352` 透傳
- `signature_service` 寫入後補 `audit_log_service.log_event`（帶 `fallback_method` + 文件 id）
- **改寫 `api/tests/test_cr_0066_coverage_batch4.py:121-143` 改走 HTTP** —— 現在測的是不可達路徑
- 若 D4 選 (a)，tech-portal 三段 fallback UI 另排

#### S4 — D5 + D6：技師開異常 + severity 政策
- 依 D5 實作端點（含 assignee 驗證、型別白名單）
- 依 D6 實作 severity 政策；**若選 M18 config，先確認 `config_namespace(code)` 已註冊**
  （CR-0197 migration 127 的教訓：namespace 沒註冊，開關永遠開不了）
- tech-portal 加第七個 subflow CTA，送出後導到 `reschedule?from=no_show`
  （接上 `reschedule/page.tsx:319-328` 的孤兒分支，A11）
- 補測試：technician 身分開立、`medium` 不設 hold 的守線
  （`test_cr_0041_exception_framework.py` 現在兩檔都以後台身分測）

**S2/S3/S4 驗證**：各自 pytest 綠 + 對 scratch 庫全套比對基線零新增失敗；
新 migration 記得登記 REGISTRY 否則 drift check 會紅。

---

### S5 — D2：加價路徑收斂（**必須序列於 S1；建議另開 CR**）

依 D2 裁決執行 §7.2 的資產處置清單。這一步跨 sprint、動 domain model、
可能要新開 ADR（supersede 或補強 ADR-027），不應與 S1–S4 混在同一次實作。

**驗證**：若選 (a)，`openapi-runtime.json` 應不再有 `recordScopeChangeV2`；
存量 `scope_changes` pending 列仍能經客戶決議或 admin override 解除
（`test_cr_0049_pending_scope_gate.py` 必須維持綠）。

---

### S6 — D7 + D8：契約與規格文件處置（**可與任何步平行**）

- `api/openapi.yaml:273-287` / `:6027-6032` / `:1521` 依 D7 標注或刪除
- `20_Test_Cases.md:304` 依 D8 加標注
- **驗證**：`scripts/ci/contract-schemathesis.sh` 與 mock-smoke 不因標注而紅

---

### S7 — 收尾（**必須最後**）

1. 本 CR §8 加「### 進度」區塊，每步完成補一行 `✅ Sx done（merge <sha>）：<關鍵成果>`
2. `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
3. `27_Product_Roadmap_WBS.md` 對應項狀態欄（2.4.3 的 ✅ 需依 S5 結果重新檢視——
   「舊路徑下架」本來就在該卡的隱含範圍內）
4. 有架構決策 → 新開 ADR（append-only）

---

## 附錄：本 CR 的查證方式與界線

- **全部技術結論都逐一開檔覆核**，不採信走查文件的引用（該輪查證共修正 36 處引用錯誤）。
  本 CR 另獨立複驗的項目：`record_arrival` 全文、`_WO_TRANSITIONS`/`_COMPLETE_FROM`/`_SUBFLOW_FROM`、
  全庫 `UPDATE work_orders SET status='in_progress'` 寫入點、全庫 `UPDATE requote_requests`（零命中）、
  `requires_supervisor` 消費者、`onsiteScopeChange` 於 `api/**/*.py`（零命中）、
  `api/openapi-runtime.json` 的 onsite/scope-change path 清單、`technician_service` online 計數 SQL、
  `_assert_transition_applied` 全部 15 個呼叫點、`signature_service` 全檔 audit 命中（零）、
  `media_service` 的 purpose 與 content-type 行號。
- **未啟動任何服務、未連外網、未跑 docker/gcloud**；**未對 5433 UAT 庫跑任何 pytest**。
  §4.4 引用的實跑數字取自走查文件（本機 Docker 測試庫），非本輪重跑。
- **`smartlock-docs/` 全程唯讀**。§2 指出的三處正典衝突以標注方式處置，見 §9 S0。
- **本階段只讀不寫 code**，依 `.claude/rules/change-governance.md` 停在 §8 等業主裁決。
