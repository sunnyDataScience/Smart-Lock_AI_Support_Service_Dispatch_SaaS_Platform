---
id: CR-0202
title: 報價引擎狀態機、有效期與冪等契約——機讀 SSOT 與實作分岔六年後的一次收斂
status: draft
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, API contract, Domain model, DB schema, External integration, Test plan, Architecture boundary]
related: [TC-QUOTE-01, TC-QUOTE-02, TC-QUOTE-03, TC-QUOTE-04, TC-QUOTE-05, TC-QUOTE-08, FR-API-02, FR-API-03, FR-API-17, FR-WEB-06, BR-Quote-002, BR-Quote-003, BR-AI-004, CR-0032, CR-0095, CR-0128, CR-0144, CR-0150, CR-0152, CR-0178, CR-0181, ADR-025, ADR-027]
---

# CR-0202 — 報價引擎狀態機、有效期與冪等契約

## 1. 一句話

報價引擎的**程式碼是對的、文件是錯的**——`api/openapi.yaml` 這份被 CI（prism mock ＋
schemathesis）當契約消費的機讀 SSOT，至今仍寫著一套從未實作過的狀態名
（`internal_approved` / `customer_sent` / `customer_confirmed`）與四支不存在的端點；
六支 TC 有四支的「缺口」其實是**照著這份錯文件出題**產生的，真正該修的只有三件事：
客服建 v2 沒串版本鏈（連帶靜默繞過金額管制）、客戶確認端點無冪等、報價狀態機零稽核。

---

## 2. 需求追溯

### 2.1 六支 TC 的正典出處

| TC | 判定基準（`smartlock-docs/enterprise/20_Test_Cases.md`）| 對應需求 | 正典條文出處 |
|---|---|---|---|
| TC-QUOTE-01 | 狀態 `draft → internal_approved → customer_sent → customer_confirmed`；quote 掛 `quote_line_items` | FR-API-02 / FR-API-03 / FR-WEB-06 | `20_Test_Cases.md:277`；FSM 定義在 `04_SRS.md:126-134`、`15_SDS.md:236`、`03_PRD.md:144` |
| TC-QUOTE-02 | 403 `AI_FORBIDDEN_FINAL_QUOTE`；AI 僅可告知「客服已備好報價」並附**範圍價** | FR-API-02 | `20_Test_Cases.md:278`；範圍價來源 `06_UX_Research_Report.md:188`、`04_SRS.md:76`（`Quote.range_only`）、`04_SRS.md:142` |
| TC-QUOTE-03 | 403 `AI_FORBIDDEN_WARRANTY_PROJECT`；**必由客服手動 approve send** | FR-API-02 / FR-API-17 | `20_Test_Cases.md:279`；`04_SRS.md:142`、`04_SRS.md:450`（BR-Quote-003）、`04_SRS.md:308`（FR-API-17）|
| TC-QUOTE-04 | 版本鏈 `supersedes_quote_id` 完整 v1→v2；舊版按鈕導向最新版 | FR-API-02 / FR-API-03 / FR-WEB-06 | `20_Test_Cases.md:280`；`04_SRS.md:143`、`15_SDS.md:236`、`03_PRD.md:144` |
| TC-QUOTE-05 | quote `expired` + audit `expired_by_cron`；舊連結 → 410 | FR-API-02 / FR-API-03 / FR-WEB-06 | `20_Test_Cases.md:281`，**但同檔 :287 已有業主裁決標注推翻**（見 §2.3）|
| TC-QUOTE-08 | 200 冪等回放；不重觸發工單建立、audit 不重複 | FR-API-02 / FR-WEB-06 | `20_Test_Cases.md:284`；`04_SRS.md:293`（FR-API-02 條文明列 `Idempotency-Key`）|

### 2.2 正典之間的三處矛盾（本身就是待裁決的事）

**矛盾 A — 狀態機詞彙：三份正典 + 機讀 SSOT 全用實作從未採用過的名字。**

| 出處 | 寫的狀態名 |
|---|---|
| `smartlock-docs/enterprise/04_SRS.md:126-134`（mermaid 圖）| `internal_approved` / `customer_sent` / `customer_confirmed` |
| `smartlock-docs/enterprise/15_SDS.md:236` | 同上，**無任何標注** |
| `smartlock-docs/enterprise/03_PRD.md:144`（FR-C01）| 同上，且寫 `expired（48h）` |
| `api/openapi.yaml:5707-5714`（`Quote.state` enum）| 同上，**無任何標注** |
| **實作** `api/services/quote_engine_service.py:29-41` | `draft / pending_approval / approved / sent / accepted / rejected / expired / retrospective_audit_only` |
| **DB 註解** `SQL/migrations/041-quote-engine.sql:20-21` | 同實作 |
| **前端** `web/brand-portal/src/app/quotes/[token]/page.tsx:29-35` | 同實作 |

`CLAUDE.md` 明定「OpenAPI 機讀 SSOT ＝ `api/openapi.yaml`」。這不是「文件過期」層級的問題——
`.github/workflows/spec-lint.yml:4-12` 與 `mock-smoke.yml` 以 paths 盯著它，
`scripts/ci/contract-schemathesis.sh:21` 直接把它當 fuzz 依據。**一份會被機器執行的錯契約。**

**矛盾 B — AI 能不能給範圍價。**

- `smartlock-docs/enterprise/06_UX_Research_Report.md:188`：「AI ⋯**不給 final 價（只給 range）**」
- `smartlock-docs/enterprise/04_SRS.md:76`：`Quote` entity 明列欄位 `range_only`（AI 不可 final）
- `smartlock-docs/enterprise/04_SRS.md:142`：`customer_sent` precondition ＝「`range_only = true`（AI 路徑）OR human approval」
- **對立面** `smartlock-docs/enterprise/04_SRS.md:452`（BR-AI-004）：「AI **不複誦個案 quote 金額**；僅 announce existence ⋯ AI 訊息由 server template 限定，**無自由文 NTD 數字**」
- **現行實作** `agent/lockcore/skills/locksmith-cs-sop/SKILL.md:34`：「金錢相關 ⋯ 呼叫 `transfer_to_human`，**不報價、不追問**」；同檔 `:64`、`references/handoff-and-dispatch.md:66`「**不承諾具體費用**（一律轉真人報價）」

`range_only` 這個欄位名在**整個 repo 零命中**（`.py` / `.sql` / `.ts` / `.tsx` / `.yaml` 全掃）。
也就是說 SRS 為 AI 範圍價設計的 domain 欄位從未落地，而 skill 走的是更保守的相反方向。

**矛盾 C — 「客服」能不能送報價。**

- `20_Test_Cases.md:279` / `04_SRS.md:142`：「必由**客服**手動 approve send」
- `api/services/quote_engine_service.py:456`：`_HUMAN_STAFF_SEND_ROLES = ("customer_service", "operations_manager", "admin")`
- **對立面** `smartlock-docs/enterprise/13_Security_Architecture.md:99`：`customer_service` 職掌＝
  「對話接管 / 問題卡 / 進線 case / 客戶管理 / 發起退款保固爭議（**無核准權**）」；
  `:106`「`operations_manager`（營運日常：派工 **+ 帳務報價**）」
- **實作 RBAC** `api/routers/quote_v2.py:219`：`:send` 守衛 ＝ `role_required(*OPS_ROLES)`，
  而 `api/core/deps.py:293-295` 定義 `OPS_ROLES = ("admin", "operations_manager")`——**不含 `customer_service`**
- `smartlock-docs/enterprise/16_API_Spec.yaml:570-572` 已有標注承認此事：
  「現行 :send RBAC=admin/ops_manager 比分層更嚴，**小編層待 RBAC 擴權另案**」

結論：`quote_engine_service.py:456` 白名單裡的 `"customer_service"` 是**死條目**——
任何角色打得到 service 層，就必然已通過 `OPS_ROLES`，而 `OPS_ROLES ⊂ _HUMAN_STAFF_SEND_ROLES`。

### 2.3 TC-QUOTE-05：業主已裁決過，走查踩到明文警告

`smartlock-docs/enterprise/20_Test_Cases.md:287`（2026-07-25，CR-0181 業主裁決）：

> 〔標注 2026-07-25（CR-0181 業主裁決「都改七天、expire 保留」）：**TC-QUOTE-05 出題請改用新規格**——
> ①「超過 48h」改為「超過報價有效期 **7 天**（一般/急件同）」②as-built 過期機制是客戶操作時的
> **lazy 檢查**（accept 當下判 `expiry_at` 逾期 → 改 expired + 409/410），**無 cron tick、
> 無 `expired_by_cron` audit**——驗證方式＝把 fixture `expiry_at` 撥到過去後客戶操作，勿等排程；
> ③expired 單保留不清除。**用 48h 舊條件測會產生假 finding。**〕

`04_SRS.md:312` 有同一份裁決的對應標注。走查文件 `TC-QUOTE-05.md` 判「不一致」的四項理由
（無 cron、無 `expired_by_cron`、非 48h、lazy 過期）**逐條都是這段標注明文預告的假 finding**。
唯一沒被標注涵蓋的只剩「舊連結回 410」，而標注寫的是「409/410」併列。

---

## 3. 歷史成因（不是疏漏，是設計稿沒退場）

`api/openapi.yaml` 的 `/quotes/{id}:approve`（:415）、`:send-to-customer`（:443）、
`/customer-confirm`（:500）、`:supersede`（:565）四支是 ADR-0062～0066 時期的**設計稿**。
實作走的是另一條路：`quote_v2.py` 的 `/tenants/{tenantId}/quotes/{id}:submit|:approve|:send|:reject|:accept|:audit-complete`。

CR-0152（2026-07-10）業主裁決時，**只有 `:send-to-customer` 那一支補了退場標注**：

`api/openapi.yaml:438-442`
```yaml
  # 標注 2026-07-10(CR-0152,業主裁決):本宣告端點不另實作——AI 雙閘
  # (AI_FORBIDDEN_FINAL_QUOTE/AI_FORBIDDEN_WARRANTY_PROJECT)已落於
  # quote_v2 POST /tenants/{tid}/quotes/{id}:send 的 service 層
  # (quote_engine_service.transition,fail-closed);本段保留為設計參考
  # (internal_approved/customer_sent 為舊 FSM 詞彙,見 15_SDS §4.1 標注)。
```

其餘三支端點與 `Quote.state` enum 本身**都沒補**。TC-QUOTE-02 之所以寫 `sender_role=ai_agent`
而不是實作用的 `actor_role`，正是因為出題者讀的是 `api/openapi.yaml:465-475` 那段
`requestBody.required: [channel, sender_role]`——這不是命名亂寫，是照著沒退場的設計稿出題。

同理 TC-QUOTE-08 寫「同 Idempotency-Key 重送 customer-confirm」，是因為
`api/openapi.yaml:511-514` 明文寫「Idempotency-Key is REQUIRED so accidental double-tap
on LIFF or flex one-tap retries do not double-confirm」，而那支端點不存在。

**一句話：文件描述的是一個沒被蓋出來的世界，測試照文件出題，於是量產假 finding。**

---

## 4. 現況證據（逐 TC，皆已回程式碼覆核）

### 4.1 TC-QUOTE-01 — 狀態機（實作勝過 spec）

判定基準②（quote 掛 `quote_line_items`）**完全成立**：
`SQL/migrations/041-quote-engine.sql:34-35` 把 `quote_line_items` 升為 quote 層；
`api/services/quote_engine_service.py:331-338` INSERT ＋ `_recompute_total`；
另有 `:477-488` 的 `QUOTE_NO_LINES` 空報價擋閘（spec 沒要求，實作多做的）。

判定基準①的實作值域見 `api/services/quote_engine_service.py:29-41`，且**功能上比 spec 更完整**：
多一段 `submit`／`approve` 分離、多一條 draft 直送＋金額門檻（`:550-559`）、
多一個 `retrospective_audit_only` 急件入口（`:41`）。

**缺口不在 code，在 `api/openapi.yaml:5707-5722`。**

### 4.2 TC-QUOTE-02 — AI 閘（成立）＋ 範圍價（不存在且與 skill 相反）

`AI_FORBIDDEN_FINAL_QUOTE` 是**縱深防禦，兩層都在**：

- router 層：`api/routers/quote_v2.py:219` `role_required(*OPS_ROLES)`，`ai_agent` 不在內
- service 層：`api/services/quote_engine_service.py:509-515`，排在保固閘（`:516-527`）、
  requote 分層核可（`:531-546`）、核准門檻（`:550-559`）**之前**
- 測試：`api/tests/test_cr_0152_ai_quote_gate.py:66-75` 直接斷言 error_code ＋ 403

範圍價側**零實作**（我自行重掃確認）：
- `範圍價 / 價格區間 / 參考價 / price_range / range_only` 於 `agent/lockcore/skills/`、
  `agent/lockcore/channels/`、`api/`、`web/`、`SQL/` **全零命中**
- 沒有價格區間資料源：`SQL/migrations/040-quote-catalog.sql:28` 的 `service_catalog`
  只有 `suggested_customer_price` 單值，無 min/max
- agent 也拿不到價：`agent/lockcore/app_config.py:21-28` 的 `CS_TOOL_ALLOWLIST` 只有
  `read_file / list_dir / find_files / grep / web_search / transfer_to_human`，無查價工具
- BR-Quote-002 的 guardrail（「NTD 數字無修飾語 / 折扣關鍵字 / 保固免費 → regen」）
  在 `agent/lockcore/` **同樣零實作**——若真做範圍價，會撞上一道還沒蓋的護欄

### 4.3 TC-QUOTE-03 — 保固閘的三個問題（比走查文件更嚴重）

**問題一：判定來源錯置（這是真缺口，且在主路徑上失效）。**

`api/services/quote_engine_service.py:516-527` 以「該工單有 `warranty_claims` 關聯」判定保固案。
但 `SQL/Schema.sql:875-895` 顯示 `warranty_claims` 是**索賠單**
（`claim_date` / `status ∈ filed|verified|approved|rejected|disputed`）——
**客戶提出索賠之後才有列**。報價階段通常還沒有任何索賠。

FR-API-17（`04_SRS.md:308`）要求的是「Device.warranty_mode 5 模式保固判定」，
而該判定的 DB 來源尚未接：`api/services/warranty_service.py:223` 明寫
`# TODO(P3): site_group_mode / device_mode 由 device_warranty + site_group 表載入`，
`api/services/warranty_service.py` 全檔的保固判定都是純函式（`:97-227`），無 DB 載入。

更關鍵：CR-0128「報價先行」是**主路徑**，PC 階段報價的 `work_order_id` 為 NULL
（`quote_engine_service.py:147-151` 以 `None` INSERT），而保固閘的入口條件是
`if wo_row and wo_row[0]:`（`:518`）——**主路徑上整段保固檢查被跳過**。

**問題二：`AI_FORBIDDEN_WARRANTY_PROJECT` 在 HTTP 面不可達。**

`api/core/deps.py:293-295` → `OPS_ROLES = ("admin", "operations_manager")`；
`quote_engine_service.py:456` → `_HUMAN_STAFF_SEND_ROLES` 含這兩者；
`quote_v2.py:199-201` 恆帶 `actor_role=user.role`（永不為 None）。
全 repo 非測試的 `transition()` 呼叫端只有兩處：`routers/quote_v2.py:199` 與
`routers/consumer_v2.py:326`（後者只做 accept/decline）。
故該 403 只在「直接呼 service 且不帶 `actor_role`」時觸發——**正是測試
`api/tests/test_cr_0152_ai_quote_gate.py:84` 的走法**。而放行測試
`:96-104` 用的是 `secondary_admin_headers`（admin），**從未驗過 `customer_service`**。

平心而論：外層 RBAC 更嚴，內層不可達代表縱深防禦有效，不是安全漏洞。
**真正的問題是它讓人（與 AI）誤以為保固閘在運作。**

**問題三：「建案」在 domain model 層根本不存在。**

錯誤訊息 `quote_engine_service.py:524-525` 寫「保固／**建案**案件」，
但 SQL 條件（`:519-521`）只有 `warranty_claims`。程式碼註解 `:508` 自承「建案判定記遺留」。
我自行重搜 `建案 / construction_project / site_group / project_case / is_project`：
`SQL/` 內 `site_group` 只有 `SQL/migrations/003-warranty-5mode.sql:78` 一個
`warranty_inherit_from_site_group` 布林欄，**無 `site_group` 表、無 project 實體**。

### 4.4 TC-QUOTE-04 — 版本鏈斷點（真缺口，且靜默繞過金額管制）

**正典明文要求**（三處一致）：
- `04_SRS.md:143`：「可 `rejected → draft` re-version（`supersedes_quote_id` 串鏈）」
- `15_SDS.md:236`：「`rejected|expired → draft` 走 re-version v+1（`supersedes_quote_id` 串鏈）」
- `03_PRD.md:144`（FR-C01）：「re-version v+1 以 `supersedes_quote_id` 串鏈」

**實作只有技師那條串。** 全 repo `SET supersedes_quote_id` 唯一寫入點：
`api/services/requote_service.py:103`。讀取點唯一：`quote_engine_service.py:535`。

**客服那條路徑不是「還沒做」，是「做了但必然斷鏈」：**

`web/brand-portal/src/app/admin/quotes/page.tsx:945-957` 對 `rejected`／`expired` 顯示
「建立新版本重估」按鈕 → `requoteNewVersion()`（`:451-475`）POST 到
`/work-orders/{wo}/quotes` 或 `/problem-cards/{pc}/quotes`，**body 只有 `{urgent:false}`**。
兩支端點（`api/routers/quote_v2.py:57-65`、`:72-80`）直呼 `create_quote`，
而 `create_quote` 的 INSERT 欄位清單（`quote_engine_service.py:147-151`）**不含 `supersedes_quote_id`**，
只算 `MAX(version)+1`。

**連帶後果——這是本 CR 最該修的一條：**

`quote_engine_service.py:531-546` 的 CR-0150 分層核可，入口是 `if rq and rq[0]:`（`:535`）。
`supersedes_quote_id` 為 NULL 就**整段跳過**。也就是：

> 客服建的 v2，即使與 v1 價差遠超 `_REQUOTE_TIER_EDITOR_MAX = 2000`（`:453`），
> 也**不會**觸發 `REQUOTE_SUPERVISOR_REQUIRED` 403，由一般 OPS 角色直接送出。
> 技師 requote 路徑（有鏈）受管，客服路徑（無鏈）不受管。

判定基準②「舊版按鈕導向最新版」兩端皆無實作：後端 `consumer_v2.py:282-294` 以 token 內
`subject_id` 直取該張、無版本查找；前端 `quotes/[token]/page.tsx:195` 只做
`const actionable = data.state === "sent"`。且 `mint_view_token`（`quote_engine_service.py:735`）
對 `rejected` 仍發 token，舊連結永遠停在舊版。

另：`state = 'superseded'` **無任何寫入點**；前端 `quotes/[token]/page.tsx:29-35` 的
`QuoteState` 不含它，`admin/quotes/page.tsx:149` 卻有色票（來源永遠不會出現的死樣式）。

### 4.5 TC-QUOTE-05 — 絕大部分應銷案

走查列的四項缺口我全部覆核**屬實**（無報價過期 job——`api/realtime/job_registry.py`
的 14 個 job 我逐一列過確無；`sla_monitor.py:133-155` 只 append alert 不改 state；
`expired_by_cron` 程式碼零命中；有效期 7 天而非 48h，見 `quote_engine_service.py:44-46`、`:704-706`）。

**但這四項全部被 `20_Test_Cases.md:287` 的業主裁決標注明文推翻**（見 §2.3）。
走查文件產生的正是那段標注預告的「假 finding」。

唯一存活的疑點是「舊連結 → 410」：
- token 逾期 → `consumer_v2.py:248-267` 一律 404（不洩露原因，安全設計）
- token 未逾期但報價已 expired → GET 回 200 帶 `state`；POST 回 409
  （`quote_engine_service.py:566` 或 `:806` 收斂為 `QUOTE_EXPIRED`）
- 前端 `quotes/[token]/page.tsx:94` **有 410 分支，後端永不觸發**（前後端未接通）
- 標注寫的是「409/410」併列 → 現行 409 也在裁決範圍內

走查文件的行號有一處錯：引 `page.tsx:73-79` 為 410/429 分支，實際在 `:94-99`。

### 4.6 TC-QUOTE-08 — 冪等（真缺口，但 TypeError 那半已修）

`8c380412` 已修掉 `quote_engine_service.py:785` 漏 `await` 的 P0
（現行 `:789-792` 已是正確的 `await (await (await _conn()).execute(...)).fetchone()`，
且 `:785-788` 留了防再犯註解）。**契約層的問題仍在：**

| 端點 | `idempotency_guard` | 證據 |
|---|---|---|
| `POST /internal/quotes/{id}:customer-respond` | ❌ 無 | `api/routers/internal_ingest.py:168-174` 簽章只有 `service_credential_required` |
| `POST /consumer/quotes/{token}` | ❌ 無 | `api/routers/consumer_v2.py:303-307` |
| `POST /tenants/{t}/quotes/{id}:accept` | ✅ 有 | `api/routers/quote_v2.py:224-228` |
| `POST /tenants/{t}/work-orders/{wo}/quotes`（建報價）| ❌ 無 | `api/routers/quote_v2.py:57-65` |
| `POST /tenants/{t}/problem-cards/{pc}/quotes`（建報價）| ❌ 無 | `api/routers/quote_v2.py:72-80` |

替代機制只有 internal 路徑有：`quote_engine_service.py:793-795` 的
「同決定 → 回既有終態 ＋ `idempotent_replay: True`」。
consumer token 路徑（`consumer_v2.py:326-328`）直呼 `transition`，
`accept` 的 `from_states = {"sent"}`（`:35`）→ **第二次落 409 `STATE_CONFLICT`**。

**掛 guard 是破壞性變更，不能直接做**：`api/config.toml:32`
`applies_to = ["POST","PATCH","PUT","DELETE"]`，而 `api/core/idempotency.py:198-206`
在缺 key 時對這些 method 回 400 `MISSING_IDEMPOTENCY_KEY`；
agent gateway 的 `_bridge_auth_headers`（`agent/lockcore/channels/line_gateway.py:87-90`）
**只送認證 header，不送 `Idempotency-Key`** → 掛上去當天 LINE 報價確認全掛。

判定基準③「audit 不重複」形式上成立，但成立的方式是**根本沒有 audit**：
`api/services/quote_engine_service.py` 全檔 `audit_log_service` / `log_event` 命中數 **0**
（同 repo 有 24 個 service 有寫，含 `requote_service.py`）。這是稽核缺口，不是冪等缺口。

判定基準②「不重觸發工單建立」天然成立：accept 只 best-effort 開發票
（`quote_engine_service.py:611-627`），開單走 `problem_cards_v2.py` 的 convert 端點。

### 4.7 測試為什麼沒擋住（Test plan 面向的真缺口）

`api/tests/test_cr_0095_quote_line_approval.py` 的 marker 分布：

```
120,138,151,170,188,208,230:  @pytest.mark.component   ← 有標
253: async def test_customer_respond_accept_twice_idempotent(client)   ← 無 component marker
272: async def test_customer_respond_conflict_codes(client)            ← 無 component marker
```

兩支直接覆蓋客戶確認冪等／衝突碼的測試**沒掛 `@pytest.mark.component`**，
而 `.github/workflows/component-nightly.yml` 跑的是 `pytest -m component`
→ **nightly 永遠 skip 它們**。這正是 `8c380412` 的 P0 能從 2026-07-21 存活到 2026-08-05
（15 天）而「看起來有測試」的機制。
（`test_customer_respond_ownership_and_accept` 有標 marker，故 nightly 應該會紅——
我無法離線查 CI 歷史確認當時是否有人看，**這點無法確認**。）

---

## 5. 程式碼現狀盤點

| 元件 | 行數 | 職責 | 觀察 |
|---|---|---|---|
| `api/services/quote_engine_service.py` | **854** | 狀態機／建報價／明細／gate／snapshot／token／consumer 回覆 | 超過 `.claude/rules/coding-style.md` 的 800 行上限；七種職責同檔 |
| `api/routers/quote_v2.py` | 251 | 後台 12 支端點 | 6 支轉態端點全掛 `idempotency_guard`，2 支建報價端點未掛 |
| `api/routers/consumer_v2.py` | 444 | 客戶端 token 路徑 | 報價 GET/POST 皆無 guard |
| `api/services/requote_service.py` | 131 | 技師現場修正 | **唯一**寫 `supersedes_quote_id` 者；且有寫 audit |
| `api/openapi.yaml`（quote 段）| :354-620, :5700-5820 | 機讀契約 | 4 支宣告端點無實作（1 支有標注）；`Quote.state` enum 全錯 |

---

## 6. 影響評估

### 6.1 誠實降級——查證後認為**不該修**的部分

| 項目 | 為什麼不該修 |
|---|---|
| **TC-QUOTE-05 的 cron 過期 ＋ `expired_by_cron` ＋ 48h** | `20_Test_Cases.md:287` 與 `04_SRS.md:312` 的 CR-0181 業主裁決標注**已明文推翻**，並預告「用 48h 舊條件測會產生假 finding」。走查踩中了。要改的是 TC 判定基準，不是 code。 |
| **TC-QUOTE-01 的狀態名改回 `internal_approved` 等** | 那是無謂的破壞性變更：要動 DB 既有 `quote.state` 值、`_TRANSITIONS`、前端兩份 enum、5 個測試檔。實作值域功能上比 spec 更完整。**該改的是文件。** |
| **TC-QUOTE-02 的參數名 `sender_role`** | 實作用 JWT 推導的 `actor_role`（`quote_v2.py:201`），客戶端**無法自填**——安全性嚴格優於 spec 的「請求體自報角色」。文件該退場，code 不動。 |
| **TC-QUOTE-03 的「`AI_FORBIDDEN_WARRANTY_PROJECT` 不可達」** | 外層 RBAC 更嚴才導致內層不可達，這是縱深防禦成立的表現，不是漏洞。要修的是**訊息謊報**與**判定來源錯置**，不是這道 403 本身。 |
| **TC-QUOTE-08 的「audit 不重複」** | 條件形式上滿足（因為根本沒 audit）。這是 NFR-Aud 缺口，不屬冪等範疇，建議另案而非塞進本 CR 的冪等工作項。 |

**六支 TC 中，需要動 code 的實質缺口只有三條**：
① 客服建 v2 斷鏈＋連帶繞過 CR-0150 金額管制（TC-QUOTE-04）
② 客戶確認端點無冪等契約（TC-QUOTE-08）
③ 保固判定來源錯置＋主路徑跳過（TC-QUOTE-03）

### 6.2 rewrite vs refactor 九維打分表

依 `.claude/rules/change-governance.md`：

| # | 維度 | 分 | 理由（含證據）|
|---|---|---|---|
| 1 | 產品目標是否改變？ | **0** | 報價引擎的產品目標完全不變。所有爭點都在「文件描述與實作對不對得上」。 |
| 2 | 核心 User Flow 是否改變？ | **1** | 主流程（建→審→送→確認）不動。新增分支：舊版導向最新版（`consumer_v2.py:282-294` + `page.tsx`）、過期報價回 410。屬新增分支。 |
| 3 | Domain Model 是否改變？ | **1** | 需新增概念：`project`／`site_group` 實體（現在完全不存在）、可能的 `range_only`。Quote 核心概念（版本鏈、snapshot、狀態機）不改，只是把 `supersedes_quote_id` 這條既有不變式**補齊執行**。 |
| 4 | API Contract 是否大量破壞？ | **1** | 依建議路徑（以實作為準）：`create_quote` 加**可選**欄位、consumer GET 加**可選**回傳欄位＝向後相容；破壞性只有兩處——過期回應 409→410、以及若選擇掛 `idempotency_guard`（`idempotency.py:198-206` 會 400，`line_gateway.py:87-90` 不送 key）。屬「多 endpoint 變動」。 |
| 5 | DB Schema 是否需重建？ | **1** | 建案 domain 要新表（`site_group` / `project` ＋ 工單關聯）、`range_only` 若做要加欄。**都是 migration 可處理的新增**，無既有表重建、無 NOT NULL 回填風險。 |
| 6 | 模組邊界是否錯誤？ | **1** | `quote_engine_service.py` 854 行、七種職責同檔（超 `coding-style.md` 800 行上限）；報價狀態機沒有 audit 而 `requote_service` 有，同一領域兩套規矩。但 service ← router 的分層本身清楚。「有些混亂」。 |
| 7 | 測試是否可信？ | **1** | 測試本身寫得對（`test_cr_0095` 那三支確實測到了 P0 路徑），但**跑不到**：兩支缺 `@pytest.mark.component` → nightly `-m component` 永遠 skip（§4.7）；`test_cr_0152_ai_quote_gate.py:96` 用 admin header 驗「客服可送保固單」＝釘錯東西。屬「部分可信」。 |
| 8 | 文件是否可信？ | **2** | 這是本 CR 的核心。`api/openapi.yaml`（**被 CI 執行的機讀 SSOT**）狀態 enum 全錯、4 支宣告端點只有 1 支有退場標注；`04_SRS.md` / `15_SDS.md` / `03_PRD.md` 三份同步錯；`04_SRS.md:76` 的 `range_only` 欄位 repo 零命中；`04_SRS.md:142` 與 `13_Security_Architecture.md:99` 對「客服」職掌互相矛盾。**大量矛盾。** |
| 9 | 團隊/AI 是否還理解系統？ | **1** | 直接實證：外部測試人員照正典出題，六支有四支得出與實作對不上的結論；走查漏讀 `20_Test_Cases.md:287` 的標注而產生假 finding；任何讀 `api/openapi.yaml` 的 AI 都會拿到錯狀態名。但知道實情的人／查得出來的路徑仍在（本 CR 即是）。「少數人懂」。 |

**總分 ＝ 0+1+1+1+1+1+1+2+1 ＝ 9 分**

### 6.3 行動建議

**9 分落在 7–12 區間 → 架構重審 + 模組拆分（多 CR + 跨 sprint）。**

但這裡的「架構重審」不是重寫報價引擎——**程式碼是這組裡最健康的部分**。要重審的是：

1. **契約層**：`api/openapi.yaml` 的 quote 段必須與實作對齊或明確標注退場，
   否則它會持續透過 CI（prism mock / schemathesis）與所有讀它的人／AI 量產錯誤。
   這是唯一的 8 分項（文件）拉高總分的來源，也是最高 ROI 的一刀。
2. **版本鏈不變式**：`supersedes_quote_id` 是三份正典都寫明的不變式，卻只有一條路徑執行，
   且不執行的那條**靜默繞過金額管制**。這不是功能缺失，是不變式沒被強制。
3. **模組拆分**：854 行的 `quote_engine_service.py` 建議拆為
   `quote_state_machine` / `quote_lines` / `quote_tokens` / `quote_consumer` 四段——
   但這屬 refactor，**不應與本 CR 的行為修正混在同一批 commit**，建議另開 CR。

**不建議做 13+ 的「新主幹」**：產品目標 0 分、核心 flow 0-1 分，
原本的產品假設完全沒死，死的只是那份沒退場的設計稿。

---

## 7. 可行路徑

### 路徑 A — 契約收斂（低風險、高 ROI、可先做）
不動 code。`api/openapi.yaml` 比照 `:438-442` 既有標注格式，為 `Quote.state`（`:5707-5722`）
補「舊 FSM 詞彙 → 現行實作值」對映表，並為 `:415`、`:500`、`:565` 三支補退場標注。
`smartlock-docs/` 依「只可新增標注、不改寫原文」規則，在 `15_SDS.md:236`、`03_PRD.md:144`
旁加同一份對映。**風險**：改 `openapi.yaml` 會觸發 spec-lint 與 mock-smoke，需確認 spectral 過。

### 路徑 B — 版本鏈補完（中風險、修掉一條金額管制漏洞）
`create_quote`（`quote_engine_service.py:96-152`）增可選參數 `supersedes_quote_id`，
INSERT 欄位清單補上；兩支客服建報價端點（`quote_v2.py:57-80`）request body 增可選欄位；
前端 `requoteNewVersion`（`admin/quotes/page.tsx:463-467`）POST body 帶入當前 `quote.id`。
**做完 CR-0150 分層核可自動恢復生效**，不需另外寫 gate 邏輯。

### 路徑 C — 冪等契約（破壞性，必須同版部署）
若掛 `idempotency_guard` 到兩個客戶確認端點，須**同一版**改
`agent/lockcore/channels/line_gateway.py` 送 `Idempotency-Key`，否則 LINE 報價確認全掛。
非破壞替代：把 `consumer_v2.py:326-328` 改走 `customer_respond_to_quote`
（取得與 internal 路徑同等的業務冪等），零 header 需求。

### 路徑 D — 保固／建案 domain（大，建議拆 CR）
建 `site_group` / `project` 實體 ＋ 工單關聯 ＋ `device_warranty` 接 DB（解 `warranty_service.py:223` 的 TODO），
再把 `quote_engine_service.py:519-521` 的判定從 `warranty_claims` 改為設備保固狀態。
在此之前的最小止血：把 `:524-525` 錯誤訊息與 `:506-508` 註解的「建案」字樣標為未實作。

---

## 8. 🛑 Human Decisions Required

> 以下每題請回覆「D<n> 選 <x>」即可。可一次回多題。

### D1：`api/openapi.yaml` 的 Quote 狀態機詞彙，以哪一邊為準？

這題決定本 CR 是「文件校正」還是「系統重寫」，其他決策的詞彙都繼承它。

- **(a) 以實作為準**——`openapi.yaml` 的 `Quote.state` enum（`:5707-5714`）補對映標注，
  三支無標注的宣告端點（`:415` `:approve`、`:500` `/customer-confirm`、`:565` `:supersede`）
  比照 `:438-442` 補退場標注；`smartlock-docs` 三份（`04_SRS.md:126-134`、`15_SDS.md:236`、
  `03_PRD.md:144`）加同一份對映標注。
  **代價**：約半天，零 code 變更，需重跑 spec-lint。
- **(b) 以 spec 為準**——把實作狀態名改成 `internal_approved` / `customer_sent` / `customer_confirmed`。
  **代價**：要 migration 改 DB 既有 `quote.state` 值、改 `_TRANSITIONS`、改前端兩份 enum
  （`quotes/[token]/page.tsx:29-35`、`admin/quotes/page.tsx`）、改 5 個測試檔、
  改 i18n 狀態文案。**且會丟掉實作多出來的 `pending_approval` 分段與 `retrospective_audit_only` 急件入口。**
  評估 3–5 天且全域破壞性。
- **(c) 補實作那四支宣告端點作為別名層**——`:approve` → 內部轉 `submit`+`approve`，
  `/customer-confirm` → 轉 `accept`⋯
  **代價**：多一套要永久維護的重複 API 面，狀態名仍兩套並存，把矛盾制度化。

> **我的建議：(a)。** 理由：實作值域**功能上嚴格優於** spec（多一段核准分離、多一條急件入口、
> 多一道空報價擋閘），沒有任何一項能力是 spec 有而實作缺的。改實作去遷就一份從未被蓋出來的
> 設計稿，是拿三到五天的全域破壞性變更換零使用者價值。而 (a) 的半天投入能同時止住
> CI mock、schemathesis 與所有讀 spec 的人／AI 的持續誤導——這是全 CR 裡 ROI 最高的一刀。

### D2：TC-QUOTE-05 要銷案到什麼程度？

`20_Test_Cases.md:287` 的 CR-0181 業主裁決標注已推翻該 TC 的四項基準之三，
並明文預告「用 48h 舊條件測會產生假 finding」——走查正好踩中。

- **(a) 全數銷案**——TC-QUOTE-05 判定基準整條改用 `:287` 標注版
  （7 天有效期／lazy 檢查／無 cron／無 `expired_by_cron`／expired 保留），
  「舊連結」基準以現行 409 `QUOTE_EXPIRED` 視為達標（標注寫「409/410」併列）。
  **代價**：零開發。前端 `quotes/[token]/page.tsx:94` 的 410 分支成為永久死碼。
- **(b) 部分銷案**——cron／`expired_by_cron`／48h 三項銷案，
  只做「過期報價的客戶端回應改 410」把前後端接通。
  **代價**：小（`consumer_v2.py` 對 `state='expired'` 改回 410），
  但 410 是破壞性回應碼變更，需確認無其他 client 依賴 409。
- **(c) 推翻 CR-0181**——真的做 `quote-expiry` cron job ＋ `expired_by_cron` audit。
  **代價**：新 job 進 `job_registry.py`、新 audit action、新測試；且與您 2026-07-25 的裁決相反。

> **我的建議：(b)。** 理由：(a) 留一個永遠不會亮的前端錯誤分支，
> 就是 CR-0197 §6 提過的那種「看起來有在擋、實際不擋」的東西，下一個人會被騙。
> 而 410 GONE 對「這份報價已過期，請重新報修」的語意比 409 CONFLICT 準確得多，
> 前端文案（`t("errors.expired")`）也早就寫好在等。成本只有一個判斷分支。

### D3：`customer_service` 到底能不能送出報價？

`quote_engine_service.py:456` 的白名單含它，但 `OPS_ROLES`（`deps.py:295`）不含
→ 它是**永遠走不到的死條目**。而 `13_Security_Architecture.md:99` 把報價歸 `operations_manager`。

- **(a) 擴權**——新增 `QUOTE_SEND_ROLES = OPS_ROLES + ("customer_service",)`，
  `quote_v2.py:219` 改用它，讓 TC 判定基準與 SRS `:142` 成立。
  **代價**：RBAC 面擴大＝L2 安全變更，須同步 `13_Security_Architecture.md` 角色矩陣
  與 `role_service._MATRIX`；且 `:approve` 仍限 `_APPROVE_ROLES`，客服只能送不能核。
- **(b) 收斂**——移除 `quote_engine_service.py:456` 的 `"customer_service"` 死條目，
  在 `20_Test_Cases.md:279` 與 `04_SRS.md:142` 旁加標注「本條『客服』指
  `operations_manager`（帳務報價職掌，見 13_Security §3.1）」。
  **代價**：零開發，一處標注。與 `16_API_Spec.yaml:570-572` 既有標注「小編層待 RBAC 擴權另案」一致。
- **(c) 維持現狀，只加程式碼註解**說明該條目目前不可達。
  **代價**：矛盾繼續存在，下一輪測試會再撞一次。

> **我的建議：(b)。** 理由：`13_Security_Architecture.md:106` 的租戶標準人力配置寫得很清楚——
> `customer_service` 是「進線 / 建單 / **發起**」、明文「無核准權」，
> `operations_manager` 才是「帳務報價」。送出報價是對客戶的金額承諾，
> 歸在有帳務職掌的角色是對的。SRS `:142` 的「客服」是口語泛稱後台人員，不是 RBAC role 名。
> 若您實務上真的要讓小編送報價，改選 (a)——但那要連 `:approve` 的 SoD 一起重想，該另開 CR。

### D4：「建案（project）」判定要不要做？

現在錯誤訊息（`quote_engine_service.py:525`）寫「保固／**建案**案件」，但 domain model 裡
**沒有建案這個東西**（無 `site_group` 表、無 project 實體，`warranty_service.py:223` TODO(P3)）。

- **(a) 完整做**——立 `site_group` / `project` 實體 ＋ 工單關聯 ＋ 接 `device_warranty`，
  再擴 `:519-521` 的判定 SQL。
  **代價**：新 migration、新 service、新 API、跨 M4/M7 模組，估 1–2 sprint，建議另開 CR。
- **(b) 只止血**——把 `:525` 錯誤訊息與 `:506-508` 註解的「建案」字樣移除或標為未實作，
  並在 `04_SRS.md:450`（BR-Quote-003）旁標注「建案側 v1 未實作」。
  **代價**：< 1 小時。缺口變成**看得見的**缺口。
- **(c) 折衷**——`work_orders` 加 `case_type` 欄（`normal|warranty|project`）由客服手動標記，
  判定 SQL 改讀它。
  **代價**：一個 migration ＋ 前端一個下拉，但引入人工標記的資料品質風險。

> **我的建議：先 (b)，(a) 另開 CR 排進 roadmap。** 理由：(a) 是真需求（BR-Quote-003 是紅標
> 業務規則）但規模遠超本 CR；(c) 的手動標記在保固／建案這種**會影響誰付錢**的判定上
> 引入人為錯誤風險，不划算。(b) 的價值在於：訊息不再謊報，下一個讀 code 的人（含 AI）
> 不會以為建案已受控——這正是 CR-0197 §6 那條「隱性成本」的同型問題。

### D5：版本鏈要補到什麼程度？

三份正典（`04_SRS.md:143`、`15_SDS.md:236`、`03_PRD.md:144`）都明寫 `supersedes_quote_id` 串鏈，
但客服路徑（前端有按鈕、後端有端點）**必然斷鏈**，且斷鏈**靜默繞過 CR-0150 的 2000 元金額管制**。

- **(a) 只補串鏈**——`create_quote` 加可選參數 ＋ 兩支端點 body 加可選欄位 ＋ 前端帶入 `quote.id`。
  **代價**：3 檔小改，向後相容（欄位可選）。做完 CR-0150 分層核可**自動恢復生效**，不需另寫 gate。
- **(b) 串鏈 ＋ 舊版導向最新版**——(a) 再加：`consumer_v2.py` GET 回傳加 `latest_quote_id`，
  前端對非最新版顯示「已有新版本」CTA。
  **代價**：(a) ＋ 後端一個查詢 ＋ 前端一個區塊，約 +0.5 天。滿足 TC-QUOTE-04 全部判定基準。
- **(c) 照 `openapi.yaml:565` 的 ADR-0065 設計做 `:supersede` 端點**——re-version 成為
  一等公民操作，前端改打它。
  **代價**：新端點 ＋ 前端改造 ＋ `state='superseded'` 寫入點；與 D1 選 (a) 的「宣告端點退場」方向相反。
- **(d) 不做**——接受客服 v2 不串鏈。
  **代價**：金額管制漏洞持續存在（客服可繞過 >2000 的主管覆核），且違反三份正典的明文不變式。

> **我的建議：(b)。** 理由：(a) 是必做——這不是「加功能」，是**修一個靜默的金額管制繞過**，
> 而且修法極廉價（補一個既有欄位的寫入，管制邏輯自己就活過來）。加碼到 (b) 只多半天，
> 卻讓客戶不會停在死掉的舊報價連結上——那是實際會發生的客訴。
> (c) 是長線正解但與 D1 打架，等契約收斂後再議；(d) 不可接受，因為它讓一道已實作的金融管制形同虛設。

### D6：兩個客戶確認端點的冪等，怎麼做？

`internal_ingest.py:168-174` 與 `consumer_v2.py:303-307` 都沒掛 `idempotency_guard`。

- **(a) 掛 guard**——並**同版**改 `line_gateway.py:87-90` 送 `Idempotency-Key`。
  **代價**：破壞性。`api/config.toml:32` 的 `applies_to` 含 POST，
  `idempotency.py:198-206` 缺 key 直接 400；agent 與 api 必須同版部署，
  部署順序錯就是 LINE 報價確認全掛。且 consumer token 路徑的呼叫端是**瀏覽器**，
  要前端也生成並保存 key。
- **(b) 走業務冪等**——把 `consumer_v2.py:326-328` 從直呼 `transition` 改為呼叫
  `customer_respond_to_quote`，取得與 internal 路徑同等的「同決定回既有終態」保護。
  **代價**：小（1 檔），零 header 需求，零破壞性。但嚴格說**不滿足 TC 字面的「同 Idempotency-Key」**。
- **(c) 掛 guard 但對這兩支 opt-out**——在 config 加 `applies_to` 例外清單，
  有 key 才去重、無 key 放行。
  **代價**：改動全域冪等機制的語意（目前是「寫操作必填」），影響面遠超報價。

> **我的建議：(b)。** 理由：TC 字面要的是 `Idempotency-Key`，但那個字面來自
> `openapi.yaml:511-514` 那支不存在的 `/customer-confirm` 端點（見 §3）。
> **真正的需求是「客戶連點兩次不要壞」**，而 (b) 完整達成且零風險。
> (a) 的代價是把一條已知會掛的破壞性變更放進 LINE 主流程——
> 依 memory 的「雲端部署參數 parity」教訓，這種需要兩個服務同版落地的變更是上線最大反覆雷。
> 若您堅持要 HTTP 層 key，建議另開 CR 單獨做，不要混在本批。

### D7：報價狀態機要不要補 audit？

`quote_engine_service.py` 全檔 `audit_log_service` / `log_event` 命中 **0**；
同 repo 24 個 service 有寫（含同領域的 `requote_service.py`）。

- **(a) 補**——`transition()` 對每個 action 寫一筆 audit（含 actor、from/to state、金額）。
  **代價**：1 檔改動 ＋ 測試，約半天。滿足 NFR-Aud 對金額相關操作的稽核要求。
- **(b) 不補**——維持現狀。
  **代價**：報價（＝對客戶的金額承諾）全程無稽核軌跡；出爭議時無法證明誰在何時送出什麼金額。

> **我的建議：(a)。** 理由：報價是本系統唯一「對外承諾金額」的物件，
> 而它是少數完全沒有稽核的 service，同領域的 `requote_service` 反而有。
> 這個不對稱本身就說明是遺漏而非決策。半天成本換掉一個爭議發生時無法舉證的風險。

### D8：AI 範圍價——正典衝突，請裁決以哪份為準？

- 支持做：`06_UX_Research_Report.md:188`「不給 final 價（**只給 range**）」＋
  `04_SRS.md:76` 的 `Quote.range_only` 欄位 ＋ `04_SRS.md:142` 的 `range_only=true`（AI 路徑）
- 反對做：`04_SRS.md:452`（BR-AI-004）「AI **不複誦個案 quote 金額**；僅 announce existence；
  **無自由文 NTD 數字**」＋ 現行 skill `SKILL.md:34`、`:64`、`handoff-and-dispatch.md:66`
  一律 `transfer_to_human` 不報價

- **(a) 以 BR-AI-004 為準，範圍價銷案**——只在
  `agent/lockcore/skills/locksmith-cs-sop/references/handoff-and-dispatch.md` 既有「專員聯繫」段
  補一句「客服已為您備好報價，稍後由專員與您確認」（＝ announce existence），
  TC-QUOTE-02 判定基準②改為此句。
  **代價**：純 skill 內容編輯，走 CR-0167 的品牌後台「知識庫 > AI 技能」發佈，≤60s 生效不重佈。無 CIA。
- **(b) 以 UX 原則為準，真的做範圍價**——需要三件都做：
  ① 價格區間資料源（`service_catalog` 加 min/max 或新增 price_range 端點＝API contract + DB schema）
  ② 讓 agent 拿得到（加內建工具要改 `CS_TOOL_ALLOWLIST`／加 MCP 要改 `agent/config.toml`
     ——依 `CLAUDE.md` §🔒 第 4 條**兩者皆屬 architecture change**）
  ③ 補 `Quote.range_only` 欄位與 AI 路徑的 `customer_sent` precondition
  **代價**：跨 agent／api／DB 三層，估 1–2 sprint，且會撞上 BR-Quote-002 的 guardrail
  （「NTD 數字無修飾語 → regen」）——**該 guardrail 在 `agent/lockcore/` 目前零實作**，
  等於要先蓋護欄才能開閘。
- **(c) 折衷**——AI 給「非個案」的公開參考價（如「一般換鎖芯服務約 NT$X–Y」），
  資料源走既有 `service_catalog.suggested_customer_price` ±區間，不綁個案 quote。
  **代價**：介於兩者，仍須 ①②，但不需 `range_only`。

> **我的建議：(a)。** 理由三點：
> ① BR-AI-004 是 SRS 的正式業務規則（tier-2 契約），`06_UX_Research_Report.md` 是研究報告
> （tier-4 探索），依 `.claude/rules/context-stability.md` 的分層，前者勝。
> ② (b) 要先蓋 BR-Quote-002 的 guardrail 才能安全開閘——**先開閘後蓋護欄**是最糟的順序。
> ③ 現行 skill 已經在「一律轉真人」的最保守位置運作，客訴風險最低；
> 而 (a) 只補「客服已備好報價」這句話，就能覆蓋 TC 判定基準裡真正有價值的那半（announce existence）。
> 若您產品上確實要 range 才能提升自助率，請把它當獨立 feature 開 CR，不要塞在這張修正單裡。

### D9：測試 marker 缺漏要不要補？

`test_customer_respond_accept_twice_idempotent`（`:253`）與
`test_customer_respond_conflict_codes`（`:272`）**沒掛 `@pytest.mark.component`**
→ `component-nightly.yml` 的 `pytest -m component` 永遠 skip 它們。
這是 `8c380412` 的 P0 存活 15 天而「看起來有測試」的機制。

- **(a) 補 marker ＋ 加 CI 守線**——補兩個 marker；另加一條 lint：
  用 `db_module._ensure_conn()` 或 `client` fixture 的測試必須有 `component` marker。
  **代價**：補 marker 極小；lint 約半天。
- **(b) 只補 marker**。
  **代價**：小。但同型漏標會再發生。
- **(c) 不補**。

> **我的建議：(a)。** 理由：這是本 CR 裡**唯一有實證因果的流程缺陷**——
> 不是「可能會出問題」，是已經讓一個 P0 在生產跑了 15 天。
> 補 marker 是止血，lint 才是止住復發。半天成本對照 15 天的 LINE 報價確認全掛，比例懸殊。

---

## 9. Suggested Implementation Order（待 §8 裁決後）

### 相依關係

```
D1（契約詞彙）──┬─→ S1 openapi 標注 ──→ S2 smartlock-docs 標注
                └─→（決定 D5 是否走 :supersede）

D9（測試 marker）─→ S0  ← 無相依，最先做，之後每步都靠它驗證

D5（版本鏈）──→ S3 create_quote 串鏈 ──→ S4 前端帶入 ──→ S5 舊版導向
D6（冪等）────→ S6 consumer 路徑改走業務冪等
D7（audit）───→ S7 transition 補 audit
D3（RBAC）────→ S8 移除死條目 ＋ 標注
D4（建案）────→ S9 訊息止血
D2（過期）────→ S10 410 接通
D8（範圍價）──→ S11 skill 話術（獨立軌，走 CR-0167 發佈流程）
```

### 順序與驗證

| 步驟 | 內容 | 相依 | 驗證方式 |
|---|---|---|---|
| **S0** | 補兩個 `@pytest.mark.component`（`test_cr_0095_quote_line_approval.py:253`、`:272`）＋ marker lint | D9 | `cd api && POSTGRES_URI=<scratch 庫> pytest -m component tests/test_cr_0095_quote_line_approval.py -q` → 12 項全跑（原 10 項）。**勿對 5433 UAT 庫跑** |
| **S1** | `api/openapi.yaml` 補 `Quote.state` 對映標注 ＋ 三支端點退場標注 | D1 | `npx spectral lint api/openapi.yaml`；`scripts/ci/contract-schemathesis.sh --check-only` |
| **S2** | `smartlock-docs` 三處加同一份對映標注（**只新增，不改寫原文**）| S1 | 人工複讀；確認 `15_SDS.md:236`、`03_PRD.md:144`、`04_SRS.md:126-134` 旁各有標注 |
| **S3** | `create_quote` 加可選 `supersedes_quote_id` ＋ INSERT 欄位；兩支端點 body 加可選欄位 | D5 | 新測試：客服路徑建 v2 → 斷言 `supersedes_quote_id` 串鏈；**斷言 delta>2000 且非主管送出回 403 `REQUOTE_SUPERVISOR_REQUIRED`**（這條是本 CR 的核心回歸） |
| **S4** | 前端 `requoteNewVersion`（`admin/quotes/page.tsx:463-467`）POST body 帶 `quote.id` | S3 | `npm run lint && npm run typecheck`；手動走「拒絕 → 建立新版本重估」→ 查 DB 該欄非 NULL |
| **S5** | `consumer_v2.py` GET 加 `latest_quote_id`；前端加「已有新版本」CTA | S3 | 新測試：以 v1 token 開 → 回傳含 v2 id |
| **S6** | `consumer_v2.py:326-328` 改走 `customer_respond_to_quote` | D6 | 新測試：consumer token 路徑連送兩次 accept → 第二次 `idempotent_replay: True` 而非 409 |
| **S7** | `transition()` 補 `audit_log_service.log_event`（action / actor / from→to / amount）| D7 | 新測試：send 後查 `audit_events` 有對應列 |
| **S8** | 移除 `quote_engine_service.py:456` 的 `"customer_service"` 死條目 ＋ 正典標注 | D3 | 既有 `test_cr_0152_ai_quote_gate.py` 全綠；**另補一支以 HTTP 驗 `customer_service` 打 `:send` 回 403** |
| **S9** | `:524-525` 訊息與 `:506-508` 註解移除「建案」字樣 ＋ `04_SRS.md:450` 旁標注 | D4 | grep 確認訊息不再含「建案」；`test_cr_0152` 若斷言訊息字串需同步 |
| **S10** | `consumer_v2.py` 對 `state='expired'` 改回 410 `GONE` | D2 | 新測試：`expiry_at` 撥到過去 → GET/POST 回 410；前端 `page.tsx:94` 分支實際被觸發 |
| **S11** | `handoff-and-dispatch.md` 補「客服已備好報價」句 | D8 | skill 走品牌後台發佈（CR-0167），≤60s 生效；`agent/tests/test_skills_loaded.py` 綠 |

### 可平行 / 必須序列

- **可平行**：S0 / S1+S2 / S11 三軌完全獨立，可同時進行
- **必須序列**：S3 → S4 → S5（前端依賴後端欄位）；S1 → S2（標注文字須一致）
- **可獨立插入**：S6 / S7 / S8 / S9 / S10 彼此無相依，但**都應排在 S0 之後**，
  否則 nightly 仍不會跑到報價冪等測試
- **建議分批 commit**：S0 ／ S1+S2 ／ S3+S4+S5 ／ S6+S7 ／ S8+S9+S10 ／ S11 共六個原子 commit，
  各自可獨立 revert

### 收尾（依 `CLAUDE.md` 的三處同步）

1. 本檔 §8 下方補 `### 進度` 區塊，逐步記 `✅ Sx done（merge <sha>）`
2. `CHANGELOG.md` `[Unreleased]` 的 Added / Changed / Decisions
3. 若 D1 選 (b)、D5 選 (c) 或 D8 選 (b)，屬架構決策 → 新開 ADR（append-only）

### 明確不在本 CR 範圍（建議另開）

- `quote_engine_service.py`（854 行，超 `coding-style.md` 800 行上限）的模組拆分
- 建案 / `site_group` domain model（D4 選 (a) 時）
- HTTP 層 `Idempotency-Key`（D6 選 (a) 時，需 agent＋api 同版部署）
- AI 範圍價完整實作（D8 選 (b)/(c) 時，含 BR-Quote-002 guardrail）

---

## 附錄：本 CR 的查證方式

- 走查文件的每個 `檔案:行號` 皆重新開檔覆核；發現一處行號誤差
  （`TC-QUOTE-05.md` 引 `page.tsx:73-79`，實際 410/429 分支在 `:94-99`，引文內容正確）。
- 對宣稱「零命中」的識別碼以多種寫法重跑 grep：`range_only`、`site_group`、
  `construction_project`、`project_case`、`expired_by_cron`、`範圍價/價格區間/參考價/price_range`
  ——全 repo（`.py`/`.sql`/`.ts`/`.tsx`/`.yaml`/`.md`）確認結果。
- `job_registry.py` 的 14 個 job 以 regex 完整抽出逐一比對，確認無報價過期 job。
- `OPS_ROLES` / `_HUMAN_STAFF_SEND_ROLES` 的交集關係由 `api/core/deps.py:293-299`
  的定義鏈實際展開，非推測。
- 測試 marker 分布以 `grep -n "@pytest.mark\|^async def test_"` 逐行對照確認。
- **未啟動任何服務、未連 DB、未跑 pytest**（依任務限制，且避免污染 5433 UAT 庫）。
  所有結論皆為靜態程式碼與文件覆核。
- 無法確認項：`component-nightly` 當時是否因 `test_customer_respond_ownership_and_accept`
  而變紅（需查 CI 歷史，離線不可得）——§4.7 已如實標注。
