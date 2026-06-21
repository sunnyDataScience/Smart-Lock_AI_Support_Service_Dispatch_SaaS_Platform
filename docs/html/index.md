<!-- 由 html/index.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="container">

<div>

# 🔒 Smart Lock SaaS

<div class="tagline">

智慧鎖 AI 客服與派工平台 — 本地文件導覽中心（反映本 repo 現況）

</div>

<div class="meta">

<span class="badge-green">🛠 實作期 dev_new_arch</span> 📅 2026-06-15 🤖
Agent = LockCore（ADR-0107） 📊 81 ADR · 53 FR · CR-0020~0022 🔗
連結皆本地相對路徑

</div>

<div style="margin-top:16px; font-size:13px; opacity:0.9; background:rgba(255,255,255,0.1); padding:10px 14px; border-radius:6px;">

💡 本頁連結**全部指向本 repo 內 `docs/` 實際檔案**（相對路徑；.md
用編輯器或 GitHub render 開）。 少數標「歷史」的連結（痛點 / 決策面板 /
handoff）仍指外部 spec repo `chatlock_dev_docs`（2026-05-24
規劃凍結版，本 repo 無對應檔）。

</div>

</div>

<div class="stats">

<div class="stat-card">

<div class="label">

AI 準確率

</div>

<div class="value">

≥80%

</div>

<div class="hint">

K1 / 50 題標準集

</div>

</div>

<div class="stat-card">

<div class="label">

自助解決率

</div>

<div class="value">

≥60%

</div>

<div class="hint">

K2 / 上線 3 月後

</div>

</div>

<div class="stat-card">

<div class="label">

合約 4.4(a)

</div>

<div class="value red">

≥90%

</div>

<div class="hint">

負面情緒識別（紅線）

</div>

</div>

<div class="stat-card">

<div class="label">

Forbidden Eval

</div>

<div class="value red">

≥95%

</div>

<div class="hint">

K8 / 200 題 block-deploy

</div>

</div>

<div class="stat-card">

<div class="label">

系統 Uptime

</div>

<div class="value">

≥95%

</div>

<div class="hint">

K7 / 合約 baseline

</div>

</div>

<div class="stat-card">

<div class="label">

ADR 已決

</div>

<div class="value green">

81

</div>

<div class="hint">

ADR-0001 → 0112（含 LockCore 0107 / HITL 0112）

</div>

</div>

</div>

<div class="section" style="border-top: 4px solid var(--green);">

## 📑本專案 HTML 報告（現行・瀏覽器直接開）

以下是本 repo（`Smart-Lock_AI_Support…`）開發過程產出的自包含 HTML
報告， 與本頁同在
`docs/html/`，點擊即相對開啟。**這些反映目前實作狀態**，
有別於下方角色導覽指向的外部規格快照。

<div class="doc-grid">

<div class="doc-card">

<span class="badge policy">操作手冊</span>

#### [LINE 啟動 + 工單觸發手冊 ↗](./agent-line-runbook.html)

<div class="desc">

本機把 agent 接到 LINE 的完整 runbook：API（INTERNAL_API_TOKEN /
AGENT_TENANT_ID）+ Gateway（agent/.env 橋接 + banner 判讀）+ ngrok +
LINE Console；含「LINE 一句話 → AI 草擬卡 → 客服 convert → 工單
NT-xxxxxx」全鏈與 500/400/503/401 排錯表。記憶後端 sqlite/postgres
切換。

</div>

<div class="path">

docs/html/agent-line-runbook.html

</div>

</div>

<div class="doc-card">

<span class="badge baseline">CS AGENT</span>

#### [鎖匠 CS Agent 評測報告 ↗](./agent-eval-report.html)

<div class="desc">

baseline（84 題 overall 0.642）+ 五層驗證框架（L0 紅線 / L1 多輪 / L2
rubric / L3 shadow / L4 KPI）+ 強模型實驗 + 記憶污染教訓。對應會議
Action \#5。

</div>

<div class="path">

docs/html/agent-eval-report.html

</div>

</div>

<div class="doc-card">

<span class="badge wip">CR-0022 測試</span>

#### [CR-0022 真人測試指南 ↗](./cr-0022-manual-test-guide.html)

<div class="desc">

LINE 對話 → AI 草擬問題卡 → 客服人審 → 工單 的 HITL 全鏈手動測試：agent
地端啟動（含 Vertex
憑證）、該傳什麼訊息觸發轉真人、後台哪裡確認、疑難排解。

</div>

<div class="path">

docs/html/cr-0022-manual-test-guide.html

</div>

</div>

</div>

</div>

<div class="section" style="border-top: 4px solid var(--blue);">

## 🚧實作現況（dev_new_arch · 規格快照後的變更）

下方角色導覽 / 文件一覽是**上線前規格**；本區是**實作期**真正動到的東西
—— Agent 重寫成 LockCore、三個 Change Request、CS Agent
評測框架、整體完成度。連結皆本地。

<div class="doc-grid">

<div class="doc-card">

<span class="badge policy">ADR-0107</span>

#### [Agent = LockCore 架構 ↗](../../agent/README.md)

<div class="desc">

2026-06-04 agent 一次性重寫：LockCore（fork nanobot）+ Agent Skills
標準 + 單一 LiteLLMProvider。捨棄 ReAct/LangGraph。

</div>

<div class="path">

agent/README.md · agent/lockcore/VENDOR.md

</div>

</div>

<div class="doc-card">

<span class="badge wip">CR-0022</span>

#### [LINE → 工單 HITL ↗](../4-exploration/CR-0022-line-to-work-order-hitl.md)

<div class="desc">

escalation → AI 草擬問題卡 → 客服人審 → 工單（ADR-0112；AI
永不自轉）。測試指南見上方 HTML 報告。

</div>

<div class="path">

docs/4-exploration/CR-0022-line-to-work-order-hitl.md

</div>

</div>

<div class="doc-card">

<span class="badge baseline">CR-0020 / 0021</span>

#### [公單號 + 五角色隔離 ↗](../4-exploration/CR-0020-wo-document-numbering.md)

<div class="desc">

CR-0020 公單號改地區前綴（NT-000001，ADR-0110）；CR-0021
五角色帳號權限隔離（ADR-0111）。

</div>

<div class="path">

docs/4-exploration/CR-0020 · CR-0021

</div>

</div>

<div class="doc-card">

<span class="badge baseline">QA</span>

#### [CS Agent 五層驗證框架 ↗](../qa/cs-agent-eval-framework.md)

<div class="desc">

L0 紅線 / L1 多輪 / L2 rubric / L3 shadow / L4 KPI。baseline
數據見上方「CS Agent 評測報告」HTML。

</div>

<div class="path">

docs/qa/cs-agent-eval-framework.md

</div>

</div>

<div class="doc-card">

<span class="badge frozen">STATUS</span>

#### [系統完成度總覽 ↗](../../web/docs/system-completion-status.md)

<div class="desc">

前端 / 後端 / Realtime / Workflow / 架構遷移整體進度，每輪開發同步更新。

</div>

<div class="path">

web/docs/system-completion-status.md

</div>

</div>

<div class="doc-card">

<span class="badge frozen">ADR × 81</span>

#### [ADR 索引（本地 81 條）↗](../architecture/adr/INDEX.md)

<div class="desc">

ADR-0001 → 0112，含實作期新增（LockCore 0107、公單號 0110、五角色
0111、HITL 0112）。

</div>

<div class="path">

docs/architecture/adr/INDEX.md

</div>

</div>

</div>

</div>

<div class="section">

## 🎯產品定位

把電子鎖售後從「靠老師傅腦袋」變成「LINE 進來 → AI 接 → 結構化資料 →
可分潤」。V1.0 上線 AI 客服 + 後台（W17）、V2.0 接派工帳務（W31）。

### 解什麼問題

- 新客服訓練成本高（3 個月才上手）
- 紙本對帳一個月吵一次
- 派錯案件師傅空跑就賠錢
- 老師傅離職 know-how 帶走

### 給誰用

- **LINE 消費者**（V1 同時 50 人 / V2 100 人 / 3-5 年 30 萬戶）
- **簽約師傅**（V2 目標 500 人 / 22 縣市）
- **客服 + 管理員**（甲方營運團隊 5-15 人）
- **家族覆核員**（合約規定的稽核角色）

</div>

<div class="section">

## 🚨合約紅線（違反 = §9 終止）

<div class="red-lines">

### ⚠️ 這 7 條 V1.0 必交 — 違反任一條，甲方可依合約 §9 終止

1.  **合約 4.4(a)** 負面情緒識別 ≥ 90%（UAT + 持續監控）
2.  **合約 4.4(d)** 家族覆核紀錄 → 採 `Option A 降級履約`（event log + 7
    日 dispute
    window）<a href="../governance/legal-memo-retrospective-review.md"
    target="_blank" rel="noopener">法務備忘</a>
3.  **合約 9.3** ProblemCard 完整率 ≥ 85%
4.  **合約 SOW 2.1(4)** AI 影像辨識禁用（violation count = 0）
5.  **AI Forbidden Eval ≥ 95%** 每次 deploy（block-deploy gate）
6.  **跨租戶資料零洩漏**（ADR-0030 tenant_id propagation）
7.  **GDPR forget ≤ 7 天**（OR customer notice within 7d）

</div>

</div>

<div class="section">

## 📖角色導覽 — 你是誰？從哪入手？

點選你的角色，看推薦閱讀路徑 + 該角色該看的文件。

<div class="role-tabs">

👔 業主 / CEO

📋 PM / BA

🛠 工程師

👤 SA / 系統分析

🏛 架構師 / SD

🗄 DBA

🧪 QA / 測試

🚀 DevOps / SRE

⚖️ 法務 / DPO

🤖 AI Specialist

</div>

<div class="role-panel active" data-role="owner">

<div class="intro">

💡 你是業主 / CEO，想做投資 / scope / KPI 決策。最該看的是 PRD 主檔 +
業主決策歷程。

</div>

1.  <a href="../prd/smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>PRD v2.2 主檔</strong></a> — 一頁讀完 + KPI +
    範圍 + 風險（\< 5 分鐘）
2.  <a
    href="https://htmlpreview.github.io/?https://github.com/Zenobia000/chatlock_dev_docs/blob/main/archive/meetings/2026-05-22/decision-dashboard.html"
    target="_blank" rel="noopener"><strong>5/22 決策面板</strong></a> —
    24 條 ADR
    互動式圈選結果<span style="color:var(--ink-mute);font-size:12px;">·
    🔗外部 spec 快照</span>
3.  <a
    href="https://github.com/Zenobia000/chatlock_dev_docs/blob/main/archive/strategy/PAIN-POINTS-SUMMARY-2026-05-21.md"
    target="_blank" rel="noopener"><strong>F1~F7 失敗劇本</strong></a> —
    Pre-mortem 戰略視角
4.  <a href="../governance/stakeholders.md" target="_blank"
    rel="noopener"><strong>Stakeholder Map</strong></a> — 18
    角色影響力矩陣

</div>

<div class="role-panel" data-role="pm">

<div class="intro">

💡 你是 PM / BA，要 align scope + KPI + stakeholder。

</div>

1.  <a href="../prd/smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>PRD v2.2</strong></a> — 30 秒 TL;DR + KPI
    K1~K9 + 範圍 + 風險 R-F1~F7
2.  <a href="../analysis/system-spec-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>System Spec</strong></a> — 18 UC + 14 物件 +
    7 狀態機
3.  <a href="../ux/user-flow-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>User Flow</strong></a> — 4 主流程 + 12 edge
    case + state coverage
4.  <a
    href="https://github.com/Zenobia000/chatlock_dev_docs/blob/main/archive/strategy/PAIN-POINTS-SUMMARY-2026-05-21.md"
    target="_blank" rel="noopener"><strong>痛點 + Pre-mortem</strong></a>

</div>

<div class="role-panel" data-role="engineer">

<div class="intro">

💡 你是新加入的工程師，要快速進入產品全貌。先看產品再看架構，最後從
handoff 開工。

</div>

1.  <a href="../prd/smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>PRD v2.2</strong></a> — 先讀產品定位
2.  <a href="../architecture/ARCH-0001-architecture-overview.md"
    target="_blank" rel="noopener"><strong>ARCH-0001</strong></a> — C4
    L1/L2 架構
3.  <a href="../architecture/c4-l3-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>C4 L3</strong></a> — Component + bounded
    context
4.  <a href="../architecture/adr/INDEX.md" target="_blank"
    rel="noopener"><strong>ADR 索引（81 條）</strong></a> —
    重大決策都在這
5.  <a
    href="https://github.com/Zenobia000/chatlock_dev_docs/blob/main/specs/smart-lock-saas/handoff.md"
    target="_blank" rel="noopener"><strong>Handoff</strong></a> — coding
    agent 入口（W1-W17
    建構順序）<span style="color:var(--ink-mute);font-size:12px;">·
    🔗外部 spec 快照</span>

</div>

<div class="role-panel" data-role="sa">

<div class="intro">

💡 你是 SA / 系統分析師，要寫 acceptance criteria + 拆 use case。

</div>

1.  <a href="../analysis/system-spec-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>System Spec</strong></a> — 14 物件 + 7
    狀態機 + 64 BR + 18 UC + 21 events + 14 integrations
2.  <a href="../analysis/fr/" target="_blank" rel="noopener"><strong>25 條
    FR</strong></a> — FR-0001~0025 個別 spec
3.  <a href="../analysis/br/BR-AUDIT-007-family-reviewer-event-log.md"
    target="_blank" rel="noopener"><strong>BR-AUDIT-007</strong></a> —
    家族覆核 event log 三要件
4.  <a href="../ux/user-flow-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>User Flow</strong></a> — Edge case + State
    coverage 對應

</div>

<div class="role-panel" data-role="arch">

<div class="intro">

💡 你是架構師 / SD，要評估 NFR / boundary / failure mode / API
contract。

</div>

1.  <a href="../architecture/ARCH-0001-architecture-overview.md"
    target="_blank" rel="noopener"><strong>ARCH-0001</strong></a> — C4
    L1/L2 + 五層 Agent 架構
2.  <a href="../architecture/c4-l3-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>C4 L3</strong></a> — 7 bounded context（AI
    Agent / API / DGS / KB / Admin / Cron）
3.  <a href="../architecture/nfr-matrix-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>NFR Matrix</strong></a> — 9 維度 + Failure
    mode 12 條
4.  <a href="../architecture/adr/" target="_blank" rel="noopener"><strong>81
    條 ADR</strong></a> — 重點：ADR-0030 / 0042 / 0060 / 0061 /
    VCH-001/002 / 0107 / 0112
5.  <a href="../architecture/api/openapi.yaml" target="_blank"
    rel="noopener"><strong>OpenAPI v1.0</strong></a> — V1 endpoints + V2
    :action 預留

</div>

<div class="role-panel" data-role="dba">

<div class="intro">

💡 你是 DBA，最該盯 migration / PII / index / lock contention。

</div>

1.  <a href="../architecture/data/erd.md" target="_blank"
    rel="noopener"><strong>ERD</strong></a> — Schema + Partition + RLS +
    Outbox + Migration 雙寫期
2.  <a href="../architecture/adr/ADR-0051-evidence-retention-policy.md"
    target="_blank" rel="noopener"><strong>ADR-0051 Evidence
    Retention</strong></a> — 1y/RMA+3y/eternal/GDPR 7d
3.  <a href="../architecture/adr/ADR-VCH-002-voucher-retention-7y.md"
    target="_blank" rel="noopener"><strong>ADR-VCH-002 Voucher
    7y</strong></a> — hot 2y PG + cold 5y Glacier + yearly+monthly
    partition
4.  <a
    href="../architecture/adr/ADR-PII-002-data-minimization-schema-ci-double-defense.md"
    target="_blank" rel="noopener"><strong>ADR-PII-002</strong></a> —
    schema CHECK + CI lint 雙層防線

</div>

<div class="role-panel" data-role="qa">

<div class="intro">

💡 你是 QA / Test Lead，最該寫 negative case + exit criteria。

</div>

1.  <a href="../qa/test-plan-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>Test Plan</strong></a> — 9 test levels + KPI
    scenarios + 8 BDD + 200 Forbidden Eval
2.  <a href="../analysis/system-spec-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>System Spec §3</strong></a> — 64 條 BR
    catalog（每條配對應 test）
3.  <a href="../ux/user-flow-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>UX Flow</strong></a> — Edge case → BDD
    scenario 對應

</div>

<div class="role-panel" data-role="ops">

<div class="intro">

💡 你是 DevOps / SRE，要管 SLO / pipeline / rollback / incident。

</div>

1.  <a href="../ops/runbook-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>Runbook</strong></a> — 11 incident
    playbooks + 3-layer kill switch + pipeline
2.  <a href="../ops/release-readiness.md" target="_blank"
    rel="noopener"><strong>Release Readiness</strong></a> — V1 W17
    launch checklist + rollback trigger
3.  <a href="../architecture/nfr-matrix-smart-lock-saas.md" target="_blank"
    rel="noopener"><strong>NFR Matrix</strong></a> §SLI/SLO + §10
    Failure Mode
4.  <a
    href="../architecture/adr/ADR-0061-data-governance-service-boundary.md"
    target="_blank" rel="noopener"><strong>ADR-0061 DGS</strong></a> —
    獨立 service 99.95% SLO

</div>

<div class="role-panel" data-role="legal">

<div class="intro">

💡 你是法務 / DPO / 合規，最該盯合約 4.4 + 個資法 + GDPR + 稅務。

</div>

1.  <a href="../governance/legal-memo-retrospective-review.md"
    target="_blank" rel="noopener"><strong>法務一頁式詮釋備忘</strong></a>
    — §4.4(d) 履約方式詮釋（不需修約）
2.  <a href="../policy/br-pii-001.rego" target="_blank"
    rel="noopener"><strong>BR-PII-001 OPA Rego</strong></a> — PII
    governance policy artifact（CODEOWNERS @legal @dpo）
3.  <a href="../architecture/adr/ADR-VCH-001-platform-as-voucher-keeper.md"
    target="_blank" rel="noopener"><strong>ADR-VCH-001 Voucher
    Keeper</strong></a> — 平台不是發票開立人
4.  <a href="../architecture/adr/ADR-0042-rbac-four-tier-principle.md"
    target="_blank" rel="noopener"><strong>ADR-0042 RBAC</strong></a> +
    <a href="../architecture/adr/ADR-0050-evidence-visibility-matrix.md"
    target="_blank" rel="noopener">ADR-0050</a> +
    <a href="../architecture/adr/ADR-0051-evidence-retention-policy.md"
    target="_blank" rel="noopener">ADR-0051</a>
5.  <a
    href="../architecture/adr/ADR-PII-002-data-minimization-schema-ci-double-defense.md"
    target="_blank" rel="noopener"><strong>ADR-PII-002</strong></a> —
    個資法 §5 資料極小化

</div>

<div class="role-panel" data-role="ai">

<div class="intro">

💡 你是 AI Specialist，要設計 prompt + skill + guardrail + eval。

</div>

1.  <a href="../architecture/adr/ADR-0028-ai-employee-charter.md"
    target="_blank" rel="noopener"><strong>ADR-0028 AI Employee
    Charter</strong></a> — Forbidden 清單
2.  <a href="../architecture/adr/ADR-0047-ai-forbidden-list-as-charter.md"
    target="_blank" rel="noopener"><strong>ADR-0047 200 題 Eval</strong></a>
    — block-deploy gate
3.  <a href="../architecture/adr/ADR-0048-ai-human-handoff-rules.md"
    target="_blank" rel="noopener"><strong>ADR-0048 轉真人 7
    條硬規則</strong></a>
4.  <a href="../architecture/adr/ADR-0055-skill-llm-decoupling-contract.md"
    target="_blank" rel="noopener"><strong>ADR-0055 SKILL↔︎LLM
    解耦</strong></a>
5.  <a
    href="../architecture/adr/ADR-0057-rag-document-retrieval-not-prompt.md"
    target="_blank" rel="noopener"><strong>ADR-0057 RAG</strong></a> —
    規則走 RAG 不寫 prompt

</div>

</div>

<div class="section">

## 🎯V1.0 / V2.0 範圍

<div class="phases">

<div class="phase v1">

### ✅ V1.0 — AI 客服 + 合規 <span class="week">W1-W17</span>

- LINE Bot AI 客服（文字 / 圖 / 對話記憶 / 情緒分流）
- ProblemCard 自動產 + 主動引導
- 三層解決（案例庫 → 手冊 RAG → 真人）
- Admin Panel + RBAC 四層
- 合約 4.4 整套（90% 情緒 / 家族覆核 event log / 個資保留期）
- 多甲方 schema 預埋（ADR-0060）
- DGS 獨立服務（ADR-0061）
- AI Forbidden 200 題 Eval block-deploy
- Voucher 內部憑證（ADR-VCH-001）

</div>

<div class="phase v2">

### 🚀 V2.0 — 派工 + 帳務 <span class="week">W18-W31</span>

- 師傅 Web App（案件池 / 接單 / ETA / 完工 / 帳戶）
- 智慧派工（自動匹配 + 手動指派）
- 報價引擎（標準矩陣 + 特殊加價）
- 帳務系統（7 帳本 / 墊款 / 月結 / 退款分層）
- Admin V2.0（生命週期 / 客訴 / 技師管理 / ChangeRequest）
- Voucher export endpoint → V2.1（電子發票 / ERP CSV）

</div>

</div>

</div>

<div class="section">

## 🏛業主決策歷程

從痛點到 PRD v2.2 frozen 的完整決策鏈。

<div class="timeline">

<div class="timeline-item done">

<div class="date">

2026-05-21

</div>

<div class="title">

Pre-mortem 戰略

</div>

<div class="desc">

F1~F7 失敗劇本 + §A-§G CEO 視角 → <a
href="https://github.com/Zenobia000/chatlock_dev_docs/blob/main/archive/strategy/PAIN-POINTS-SUMMARY-2026-05-21.md"
target="_blank" rel="noopener">PAIN-POINTS</a>

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-22

</div>

<div class="title">

業主拍板會議 + 29 條 ADR accepted

</div>

<div class="desc">

ADR-0031~0059 → <a
href="https://htmlpreview.github.io/?https://github.com/Zenobia000/chatlock_dev_docs/blob/main/archive/meetings/2026-05-22/decision-dashboard.html"
target="_blank" rel="noopener">互動式 decision-dashboard.html</a>

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-22

</div>

<div class="title">

PRD v2 draft + Lane A critique

</div>

<div class="desc">

PM/PO/BA 三 persona 並行 → 4 CB + 5 conflicts → 升 Lane B

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-22

</div>

<div class="title">

3 場 Forum-Lite 收斂

</div>

<div class="desc">

Contract Template Option C++ / K2 Option A++ / DGS Option C++

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-22

</div>

<div class="title">

PRD v2.1 frozen + CEO Verdict

</div>

<div class="desc">

5 conflicts 全裁決 + Epic 4 → V1.5

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-24

</div>

<div class="title">

2 場 Roundtable + 11 條 OQ 業主答覆

</div>

<div class="desc">

Option A 降級履約 + Voucher Keeper 路線 + 7y retention

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-24

</div>

<div class="title">

PRD v2.2 frozen + 全面 cascade

</div>

<div class="desc">

7 個新 ADR（PII-002 / VCH-001/002 / PIVOT-001 / BR-AUDIT-007 + 0060/0061
update）

</div>

</div>

<div class="timeline-item done">

<div class="date">

2026-05-25

</div>

<div class="title">

文件大重構：docs/ = SoT

</div>

<div class="desc">

0/2/3/4 → docs/ + archive/ 整併；ADR 從 3 處合到 docs/architecture/adr/
66 條

</div>

</div>

<div class="timeline-item current">

<div class="date">

W1-W17

</div>

<div class="title">

V1.0 開發中

</div>

<div class="desc">

→ 開發團隊起手式 <a
href="https://github.com/Zenobia000/chatlock_dev_docs/blob/main/specs/smart-lock-saas/handoff.md"
target="_blank" rel="noopener">specs/smart-lock-saas/handoff.md</a>

</div>

</div>

</div>

</div>

<div class="section">

## 🗂所有文件一覽

<div class="doc-grid">

<div class="doc-card">

<span class="badge frozen">v2.2 FROZEN</span>

#### PRD 主檔

<div class="desc">

產品定位 / KPI / Scope / 風險 / OQ 全 closed

</div>

<div class="path">

<a href="../prd/smart-lock-saas.md" target="_blank"
rel="noopener">prd/smart-lock-saas.md</a>

</div>

</div>

<div class="doc-card">

<span class="badge baseline">BASELINE</span>

#### SOW / BIZ / DISC

<div class="desc">

合約聲明書 + 商業架構 + Discovery snapshot

</div>

<div class="path">

prd/SOW-0001 · BIZ-0001 · DISC-0001

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### User Flow

<div class="desc">

4 主流程 + 12 edge case + state coverage + WCAG 2.2 AA

</div>

<div class="path">

<a href="../ux/user-flow-smart-lock-saas.md" target="_blank"
rel="noopener">ux/user-flow-smart-lock-saas.md</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### System Spec

<div class="desc">

14 物件 + 7 狀態機 + 64 BR + 18 UC + 21 events

</div>

<div class="path">

<a href="../analysis/system-spec-smart-lock-saas.md" target="_blank"
rel="noopener">analysis/system-spec-smart-lock-saas.md</a>

</div>

</div>

<div class="doc-card">

<span class="badge baseline">BASELINE × 25</span>

#### Functional Requirements

<div class="desc">

FR-0001~0025 個別 spec

</div>

<div class="path">

<a href="../analysis/fr/" target="_blank"
rel="noopener">analysis/fr/</a>

</div>

</div>

<div class="doc-card">

<span class="badge wip">WIP</span>

#### Business Rules

<div class="desc">

BR-AUDIT-007 Family Reviewer event log 三要件

</div>

<div class="path">

<a href="../analysis/br/" target="_blank"
rel="noopener">analysis/br/</a>

</div>

</div>

<div class="doc-card">

<span class="badge baseline">BASELINE</span>

#### 架構主檔 (C4 L1/L2)

<div class="desc">

系統情境圖 + Container view + DDD 戰略

</div>

<div class="path">

<a href="../architecture/ARCH-0001-architecture-overview.md"
target="_blank" rel="noopener">architecture/ARCH-0001...</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### C4 L3 Component

<div class="desc">

7 bounded context + failure mode + module boundary

</div>

<div class="path">

<a href="../architecture/c4-l3-smart-lock-saas.md" target="_blank"
rel="noopener">architecture/c4-l3-...</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### NFR Matrix

<div class="desc">

9 NFR 維度 + 12 failure mode + 4 SLI

</div>

<div class="path">

<a href="../architecture/nfr-matrix-smart-lock-saas.md" target="_blank"
rel="noopener">architecture/nfr-matrix-...</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">本地 × 81</span>

#### Architecture Decision Records

<div class="desc">

ADR-0001 → 0112（規格 66 + 實作期新增 LockCore/公單號/五角色/HITL 等）

</div>

<div class="path">

<a href="../architecture/adr/INDEX.md" target="_blank"
rel="noopener">architecture/adr/INDEX.md</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### OpenAPI v1.0

<div class="desc">

V1 endpoints + V2 :action 預留 + 12 error codes

</div>

<div class="path">

<a href="../architecture/api/openapi.yaml" target="_blank"
rel="noopener">architecture/api/openapi.yaml</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### ERD

<div class="desc">

Schema + Partition + RLS + Outbox + 7y retention

</div>

<div class="path">

<a href="../architecture/data/erd.md" target="_blank"
rel="noopener">architecture/data/erd.md</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### Test Plan

<div class="desc">

9 levels + KPI scenarios + 8 BDD + 200 Forbidden Eval

</div>

<div class="path">

<a href="../qa/test-plan-smart-lock-saas.md" target="_blank"
rel="noopener">qa/test-plan-...</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### Runbook

<div class="desc">

11 incident playbooks + 3-layer kill switch + pipeline

</div>

<div class="path">

<a href="../ops/runbook-smart-lock-saas.md" target="_blank"
rel="noopener">ops/runbook-...</a>

</div>

</div>

<div class="doc-card">

<span class="badge frozen">FROZEN</span>

#### Release Readiness

<div class="desc">

V1 W17 launch checklist + rollback trigger

</div>

<div class="path">

<a href="../ops/release-readiness.md" target="_blank"
rel="noopener">ops/release-readiness.md</a>

</div>

</div>

<div class="doc-card">

<span class="badge policy">POLICY</span>

#### OPA Rego Policy

<div class="desc">

BR-PII-001 個資治理決策樹（CODEOWNERS @legal @dpo）

</div>

<div class="path">

<a href="../policy/br-pii-001.rego" target="_blank"
rel="noopener">policy/br-pii-001.rego</a>

</div>

</div>

<div class="doc-card">

<span class="badge legal">LEGAL</span>

#### 法務一頁式詮釋備忘

<div class="desc">

合約 §4.4(d) 履約方式 = retrospective event log，不需修約

</div>

<div class="path">

<a href="../governance/legal-memo-retrospective-review.md"
target="_blank" rel="noopener">governance/legal-memo-...</a>

</div>

</div>

<div class="doc-card">

<span class="badge baseline">REFERENCE</span>

#### Stakeholder Map

<div class="desc">

18 角色四層 RBAC + influence × interest 矩陣

</div>

<div class="path">

<a href="../governance/stakeholders.md" target="_blank"
rel="noopener">governance/stakeholders.md</a>

</div>

</div>

</div>

</div>

Smart Lock SaaS · 本地文件導覽中心 · 規格快照 PRD v2.2 (2026-05-24) +
實作期 dev_new_arch (2026-06-15)

產出 by <a href="https://github.com/Zenobia000/Architecture_Autopilot"
target="_blank" rel="noopener">DevTeam Harness</a> · 單一事實 in
<a href="../" target="_blank" rel="noopener">docs/</a>

</div>
