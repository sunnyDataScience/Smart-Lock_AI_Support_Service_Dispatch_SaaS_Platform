# Agent Harness Gap Analysis

> 8 層 Harness 框架 vs 現有 Smart Lock AI 客服系統的詳細差距分析
>
> **Architecture reference**: 診斷推理引擎採 Software 3.0 設計（LLM prompt reasoning with knowledge injection），
> 詳見 `[diagnostic-intelligence-architecture.md](./diagnostic-intelligence-architecture.md)`。
> 啟用策略詳見 `[optimization-strategy.md](./optimization-strategy.md)` §4/§6。

---

## Overview

本文件基於 `harness-architecture.md` 定義的 8 層框架，逐層盤點現有程式碼的對應實作、成熟度、以及需要補齊的缺口。

---

## L1 Task Representation Layer (任務表達層)

**成熟度: 60%** (↑ from 20% — Software 3.0 diagnostic engine implemented)

### 現有實作


| 元件                        | 檔案                                             | 功能                                                                                   |
| ------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------ |
| `question` 欄位             | `graph/state.py:34`                            | 原始使用者輸入                                                                              |
| `task` dict               | `graph/state.py:45`                            | Harness L1 state (goal, subtasks, diagnostic_context, problem_card)                  |
| `router` 意圖分類             | `graph/nodes.py:193-312`                       | LLM 分類 → 未來由 task_decompose 吸收，router 退化為 config lookup                              |
| `decomposer.py`           | `harness/task/decomposer.py`                   | **Software 3.0 實作** — KnowledgeLoader + LLM diagnostic reasoning + structured output |
| `knowledge_loader.py`     | `harness/task/knowledge_loader.py`             | 載入知識資產 (JSON/TOML) → 序列化為 prompt context                                             |
| `diagnostic_reasoning.md` | `harness/task/prompts/diagnostic_reasoning.md` | PDCA 診斷推理 prompt 模板                                                                  |
| `problem_card.py`         | `harness/task/problem_card.py`                 | ProblemCard dataclass + completeness scoring                                         |
| Knowledge assets          | `harness/task/knowledge/`                      | fault_trees, failure_modes, failures, SOP (JSON)                                     |
| Taxonomies                | `harness/task/taxonomy/`                       | symptoms.toml, components.toml (已驗證交叉引用正確)                                           |


### 缺口 (剩餘)

1. **task_decompose 尚未 wired into graph**: `decomposer.py` 實作完成但 `graph/builder.py` 未連接
2. **Router 未改為 config lookup**: 仍是 LLM-based intent classification
3. **agent prompt 未注入 diagnostic_context**: hardware_technician.md 未新增 `{diagnostic_context}` variable
4. **decompose_enabled = false**: config.toml 中仍為停用狀態 (需要 wiring 完成後再啟用)

---

## L2 Context Assembly Layer (上下文裝配層)

**成熟度: 40%**

### 現有實作


| 元件                       | 檔案                         | 功能                        |
| ------------------------ | -------------------------- | ------------------------- |
| `manage_memory`          | `graph/nodes.py:62-125`    | 50 則閾值語意壓縮，保留 20 對        |
| `pre_process` summary 注入 | `graph/nodes.py:40-47`     | 將摘要以 SystemMessage 注入     |
| `_extract_recent_pairs`  | `graph/nodes.py:165-190`   | Router 取最近 3 輪對話          |
| `user_profile` 注入        | `agents/__init__.py:60-61` | 固定注入至 agent system prompt |


### 缺口

1. **無 Context Rot 偵測**: summary 可能包含與當前問題無關的歷史話題，`pre_process` 只加了警告文字但無實質過濾
2. **無 Selective Retrieval**: 所有 agent 不論問題類型，都使用固定 `top_k` 查詢
3. **無 Token Budget**: 無法控制 context 總 token 量，依賴 LLM 自身的截斷
4. **Profile 注入不分場景**: `user_profile` 總是完整注入，不區分本次對話是否需要

### 補齊方案

- 新增 `harness/context/assembler.py` (graph node)
- 新增 `harness/context/budget.py` + `freshness.py`
- GraphState 新增 `context_meta: dict` 欄位

---

## L3 Tool Governance Layer (工具治理層)

**成熟度: 35%**

### 現有實作


| 元件                          | 檔案                      | 功能                      |
| --------------------------- | ----------------------- | ----------------------- |
| `build_tools()`             | `tools/__init__.py`     | Registry pattern 建構所有工具 |
| `config.toml [[databases]]` | `config.toml:86-172`    | 7 個 retriever 定義        |
| `llm_force_tool`            | `agents/__init__.py:48` | 有 retriever 時首次強制使用工具   |


### 缺口

1. **全工具啟動時全載**: `build_tools()` 在 `build_graph()` 時建構所有 7 個工具，即使 agent 只用 1 個
2. **無 Risk Stratification**: `transfer_to_human` 和 `db_video` 使用相同權限等級
3. **無 Parameter Validation**: 工具參數無 schema 驗證
4. **結果未裁剪**: pgvector 固定回傳 `top_k` 條，單條 document 長度無限制

### 補齊方案

- 新增 `harness/governance/registry.py` (ToolRegistry with risk levels)
- 新增 `harness/governance/validator.py`
- 修改 `agents/__init__.py` 的 `execute_tools` 包裹 middleware

---

## L4 State & Memory Layer (狀態與記憶層)

**成熟度: 45%**

### 現有實作


| 元件                      | 檔案                         | 功能                                       |
| ----------------------- | -------------------------- | ---------------------------------------- |
| PostgreSQL Checkpointer | `memory/postgres_saver.py` | LangGraph 原生持久化                          |
| `ProfileManager`        | `profiles/manager.py`      | SCD Type 2 hard_facts + .md soft_profile |
| `summary` 欄位            | `graph/state.py:24`        | 語意壓縮摘要                                   |
| `history` 欄位            | `graph/state.py:23`        | 路徑追蹤                                     |


### 缺口

1. **無 Artifact State**: ProblemCard 的診斷進度無法跨輪保存
2. **無 Instruction Fade-out 防護**: 長對話中 system prompt 的指令會因壓縮而淡化
3. **無 Event-driven Reminder**: 無法在特定條件下重新注入關鍵指令

### 補齊方案

- L4 主要利用現有 `memory/` + `profiles/` 基礎設施
- ProblemCard 持久化 (`harness/task/problem_card.py`) 補齊 artifact state
- Phase 2 的 `context_assemble` 實作 instruction reminder 機制

---

## L5 Feedback & Verification Layer (回饋與驗證層)

**成熟度: 0%**

### 現有實作

**無任何回饋驗證機制。**

`merge_answers` (`graph/nodes.py:317-452`) 僅做:

- 單 agent: 取最後一個 AI message
- 多 agent: LLM 合併
- 無品質檢查、無 confidence score、無 retry

### 缺口

1. **無 Evaluator Agent**: generator 和 evaluator 是同一個 LLM，無分離
2. **無品質分數**: 無法量化回覆的 completeness, accuracy, safety
3. **無 Retry 機制**: 低品質回覆直接送出
4. **無 Machine-consumable Failure Messages**: 錯誤訊息是人讀的罐頭文字

### 補齊方案

- 新增 `harness/feedback/verifier.py` (graph node)
- 新增 `harness/feedback/prompts/evaluate_answer.md`
- `builder.py` 加入 conditional feedback edge (retry loop)

---

## L6 Safety & Control Layer (安全與控制層)

**成熟度: 15%**

### 現有實作


| 元件                   | 檔案                        | 功能                   |
| -------------------- | ------------------------- | -------------------- |
| `sensitive_keywords` | `graph/nodes.py:219-227`  | 敏感詞強制轉接 receptionist |
| `transfer_to_human`  | `tools/transfer_human.py` | 人工轉接工具               |
| `debug_log`          | `core/debug_log.py`       | 原始訊息記錄               |


### 缺口

1. **無 Least Privilege 分級**: 所有 agent 共享相同工具權限
2. **無 Sandbox**: 無隔離執行環境
3. **無 Approval Gates**: `transfer_to_human` 以外無需批准的操作
4. **Audit Trail 不完整**: 只記錄原始訊息，未記錄 tool call 細節

### 補齊方案

- 新增 `harness/safety/gate.py` (graph node)
- `config.toml` 新增 `dangerous_instruction_keywords`
- GraphState 新增 `safety: dict` 欄位

---

## L7 Observability & Legibility Layer (觀測與可讀性層)

**成熟度: 15%**

### 現有實作


| 元件             | 檔案                             | 功能              |
| -------------- | ------------------------------ | --------------- |
| `debug_log.py` | `core/debug_log.py`            | 原始訊息 JSON dump  |
| `history` 欄位   | `graph/state.py:23`            | 路徑追蹤字串列表        |
| 散落的 `print()`  | 各 nodes.py, agents/**init**.py | 非結構化 console 輸出 |


### 缺口

1. **無結構化 Logging**: 所有輸出為非結構化 print()
2. **無 Metrics**: L1/L2/L3 命中率無計數
3. **無 Traces**: 節點延遲、token 使用量無追蹤
4. **無 Run Report**: 對話結束後無結構化的 session 報告

### 補齊方案

- 新增 `harness/observability/tracer.py` (`@traced` decorator)
- 新增 `harness/observability/metrics.py` (SessionMetrics)
- PostgreSQL migration: `harness_traces` table

---

## L8 Entropy Management Layer (熵管理層)

**成熟度: 0%**

### 現有實作

**無任何熵管理機制。**

知識庫是靜態的（ETL pipeline 手動觸發），無自動品質檢查、無新案例偵測、無 SOP 自動生成觸發。

### 缺口

1. **無 Golden Principles**: 無定義回覆品質標準文件
2. **無 Freshness Check**: pgvector 中過時的 document 無標記
3. **無 Quality Score**: 無歷史 feedback_score 分布
4. **無 SOP Auto-generation Trigger**: moat 文件定義了 SOP 飛輪但代碼未實作
5. **無 Scheduled Cleanup**: 無定期背景任務

### 補齊方案

- 新增 `harness/entropy/checker.py` (graph node)
- 新增 `harness/entropy/sop_generator.py`
- 新增 `harness/entropy/prompts/generate_sop.md`
- Async scheduled tasks for freshness + SOP generation

---

## Summary Matrix


| Layer            | Maturity | Key Gap                 | Phase   |
| ---------------- | -------- | ----------------------- | ------- |
| L1 Task          | 20%      | ProblemCard not in code | Phase 2 |
| L2 Context       | 40%      | No selective retrieval  | Phase 4 |
| L3 Governance    | 35%      | No risk stratification  | Phase 3 |
| L4 State         | 45%      | No artifact persistence | Phase 2 |
| L5 Feedback      | 0%       | Nothing exists          | Phase 5 |
| L6 Safety        | 15%      | Minimal guardrails only | Phase 3 |
| L7 Observability | 15%      | Unstructured print()    | Phase 1 |
| L8 Entropy       | 0%       | Nothing exists          | Phase 6 |


