---
title: Flows, BDD & Test Governance (V-Model + 雙北極星架構)
phase: CROSS-PHASE
status: Active
last_updated: 2026-05-07
owners: [PM, Tech Lead, QA Lead]
---

# _flows-bdd-test/ — Flows, BDD & Test Governance

> **Zone Purpose**：Cross-phase topic folder consolidating user journeys, end-to-end interaction flows, BDD acceptance scenarios, and test plan governance.
>
> **Spans Gates**：TR0 (journey discovery) | TR4 (flow design) | TR5 (BDD + test plan) | TR7 (pre-prod gate)
>
> **架構**：Phase 1+2 重構後採 **V-Model + 雙北極星 + MECE** 結構（見 [[_RESTRUCTURE-PROPOSAL]]）。

---

## ⭐ 雙北極星 (Dual SSOT)

| 北極星 | 角色 | 對應 V-Model 層 |
|--------|-----|----------------|
| [[_SSOT-alignment-matrix]] | **流程** SSOT — 23 user flow × 8 維對應 | User Story / Flow 層 |
| [[north-star-requirements]] | **需求** SSOT — REQ-NNN catalog + QA + COM | Requirements 頂層 |

任何問題都從這裡開始查：
- 「F-016 在哪？」→ `_SSOT-alignment-matrix` §1
- 「為什麼要做？」→ `north-star-requirements` REQ-NNN
- 「該寫什麼測試？」→ `v-model-right/` 對應 layer

---

## V-Model 結構

```
                     REQUIREMENTS                     ACCEPTANCE TEST
                     ─────────────                    ─────────────
                  ⭐ north-star-requirements    ←→    AT-NNN（v-model-right/E7--bdd-scenarios.md）
                  ⭐ _SSOT-alignment-matrix
                     (decision-log/E7x--pm-alignment-Q1-Q10)
                                          ↓
                     SYSTEM DESIGN                     SYSTEM TEST
                     ─────────────                    ─────────────
                     v-model-left/E1x--user-journey   ST-NNN（v-model-right/E7x--test-plan-and-readiness.md）
                     v-model-left/E5x--workflow-*×3
                                          ↓
                     ARCHITECTURE                      INTEGRATION TEST
                     ─────────────                    ─────────────
                     (02-design/specs/*)              IT-NNN（v-model-right/integration-test-matrix.md）
                                          ↓
                     MODULE DESIGN                     UNIT TEST
                     ─────────────                    ─────────────
                     v-model-left/E7x--module-spec-v1-core.md ←→ UT-NNN（同檔 §test cases）
                                          ↓
                     CODE
                     ────
                     (agent/, api/, web/)

                     CROSS-CUTTING
                     ─────────────
                     v-model-right/performance-baseline.md  (PT-NNN)
                     v-model-right/security-checklist.md    (SEC-NNN)
                     decision-log/E7x--pm-alignment-Q1-Q10  (DEC-NNN)
```

---

## Documents

### ⭐ Hub / SSOT（先看這 2 個）

| File | Description |
|------|-------------|
| [[_SSOT-alignment-matrix]] | **流程北極星** — 23 user flow × 11 dimension matrix（PM/TL/QA 入口）|
| [[north-star-requirements]] | **需求北極星** — REQ + QA + COM catalog（V-Model 左頂）|

### v-model-left/ — 設計層（Requirements → Module Design）

| File | Description |
|------|-------------|
| [[v-model-left/E1x--user-journey-map]] | 4 角色 narrative + 情緒曲線（消費者 / 技師 / 管理員 / 客服主管）|
| [[v-model-left/E5x--workflow-work-order]] | 工單狀態機（16 狀態）+ Flow 1-13 完整生命週期 |
| [[v-model-left/E5x--workflow-dispatch]] | 派工營運：排班 / 媒合演算法 / 薪酬 / 拒單重派 |
| [[v-model-left/E5x--workflow-admin-governance]] | 後台治理：RBAC / 稽核 / 庫存 / 爭議仲裁（G1-G4）|
| [[v-model-left/E7x--module-spec-v1-core]] | V1.0 模組 1-5 DbC 規格 + Unit Test 案例 |

### v-model-right/ — 測試層（Unit → Acceptance Test + 性能/安全）

| File | Description | Test Layer |
|------|-------------|------------|
| [[v-model-right/E7--bdd-scenarios]] | 19 BDD Feature × ~85 Gherkin scenario | Acceptance |
| [[v-model-right/E7x--test-plan-and-readiness]] | 測試金字塔 + Sprint 1 路線圖 + readiness 矩陣 | Strategy |
| [[v-model-right/integration-test-matrix]] | AsyncAPI 10 channel × IT-NNN（補 reliability gap）| Integration |
| [[v-model-right/performance-baseline]] | k6 load / stress / spike test + SLA 目標 | Performance |
| [[v-model-right/security-checklist]] | OWASP Top 10 + pen test scope | Security |

### decision-log/ — 決策紀錄

| File | Description |
|------|-------------|
| [[decision-log/E7x--pm-alignment-Q1-Q10]] | PM Q1-Q10 決策矩陣（90 min 會議議程）|

### Governance（治理 / Review）

| File | Description |
|------|-------------|
| [[_review-notes]] | 9 檔逐一 review：結構摘要 / cross-refs / 對齊狀態 / 修正建議 |
| [[_RESTRUCTURE-PROPOSAL]] | 本次重構提案（含 ID 系統設計、V-Model、MECE 分析）|

### _archive/ — 已封存

| File | Reason |
|------|--------|
| [[_archive/E7x--module-roadmap-v2-draft]] | V2.0 業務模組 6-21 草稿（33 天未動，待 V2.0 架構鎖定後復活）|

---

## Reading Order（建議）

1. **入口 SSOT**：[[_SSOT-alignment-matrix]] ← 從這裡看 23 流程全貌
2. **需求**：[[north-star-requirements]] ← REQ catalog（為什麼要做）
3. **設計**（V-Model 左）：
   - [[v-model-left/E1x--user-journey-map]] ← 用戶感受
   - [[v-model-left/E5x--workflow-work-order]] ← 工單流程
   - [[v-model-left/E5x--workflow-dispatch]] ← 派工
   - [[v-model-left/E5x--workflow-admin-governance]] ← 治理
   - [[v-model-left/E7x--module-spec-v1-core]] ← V1.0 模組規格
4. **測試**（V-Model 右）：
   - [[v-model-right/E7--bdd-scenarios]] ← BDD 驗收
   - [[v-model-right/E7x--test-plan-and-readiness]] ← 測試策略
   - [[v-model-right/integration-test-matrix]] ← 整合測試
   - [[v-model-right/performance-baseline]] ← 性能
   - [[v-model-right/security-checklist]] ← 安全
5. **決策 / 治理**：
   - [[decision-log/E7x--pm-alignment-Q1-Q10]] ← PM 拍板
   - [[_review-notes]] ← 細部 review

---

## Cross-References

- Parent (DESIGN phase): [[../02-design/_MOC]]
- Parent (DISCOVER phase): [[../00-discover/_MOC]]
- Documentation hub: [[../HOME]]
- Gate framework: [[../GATE-MAP]]

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-07 | 初版（PR #35 統整 8 檔至 `_flows-bdd-test/`）|
| 2026-05-07 | PR #36 新增 _alignment-matrix + _review-notes，加 V-Model 索引提示 |
| 2026-05-07 | **Phase 1+2 重構**：V-Model 子目錄（v-model-left / v-model-right / decision-log / _archive）、雙北極星宣告（_SSOT-alignment-matrix + north-star-requirements）、4 新檔補 MECE（performance / security / integration + 需求 catalog）、module-spec SPLIT V1.0 / V2.0 |
