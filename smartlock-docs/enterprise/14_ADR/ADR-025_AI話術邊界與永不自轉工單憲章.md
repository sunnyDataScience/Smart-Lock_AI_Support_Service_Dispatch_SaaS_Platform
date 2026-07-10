---
title: "ADR-025: AI 話術邊界與「永不自轉工單」紅線憲章"
version: 1.0
status: active
owner: 平台架構團隊 + 法務
last-updated: 2026-07-10
upstream:
  - docs/architecture/adr/ADR-0047-ai-forbidden-list-as-charter.md
  - docs/architecture/adr/ADR-0048-ai-human-handoff-rules.md
  - docs/architecture/adr/ADR-0063-ai-utterance-boundary.md
---

# ADR-025: AI 話術邊界與「永不自轉工單」紅線憲章

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 · 領域安全憲章 |
| 關聯 ADR | [ADR-011](./ADR-011_Agent整合風格三分類.md)（類別 3 的領域憲章版）· [ADR-015](./ADR-015_工單狀態機核心不變式.md) · [ADR-012](./ADR-012_Agent_Configuration_Studio.md)（受保護層承載本憲章）|

## Context（背景與問題）

AI 客服直接面對真實客戶，其邊界若散落在 prompt、SKILL.md、safety gate code、客服 SOP 各處，每次新增 skill / 新 tool 都要重新對齊，工程 / 法務 / 客服口徑不一致——這是 HITL 邊界漂移的最大來源。AI 越權承諾保固 / 報價 / 退款，一次重大客訴 + 法律風險即可讓品牌信任歸零（誤轉率即使 0.5%，月 1000 單 × NTD 30k 客訴成本 = NTD 15 萬/月量級）。邊界必須是**憲章級明文 + 自動化驗證**，model swap 不稀釋。

## Decision（決策）

### Forbidden List（集中憲章，唯一明文來源）

```yaml
ai_forbidden:
  finance:
    - final_price_commitment        # 不承諾個案最終價格
    - refund_approval               # 不核准退款
    - settlement_modification       # 不改結算
  warranty_legal:
    - warranty_liability_judgment   # 不判定保固責任
    - legal_safety_promise          # 不做法律 / 安全承諾
  operational:
    - convert_to_work_order_direct  # 永不自轉工單（1-click 人審，ADR-015）
    - dangerous_repair_instruction  # 不給危險操作指引（拆電路 / 自行拆鎖）
  data:
    - cross_tenant_data_access      # 不跨租戶取資料
    - pii_disclosure_in_reply       # 回覆不暴露非必要 PII
```

任何項目移出 Forbidden → **必須開新 ADR + 法務簽字**。

### 話術邊界：announce existence, never echo numbers

- **允許**：「客服已準備好您的報價，請點選下方按鈕查看詳細金額與條款。系統報價編號 Q-12345。」——宣告存在 + 引用 quote_id，客戶至 LIFF / Flex Message（system-of-record）看金額。
- **禁止（永久）**：複誦個案 NTD 數字（口語 / Flex body / Push body）：「您的維修費用是 NTD 2,800」❌。
- 一般性**區間**話術允許（「依案件不同，一般落在 NTD 800-1,500 之間」）；但個案 quote 已存在後，不得再以 range 描述本案。
- **Server-side enforce（不依賴 prompt）**：`POST /quotes/{id}:send-to-customer` 雙閘——`sender_role = ai_agent AND quote.state < internal_approved` → `403 AI_FORBIDDEN_FINAL_QUOTE`；`case_type IN [warranty, project]` → `403 AI_FORBIDDEN_WARRANTY_PROJECT`。response 只回 server-generated `flex_message_template_id`——AI 拿 template ID、拿不到原始金額字串，prompt injection 也組不出數字。
- Guardrail：偵測 `NTD <number>` 缺修飾語 → regen；高風險 prefix（「您的維修費用是」）→ regen；token-level price utterance → block + audit。

### 人機交接 7 硬規則（任一觸發 → 強制 `transfer_to_human`，無 LLM judgment 餘地）

| # | 觸發條件 | 判定方式 |
|---|---|---|
| 1 | **急件**（4 類：locked_out / trapped_inside / safety_risk / angry_high_risk）| 關鍵字 + 規則匹配 |
| 2 | **怒客**（情緒分流 ≥ 高）| 情緒分類 ≥ 0.9 |
| 3 | **高額**（quote > 品牌閾值）| 金額閾值（per 品牌合約）|
| 4 | **保固爭議** | 保固判定爭議（對齊 forbidden）|
| 5 | **退款請求** | 客戶提退款 |
| 6 | **法律 / 安全詢問** | 法律 / 安全關鍵字 |
| 7 | **3+ 次未解決** | 對話內 AI 嘗試 ≥ 3 次未解決 |

### 自動 guardrail eval gate

每次部署前跑 ≥ 200 題 regression eval（每條 forbidden + 每條 handoff 規則至少 30 題，含正例 + 反例 + 誘導 injection）；**pass < 95% → deploy block**。Eval set 每季 review。

## Alternatives（考量的選項）

- **A：LLM 自判斷邊界** — 綁特定模型，model swap 重訓，邊界漂移。
- **B：全黑名單關鍵字** — false positive 高，正常對話被誤攔。
- **C：憲章明文 + server-side enforce + 自動 eval（採用）** — 邊界寫進 ADR 與 API 契約，model 無關。

## Consequences（後果）

**正面**：工程 / 法務 / 客服單一口徑；server-side template enforce 使 prompt injection 無法外洩金額；eval gate 量化守線；「永不自轉工單」與 [ADR-015](./ADR-015_工單狀態機核心不變式.md) 不變式③、[ADR-011](./ADR-011_Agent整合風格三分類.md) 類別 3 三處互鎖。
**風險**：轉真人率 +5-10%（vs 純 LLM 自判）；客戶 LIFF 多一跳（由 5s 自助體驗對沖）；eval pipeline 每次 build +5-10 min（可平行化）；規則覆蓋不足的 edge case 漏轉 → 客服手動發現後補入 eval set。
**影響範圍**：agent skill 受保護層（[ADR-012](./ADR-012_Agent_Configuration_Studio.md)）、`POST /quotes/{id}:send-to-customer` 契約、CI eval gate、客服 macro / 培訓。
**重評觸發**：任何 forbidden 項目要開洞 → 新 ADR + 法務 + CEO + 客服主管簽核，本 ADR 為 baseline。

## Status 附註

- 本憲章由 [ADR-012](./ADR-012_Agent_Configuration_Studio.md) 受保護層承載——品牌自服務調校**不可移除 / override** 本憲章任何條目。
- 🔜 規劃中：200 題 eval set 建置 + CI eval gate；情緒分類器準確率 ≥ 90% 驗收；BI「handoff by trigger」分布監控。
- 2026-07-10：200 題 eval + CI gate 已完成（CR-0135，WBS 1.5.1 ✅；nightly live 已掛 2026-07-10）；稽核查實兩缺口——openapi 宣告之 `:send-to-customer` AI 雙閘端點 runtime 不存在、生成後 guard 未接 agent loop（僅 CI 層）→ 立案 CR-0152 待業主裁決（補實作 vs spec 降版）。
