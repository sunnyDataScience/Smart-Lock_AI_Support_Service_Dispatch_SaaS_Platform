---
id: CR-0014
title: "FR-0034 AI Employee Charter / PRD 治理 — Phase II 性質 ACK + 取證 ADR-0028 落地差距 + 最小裁決"
status: open-awaiting-decisions
decided: null
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: 北極星條件 (1) draft FRs 4 → 3（與 CR-0011/0012/0013 並列；本 CR 結論可能為「維持 draft」）
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/analysis/fr/FR-0034-ai-employee-charter.md
  - docs/architecture/adr/ADR-0028-ai-employee-charter.md
  - docs/analysis/br/BR-A12-01.md
  - docs/analysis/br/BR-A12-02.md
  - docs/analysis/br/BR-A12-NN.md
  - docs/_audit/CR-0010-fr-0019-promote-to-active.md
  - agent/harness/safety_gate.py
---

# CR-0014 — FR-0034 AI Employee Charter / PRD 治理 CIA

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md` + CR-0010 HD-03=a「同步開 CR-0011~0014 審查其他 4 draft FR」（CR-0011~0014 batch 收尾件）
> **Triggered by**: MISSION 北極星 (1) draft FR = 0；FR-0034 為 4 剩餘 draft FR 第 4 件，**但與其他 3 件性質不同**：屬 Phase II 骨架 + 已 explicit 延後（per Q2=C），可能不該強推 active

---

## 1. Change Statement

**As-is**：
- `FR-0034` `status: draft`，`phase: II`，`note: "Phase II 延後 per Q2=C 業主裁決。本 FR 為骨架。"`
- FR-0034 全文僅 61 行（§1 §2 §3 §4 皆「骨架」標示）
- **ADR-0028** (AI 鎖匠客服助理 Employee Charter) `status: accepted` — 完整 Charter 表（Allowed / Collaborative / Forbidden / Tool Permissions / Knowledge Sources / KPI / Off-board Triggers）+ 3 條 Hard constraints + Open items（30d shadow 未啟動）
- **BR-A12-01** (Gate ↔ owner ↔ status ↔ source) `status: active`
- **BR-A12-02** (Final PRD inputs 主要輸出) `status: active`
- **BR-A12-NN** (Charter rule from ADR-0028) — 未編號 placeholder
- **Charter 落地取證**（grep）：
  * `agent/harness/safety_gate.py` (41 LOC) + `agent/config.toml [output_validator] forbidden_phrases` 已落地 prompt-level guardrail（output 文字檢查）
  * `agent/app.py:167 safety_gate.init(_cfg.safety)` 啟動
  * ADR-0040 與 ADR-0028 對齊（AI 永禁核准退款，CR-0009 agent 走 :agent-initiate single-actor，無 approve 權限）✅
  * **Off-board Triggers (KPI<70% 連 2 週 → 48h hand-off) 未在 code 內**：grep `KPI\|off.board\|pass_rate` 顯示 `quality_check.py` 有 pass_rate 但無 trigger；`reports_v2.py:33 GET /tenants/{tid}/reports/kpi` 有 KPI 但無綁 Charter triggers
  * **Promotion 條件「KPI 全綠 4 週是 hard gate」未在 code 內**（純 ops 流程）

**To-be**（**本 CR 不一定要 status flip**）：
- 釐清 FR-0034 是否在 V1 階段強推 active（HD-01）
- BR-A12-NN 是否編號 BR-A12-03（HD-02）
- ADR-0028 implementation gap（Off-board / Promotion triggers）是否要列追蹤項（HD-03）
- 取證 ADR-0028 + BR-A12-01/02 + safety_gate + ADR-0040 = Charter 95% **rule body** 已存在於 codebase + governance docs，僅 FR-0034 內骨架未填

**Driver**：
- 北極星條件 (1) 4 → 3 第 4 路徑（**但結論可能為「維持 draft」**，因 phase II 延後是正當狀態）
- 完成 CR-0010 HD-03=a batch（CR-0011~0014）的最後 1 件
- ADR-0028 Open items / implementation gap 需 explicit 追蹤項，避免 silent decay

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-AI-CHAR-001`（Charter rule 變動）| **TBD** | 視 HD-03 結論決定是否 spell out Charter 變動流程 |
| `BF-AI-OFFBOARD-001`（KPI<70% 2 週 → 48h hand-off）| **Implementation gap** | ADR-0028 規定但 code 未落地；HD-03 flag |
| `BF-AI-PROMO-001`（KPI 4 週全綠 → promote new behavior）| **Implementation gap** | 同上 |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0034` | **TBD per HD-01** | (a) 維持 draft (Phase II) / (b) Promote active in V1 / (c) Promote active + 改 phase: I |
| `BR-A12-03`（前 BR-A12-NN，Charter rule from ADR-0028）| **New 編號 per HD-02** | 引用 ADR-0028 Charter 表 |
| `ADR-0028` | Referenced | accepted，Charter 正典 |
| `ADR-0040` | Referenced | AI 永禁核准退款，與 ADR-0028 對齊（已落地）|

---

## 4. Affected API

無新增 API。

**Implementation gap flag**：
| API ID | Endpoint | Action | Notes |
|---|---|---|---|
| `API-KPI-OFFBOARD-CHECK` | （TBD）內部 cron / scheduled job | **Implementation gap per ADR-0028** | KPI<70% 連 2 週 偵測 + 48h hand-off 觸發；HD-03 決定是否列追蹤項至 Phase II BUILD |

---

## 5. Affected Data

無 schema 變動（本 CR 範疇）。

ADR-0028 Open items「30d shadow 未啟動」屬 Phase II / v2 啟動條件，不在本 CR。

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-AI-CHAR-FORBIDDEN-001`（agent 嘗試呼 forbidden tool 必 reject）| Existing | safety_gate / Tool Permissions L1/L2 HITL 已落地；既有 quality_check 涵蓋 |
| `TC-AI-OFFBOARD-001`（KPI<70% 連 2 週 觸發 48h hand-off）| **Missing** | ADR-0028 Hard constraint #2 規定但無對應 test；HD-03 決定是否列追蹤項 |
| `TC-AI-PROMOTION-001`（KPI 4 週全綠 promote）| **Missing** | 同上 |

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | A12 PRD 治理為 process 級，非 code 模組 |
| New ADR? | **No** | ADR-0028 已涵蓋；若 HD-03=(a) 要寫 ADR-0028-supplement 補 implementation triggers 則例外 |
| External integration | None | — |
| Phase II 啟動條件 | Open | 30d shadow（per ADR-0028 Open items）+ Phase I A03-A11 穩定（per FR-0034 §1 Precondition）|

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | FR-0034 status 處理 | (a) **維持 draft + phase: II**（Q2=C 延後是正當狀態；不違北極星可接受 reality；補一行 frontmatter `acknowledged_in: CR-0014`）<br>(b) Promote draft → active 但維持 phase: II（spec 主體骨架在 V1 補完，行為治理走 ADR-0028）<br>(c) Promote active + 改 phase: I（脫 Phase II 延後限制，spec 主體完整補完，視為 V1 governance baseline）<br>(d) 留 draft 但補 §1 §2 主體至「Phase I 適用部分」(部分 promotion) | PM + Tech Lead | **pending** | — |
| **HD-02** | BR-A12-NN（Charter rule from ADR-0028）編號 | (a) 編號 `BR-A12-03`，body 引用 ADR-0028 Charter 表（rule 不重複，避免雙 source of truth）<br>(b) 維持 BR-A12-NN placeholder 至 Phase II 啟動<br>(c) 編號 `BR-A12-03` 但 body 完整 inline 整個 Charter 表（risk：與 ADR-0028 同步維護負擔）| PM + Compliance | **pending** | — |
| **HD-03** | ADR-0028 implementation gap 處理 | (a) 列入「Phase II 啟動 checklist」，本 CR 不啟 BUILD task<br>(b) 開 ADR-0028-supplement 補 Off-board / Promotion triggers 落地設計（cron job / scheduler 對齊 FR-0012 HD-02 同 cron infra？）<br>(c) 接受純 ops 流程（無 code triggers）+ runbook 化（PROC-NNNN 新增）<br>(d) Phase I 階段忽略，標 known limitation | Ops + Compliance | **pending** | — |
| **HD-04** | M20 mapped_to **8 FR 重疊**（FR-0017/0028/0029/0030/0034/0048/0050/0051）職責切分釐清 | (a) 本 CR scope 不釐清，另開 governance CR（推薦）<br>(b) 本 CR §A 附錄列現況對照表，pending Phase II 統合（已落地）<br>(c) 強制本 CR 內裁 8 FR 邊界（工程量大，不建議） | PM + Tech Lead | **pending** | — |

---

## 9. Suggested Implementation Order

§8 業主裁決後，依以下順序實作：

1. **Decisions** → 不新開 ADR（HD-03=(b) 例外）；frontmatter 補 `acknowledged_in: CR-0014` 至 FR-0034
2. **BR-A12-NN 編號**（per HD-02）→ rename `BR-A12-NN.md` 為 `BR-A12-03.md` + body 對齊 HD-02 選項
3. **FR-0034 status 處理**（per HD-01）：
   - (a) 維持 draft → 補 acknowledgment + 移除 `blocked_by`（若有）
   - (b)/(c)/(d) → 對應補完 §1 §2 主體 + 改 phase / status
4. **ADR-0028 implementation gap**（per HD-03）：
   - (a) 列入 Phase II checklist + 寫到 system-completion-status §7
   - (b) 開 ADR-0028-supplement（OOSCope of 本 CR）
   - (c) 新增 PROC-NNNN runbook
5. **TM-0000 更新** → 補 FR-0034 ↔ ADR-0028 ↔ BR-A12-01/02/03 ↔ safety_gate.py ↔ TC-AI-CHAR-* row
6. **CR-0014 status flip** → open-awaiting-decisions → decided
7. **system-completion-status.md** → 依 HD-01 outcome 調整 draft FR table（可能 4 → 3 或維持 4 但補 acknowledged 標記）+ §7 列 ADR-0028 implementation gap（若 HD-03 列追蹤項）

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HD-01 選 (b)/(c)/(d) 但 Phase II 短期不啟動 → spec 主體填寫成 sunk cost | Medium | Low | 推薦 HD-01=(a) 維持 draft + acknowledged，工程零成本 |
| HD-03 選 (b) 但 ADR-0028-supplement 又卡 Phase II → 雙重 stale 風險 | Medium | Medium | 推薦 HD-03=(a) 列 checklist + (c) runbook 化雙保險 |
| ADR-0028 Forbidden 清單在 code 與 Charter 表不一致 | Low | High | 既有 safety_gate.py + tool permission L1/L2 + ADR-0040 已對齊；定期 audit（已有 ai_agent_audit_2026-04-27.md 範本）|
| Charter 變更走 ADR + audit（per AC-01）— 但 ADR-0028 既有 Hard constraint #1 已規定 | Low | Low | 已落地 |
| HD-04 三 FR 重疊未釐清 → 後續 spec rewrite cost | Medium | Medium | 推薦 HD-04=(b) §A 列對照表 pending Phase II 統合 |

**Rollback plan**：
- 本 CR 大部分為 doc-only（acknowledgment / BR rename / status flip）→ revert 1 PR 即可
- 若 HD-03=(b) 開 ADR-0028-supplement → 標 superseded_by 即可 append-only

---

## 11. Out of Scope

- **ADR-0028 Open items「30d shadow」啟動** → Phase II / v2 條件，不在本 CR
- **ADR-0028 Off-board / Promotion triggers code 落地** → HD-03=(b) 時另開
- **FR-0029 / FR-0030 spec 重寫** → HD-04=(a)/(b) 時另開
- **AI v2 / 新品牌 30d shadow runbook** → ops 另開
- **agent code refactor (safety_gate / tool permission)** → 既有架構 lock per CLAUDE.md，不動

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product (PM) | | | |
| Tech Lead | | | |
| AI Lead | | | |
| Legal | | | |
| Compliance | | | |
| Knowledge Owner | | | |
| Ops | | | |

---

## §A 取證附錄（為何此 CR 是必要 + Charter 落地情形對照）

```bash
# 1. FR-0034 為 Phase II 骨架（與其他 3 draft FR 性質不同）
$ grep -E "^status:|^phase:|^note:" docs/analysis/fr/FR-0034-ai-employee-charter.md
status: draft
phase: II
note: "Phase II 延後 per Q2=C 業主裁決。本 FR 為骨架。"

# 2. ADR-0028 accepted（Charter 95% rule body 已存在於正典）
$ grep "^status:" docs/architecture/adr/ADR-0028-ai-employee-charter.md
status: accepted

# 3. BR-A12-01 / 02 active；BR-A12-NN 為 placeholder
$ ls docs/analysis/br/BR-A12-*
BR-A12-01.md  BR-A12-02.md  BR-A12-NN.md

# 4. Charter Forbidden 清單 prompt-level 落地（safety_gate + forbidden_phrases）
$ grep -n "safety_gate" agent/app.py | head -3
50:import harness.safety_gate as safety_gate
167:    safety_gate.init(_cfg.safety)

# 5. AI 永禁核准退款（ADR-0040 對齊 ADR-0028）已落地 — agent 走 :agent-initiate single-actor 不能 approve
$ grep -A1 "agent-initiate" api/routers/refunds_v2.py | head -3
（CR-0009 已落地，refunds:agent-initiate role enforce agent|system，無 approve 權限）

# 6. ADR-0028 Off-board Triggers (KPI<70% 2週→48h hand-off) **未** 在 code 內
$ grep -rn "off.board\|hand_off\|pass_rate.*70\|kpi.*trigger" agent/ api/ 2>/dev/null
（無 — 屬 ADR-0028 Open items / implementation gap）
$ grep -n "pass_rate" agent/quality/quality_check.py
1035:    pass_rate = pass_n / total * 100
（純報表計算，無自動 trigger）

# 7. Promotion 條件「KPI 4 週全綠 hard gate」未 code 化
$ grep -rn "4.*week\|promotion.*gate\|charter.*promote" agent/ api/ 2>/dev/null
（無 — 屬純 ops 流程）

# 8. M20 mapped_to 全現況（HD-04 對照）— **8 FR 重疊**：
$ grep -l "M20" docs/analysis/fr/*.md
docs/analysis/fr/FR-0017-sop-draft-review.md         # A10+M20+A04
docs/analysis/fr/FR-0028-skill-gated-react-agent.md  # A03+M20+M17
docs/analysis/fr/FR-0029-skill-knowledge-base.md     # A04+M20
docs/analysis/fr/FR-0030-guardrails-output-validator.md  # A05+M20+M15
docs/analysis/fr/FR-0034-ai-employee-charter.md      # A12+M20
docs/analysis/fr/FR-0048-rma-quality-feedback-loop.md  # M13+M20+M07
docs/analysis/fr/FR-0050-ai-governance-prd-trace.md  # A12+M20
docs/analysis/fr/FR-0051-sop-feedback-spiral-deep.md  # A10+M20+M13
```

**結論**：FR-0034 與其他 3 draft FR (FR-0011/0012/0022) 性質不同 — 屬 **Phase II 骨架 + Q2=C 延後正當狀態**；Charter rule body 95% 已透過 ADR-0028 + BR-A12-01/02 + safety_gate + ADR-0040 在 codebase 落地；唯一 gap 為 **Off-board / Promotion triggers** (Hard constraint #2/#3) **無 code 落地**，屬 Phase II 啟動條件。

**推薦立場（HD 預設答）**：
- HD-01 = (a) 維持 draft + phase: II + acknowledged_in: CR-0014（不強推 active；尊重 Q2=C 延後決策）
- HD-02 = (a) 編號 BR-A12-03，body 引用 ADR-0028 Charter 表（避免雙 source of truth）
- HD-03 = (a)+(c) 列入 Phase II checklist + 補 PROC-NNNN runbook（不開 ADR-supplement）
- HD-04 = (b) §A 列對照表 pending Phase II 統合（已在本 CR 落地，不在本 CR 強制裁 8 FR 邊界）

若業主依推薦立場全選，**北極星條件 (1) 4 → 3 不會推進** — FR-0034 維持 draft 但被 explicit acknowledged 為 reality-aligned；其他 3 件 (FR-0011/0012/0022) 才是真實推進目標。
