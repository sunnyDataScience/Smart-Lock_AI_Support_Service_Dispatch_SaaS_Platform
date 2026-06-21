---
title: 散落文件歸檔索引
status: archived
archived-at: 2026-06-18
archived-from: 專案根目錄 / docs/ / web/docs / reports/
related: ../../.claude/rules/context-stability.md
---

# docs/_archive — 歸檔區索引

> 本目錄保留**已非現行事實但具歷史/audit 價值**的文件。所有檔案皆為 `status: archived` 性質：
> **可讀作歷史脈絡，但不可當 source of truth、不可被新文件引用為現行依據。**
> 現行正典請走各 tier 對應文件。

子區索引：[`blueprints/`](blueprints/README.md)（週會藍圖）、[`extras/`](extras/README.md)（前端工具方法論）、[`legacy/`](legacy/README.md)（舊 design-spec pipeline）。

---

## 2026-06-18 批次 — 散落文件治理稽核歸檔

來源：一次全 repo 散落/暫存文件稽核（107 檔分 12 叢集），結論 0 刪除、其餘保留或歸檔。
本批次實際歸檔 **17 檔**（git 歷史以 rename 保留）。稽核原建議歸檔 27 檔，執行時調整：
- 4 檔在已不存在於工作樹的 `20260617資料/` —— 無法搬移（見報告）。
- 7 份 `docs/governance/reviews/` critique —— **暫不歸檔**（見下方 D 段，append-only ADR 反向連結不可改）。

### A. 重寫前架構殘留（白皮書/早期規格）

| 歸檔位置 | 原位置 | 簡介 | 歸檔理由 / 對應現行 |
|---|---|---|---|
| `agent_x-EA-whitepaper-v3.md` | `/agent_x.md` | 115KB AI 藍領客服 EA 白皮書 v3，建立在 Hermes / Belief-Driven Runtime / ReAct / LangGraph | 架構主軸已於 2026-06-04 被 **LockCore 重寫**取代（見 `CLAUDE.md` Architecture Lock + `ADR-0107`）；無引用、無 frontmatter |
| `prd/BIZ-0001-executive-architecture-overview.md` | `docs/prd/` | 六層系統架構總覽 v2.0（2026-04-04），L3 為 LangGraph/8-Layer Harness | L3 AI 服務層已被 LockCore + `ADR-0107` 取代 |
| `prd/SOW-0001-2026-q1.md` | `docs/prd/` | 軟體需求/工作說明書 SOW v1.0（已批准），技術棧 LangChain 0.3 / Gemini 2.5 Flash | LLM 框架已被 LockCore + LiteLLM 取代；被 `CR-0004` audit 引用故歸檔不刪 |

### B. 一次性報告 / session 快照（機器產出，可重跑再生）

| 歸檔位置 | 原位置 | 簡介 | 歸檔理由 / 對應現行 |
|---|---|---|---|
| `reports/p4-stage7-deletion-plan-2026-06-07.md` | `/reports/` | dry-run script 產出的 47 個 v1 router 刪除清單 | tier-5 機器快照，可由 `scripts/ops/p4_stage7_delete_v1_dry_run.py` 重跑 |
| `reports/p4-stage7-dev-readiness-2026-06-07.md` | `/reports/` | P4 Stage 7 dev 就緒摘要 | 內容已被 `docs/_audit/P4-stage-2-7-prep-checklists.md` + `ADR-0109` 涵蓋 |
| `reports/uat-report-2026-06-07.md` | `/reports/` | UAT-001~010 全 100% 通過執行輸出 | `uat_runner.py` 一次性快照；規格在 `docs/_ops/uat-plan-2026-q3.md` |
| `_audit/playwright-e2e-verify-session-2026-06-07.md` | `docs/_audit/` | 單次 Playwright e2e 驗證 session 記錄 | 結論與 bug 已落 commit；一次性過程記錄 |
| `_audit/session-2026-06-05-final-stats.md` | `docs/_audit/` | 2026-06-05 session 統計總表 | frontmatter 原已標 `status: archived` |
| `_audit/session-summary-2026-06-05.md` | `docs/_audit/` | 2026-06-05 session 成果摘要 | 原已標 `status: archived`；與 final-stats 高度重疊 |
| `_ops/release-checklist-2026-06-05.md` | `docs/_ops/` | 2026-06-05 session 一次性發布 checklist | 綁定該 session 的 migration 017-027，已部署完成 |

### C. 被現行活躍文件取代（時點快照）

| 歸檔位置 | 原位置 | 簡介 | 被誰取代 |
|---|---|---|---|
| `web-docs/progress-report-2026-04-29.md` | `web/docs/` | PM 兩週進度報告（凍結於 04-29） | → `web/docs/system-completion-status.md`（每輪強制更新的 SSOT） |
| `web-docs/progress-report-2026-05-05.md` | `web/docs/` | PM 進度報告（凍結於 05-05） | → 同上 |
| `web-docs/wbs-completion-report.md` | `web/docs/` | WBS-vs-合約對照（05-05，仍稱師傅端未開發） | → 同上 |
| `ops/release-readiness.md` | `docs/ops/` | 舊版 Release Readiness（2026-05-23，PRD v2.1） | → `docs/ops/release-readiness-smart-lock-saas.md`（雙向 frontmatter 註記 Supersedes） |
| `index/traceability-matrix.md` | `docs/_index/` | FR↔BR↔ADR 追溯矩陣（auto-gen，停在 75 ADR） | 已失準（repo 已到 ADR-0114）；生成器 `tools/traceability_matrix.py` 已遺失，**需重建後再生** |
| `index/migration/fr-mapping-2026-05-27.md` | `docs/_index/migration/` | 一次性 FR 遷移規劃骨架（status: partial） | 規劃已落地為 `docs/analysis/fr/` 53 個 FR 檔 |

### D. 審查過程記錄 — 已評估但**暫不歸檔**（留在 `docs/governance/reviews/`）

`docs/governance/reviews/` 的 7 份 lane-a critique，稽核原判 ARCHIVE（verdict 都已落地對應 ADR）。
但執行時的反向連結檢查發現：**7 個 tier-1 ADR 以 clickable link 引用這些 critique 作為審查證據**
（如 `ADR-0040` → `[...](../../governance/reviews/ADR-0040-lane-a-critique-2026-05-28.md)`），
且 `docs/governance/freeze-sign-off-2026-05-28.md` frontmatter `related_evidence` 也列入這 7 檔。
依 `context-stability` 規則 **accepted ADR / frozen sign-off 為 append-only 不可就地編輯**，
歸檔會造成這些連結永久失效且無法修復，故**本批次不動，維持原位**。
（若日後要歸檔，須先以新 ADR 處理連結，或由人裁決。）

### E. 業主裁決快照（已 deferred-accepted）

| 歸檔位置 | 原位置 | 簡介 | 歸檔理由 |
|---|---|---|---|
| `governance/pending-business-decisions-2026-06-06.html` | `/pending-business-decisions-2026-06-06.html` | 4 項業主待裁決卡片 | 事項 2/3 已 deferred-accepted（commit `a02057c6`）、落地 `ADR-0108`；**改歸檔保留**而非硬刪（仍被 ADR-0108/0109 引為證據） |

---

## 斷鏈引用處置（2026-06-18）

搬移後做了反向連結檢查，原以舊路徑引用這些檔的地方處理如下：

**✅ 已更新指向新歸檔路徑（可編輯的 active 文件）：**
- `pending-business-decisions-...html` ← `docs/_audit/wbs-recalc-2026-06-07.md`、`docs/_ops/p4-stage7-readiness-runbook.md`、`web/docs/system-completion-status.md`
- `traceability-matrix.md` ← `docs/qa/test-plan-cascade-strategy-2026-05-28.md`（clickable link）
- `session-2026-06-05-final-stats.md` / `session-summary-2026-06-05.md` ← `docs/_ops/uat-plan-2026-q3.md`、`docs/_ops/wbs-100-closeout-plan.md`、`docs/_audit/phase-ii-web-integration-plan.md`
- `release-checklist-2026-06-05.md` ← `docs/_ops/uat-plan-2026-q3.md`、`docs/_ops/alert-receivers-comparison.md`、`docs/_audit/P4-stage1-build-checklist.md`
- `release-readiness.md` ← `docs/ops/release-readiness-smart-lock-saas.md`（frontmatter `related_docs` + Supersedes 指標）

**⚠️ 刻意不動（歷史紀錄 / append-only，路徑指向搬移前狀態屬合理）：**
- `docs/architecture/adr/ADR-0108-*.md`、`ADR-0109-*.md` —— tier-1 ADR append-only，仍以根路徑引用 pending-business HTML；連結失效但內容於本區可追溯。
- `docs/governance/freeze-sign-off-2026-05-28.md` —— frozen 簽核紀錄，body/表格以原 `docs/_index/` 路徑記載 traceability-matrix 為 freeze 當下的交付證據（commit `44f16f3`），屬歷史事實不改寫。
- `CHANGELOG.md`、`web/docs/system-completion-status.md` 內的**日期化歷史 log 條目**（描述「6/07 寫了 reports/p4-stage7-dev-readiness」等）—— 屬當時事件紀錄，保留原文。

- `docs/governance/reviews/user-flow-v2-gate2-critique-2026-05-28.md` 多處引用 `docs/_index/traceability-matrix.md` —— 該 critique 為 2026-05-28 已完成的歷史審查記錄（且本身因 append-only ADR 連結而留原位，見 D 段），路徑屬歷史 reasoning，不改寫；檔案於本區可追溯。

**📌 順帶發現（本批次未處理，pre-existing / 非斷鏈）：**
- `docs/_ops/uat-plan-2026-q3.md` 引用 `docs/_ops/phase-ii-web-integration-plan.md`，但該檔實際在 `docs/_audit/` —— 與本次搬移無關的既有錯路徑。
- `scripts/ops/README.md` 的 `--output reports/p4-stage7-deletion-plan.md` 是 script 重新產生報告的命令範例（非引用本批次歸檔檔）；script 重跑時會自行重建 `reports/`。

---

## 不要做

- ❌ 把本區任何檔當作**現行事實**或新文件的引用來源 —— 它們是歷史快照。
- ❌ 編輯後再「復活」回原位 —— 若要重啟某文件，走 CR/CIA 開新正典檔，本區保持唯讀。
- ❌ 依本區描述的架構（LangGraph / ReAct / Hermes / Belief-Driven Runtime / `agent/skills/`）推斷現況 —— 現行架構是 LockCore，見 `CLAUDE.md` Architecture Lock。
