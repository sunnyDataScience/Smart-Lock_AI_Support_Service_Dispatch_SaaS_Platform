# Harness 框架比較報告：agent/ vs agent_skills/

> 撰寫日期：2026-04-10

---

## 1. 架構概覽

| 面向 | `agent/harness/` | `agent_skills/harness/` |
|------|------------------|------------------------|
| **設計哲學** | 8 層企業級框架，每層可獨立開關 | 9 個輕量中介層，嵌入 pipeline |
| **Agent 模式** | Multi-agent router + 13 node graph | Single ReAct agent + 2 tools |
| **整合方式** | Graph node（每層是獨立節點） | 函式呼叫（debounce.py 為 orchestrator） |
| **設定管理** | `config.toml [harness.*]` 巢狀結構 | `config.toml` 頂層區段各自 `enabled` |
| **程式碼量** | ~1,800 LOC（不含 graph） | ~1,450 LOC（含 orchestrator） |
| **知識來源** | pgvector RAG + fault trees + TOML 分類學 | Markdown SKILL.md SOPs |

---

## 2. 逐層比較

### L1 / H1 — 任務分解 vs 訊息路由

| | `agent/` L1 Task Decomposition | `agent_skills/` H1 Message Routing |
|--|--------------------------------|-----------------------------------|
| **檔案** | `harness/task/decomposer.py` (351 LOC) + `knowledge_loader.py` (178 LOC) | `app.py` webhook handler (~70 LOC) |
| **功能** | ProblemCard FSM + 4 層因果鏈（症狀→故障→故障模式→故障樹）+ LLM 診斷推理 | LINE 訊息四路分流（文字/媒體/貼圖/其他） |
| **設定** | `[harness.task] decompose_enabled = true` | 無開關（始終啟用） |
| **複雜度** | DiagnosticContext 狀態機（8 狀態轉換）、ProblemCard 完整度評分、PostgreSQL 持久化 | 簡單 isinstance 分支 |
| **agent_skills 不移植原因** | SKILL.md SOP 已內建診斷流程，不需要額外狀態機。維護 fault_trees JSON + symptoms TOML 成本遠高於維護 SKILL.md |

### L2 / H2 — 上下文組裝 vs 多模態前處理

| | `agent/` L2 Context Assembly | `agent_skills/` H2 Multimodal |
|--|------------------------------|-------------------------------|
| **檔案** | `harness/context/assembler.py` + `budget.py` + `token_tracker.py` + `freshness.py` (383 LOC) | `harness/multimodal.py` (176 LOC) + `media_storage/` |
| **功能** | Token 預算管理、來源新鮮度評分、RAG 相關性加權、L5 重試調整 | LINE 媒體下載 → Gemini Flash-Lite 文字描述 → 注入 buffer |
| **設定** | `[harness.context] assemble_enabled = false` | `[multimodal] enabled = false` |
| **狀態** | V1.0 停用（Phase 2 再啟用） | 程式碼完整，設定停用中 |
| **備註** | agent_skills 無 RAG，Token Budget 在 Gemini 1M context window 下非瓶頸 |

### L3 — 工具治理

| | `agent/` L3 Tool Governance | `agent_skills/` |
|--|----------------------------|-----------------|
| **檔案** | `harness/governance/registry.py` + `validator.py` (99 LOC) | **無對應** |
| **功能** | 工具風險分級（READ/WRITE/ESCALATE）、語意參數驗證、空查詢攔截 | — |
| **agent_skills 不移植原因** | 只有 2 個工具（`load_skill` + `transfer_to_human`），治理框架是過度設計 |

### L4 / H4+H5 — 狀態與記憶

| | `agent/` L4 State & Memory | `agent_skills/` H4 + H5 |
|--|----------------------------|--------------------------|
| **H4 畫像注入** | `graph/nodes.py` pre_process 節點載入 profile | `harness/debounce.py` run_agent() 注入 `[用戶資料]` 前綴 |
| **H5 記憶壓縮** | `graph/nodes.py` manage_memory 節點 | `harness/memory_manager.py` (144 LOC) |
| **Checkpointer** | PostgreSQL/SQLite（registry） | PostgreSQL/SQLite/MemorySaver（registry） |
| **Profile** | `profiles/manager.py` SCD Type 2 | 相同架構，已搬遷 |
| **壓縮機制** | LLM 摘要 + RemoveMessage | 相同機制 |
| **設定** | `[memory]` 區段 | `[memory] compression_enabled = true` |

### L5 — 回覆品質驗證

| | `agent/` L5 Feedback Loop | `agent_skills/` |
|--|--------------------------|-----------------|
| **檔案** | `harness/feedback/verifier.py` (129 LOC) | **無對應** |
| **功能** | LLM 4 維度評分（完整性/準確性/安全性/可操作性）、低分重試（→ L2 重新組裝上下文） | — |
| **設定** | `[harness.feedback] verify_enabled = false` | — |
| **狀態** | V1.0 已停用（latency ×2） | — |
| **agent_skills 不移植原因** | 每次回答多一次 LLM = latency ×2、cost ×2。`quality/quality_check.py` 離線 50 題測試已覆蓋品質保障 |

### L6 / H6 — 安全閘門

| | `agent/` L6 Safety Gate | `agent_skills/` H6 Safety Gate |
|--|------------------------|-------------------------------|
| **檔案** | `harness/safety/gate.py` (157 LOC) | `harness/safety_gate.py` (41 LOC) |
| **危險關鍵字** | regex 比對 + 攔截回應 | regex 比對 + 攔截回應 |
| **PII 偵測** | 電話 `09\d{2}`、email、身分證 `[A-Z][12]\d{8}` | **無** |
| **情緒分析** | OCAP 規則 → 4 級情緒（normal/medium/high/emergency）→ Red_Code 緊急升級 | **無** |
| **設定** | `[harness.safety] dangerous_instruction_keywords` | `[safety] enabled, dangerous_keywords, block_response` |
| **graph 整合** | 獨立 node，可觸發 3 路分支（block/diagnostic shortcut/normal） | debounce.agent_and_reply() 內呼叫，命中即 return |
| **差距** | — | 缺少 PII 偵測、情緒分析、OCAP 規則。可視需求逐步補上 |

### L7 / H7 — 輸出後處理

| | `agent/` Post-process | `agent_skills/` H7 LINE UI Factory |
|--|----------------------|-------------------------------------|
| **檔案** | `graph/nodes.py` post_process 節點 | `harness/line_ui_factory.py` (256 LOC) |
| **功能** | 格式化最終回覆 | URL 偵測 → Flex Message 卡片（GDrive PDF / YouTube）+ Markdown 清理 |
| **特色** | — | DOWNLOAD_CARD（品牌型號自動提取）、VIDEO_CARD（縮圖預覽） |
| **設定** | — | 無開關（始終啟用） |

### L7 / H8 — 可觀測性 vs 審計日誌

| | `agent/` L7 Observability | `agent_skills/` H8 Audit Logging |
|--|--------------------------|----------------------------------|
| **檔案** | `harness/observability/tracer.py` (163 LOC) + `metrics.py` (78 LOC) | `storage/postgres_impl.py` (202 LOC) |
| **追蹤方式** | `@traced` 裝飾器包裹每個 graph node → JSONL + PostgreSQL traces 表 | 結構化事件 API → PostgreSQL audit_log 表 |
| **事件類型** | node 執行追蹤（duration_ms, status, diagnosis_status） | 6 類事件：conversation, tool_invocation, safety_gate, escalation, llm_interaction, (removed: rag_citation) |
| **Session 指標** | SessionMetrics（node_path, total_latency, resolution_level） | **無** session 層級聚合 |
| **PII 處理** | — | `_mask_pii()` 遮罩電話/email/身分證 |
| **設定** | `[harness.observability] trace_enabled = true` | `[storage] type = postgres` |
| **差距** | — | 缺少 node 級執行追蹤、session 指標聚合。可用 Cloud Logging + Cloud Trace 替代 |

### L8 / H9 — 熵管理 vs 輪廓萃取

| | `agent/` L8 Entropy Management | `agent_skills/` H9 Profile Extraction |
|--|-------------------------------|--------------------------------------|
| **檔案** | `harness/entropy/checker.py` (92 LOC) + `sop_generator.py` (97 LOC) | `harness/profile_updater.py` (98 LOC) |
| **功能** | 偵測新型解法（fault tree 未覆蓋）→ LLM 自動生成 SOP 草稿 → 存入 knowledge_drafts/ | 每次對話後 LLM 萃取 phone/address/device_model/device_brand → PostgreSQL SCD Type 2 |
| **設定** | `[harness.entropy] sop_generation_enabled = true` | `[user_profile] enabled = true` |
| **備註** | agent_skills 的知識更新走 `data_skills/` pipeline，不從 runtime 繞過品質管控 |

---

## 3. 執行流程對比

### agent/ — 13 節點 Graph Pipeline

```
START → pre_process → manage_memory → rewrite_query
  → task_decompose [L1] → context_assemble [L2] → safety_gate [L6]
  → {diagnostic_respond | router → [7 agents]} → merge_answers
  → verify_answer [L5] → update_profile → entropy_check [L8]
  → post_process → END
```

- 3 個條件分支（safety_gate / verify_answer / router fan-out）
- 支援診斷短路（跳過 RAG 直接回覆）
- 支援品質重試迴圈（L5 → L2）

### agent_skills/ — 線性 Middleware Pipeline

```
LINE Webhook → H1 路由 → H2 多模態（可選）→ H3 防抖合併
  → H8 記錄使用者訊息 → H6 安全閘門
  → H4 用戶畫像注入 → H5 記憶壓縮 → Agent ainvoke()
  → H8 記錄工具呼叫/轉接/LLM 延遲
  → H9 背景輪廓萃取 → H8 記錄 AI 回覆
  → H7 URL→Flex 卡片 → LINE 回覆
```

- 純線性流程，無分支、無重試
- debounce.py 作為 orchestrator，串接所有 harness
- 背景非阻塞任務（H9 輪廓萃取、H8 audit）

---

## 4. 設定開關對照

| Harness | `agent/` config key | `agent_skills/` config key | 預設值 |
|---------|--------------------|-----------------------------|--------|
| 任務分解 / 路由 | `harness.task.decompose_enabled` | — (始終啟用) | ON / — |
| 上下文 / 多模態 | `harness.context.assemble_enabled` | `multimodal.enabled` | OFF / OFF |
| 工具治理 | — (始終啟用) | — (不適用) | — |
| 記憶壓縮 | `memory.max_messages` | `memory.compression_enabled` | ON / ON |
| 品質驗證 | `harness.feedback.verify_enabled` | — (不適用) | OFF / — |
| 安全閘門 | — (始終啟用) | `safety.enabled` | ON / ON |
| 可觀測 / 審計 | `harness.observability.trace_enabled` | `storage.type` | ON / ON |
| 熵管理 / 輪廓 | `harness.entropy.sop_generation_enabled` | `user_profile.enabled` | ON / ON |
| 防抖 | — (始終啟用) | `debounce.enabled` | — / ON |

---

## 5. 刻意不移植的層與原因

| agent/ 層 | 決策 | 原因 |
|-----------|------|------|
| **L1 Task Decomposition** | 不移植 | SKILL.md SOP 已內建診斷流程。ProblemCard FSM 是 RAG 路由專用機制，維護 fault_trees + symptoms TOML 成本高 |
| **L2 Token Budget** | 不移植 | Gemini 1M context window，短期非瓶頸 |
| **L3 Tool Governance** | 不移植 | 只有 2 個工具，框架過重 |
| **L5 Feedback Loop** | 不移植 | latency ×2，agent/ 自己也停用了 |
| **L7 @traced 裝飾器** | 不移植 | Cloud Logging + 現有 audit log 足夠 |
| **L8 SOP Generator** | 不移植 | 知識更新走 data_skills pipeline，不從 runtime 繞過品質管控 |

---

## 6. agent_skills/ 可補強方向

| 項目 | 優先級 | 說明 |
|------|--------|------|
| H6 PII 偵測 | 中 | 在 safety_gate.py 加入 `09\d{2}` / email / 身分證 pattern，攔截或遮罩後再送 LLM |
| H6 情緒分析 | 低 | 簡化版 OCAP：關鍵字偵測（非 LLM），高風險自動觸發 transfer_to_human |
| H8 Session 指標 | 低 | 聚合單次對話的 tool 呼叫次數、總延遲、是否轉接，供儀表板使用 |
| H7 輸出安全過濾 | 中 | AI 幻覺產生不當內容時的後置攔截（目前僅前置安全閘門） |

---

## 7. 程式碼量比較

| 模組 | `agent/` | `agent_skills/` |
|------|----------|-----------------|
| L1 / H1 | 529 LOC | 70 LOC |
| L2 / H2 | 383 LOC | 176 LOC |
| L3 | 99 LOC | — |
| L5 | 129 LOC | — |
| L6 / H6 | 157 LOC | 41 LOC |
| L7 / H7+H8 | 241 LOC | 256 + 202 LOC |
| L8 / H9 | 189 LOC | 98 LOC |
| H3 防抖 | — | 297 LOC |
| H5 記憶壓縮 | — | 144 LOC |
| **合計** | **~1,800 LOC** | **~1,450 LOC** |
