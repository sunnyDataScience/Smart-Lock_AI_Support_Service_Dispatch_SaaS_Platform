<!-- 由 _archive/governance/pending-business-decisions-2026-06-06.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="container">

# 業主待裁決事項清單

<div class="subtitle">

backend-coder agent 已飽和（73 merges / WBS **98.7%**）。**2026-06-06
業主已裁決事項 2 + 3**（皆選維持現狀），剩 2 項待 sign-off。

</div>

<div class="owner-only-banner"
style="background: linear-gradient(135deg, #e8f5e9 0%, #f0fdf4 100%); border-color: #34c759;">

## ✅ 業主已裁決（2026-06-06）— 兩項皆選「維持現狀」

以下 2 項本為「只能業主親自決定（合規/scope 取捨）」，已於
**2026-06-06** 完成裁決，均選擇**維持現狀 (deferred-accepted)**，不需
BUILD。

1.  **事項 2 — Reconciliation 雙簽 UX rework**
    <span class="owner-only-tag"
    style="background: #34c759;">已裁決</span>\
    <span style="font-size: 13px; font-weight: normal; color: #424245;">
    ✅ 維持現狀（同人雙簽 + audit log）— audit_log + change_request
    作合規補強，接受 Sox-like「不嚴格不同人」風險 </span>
2.  **事項 3 — 計價引擎 GUI** <span class="owner-only-tag"
    style="background: #34c759;">已裁決</span>\
    <span style="font-size: 13px; font-weight: normal; color: #424245;">
    ✅ 維持 SQL config + audit log — 規則由 DBA 透過 SQL +
    change_request 維護，認定改動頻率低 + 不開 GUI </span>

📈 兩項裁決推進 WBS 從 98.5% → **98.7%**（Flow 6/13 EX5 + Phase 7 收
100%）。

</div>

<div class="summary">

## 📊 總覽

<div class="summary-grid">

<div class="summary-card">

<div class="label">

原待決事項

</div>

<div class="value">

4 項

</div>

</div>

<div class="summary-card">

<div class="label">

已裁決

</div>

<div class="value" style="color: #34c759;">

2 項 ✅

</div>

</div>

<div class="summary-card">

<div class="label">

剩待決

</div>

<div class="value" style="color: #ff9500;">

2 項

</div>

</div>

<div class="summary-card">

<div class="label">

產生日期

</div>

<div class="value">

2026-06-06

</div>

</div>

</div>

</div>

<div class="wbs-flow">

## 📈 WBS 完成度推進路徑（98.5% → 100%）

2026-06-06 業主裁決 2 項推到 98.7%。剩 1.3% 拆成 4 區段，每段需要不同
owner 解決：

<div class="wbs-bar">

<div class="done" style="width: 98.7%;">

已完成 98.7%（backend MVP + 工具鏈 + 業主 2 項裁決）

</div>

<div class="stage-1" style="width: 0.3%;">

</div>

<div class="stage-2" style="width: 0.5%;">

</div>

<div class="stage-3" style="width: 0.5%;">

</div>

</div>

<div class="wbs-legend">

<span class="swatch" style="background:#34c759;"></span>98.7% 完成（73
merges + 業主 2 項裁決） <span class="swatch"
style="background:#ff9500;"></span>+0.3% 業主剩 2 項裁決（事項 1 P4
Stage 7 + 事項 4 A37） <span class="swatch"
style="background:#ffcc00;"></span>+0.5% Web Sprint 1-5 + Production env
<span class="swatch" style="background:#5ac8fa;"></span>+0.5% UAT 期程 +
業務 sign-off

</div>

| 區段 | 解鎖條件 | WBS 推進 | Owner |
|----|----|----|----|
| **業主裁決事項 2 + 3** ✅ | 2026-06-06 已決：皆維持現狀 | 98.5% → **98.7%** | 👤 業主（已完成） |
| **業主裁決剩 2 項** | 事項 1 P4 Stage 7 + 事項 4 A37 drawer | 98.7% → **99.0%** | 👤 業主 |
| **Web Sprint 1-5 BUILD** | 9 FR page 對接 + e2e active | 99.0% → **99.3%** | 💻 Web dev |
| **Production env 部署** | Migration apply + Lifespan + 30 day 觀察 | 99.3% → **99.7%** | 🛠 DBA + Ops |
| **UAT 10 案執行** | 9 FR + Ops drill 全 Pass + 業主簽 | 99.7% → **100%** | 📋 業務 + QA |

</div>

<div class="decision critical">

### 1. P4 Stage 7 — v1 router 刪除批准

<div class="meta">

<span class="badge critical">CRITICAL</span>
<span class="badge blocker">阻擋 WBS 1%</span> Owner: 業主 + Tech Lead
狀態: blocked — 需 30 day production 0-traffic 觀察 + 業主簽

</div>

<div class="section-label">

📂 來源文件

</div>

- `docs/_audit/P4-cutover-v1-caller-inventory-2026-06-05.md` — v1 caller
  清查盤點
- `docs/_audit/P4-stage-2-7-prep-checklists.md` §7 — Stage 7 進入條件
- `docs/_audit/P4-progress-dashboard.md` — 階段進度總覽
- `docs/_ops/wbs-100-closeout-plan.md` §2.1
- Production deprecation hit log — 待 Stage 6 部署後 30 day 收集

<div class="section-label">

⚡ 影響範圍

</div>

| 層面 | 影響 |
|----|----|
| v1 API endpoint | ~41 個 endpoint 命運 — 刪除 / 永久 410 / 延期 |
| Backend code | `api/routers/*_v1.py` 整批檔案命運 + auth flattening |
| Web 端 | 剩 41 個 v1 caller 必須完成遷 v2 才能執行 |
| Agent | P4-T1 batch (refunds/warranty/problem-cards) 需確認 0 traffic |
| 對外文件 | OpenAPI / API 文件 v1 段全廢 |
| 監控 | deprecation middleware + hit metrics endpoint 可一併撤 |

<div class="section-label">

🎯 決策選項

</div>

1.  **直接刪 v1 router** <span class="recommend-tag">推薦</span>\
    前提：30 day production 觀察真正 0 traffic。完成 P4 全部
    cutover，架構 v2 single-track。
2.  **留 v1 router 但永久 410 Gone**\
    保險作法：仍保留 routing 表但所有 v1 endpoint 直接回 `410 Gone` +
    log。可隨時恢復若客戶投訴。
3.  **延期觀察至 60 day**\
    保守選項：若 30 day 觀察期有 sporadic traffic，延長至 60 day
    確認真停。

<div class="wbs-impact">

**📈 完成後 WBS 推進**：架構遷移從 ~88% → 95%（Phase 9 P4 收尾），整體
+0.2% 至約 98.7%

</div>

</div>

<div class="decision minor" style="border-left-color: #34c759;">

### 2. Reconciliation 雙簽 UX rework <span style="background: #34c759; color: white; font-size: 12px; padding: 3px 10px; border-radius: 4px; margin-left: 8px; vertical-align: middle;">✅ 業主已決 2026-06-06</span>

<div class="meta">

<span class="badge minor">DEFERRED-ACCEPTED</span> 業主決議: 維持現狀
(同人雙簽 + audit log) 狀態: ✅ 已收 100%

</div>

<div class="section-label">

📂 來源文件

</div>

- `docs/_audit/CR-0018-flow13-ex5-reconciliation-exception-cia.md` —
  recon 例外 CIA
- `docs/_ops/wbs-100-closeout-plan.md` §2.2
- Flow 6 reconciliation deep audit（業主早期表態 dual-sign UI 缺口）
- `api/services/reconciliation_service.py` — 現行 dual-sign 邏輯

<div class="section-label">

⚡ 影響範圍

</div>

| 層面 | 影響 |
|----|----|
| 合規 / 內控 | Sox-like 雙簽是否真正落實「不同人」原則 — legal 依據 |
| Web UI | `web/src/app/admin/recon-exceptions/*` 整段 UX 重做或維持 |
| Backend | `reconciliation_service.py` dual-sign 邏輯可能加 `same_user_forbidden` 強制驗證 |
| 稽核 | `approval_chain` JSONB audit 既有，但若加 cooling-off 需新 timestamp 欄 |
| WBS | 影響 Phase II 7 + Flow 13 EX5 完成度認定 |

<div class="section-label">

🎯 決策選項

</div>

1.  **維持現狀（同人雙簽 + audit log）**\
    Status quo：技術上允許同人簽，audit_log 保留
    trail。最便宜，但合規風險。
2.  **強制不同人（A 提案 → B 核准）+ 改 UI 流程**\
    合規嚴格：backend `DUAL_SIGN_SAME_USER 409` 強制驗 actor_user_id
    不同。Web UI 重做為兩階段表單。
3.  **加 timestamp gap（最少 5 分鐘）模擬 cooling-off**\
    折衷：同人仍可但需間隔。技術簡單但合規效果弱於選項 2。

<div class="wbs-impact">

**📈 完成後 WBS 推進**：Flow 6 / Flow 13 EX5 收尾 100%，整體 +0.1% 至約
98.6%

</div>

</div>

<div class="decision minor" style="border-left-color: #34c759;">

### 3. 計價引擎 GUI <span style="background: #34c759; color: white; font-size: 12px; padding: 3px 10px; border-radius: 4px; margin-left: 8px; vertical-align: middle;">✅ 業主已決 2026-06-06</span>

<div class="meta">

<span class="badge minor">DEFERRED-ACCEPTED</span> 業主決議: 維持 SQL
config + audit log 狀態: ✅ 已收 100%

</div>

<div class="section-label">

📂 來源文件

</div>

- `SQL/migrations/004-config-m18.sql` — pricing_rule_canary 現行機制
- `api/routers/pricing_rules_v2.py` — Track B S4 已建 CRUD +
  change_request 審計
- `api/services/pricing_v2_service.py` — 計算邏輯
- `docs/_ops/wbs-100-closeout-plan.md` §2.3
- `docs/architecture/adr/ADR-0046-pricing-rules.md`

<div class="section-label">

⚡ 影響範圍

</div>

| 層面     | 影響                                                          |
|----------|---------------------------------------------------------------|
| Web 工時 | 10 天（最小 GUI）/ 30 天（全功能編輯器）                      |
| 業務操作 | 規則調整門檻 — DBA SQL（高） vs admin GUI（低）               |
| 變更風險 | GUI 越強大 → 業務誤改規則風險越大 → 需 canary % slider + 預檢 |
| 稽核     | change_request audit 已就緒，GUI 介面同等需求                 |
| WBS      | Phase 7 會計 / Phase 9 P4 都不依賴；屬於獨立增量              |

<div class="section-label">

🎯 決策選項

</div>

1.  **維持 SQL config + audit log**
    <span class="recommend-tag">推薦（MVP）</span>\
    最便宜：規則由 DBA 透過 SQL 改，change_request
    記錄。適合「規則改動頻率低」場景。
2.  **開最小 GUI（rule list + canary % slider）**\
    ~10 天 web dev。業務人員可看清單 + 微調 canary
    比例，但不能新增/刪除規則。中等平衡。
3.  **全功能規則編輯器**\
    ~30 天 web dev。業務可完全自編規則 + 預覽 +
    canary。最強大但開發成本高 + 誤改風險高。

<div class="wbs-impact">

**📈 完成後 WBS 推進**：選項 1 維持 +0.1%（標 deferred）/ 選項 2-3
+0.1-0.3%（GUI BUILD 完成計入）

</div>

</div>

<div class="decision minor">

### 4. A37 candidate-detail drawer 元件

<div class="meta">

<span class="badge minor">MINOR</span> <span class="badge blocker">阻擋
A37 收尾 100%</span> Owner: UX + Web dev 狀態: blocked — 設計稿未定

</div>

<div class="section-label">

📂 來源文件

</div>

- `web/src/app/admin/dispatch-manual/page.tsx` — A37 主頁面（已 100% 但
  drawer 缺）
- `docs/_audit/flow-12-14-deep-audit.md` — A37 deep audit
- `docs/_ops/wbs-100-closeout-plan.md` §2.4
- 對應 PRD（待業主指明確切設計稿來源）

<div class="section-label">

⚡ 影響範圍

</div>

| 層面 | 影響 |
|----|----|
| Web UI | A37 dispatch-manual 候選技師詳情顯示方式（drawer / sheet / modal） |
| Design system | 是否引入新 drawer pattern 影響其他 admin 頁面一致性 |
| WBS | `system-completion-status.md` A37 從「~98%」推到 100% 的最後缺口 |
| Web dev 工時 | 1-3 天（依選項） |

<div class="section-label">

🎯 決策選項

</div>

1.  **用 shadcn `<Sheet>` 直接套**
    <span class="recommend-tag">推薦（MVP）</span>\
    最快：1 天 web dev。專案已用 shadcn，零新 dependency。
2.  **自客製化 drawer 元件**\
    2-3 天。Design system 一致性最高，但需先定 design token / animation
    curve。
3.  **暫不做，先用 modal 替代**\
    0 天 — 接受 A37 停在 98%，等正式 design review 後再 BUILD。

<div class="wbs-impact">

**📈 完成後 WBS 推進**：A37 從 98% → 100%（管理員後台收尾），整體 +0.1%
至約 98.6%

</div>

</div>

<div class="footer">

📄 對應 WBS 收尾計畫：`docs/_ops/wbs-100-closeout-plan.md` §2\
📄 對應 UAT 期程：`docs/_ops/uat-plan-2026-q3.md`\
📄 對應 session 統計：`docs/_audit/session-2026-06-05-final-stats.md`\
本檔由 AI agent 生成 — 4 項皆 **需業主 sign-off**，AI
僅整理選項與影響，不替業主決策。

</div>

</div>
