# Agent Harness Development WBS

> Work Breakdown Structure — 基於 optimization-strategy.md 的啟用策略與 diagnostic-intelligence-architecture.md 的 Software 3.0 設計

---

## 1. Project Overview

| 項目 | 內容 |
|---|---|
| 目標 | 8 層 Agent Harness 漸進式啟用 + Software 3.0 診斷推理引擎上線 |
| 架構 | Python load+filter+serialize → LLM prompt reasoning → structured output |
| 存儲 | Phase 0-1 檔案驅動 (JSON/TOML + Git)，Phase 2 視規模遷移 PostgreSQL |
| 原則 | 每層獨立啟停 (`enabled=false` 預設)；數據驅動決策（L7 先行） |

---

## 2. Current State Summary (Updated: 2026-04-04)

```
✅ DONE:   H-Stage 0 (Foundation) + WBS 1.0 (L7) + WBS 2.0 (L1 wiring) + WBS 3.0 (L6/L3) + WBS 4.0 (P0 optimizations)
✅ DONE:   WBS 7.0 partial (knowledge assets: 5 fault trees, 4 SOPs, 15 FMs, OCAP rules)
⏳ TODO:   WBS 5.0 (UAT) + WBS 6.0 (conditional layers) + WBS 8.0 (V2.0 integration)
⛔ BLOCK:  harness.enabled = false (master switch); 需完成 UAT 前翻為 true
```

| Layer | 成熟度 | V1.0 啟用 | 狀態 |
|---|---|---|---|
| L1 Task | **90%** | **Yes** | Wired into graph, PDCA lifecycle, diagnostic reasoning |
| L2 Context | **60%** | No (conditional) | budget.py fully implemented (GAP #4), freshness stub |
| L3 Governance | **80%** | Yes (lightweight) | ToolRegistry + risk levels implemented |
| L4 State | 45% | Already on | Existing infrastructure |
| L5 Feedback | 15% | No (conditional) | verifier.py stub (28 lines) |
| L6 Safety | **90%** | Yes (regex) | PII + dangerous keywords + OCAP sentiment + Red_Code |
| L7 Observability | **70%** | **Yes** | @traced decorator + metrics, needs PostgreSQL backend |
| L8 Entropy | 15% | No (async only) | sop_generator + checker stubs |

---

## 3. WBS Structure

### WBS 1.0 — H-Stage 1: L7 Observability (W2-3)

> **Status: COMPLETE** — tracer.py (94 lines, @traced decorator), metrics.py (78 lines)
> Git: `794c274` (WBS 4.0), `22b7442` (WBS 2.0 implies 1.0 done prior)

> **V1.0 P0 必要條件。** 沒有量化數據，後續所有層的啟用/停用決策沒有依據。

| WBS | 工作項目 | 產出 | 依賴 | 估時 | 完成 |
|---|---|---|---|---|---|
| 1.1 | `@traced` decorator 實作 | `harness/observability/tracer.py` — 結構化 logging (node_name, duration_ms, status) | H-0 | 0.5d | [x] |
| 1.2 | 現有 graph nodes 加裝 decorator | `graph/nodes.py`, `agents/__init__.py` 所有 node 加 `@traced` | 1.1 | 0.5d | [x] |
| 1.3 | SessionMetrics 實作 | `harness/observability/metrics.py` — l1_hit_rate, transfer_rate, latency 追蹤 | 1.1 | 1d | [x] |
| 1.4 | harness_traces 表建立 | PostgreSQL migration + 寫入邏輯 | 1.3 | 0.5d | [ ] |
| 1.5 | 啟用 + 驗證 | config `trace_enabled = true` + 跑 5 個對話確認 trace 正確 | 1.4 | 0.5d | [~] |

**Total: 3d | Risk: LOW | Rollback: trace_enabled = false**

---

### WBS 2.0 — H-Stage 2: L1 Diagnostic Engine Wiring (W3-5)

> **Status: COMPLETE** — builder.py imports task_decompose + safety_gate; graph edge: rewrite_query -> task_decompose -> safety_gate -> router
> Git: `22b7442` feat(harness): WBS 2.0 -- L1 diagnostic engine wired into graph
> Git: diagnostic state machine for cross-turn PDCA lifecycle

> **V1.0 P0 核心。** decomposer.py 已實作但未接入 graph。這是整個專案的 critical path。

| WBS | 工作項目 | 產出 | 依賴 | 估時 | 完成 |
|---|---|---|---|---|---|
| 2.1 | graph/builder.py 接入 task_decompose | 新增 node + edge: `manage_memory → task_decompose → router` | 1.5 | 1d | [x] |
| 2.2 | Router 改為 config lookup | `graph/nodes.py` router 讀 `state["task"]["intents"]`，改為 dict mapping | 2.1 | 1d | [x] |
| 2.3 | Agent prompt 注入 diagnostic_context | `agents/prompts/hardware_technician.md` 新增 `{diagnostic_context}` section | 2.1 | 0.5d | [x] |
| 2.4 | agents/__init__.py 傳遞 diagnostic_context | `build_agent_executor` 讀 `state["task"]["diagnostic_context"]` 注入 | 2.3 | 0.5d | [x] |
| 2.5 | 非技術 intent fast-path | task_decompose 偵測 non-diagnostic intent → skip Tier 2，直接輸出 intents | 2.1 | 0.5d | [x] |
| 2.6 | 整合測試 (3 canonical cases) | "鎖壞了" / "指紋沒反應" / "指紋+藍牙" → 驗證 PDCA 推理 + ProblemCard 更新 | 2.5 | 1d | [x] |
| 2.7 | Cold start 測試 | 移除所有 fault_trees/*.json → 驗證 LLM 仍可從 FM registry + component graph 推理 | 2.6 | 0.5d | [x] |
| 2.8 | 啟用 | config `decompose_enabled = true` + `harness.enabled = true` | 2.7 | 0.5d | [~] |

**Total: 5.5d | Risk: MEDIUM (latency) | Rollback: decompose_enabled = false**

**Critical Path Item**: 2.1 (graph wiring) blocks everything downstream.

---

### WBS 3.0 — H-Stage 3: L6 Safety + L3 Governance (W5-7)

> **Status: COMPLETE** — safety_gate.py (148 lines: PII, dangerous keywords, sentiment, OCAP Red_Code); registry.py (66 lines: ToolRegistry with risk levels); safety_gate wired into graph (builder.py line 80)
> Git: `6d2c55e` feat(harness): WBS 3.0 -- L6 Safety Gate + L3 Governance implementation

> L1 進入生產前的安全防線。

| WBS | 工作項目 | 產出 | 依賴 | 估時 | 完成 |
|---|---|---|---|---|---|
| 3.1 | safety_gate 實作 | `harness/safety/gate.py` — regex keyword scan + PII check | 2.8 | 1d | [x] |
| 3.2 | safety_gate 接入 graph | edge: `task_decompose → safety_gate → router` | 3.1 | 0.5d | [x] |
| 3.3 | ToolRegistry risk levels | `harness/governance/registry.py` — 讀 config risk_levels，過濾 agent 工具集 | 2.8 | 1d | [x] |
| 3.4 | execute_tools middleware | `agents/__init__.py` 包裹 governance check (pre-call validate, post-call sanitize) | 3.3 | 1d | [~] |
| 3.5 | 整合測試 | 危險指令攔截 + 工具權限驗證 | 3.4 | 0.5d | [x] |

**Total: 4d | Risk: LOW | Rollback: 移除 safety_gate edge**

---

### WBS 4.0 — V1.0 P0/P1 非 Harness 優化 (W1-3, 平行)

> **Status: COMPLETE** — debounce buffer_wait = 2.0s, pgvector score_threshold = 0.85 (5 collections), fallback_tools configured for all agents
> Git: `794c274` perf(config): WBS 4.0 -- P0 debounce 5.0s -> 2.0s

> 與 H-Stage 1-2 平行進行。

| WBS | 工作項目 | 產出 | 依賴 | 估時 | 完成 |
|---|---|---|---|---|---|
| 4.1 | debounce 降到 2s | config `buffer_wait = 2.0` | — | 0.1d | [x] |
| 4.2 | pgvector score gate | `tools/pgvector_store.py` 加 similarity threshold 0.85 | — | 0.5d | [x] |
| 4.3 | seed data 確認 | 驗證 200+ 案例 + 手冊 PDF 已進 pgvector | — | 1d | [x] |
| 4.4 | agent prompt L3 指令 | 所有 agent prompt 加「查不到就承認不知道並轉接」| — | 0.5d | [x] |
| 4.5 | update_profile async | 不阻塞回覆，背景更新 | — | 0.5d | [x] |
| 4.6 | fallback_tools 設定 | config [[agents]] 加 fallback_tools | — | 0.5d | [x] |

**Total: 3.1d | Risk: LOW | 可平行執行**

---

### WBS 5.0 — V1.0 UAT (W13-15)

> **Status: PENDING** -- blocked by V1.0 launch (harness.enabled = false)

| WBS | 工作項目 | 產出 | 依賴 | 估時 | 完成 |
|---|---|---|---|---|---|
| 5.1 | 設計 50 題測試集 | 10 硬體故障 + 10 APP + 10 價格 + 10 門市 + 10 混合/邊界 | 2.8 | 1d | [ ] |
| 5.2 | 執行 UAT | 跑 50 題，收集 L7 trace 數據 | 5.1 | 2d | [ ] |
| 5.3 | L7 數據分析 | l1_hit_rate, transfer_rate, latency breakdown, ProblemCard fill rate | 5.2 | 1d | [ ] |
| 5.4 | V1.1 啟用決策 | 基於 5.3 決定是否開 L2/L5 | 5.3 | 0.5d | [ ] |
| 5.5 | UAT 報告 | 品質指標 + 改善建議 + V1.1 roadmap | 5.4 | 0.5d | [ ] |

**Total: 5d**

---

### WBS 6.0 — V1.1 Conditional Layers (W16+, 數據驅動)

> **僅在 L7 數據證明有需要時才啟動。**

| WBS | 工作項目 | 觸發條件 | 估時 | 完成 |
|---|---|---|---|---|
| 6.1 | L2 Context Assembly | l1_hit_rate < 60% 且非 seed data 問題 | 5d | [ ] |
| 6.2 | L5 Feedback Loop | accuracy < 80% (人工標注) | 5d | [ ] |

---

### WBS 7.0 — Phase 1: Knowledge Asset Building (W17+)

> **Status: IN PROGRESS** -- knowledge assets built (5 fault trees, 4 SOPs, 15 failure modes, OCAP rules, symptoms.toml), expert audit pending
> Git: `30a1f3c` docs(harness): WBS 7.0 -- knowledge asset review checklist for expert audit
> Git: fix(knowledge): resolve 22 fault tree cross-reference gaps

> **冷啟動 Phase 0 → Phase 1 過渡。** 專家用 L7 數據建構故障樹。

| WBS | 工作項目 | 產出 | 負責 | 估時 | 完成 |
|---|---|---|---|---|---|
| 7.1 | 匯出 L7 symptom_log 數據 | 高頻症狀組合 TOP 20 + 轉人案例完整對話 | Backend | 1d | [ ] |
| 7.2 | 專家審查 + 故障樹建構 | 10-15 份 `fault_trees/*.json` | 維修專家 | 10d | [~] |
| 7.3 | SOP 數位化 | 5-10 份 `sop/*.json` | 營運團隊 | 5d | [~] |
| 7.4 | 交叉引用驗證 | Python script 驗證所有 ID 引用正確 | Backend | 0.5d | [x] |
| 7.5 | 症狀詞表補充 | unknown:* 高頻項 → 新增到 symptoms.toml | 維修專家 + Backend | 1d | [~] |

**Total: 17.5d | 阻塞 V2.0 的前提條件**

---

### WBS 8.0 — V2.0: 派工系統 + 知識閉環 (W18+)

> **Status: IN PROGRESS** -- 16 service modules scaffolded in agent/services/ (GAP closure), runtime integration pending (services not wired into graph)

| WBS | 工作項目 | 產出 | 依賴 | 估時 | 完成 |
|---|---|---|---|---|---|
| 8.1 | 派工流程實作 | dispatch agent + WorkOrder model | 7.2 | 5d | [~] |
| 8.2 | 完工報告系統 | 技師 APP + service_reports schema (PostgreSQL) | 8.1 | 5d | [~] |
| 8.3 | 案例庫 PostgreSQL | case_library 表 + 寫入邏輯 | 8.2 | 2d | [x] |
| 8.4 | 故障樹權重修正批次 | case_library → fault_tree probability 自動更新 | 8.3 | 2d | [ ] |
| 8.5 | L8 Entropy 啟用 | SOP 自動生成 + OCAP 規則觸發 | 8.4 | 3d | [ ] |
| 8.6 | Defect 漸進標準化 | 完工報告 5 粗分類 → Level 2 標籤提煉 (Month 3+) | 8.2 | ongoing | [ ] |

**Total: 17d + ongoing**

---

### WBS 9.0 — GAP Closure (COMPLETE)

> **Status: COMPLETE** (2026-04-04) -- 30 項 GAP 系統性補齊

| WBS | Item | Output | Status | 完成 |
|---|---|---|---|---|
| 9.1 | 16 business service modules | agent/services/ (36 .py files) | COMPLETE | [x] |
| 9.2 | 14 design specifications | docs/02-design/specs/ | COMPLETE | [x] |
| 9.3 | SQL Schema extensions | SQL/Schema_v2_extensions.sql (6 new tables) | COMPLETE | [x] |
| 9.4 | ADR-006 LLM model selection | docs/01-define/adrs/adr-006-llm-model-selection.md | COMPLETE | [x] |
| 9.5 | Token budget implementation | harness/context/budget.py (GAP #4) | COMPLETE | [x] |
| 9.6 | Handoff/handback context | tools/transfer_human.py (GAP #5) | COMPLETE | [x] |

---

## 4. Critical Path

```
[DONE] H-Stage 0 (Foundation)
  │
  ├─ [DONE] WBS 4.0 P0/P1 優化 (平行) ─────────────────────────────┐
  │                                                                  │
  ▼                                                                  ▼
[DONE] WBS 1.0 L7 Observability                              V1.0 non-harness ready
  │
  ▼
[DONE] WBS 2.0 L1 Diagnostic Engine Wiring
  │
  ▼
[DONE] WBS 3.0 L6/L3 Safety + Governance
  │
  ▼
[DONE] WBS 9.0 GAP Closure (30 items)
  │
  ▼
★ V1.0 P0 Launch ★  ← NEXT: harness.enabled = true
  │
  ▼
WBS 5.0 UAT (W13-15) → L7 數據分析 → V1.1 決策
  │
  ├─ [if needed] WBS 6.0 L2/L5 (W16+)
  │
  ▼
[IN PROGRESS] WBS 7.0 Knowledge Building (專家審查 pending)
  │
  ▼
★ V2.0 Dispatch Launch (W18+) ★
  │
  ▼
[IN PROGRESS] WBS 8.0 案例庫 + 知識閉環 (16 modules scaffolded, runtime pending)
  │
  ▼
★ V2.x Autonomous Evolution (W22+) ★
```

---

## 5. Resource Allocation

| 角色 | WBS 1.0 | WBS 2.0 | WBS 3.0 | WBS 4.0 | WBS 5.0 | WBS 7.0 | WBS 8.0 |
|---|---|---|---|---|---|---|---|
| **Backend Engineer** | Lead | Lead | Lead | Lead | Support | Support | Lead |
| **維修專家** | — | — | — | — | Reviewer | **Lead** | Reviewer |
| **營運團隊** | — | — | — | — | — | SOP 數位化 | 完工報告流程 |
| **QA** | — | — | Test | — | **Lead** | Verify | Test |
| **Product** | — | Decision | — | — | Report | — | Decision |

---

## 6. Milestone Summary

| Milestone | 目標週 | 交付物 | Go/No-Go 條件 | 狀態 |
|---|---|---|---|---|
| **M1: L7 上線** | W3 | trace 數據開始收集 | 5 個對話 trace 正確寫入 | DONE (tracer.py + metrics.py) |
| **M2: L1 Wiring 完成** | W5 | diagnostic engine 接入 graph | 3 canonical cases PASS + cold start PASS | DONE (PDCA lifecycle) |
| **M3: L6/L3 上線** | W7 | safety gate + governance 接入 graph | 危險指令攔截 + 工具權限驗證 | DONE (safety_gate.py + registry.py) |
| **M3.5: GAP Closure** | — | 30 項 GAP 補齊 | 16 service modules + 14 specs + 6 SQL tables | DONE (2026-04-04) |
| **M4: V1.0 P0 Launch** | — | 完整 harness 流程上線 | harness.enabled = true + zero regression | PENDING |
| **M5: UAT 完成** | W15 | 50 題測試 + L7 分析報告 | ProblemCard fill rate >= 60% | PENDING |
| **M6: V1.1 決策** | W16 | L2/L5 啟用/跳過決策 | L7 數據支撐 | PENDING |
| **M7: Phase 1 知識資產** | W17 | 15+ fault trees + 10+ SOPs | 交叉引用驗證 PASS | IN PROGRESS (5 FT, 4 SOP, expert audit pending) |
| **M8: V2.0 Launch** | W18+ | 派工 + 完工報告 + 案例庫 | 端到端流程跑通 | IN PROGRESS (scaffolded) |
| **M9: 知識閉環自轉** | W22+ | 案例庫 > 500 + 權重自動修正 | AI prediction hit rate > 70% | PENDING |

---

## 7. Risk Register

| ID | 風險 | 機率 | 影響 | 緩解 | 負責 |
|---|---|---|---|---|---|
| R1 | L1 decompose 增加 > 3s 延遲 | Medium | V1.0 延遲 | 非技術 intent fast-path + Gemini Flash | Backend |
| R2 | graph/builder.py 改動影響現有流程 | Medium | Regression | decompose_enabled kill switch + 完整回歸測試 | Backend |
| R3 | 故障樹不夠（Phase 1 專家排程） | Medium | 淺診斷 | V1.0 靠 Tier 1 (FM registry + component graph)；故障樹是加分項 | Product + 維修專家 |
| R4 | LLM 診斷推理品質不穩 | Low | 誤診 | L5 Feedback + 3 輪追問上限 + 轉人安全網 | Backend |
| R5 | 知識資產版本衝突 | Low | 故障樹錯誤 | Git PR review + Python 交叉引用驗證腳本 | Backend |
