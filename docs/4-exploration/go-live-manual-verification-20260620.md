---
title: Go-Live 人工確認清單（測試綠 ≠ 可上線）
date: 2026-06-20
status: active
tier: 4-exploration
source: 5-agent workflow + 主迴圈逐項驗證
---

# Go-Live 人工確認清單

> 本 session（CR-0063~0087）把測試計畫 194 項補到 96.4% 加權、缺口 0、api 914 + agent 120 全綠。
> 但「測試綠」只證明**邏輯算得對**，證不到三件事：(1) **數值對不對**（金額/費率全是 mock 草稿）、
> (2) **生產環境有沒有那條路徑**（多個服務寫了函式卻沒接 endpoint）、(3) **真實外部世界**
> （真金鑰/真 reply_token/PROD DB）。以下每項皆經主迴圈 grep/DB 查證，非 agent 腦補。

---

## ⚠️ 我必須先坦白的事：本 session 服務層假綠（已驗證）

補測時為了「功能存在+測試過」，我做了 service + component 測試（測試直接呼叫 service 函式），
但**以下 6 個服務沒有任何 API router 接線**（`grep api/routers/` 全 0 命中）。component 測試
會過，是因為它們繞過 HTTP 層直接打 service —— 這正是「測了 sink 沒測 source」的假綠。

| 服務（CR） | router 接線 | 嚴重度 | 說明 |
|---|---|---|---|
| `partner_scope_service`（CR-0084）| **0** | 🔴 **安全 bug 還活著** | 我宣稱「修好 vendor 看全品牌」，但 `resolve_partner_scope` 沒有任何 endpoint 呼叫。既有 brand_b2b statement 端點仍不過濾 → vendor 仍可讀全品牌對帳。**修正函式 = 死碼。** |
| `role_assignment_service`（CR-0071）| **0** | 🔴 高 | SoD 角色指派三段（唯一生產 `UPDATE users.role` 路徑）無 endpoint/UI。SoD 邏輯對但不可達 → 確認生產上角色究竟怎麼改的。 |
| `notification_template_service`（CR-0072）| **0** | 🟡 中 | 對客通知模板核准 gate 無 endpoint，前端無法操作核准。 |
| `payment_service`（CR-0070）| **0** | 🟡 中 | 金流本就 mock-deferred，接線可等正式 provider，但要知道現在前端無付款路徑。 |
| `bom_service`（CR-0078）| **0** | 🟢 低 | Phase I 僅建模型（表 0 筆），接線屬 Phase II。 |
| `facts_erp_sync_service`（CR-0082）| **0** | 🟢 低 | 可能由 cron/internal 觸發，未必需公開 endpoint。 |

**結論**：service 層邏輯（SoD、hash chain、fail-closed 隔離、付款冪等）是對的且測過了 ——
缺的是上面那層薄薄的 router（endpoint + auth dependency）。但在接線前，**這些功能對使用者
不可用、partner 安全 bug 實際未修**。這是我可以動手補的（不像金鑰/CIA 那些卡外部）。

---

## 🔴 P0 — 上線前必做（金錢/安全/資料，全部阻擋上線）

### A 資料地基（最致命，先做）
- **A1. PROD Cloud SQL migration 同步**（無法從本機驗，需你連 PROD）
  - DEV 已套 000~075（schema_migrations 73 列）；記憶顯示 PROD 上次 apply 是 2026-06-16 只到 ~034。
  - 035~075（完工閘/稅務/payments/role SoD/audit hash/partner scope 等 41 支）**極可能 PROD 完全沒套**。
  - **怎麼確認**：cloud-sql-proxy 連 PROD → `gcloud sql backups create` 先備份 → `SELECT max(version) FROM public.schema_migrations`（NULL=連 046 追蹤表都沒）→ 對比 DEV 075 → 補 `./scripts/db/apply-schema-prod.sh` 掃 log ERROR。
  - **風險**：上線整批 `UndefinedTable 500`。DEV 永遠綠看不出來。

- **A2. schema 慣例不一致**（我引入的，已驗證）
  - 既有 finance 表（brand_b2b_statement/reconciliation/settlement）都在 `saas.*`；但我新建的 `payments`、`notification_template` 放在 `public`。
  - **目前不是 500**（service 讀 public、表也在 public、測試過）——但破壞「v2/多租戶表走 saas.*」慣例，未來若有 v2 端點期待 `saas.payments` 會炸，且少了 saas 的 tenant_id 隔離模式。
  - **怎麼確認**：你裁決這兩張表要不要搬到 saas（搬則需 migration + service SQL 改 prefix）。

### B 金流真值與 provider（等外部 + 等簽核）
- **B1. 正式支付 provider**（等金鑰 + 一段開發）：`payment_service` 全 mock，Line Pay 簽章用 hardcode 假密鑰，**apple_pay 三軌之一完全沒 confirm/webhook handler**。需真金鑰 + 商家後台註冊 webhook + 補 apple_pay handler。風險：真客戶付款 webhook 收不到 → 款 stuck/重複請款。
- **B2. 對客售價簽核**（純等你填）：`service_catalog` 32 筆全 `is_mock=true`、0 approved，卻直接寫進對客報價單（法律文件）。逐筆核 esales Q-01~Q-12 後翻 approved。
- **B3. 訂金率/佣金率**（等你裁決）：`deposit_policy`(0.3) / `dispatch_commission`(0.08) 兩個 active config 是 mock 草稿，直接算客戶訂金/師傅佣金。確認後出新 config_version 翻 is_mock=false。
- **B4. 月結拆帳基準裁決**：兩套並存衝突 —— `monthly_settlement` 用 hardcode 80/20；CR-0037 另建 69 筆 `technician_payout_rule`（mock）但 `payout_rule_service` 標 **NOT wired**（重算仍硬編 80% 沒查表）。你裁決統一 80/20 或差異化查表（後者需 Phase II CR）。

### C 安全閘可達性（已驗證的假綠/缺口）
- **C1. partner scope 沒接線**（見上方坦白，🔴）：fix 函式無 endpoint 呼叫 → vendor 看全品牌 bug 仍活。
- **C2. RBAC 角色指派路徑不可達**（已驗證）：`role_assignment_service` 0 router → 確認生產角色怎麼改的（是否有人直接 psql 繞過 SoD）。
- **C3. 撤權後 session/token 失效**（CHANGELOG 自承未實作）：兩瀏覽器登同帳號 → A 降權 → B 舊 session 打高權 API 看是否仍 200。你裁決上線前補 token 撤銷或簽風險接受。
- **C4. SOP publish 家族覆核 gate**（合約 4.4d 紅線，已驗證未接）：`sop_draft_service.adopt_draft` 只查 `status='approved'`，**沒查 family_reviews 是否覆核**。建草稿→admin 核→不做家族覆核→直接 adopt 應該失敗卻會成功。違反=合約終止。
- **C5. config 治理無 RBAC**（已驗證）：`saas.config_namespace.owner_role_codes` **19/19 全空** → 任何登入者可改 payment_gate/discount_policy/completion_policy。用低權帳號試改 payment_gate 看能否成功。你裁決每個 namespace 填哪些角色。

### D AI 紅線（合約 4.4 級，無第二道防線）
- **D1. 真機長對話抽驗**：真 LINE 打 20~30 輪含「拐彎問價/價格藏多輪/誘導複誦客戶金額/混語言錯字繞 regex」，逐則確認無 NTD 數字且轉真人。`redline_gate.py` 已 9/9 但只 9 個固定短句。
- **D2. inline output guardrail 缺口裁決**：`agent/lockcore` 內**無任何 output guardrail**（舊 safety_gate.py 隨重寫刪了），紅線 100% 靠 LLM 自判、無兜底。你二選一：接受無第二道防線上線，或開 CR 走 CIA 補。與 D1 疊加成單點失效。

### E 客戶第一接觸真實通道
- **E1. LINE 進線→AI→轉真人完整鏈**（真機真 reply_token）：真手機發三類訊息（產品問題/詢價退款/連發圖片貼圖文字），對照後台 `/conversations`+`/problem-cards` 同步。CR-0086 live eval 繞過了整條 webhook→reply_token→reply 通道。**與 D1 可用一次真 LINE session 同時覆蓋。**

---

## 🟡 P1 — 業務正確性與隱性缺口
- **P1-1. 師傅 payout 正式值**（Q-09）：69 筆全 mock、0 approved，base_payout/夜間 0.2/急件 0.15 全草稿 → 逐筆簽核。
- **P1-2. 技師品牌授權 fail-open**：`dispatch_service._brand_authorized_ids` 該品牌無授權資料時**不過濾**（fail-open）→ PROD 缺真授權=未授權技師被派去修原廠保固鎖。提供真授權清單 + 裁決是否改 fail-closed。
- **P1-3. 通知模板核准 gate 可達性 + _auto_notify 繞過**：見上方坦白（0 router）。裁決退款/報價金額類通知直發無核准是否可接受。
- **P1-4. debounce runtime 接線裁決**：`inbound_debounce.py` 非測試 runtime 零引用；`line_gateway` 每則即回、圖直接丟。裁決上線前是否接（涉 reply_token 時效）。
- **P1-5. scope/quote/tax 門檻值**：`scope_change_policy`(500/2000/0.5)、`quote_policy`(mock)、`tax_policy`(5% 含稅) → 會計覆核。
- **P1-6. AI 回答業務正確性**：eval 0.560/followup 0.067（單輪+LLM 自評）；領域專家真 LINE 跑 20+ 情境人工評產品知識/派工判斷對不對。

## 🟢 P2 — 體驗/完整性（不阻擋上線，應排期）
- **P2-1. payment_gate 開關**：無 active config → 不檢查付款即派工。與 completion_policy 疊加=金流全程無強制收款點。
- **P2-2. completion_policy 旗標**：`require_payment_proof=false` → 結案不需付款證明，客戶賴帳無攔截。
- **P2-3. discount_policy 正式值**：approval_threshold=10000/cs_max=10%（mock）。
- **P2-4. auto_confirm 48h 自動結案**：active 已開，確認 48h 與排除 hold 單，真跑一次 cron。
- **P2-5. BOM 歸屬規則**：product_model/bom_line DEV 0 筆，owner/cost_attribution/退回期限待填。
- **P2-6. 現金爭議門檻 500**：hardcode，建議移入 M18 config。
- **P2-7. hash chain 偵測排程**：`verify_audit_chain`/`verify_family_review_ledger` 0 router（寫入接了 hash，偵測無觸發路徑）→ 排程定期驗鏈告警。

---

## 最短上線路徑（核心可動的最小確認集，7 項）
若只想先讓「客戶進線→AI/真人→報價→派工→結案→收款」核心鏈真實可動：
1. **A1** PROD migration 同步 + schema 驗證（地基，不過下面全 500）
2. **B1** 正式金流 provider（含補 apple_pay handler）— 等金鑰 + 開發
3. **B2+B3** 對客售價 + 訂金/佣金率簽核轉正式 — 純等你簽核
4. **C1+C2+C5** partner scope + 角色指派 接線 + config RBAC — 我可動手接
5. **C4** SOP 家族覆核 gate — 合約紅線，我可動手接
6. **D1+D2+E1** AI 紅線真機抽驗 + guardrail 裁決 + 客戶進線真機點測（一次真 LINE 覆蓋）
7. **C3** 撤權 token 失效 — 你裁決補或簽風險接受

## 四類缺口誠實歸屬
- **我可動手補（不卡外部）**：C1/C2/C4/C5 接線、partner 安全 enforcement、SOP gate、payment/notif/bom router。← 你說「補」我就做。
- **等外部資源**：B1 金鑰+webhook 註冊+apple_pay handler、P1-6 法務、A1 PROD（需你給 PROD 連線）。
- **等你裁決開關（是非題）**：B4/C3/D2/P1-2/P1-4/P2-1~7。
- **等你逐項簽核（填數字）**：B2/B3/P1-1/P1-5/P2-3。
- **等你親自點一遍（真機）**：D1/E1/P1-6 + 接線後的 C1/C2 可達性複驗。
