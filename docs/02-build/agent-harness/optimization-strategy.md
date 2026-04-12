# Agent Harness Optimization Strategy

> 以用戶體驗為核心的架構優化策略：什麼該開、什麼不開、為什麼

---

## 1. 核心原則

LINE 用戶只在乎三件事：

1. **快不快？** (目標 < 5 秒回覆)
2. **準不準？** (解決我的問題)
3. **不行的話，能不能馬上找到人？**

架構決策的唯一標準：**用戶能感知到的改善 > 工程師自嗨的優雅**。

---

## 2. 延遲預算分析

### 當前架構 (全 Harness 啟用)

```
debounce wait          5.0s   ← 用戶在等，什麼都沒發生
pre_process            0.1s
manage_memory          0.1s
[task_decompose]       1.5s   ← LLM call
[context_assemble]     0.5s   ← DB query
[safety_gate]          0.1s
router                 1.5s   ← LLM call
agent (tool + LLM)     3.0s   ← pgvector + LLM call
merge_answers          0.1s
[verify_answer]        1.5s   ← LLM call
[retry if fail]       +5.0s   ← 整個 agent 再跑一次
update_profile         1.0s   ← LLM call
[entropy_check]        0.5s
post_process           0.1s
───────────────────────────────
最佳 (無 harness):     5.0 + 5.8 = ~11s
全 harness:            5.0 + 9.9 = ~15s
加 retry:              5.0 + 14.9 = ~20s
```

### 優化後（rewrite_query + task_decompose 診斷 + Router 零 LLM）

```
                       V1.0                 V2.0
debounce wait          2.0s                 2.0s
pre_process            0.1s                 0.1s
manage_memory          0.1s                 0.1s
rewrite_query          1.0s (LLM 改寫)       1.0s
task_decompose         1.5s (分類+診斷)       2.0s (分類+診斷+SOP)
router                 0.0s (config lookup) 0.0s (config lookup)
agent (tool + LLM)     3.0s                 3.0s
merge_answers          0.1s                 0.1s
update_profile         ---  (async)         ---  (async)
post_process           0.1s                 0.1s
─────────────────────────────────────────────────────
V1.0:                  2.0 + 5.9 = ~8s
V2.0:                  2.0 + 6.4 = ~8.4s
```

**V1.0: 11-20s → ~8s**。差距來自：砍 debounce 3s + async profile 1s + router 改 config lookup 省 1.5s。新增 rewrite_query +1.0s（口語→精確檢索句，提升 RAG 命中率）。
**V2.0: ~8.4s**。task_decompose 加 SOP 檢索 +0.5s。

---

## 3. 三機制疊加架構

### 設計公式

```
Multi-Agent Fan-out (平行查對的知識庫)
  × Three-Layer Cascade (每個 agent 內部有 L1→L2→L3 fallback)
  × Harness L5 Verify (跨 agent 的品質閘門)
  = 快速 + 精準 + 有保底
```

### 三機制角色分工


| 機制                      | 解決什麼問題             | 延遲成本               | V1.0 啟用？           |
| ----------------------- | ------------------ | ------------------ | ------------------ |
| **Multi-Agent Fan-out** | 問誰 (意圖→知識庫)        | 0s (平行)            | **Yes**            |
| **Three-Layer Cascade** | 答不出來怎麼辦 (L1→L2→L3) | +1-3s (worst case) | **Yes (agent 內部)** |
| **Harness L5 Verify**   | 答得好不好 (品質閘門)       | +1.5-5s            | **No (V1.2)**      |


### Fan-out vs Cascade：為什麼不重複？

乍看之下，task_decompose 的「意圖分類」和 Cascade 的「向量搜尋」都在「理解用戶問什麼」，容易誤判為功能重複。實際上它們是**正交的兩個維度，序列執行**：


|          | Multi-Agent Fan-out (task_decompose + router)             | Three-Layer Cascade (L1/L2/L3)       |
| -------- | --------------------------------------------------------- | ------------------------------------ |
| **決策問題** | **問誰** — 這句話屬於哪個知識領域？                                     | **找不找得到** — 選定 agent 的知識庫有沒有答案？      |
| **決策維度** | 分類 (categorical)：task_decompose LLM 分類 → router config 派發 | 相似度 (similarity)：score ≥ 0.85？       |
| **執行位置** | graph 層 (task_decompose: LLM / router: config lookup)     | agent 內部 (tool execution)            |
| **輸入**   | 用戶原始訊息 + 既有 TaskPlan（如有）                                  | agent 已確定後的 consolidated query       |
| **輸出**   | `next_agents: ["hardware_technician"]`                    | 一筆具體回覆 or `RETRIEVAL_LOW_CONFIDENCE` |


**分類是 Cascade 的必要前置步驟**：必須先知道「問哪個 agent」(task_decompose 分類 → router 派發)，才能決定「在哪個知識庫做搜尋」(Cascade)。

```
用戶: "我的門鎖按指紋沒反應"

task_decompose: "這是硬體問題" → intents=["hardware_tech"]  ← 解決: 問誰？(LLM)
router: config lookup → hardware_technician                ← 確定性派發

Agent 內部:
  L1: pgvector(db_video) score=0.92 → HIT，回覆              ← 解決: 找不找得到？
  L1 miss → L2: db_line_chat, db_manuals → 回覆
  L2 miss → L3: transfer_to_human
```

刪掉分類直接搜全部知識庫不可行 — 不同 agent 有不同 system prompt、回覆風格、fallback 策略。分類選的不只是知識庫，是**整套回覆行為**。

> `**task_decompose` (Harness L1) = 意圖分類 + 診斷推理引擎。** 非技術查詢直接派發；技術查詢全部進入診斷推理（PDCA 結構），推理深度由資訊充分度動態決定。Router 退化為純確定性派發器。詳見 §6 + `[diagnostic-intelligence-architecture.md](./diagnostic-intelligence-architecture.md)`。

### 資訊流

```
User Message
  │
  ▼
[debounce 2s] → [pre_process] → [manage_memory]
  │
  ▼
[task_decompose]
  │  Tier 1: 意圖分類 (所有查詢, ~1.5s)
  │  Tier 2: 診斷推理引擎 (所有技術性查詢, PDCA loop)
  │          Plan → Do → Check → Act, 深度由資訊充分度決定
  │
  ▼
[router: 確定性派發 (零 LLM)]
  │  intents → config lookup → next_agents
  │                                          ↑ 純 dict mapping
  ▼ Send() fan-out
┌─────────────── Agent Subgraph (each) ───────────────┐
│                                                      │
│  agent_llm → tool call:                              │
│    L1: pgvector search (similarity ≥ 0.85)           │  ← "找不找得到"
│      ├─ HIT → 用 context 生成回覆                     │     (Cascade)
│      └─ MISS → "RETRIEVAL_LOW_CONFIDENCE"            │
│                  │                                    │
│                  ▼                                    │
│    L2: fallback tools (config.toml fallback_tools)   │
│      ├─ HIT → 用 broader context 生成回覆             │
│      └─ MISS → agent 呼叫 transfer_to_human          │
│                  │                                    │
│                  ▼                                    │
│    L3: 轉接真人 (帶 ProblemCard + profile)             │
│                                                      │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
[merge_answers] → [update_profile (async)] → [post_process] → LINE 回覆
```

---

## 4. Harness 各層啟用策略

### V1.0：只開必要的


| Layer            | 元件                       | 啟用？                    | 理由                                                            |
| ---------------- | ------------------------ | ---------------------- | ------------------------------------------------------------- |
| L1 Task          | task_decompose           | **Yes (Software 3.0)** | 意圖分類 + 診斷推理引擎 (LLM prompt reasoning with knowledge injection) |
| L2 Context       | context_assemble         | **No**                 | 理論改善未驗證；manage_memory 已夠用                                     |
| L3 Governance    | ToolRegistry risk levels | **Yes (輕量)**           | 不用 LLM，regex + config 判斷，成本 ~0                                |
| L4 State         | memory + profiles        | **Already on**         | 核心功能                                                          |
| L5 Feedback      | verify_answer            | **No**                 | +1.5-5s 延遲，品質提升 vs 速度損失不划算                                    |
| L6 Safety        | safety_gate              | **Yes (regex)**        | regex 攔截危險指令，不用 LLM，成本 ~0                                     |
| L7 Observability | @traced                  | **Yes**                | decorator 不影響延遲，提供量化數據                                        |
| L8 Entropy       | entropy_check            | **Yes (async)**        | 不在 request path，背景執行零延遲影響                                     |
| —                | router                   | **Yes (config only)**  | 純確定性派發：intents → config lookup → next_agents，零 LLM            |


### Software 3.0: 不再區分 lite/full mode

> 舊設計 (已淘汰): `mode = "lite"` (純分類) vs `mode = "full"` (分類 + Python set matching + SOP)。
> 新設計: 診斷推理深度由**知識上下文的豐富度**自然決定，不需要 mode 切換。

```
零故障樹 (Day 1):
  Tier 1 context (FM registry + component graph) → LLM 做基本推理
  → 淺診斷，但比沒有好

有故障樹 (Phase 1+):
  Tier 1 + Tier 2 context (filtered fault trees) → LLM 用驗證鏈做精確鑑別
  → 深診斷，expert-curated precision

更多故障樹 + 案例庫統計 (Phase 2):
  Tier 1 + Tier 2 + 歷史統計 → LLM 有數據支撐的假設排序
  → 最深診斷，data-driven
```

### 為什麼合併 task_decompose + router

```
原設計 (分離):
  task_decompose → category = hardware_fault    ← LLM call #1
  router         → intent  = hardware_tech      ← LLM call #2
  問題: 兩個 LLM 可能分類不一致，延遲 3.0s

Software 3.0 (合併):
  task_decompose → 意圖分類 + 診斷推理 (單一 LLM call with knowledge context)
  router         → config lookup → next_agents  ← 0ms (確定性)
  優勢: 零矛盾，單一 LLM call 涵蓋分類+診斷
```

### V1.1 (Harness H-Stage 1-3)：有 data 證明再開


| Layer       | 啟用條件                                  | 量化依據                         |
| ----------- | ------------------------------------- | ---------------------------- |
| L1 Task     | **V1.0 即啟用** (Software 3.0 不需要等 V2.0) | 知識上下文豐富度自然決定深度               |
| L2 Context  | L7 數據顯示 context 品質是瓶頸                 | L1 命中率 < 60% 且非 seed data 問題 |
| L5 Feedback | L7 數據顯示回覆品質低於 SOW 標準                  | 準確率 < 80% 且非知識庫覆蓋問題          |


### 決策原則

```
不要因為「可能有用」就啟用。
要因為「數據證明有用」才啟用。
L7 Observability 的存在就是為了產出這些數據。
```

---

## 5. Three-Layer Cascade 實作規格

### L1: pgvector Score Gate

```
位置: agent/tools/pgvector_store.py
改動: similarity_search → similarity_search_with_score
邏輯: score ≥ 0.85 → 使用，score < 0.85 → 過濾
miss: 回傳 "RETRIEVAL_LOW_CONFIDENCE" 信號給 agent LLM
```

### L2: Fallback Tool Cascade

```
位置: agent/config.toml [[agents]] + agent/agents/__init__.py
設定: fallback_tools = ["db_line_chat", "db_manuals"]
邏輯: agent LLM 收到 LOW_CONFIDENCE → 自動嘗試 fallback tools
```

### L3: Auto-Escalation Gate

```
位置: agent prompt (agents/prompts/*.md) + transfer_to_human tool
邏輯: L1+L2 都 miss → agent prompt 明確指示「承認不知道並轉接」
      不依賴 LLM 主觀判斷，靠 prompt engineering 確保行為
```

### 三層命中率目標

```
L1 (primary pgvector, ≥0.85):     目標 ≥ 60%
L2 (fallback collections):         目標 ≥ 80% (L1+L2 合計)
L3 (transfer_to_human):            目標 ≤ 20%
```

---

## 6. task_decompose 意圖分類 + 診斷推理引擎 + Router 純派發

> 完整診斷架構設計詳見 `[diagnostic-intelligence-architecture.md](./diagnostic-intelligence-architecture.md)`。
> 本節為 optimization-strategy 視角的摘要與延遲預算。

### 架構決策：診斷推理是核心引擎，不是可選功能

**舊設計的問題**：診斷分析只在「多症狀共現」才觸發。但即使用戶只說「鎖壞了」三個字，仍需要假設→驗證→縮窄→確認的推理鏈。把診斷當作可選功能，等於放棄了系統的核心價值。

**新設計**：所有技術性查詢都進入診斷推理。推理深度由**資訊充分度**動態決定，而非症狀數量。

```
task_decompose 內部兩層：

  Tier 1 — 意圖分類 (所有查詢，~1.5s)
    非技術性 → 直接派發，不進入診斷
    技術性   → 進入 Tier 2 診斷推理引擎 ↓

  Tier 2 — 診斷推理引擎 (所有技術性查詢，深度動態調整)
    遵循 PDCA 結構:
      Plan: 症狀提取 → Failure 識別 → FM 假設排序 → 資訊充分度評估
      Do:   資訊不足 → 從驗證鏈取最高效問題 → 注入 agent prompt 追問
      Check: 用戶回覆 → 更新假設空間 → 重新評估充分度
      Act:  充分 → 給結論 + CA/PA | 3 輪仍不足 → 建議到府檢測
```

### 所有技術性查詢的處理路徑


| 查詢         | 意圖            | 診斷推理？   | LLM diagnosis_status          | 知識上下文                                  |
| ---------- | ------------- | ------- | ----------------------------- | -------------------------------------- |
| "營業時間?"    | store_info    | **No**  | —                             | —                                      |
| "你們鎖多少錢?"  | sales         | **No**  | —                             | —                                      |
| "鎖壞了"      | hardware_tech | **Yes** | `need_more_info` — 追問具體現象     | Tier 1 only                            |
| "指紋沒反應"    | hardware_tech | **Yes** | `need_more_info` — 匹配 FM，走驗證鏈 | Tier 1 + Tier 2 (if fault tree exists) |
| "指紋+藍牙都不行" | hardware_tech | **Yes** | `confident` — 共因分析    | Tier 1 + Tier 2 (FT-HW-003 matched)    |
| "怎麼換電池"    | hardware_tech | **Yes** | `recommend_dispatch` — 操作指引    | Tier 1 (非故障，LLM 直接判斷)                  |


**Software 3.0 關鍵**：所有技術查詢都進入同一個 LLM call，差異在知識上下文的豐富度。LLM 自行判斷 `diagnosis_status`，Python 不做 hardcoded confidence 計算。

### 三類知識資產：故障樹 + SOP + 案例庫

> **命名區分**：本節的「知識資產 KA-1/2/3」是存儲層分類。
> 診斷架構的「Layer 0-6」是推理層分類，詳見 `[diagnostic-intelligence-architecture.md](./diagnostic-intelligence-architecture.md)` §3。

老師傅的「直覺」不是玄學，是壓縮過的因果模型。系統化後分三類知識資產，供診斷推理引擎使用：

```
KA-1: 故障樹 (Fault Tree) — 因果知識
  ┌──────────────────────────────────────────────────────┐
  │  症狀組合 → 根因假設（含機率權重）→ 鑑別問題 → 解決方案  │
  │  存儲: JSON 檔案 (knowledge/fault_trees/*.json)        │
  │  查詢: Python set 匹配 (確定性，記憶體操作)             │
  │  來源: 老師傅經驗提煉 + 產品技術文件                     │
  │  對應診斷架構: Layer 3 (Failure Mode) + Layer 5 (驗證鏈) │
  └──────────────────────────────────────────────────────┘
        │ 確認根因後
        ▼
KA-2: SOP 流程 (Standard Operating Procedure) — 處理流程
  ┌──────────────────────────────────────────────────────┐
  │  根因/類別 → 標準處理步驟（診斷/報價/派工/完工）          │
  │  存儲: JSON 檔案 (knowledge/sop/*.json)                │
  │  查詢: Python dict lookup by category (確定性)         │
  │  來源: 公司營運流程、維修部 SOP 文件                     │
  │  觸發: 需跨輪次追蹤的任務 (V2.0 派工流程)                │
  └──────────────────────────────────────────────────────┘
        │ 完工回報後
        ▼
KA-3: 案例庫 (Case Library) — 經驗回饋
  ┌──────────────────────────────────────────────────────┐
  │  完工紀錄: 實際根因 + 實際解法 + 耗時 + 費用             │
  │  存儲: Phase 0-1 不存在; Phase 2 遷移至 PostgreSQL      │
  │  查詢: Phase 2 才需要 (結構化 SQL)                     │
  │  來源: 技師完工回報、客戶滿意度調查                      │
  │  用途: 修正故障樹機率權重，持續進化                      │
  │  對應診斷架構: Layer 6 (Knowledge Loop)                 │
  └──────────────────────────────────────────────────────┘

元件關係圖: Config TOML (靜態拓撲)
  ┌──────────────────────────────────────────────────────┐
  │  元件間的連接與依賴關係 (幾十行 TOML，非圖資料庫)        │
  │  存儲: harness/task/taxonomy/components.toml          │
  │  用途: 診斷推理中判斷不同 component 是否共享上層依賴      │
  │  例: fingerprint_module → i2c_bus ← comm_module       │
  │      兩者共享 i2c_bus → 可能同源故障                    │
  └──────────────────────────────────────────────────────┘
```

#### 存儲方案決策：檔案驅動 + 漸進遷移

> 完整存儲架構設計詳見 `[diagnostic-intelligence-architecture.md](./diagnostic-intelligence-architecture.md)` §7。

**Phase 0-1 全部用檔案，Phase 2 再視規模遷移。** 理由：

```
Phase 0-1 的現實:
  故障樹 20-50 份、SOP 10-20 份、案例庫 0 筆
  資料模型還在迭代 (本次對話就改了 4 次)
  
  PostgreSQL 在這個階段 = schema migration 摩擦 + ORM 學習成本 + 本地開發需啟動 DB
  JSON 檔案 = Git 版本控制 + 專家可直接編輯 + 零依賴 + 改格式不需 migration

  pgvector 不適用: 知識資產的查詢是確定性集合匹配，不是語意相似度
  Graph RAG 不適用: 元件拓撲固定，幾十行 TOML 就能表達
```


| 存儲             | 適用對象                   | 查詢方式                              | Phase          |
| -------------- | ---------------------- | --------------------------------- | -------------- |
| **JSON 檔案**    | 故障樹、SOP、Failure 定義     | Python `json.load()` + 記憶體 set 匹配 | Phase 0-1      |
| **TOML 檔案**    | 症狀詞表、元件拓撲              | Python dict lookup                | 永久 (靜態配置)      |
| **pgvector**   | 手冊、影片字幕、LINE 對話紀錄      | cosine similarity                 | 永久 (RAG 場景)    |
| **PostgreSQL** | 案例庫 (累積寫入)、symptom_log | SQL 結構化查詢                         | Phase 2 (規模化後) |


**遷移觸發條件** (任一成立): 案例庫 > 500 筆 / 多 instance 併發寫入 / 故障樹 > 100 份。
JSON 結構 1:1 對映 PostgreSQL 表，`KnowledgeLoader` 介面不變，底層替換。

#### 檔案結構與匹配邏輯

```
agent/harness/task/
├── taxonomy/                          # TOML — 標準化詞表
│   ├── symptoms.toml                  # 51 症狀 (含口語 aliases)
│   └── components.toml                # 30 元件 (含拓撲關係)
├── knowledge/                         # JSON — 知識資產
│   ├── failures/failure_taxonomy.json # 7 故障類別
│   ├── failure_modes/failure_mode_registry.json  # 15 失效模式
│   ├── fault_trees/                   # 5 棵故障樹
│   │   ├── FT-HW-001.json            # 門扇卡死
│   │   ├── FT-HW-002.json            # 自動上鎖失效
│   │   ├── FT-HW-003.json            # 異常警報
│   │   ├── FT-HW-004.json            # 驗證失敗
│   │   └── FT-HW-005.json            # 電力與網路
│   ├── sop/                           # 4 份 SOP
│   │   ├── SOP-HW-001.json           # 硬體維修
│   │   ├── SOP-CS-001.json           # 客服分診
│   │   ├── SOP-DISPATCH-001.json     # 派工決策
│   │   └── SOP-EMERGENCY-001.json    # 緊急鎖門 Red_Code
│   └── ocap_rules.json               # OCAP + 情緒升級規則
├── prompts/
│   ├── diagnostic_reasoning.md        # 主 prompt: PDCA 診斷推理
│   └── decompose_task.md              # 任務分解 prompt
├── knowledge_loader.py                # 知識載入 + 序列化
├── decomposer.py                      # task_decompose node
└── problem_card.py                    # ProblemCard dataclass
```

```python
# Software 3.0: Python 只做 load + filter + serialize，推理全在 LLM prompt 中
loader = KnowledgeLoader("harness/task")

# Tier 1 (always injected)
symptom_taxonomy = loader.get_symptom_taxonomy()   # symptoms.toml → str
failure_context = loader.get_failure_context()       # failures + FMs → JSON str
component_graph = loader.get_component_graph()       # components.toml → str

# Tier 2 (filtered by previous round's symptoms — NOT diagnostic reasoning)
fault_trees = loader.get_relevant_fault_trees(prev_symptom_ids)  # any overlap → include

# SOP lookup: dict by category
sop = loader.get_sop("hardware_fault")

# Post-LLM output: validate symptom IDs (3-line safety check)
validated = loader.validate_symptom_ids(llm_output["extracted_symptoms"])
```

知識資產格式範例見 `knowledge/fault_trees/FT-HW-*.json` 和 `knowledge/sop/SOP-*.json`。

#### 症狀詞表 (Symptom Taxonomy)

故障樹的 `symptom_pattern` 使用標準 symptom_id。LLM 從使用者口語提取症狀時也必須輸出相同的 id，否則匹配會失敗。因此需要一份共享詞表作為橋樑。

**檔案位置**：`agent/harness/task/taxonomy/symptoms.toml`
**Config 引用**：`config.toml` → `[harness.task].symptom_taxonomy`

```toml
# 範例：symptoms.toml 結構

[symptoms.fingerprint_no_response]
label     = "指紋無反應"
aliases   = ["按指紋沒反應", "指紋辨識不了", "指紋失靈", "感應不到指紋"]
component = "fingerprint_module"
severity  = "high"

[symptoms.bluetooth_disconnected]
label     = "藍牙無法連線"
aliases   = ["藍牙連不上", "APP連不到", "配對失敗", "搜不到鎖"]
component = "comm_module"
severity  = "high"
```

**四個欄位各司其職**：


| 欄位                 | 用途                          | 使用者                        |
| ------------------ | --------------------------- | -------------------------- |
| `symptom_id` (key) | 標準標籤，故障樹 symptom_pattern 引用 | task_decompose ↔ 故障樹       |
| `aliases`          | 使用者口語對照表，注入 LLM prompt 供映射  | task_decompose Tier 1      |
| `component`        | 所屬硬體元件，用於症狀關聯快速判斷           | task_decompose Tier 2 觸發條件 |
| `severity`         | 嚴重程度，影響回覆優先順序和是否建議緊急到府      | agent prompt               |


**LLM 如何使用詞表**：task_decompose 的 Tier 1 prompt 注入詞表摘要，LLM 將口語映射為標準標籤：

```
用戶: "按指紋沒反應，APP也連不上藍牙"

LLM 拿到詞表:
  "按指紋沒反應" → 匹配 fingerprint_no_response.aliases → ✓
  "APP也連不上藍牙" → 匹配 bluetooth_disconnected.aliases → ✓

輸出: symptoms = ["fingerprint_no_response", "bluetooth_disconnected"]
```

**故障樹匹配**：因為兩邊用同一套 symptom_id，匹配是確定性集合運算：

```
故障樹 FT-HW-003.symptom_pattern.required = ["fingerprint_no_response", "bluetooth_disconnected"]
task_decompose 提取結果 = ["fingerprint_no_response", "bluetooth_disconnected"]
set(required) ⊆ set(extracted) → 命中 ✓
```

**component 的 Tier 2 觸發判斷**：

```
symptoms = [fingerprint_no_response, bluetooth_disconnected]
components = {fingerprint_module, comm_module}  ← 兩個不同元件

→ 不同元件同時故障 → 可能共享上層依賴 → 觸發故障樹搜尋

對比:
symptoms = [fingerprint_no_response, fingerprint_slow]
components = {fingerprint_module}  ← 同一元件

→ 同元件多症狀 → 根因明顯是指紋模組本身 → 不需故障樹
```

**未知症狀處理**：

```
用戶: "我的鎖會發出怪聲"

LLM 匹配到 abnormal_noise.aliases → symptoms = ["abnormal_noise"]

用戶: "我的鎖會噴水" (詞表沒有)

LLM 無法匹配 → symptoms = ["unknown:鎖會噴水"]
→ 不觸發 Tier 2，正常派給 hardware_tech
→ L8 Entropy 監測 unknown:* 出現頻率
→ 高頻 unknown 通知維修部新增詞表條目
```

### task_decompose 覆蓋所有場景


| 場景            | Tier 1 意圖分類                    | Tier 2 診斷深化？    | SOP/TaskPlan？  | Router                        |
| ------------- | ------------------------------ | --------------- | -------------- | ----------------------------- |
| "營業時間?"       | `store_info`                   | No              | No             | → store_assistant             |
| "APP怎麼配對藍牙?"  | `app_support`                  | No              | No             | → app_specialist              |
| "你們鎖多少錢?"     | `sales`                        | No              | No             | → sales_representative        |
| "怎麼換電池"       | `hardware_tech`                | No (單一明確問題)     | No             | → hardware_technician         |
| "指紋不行+藍牙不通"   | `hardware_tech`                | **Yes** (多症狀共現) | Yes (ProblemCard)  | → hardware_technician (帶根因假設) |
| "鎖壞了+營業時間"    | `hardware_tech` + `store_info` | Yes (模糊→追問)      | Yes (ProblemCard)  | → fan-out 2 agents            |
| "幫我叫師傅" (跨輪次) | 讀 TaskPlan                     | 視累積症狀而定         | Yes (推進 step)    | → sales / dispatch            |


### 診斷深度由知識上下文自然決定（不再區分 lite/full mode）

> 舊設計的 lite/full mode 切換已淘汰（見 §4）。Software 3.0 中所有技術查詢進入同一個 LLM call，差異在知識上下文的豐富度。

```
零故障樹 (Day 1):
  Tier 1 context only (FM registry + component graph)
  → LLM 做基本分類 + 淺診斷，延遲 ~1.5s

有故障樹 (Phase 1+):
  Tier 1 + Tier 2 context (filtered fault trees + SOP)
  → LLM 用驗證鏈做精確鑑別，延遲 ~2.0s

更多故障樹 + 案例庫 (Phase 2):
  Tier 1 + Tier 2 + 歷史統計
  → LLM 有數據支撐的假設排序，延遲 ~2.0-2.5s
```

### Router 的新角色：確定性派發器

```python
# 新 router — 零 LLM，純 config mapping
def router(state: GraphState) -> dict:
    intents = state["intents"]  # from task_decompose
    intent_agent_map = load_intent_agent_map()  # from config.toml
    next_agents = [intent_agent_map[i] for i in intents]
    return {"next_agents": next_agents}
```

Router 不再需要理解自然語言，它只做一件事：查表。100% 可測試，零幻覺。

### 完整範例對比：不同查詢的處理路徑

> 完整 4 輪對話範例詳見 `[diagnostic-intelligence-architecture.md](./diagnostic-intelligence-architecture.md)` §5。

#### 範例 1：非技術查詢（只走 Tier 1）

```
用戶: "你們週末有開嗎？"

task_decompose:
  Tier 1: intents=["store_info"], category=general_info
  → 非技術意圖，不進入 Tier 2
  輸出: { intents: ["store_info"] }

router: config lookup → store_assistant
agent: "我們週末 10:00-18:00 營業。"

延遲: ~1.5s
```

#### 範例 2：技術查詢 — 操作指引類（Tier 2 即結）

```
用戶: "怎麼換電池？"

task_decompose:
  Tier 1: intents=["hardware_tech"], category=hardware_maintenance
  Tier 2 (診斷推理):
    Symptom: 無故障症狀，是操作問題
    diagnosis_status: "confident" (根因明確: 用戶需要操作指引，非故障診斷)
    → 即結，不需追問
  輸出: { intents: ["hardware_tech"], query_type: "how_to" }

router: config lookup → hardware_technician
agent: 從知識庫撈到換電池教學 → 回覆步驟

延遲: ~1.5s (Tier 2 判定為即結，無額外成本)
```

#### 範例 3：技術查詢 — 模糊描述（Tier 2 追問）

```
用戶: "我的鎖壞了"

task_decompose:
  Tier 1: intents=["hardware_tech"], category=hardware_fault
  Tier 2 (診斷推理):
    Symptom: 無具體症狀 (用戶描述太模糊)
    Failure: 無法確定 (可能是 F-LOCK-001~007 中任一)
    diagnosis_status: "need_more_info" (資訊嚴重不足)
    → 需要追問，注入驗證步驟到 agent prompt
    → CA 預備: "如果急著進門，可以先試備用鑰匙"
  輸出: { intents: ["hardware_tech"], verification_next_step: "請描述具體現象" }

router: config lookup → hardware_technician
agent: "能描述一下具體是什麼狀況嗎？例如按指紋沒反應？螢幕不亮？
       如果您現在急著進門，可以先試試備用鑰匙。"

延遲: ~1.8s (Tier 2 做了充分度評估 + CA 準備)
```

#### 範例 4：技術查詢 — 多症狀深度診斷（Tier 2 假設 + 鑑別）

```
用戶: "指紋沒反應，APP也連不上藍牙，順便問你們週末有開嗎？"

task_decompose:
  Tier 1: intents=["hardware_tech", "store_info"]
  Tier 2 (診斷推理):
    Symptom: [fingerprint_no_response, bluetooth_disconnected]
    Failure: F-LOCK-003 間歇性功能失效 (兩個模組同時異常)
    FM 假設 (fault_trees 查詢):
      FM-ELEC-002 I2C 通訊中斷 (45%)
      FM-ELEC-002 接觸不良 / 排線鬆脫 (30%)
      FM-POWER-002 供電波動
    diagnosis_status: "need_more_info" → 需鑑別
    verification_next_step: "螢幕有亮嗎？"
  輸出: hardware_tech → 帶假設 + 鑑別問題; store_info → 無附加

router: fan-out → hardware_technician + store_assistant

hardware_technician 收到: symptoms + fm_hypotheses + "先問螢幕是否亮起"
store_assistant 收到: 正常問答

延遲: ~2.0s (Tier 2 做了故障樹查詢 + 假設排序)
```

### V2.0 跨輪次派工

```
第 1 輪: "我的鎖壞了"
  task_decompose:
    Tier 1: intents=["hardware_tech"]
    Tier 2: diagnosis_status="need_more_info" → 追問具體現象
    SOP-HW-001 → subtasks: [diagnose✦, quote, confirm, dispatch, complete]
  router: → hardware_technician
  agent: "能描述一下是什麼狀況嗎？按指紋沒反應還是密碼按了沒動靜？"

第 2 輪: "按指紋沒反應，藍牙也連不上"
  task_decompose:
    Tier 1: 讀取 TaskPlan → diagnose 進行中
    Tier 2: 累積症狀=[fingerprint, bluetooth] → 觸發故障樹 FT-HW-003
    → 根因假設 + 鑑別問題
  router: → hardware_technician (帶根因假設)
  agent: "這兩個問題可能是同一個原因造成的。請問螢幕有亮嗎？"

第 3 輪: "螢幕正常，就是指紋和藍牙不行"
  task_decompose:
    → 鑑別結果: 排除 mainboard_power → 聚焦 comm_board/cable (75%)
    → diagnose ✓ → current_step=quote✦
  router: → sales_and_service
  agent: "可能是通訊板或排線問題，需到府檢測。
         檢測費 $500 (可折抵)，維修 $1,800-$3,500..."

第 4 輪: "好，幫我叫師傅"
  task_decompose:
    Tier 1: 讀取 TaskPlan → quote ✓ → confirm ✓ → dispatch✦
    Tier 2: 不觸發 (非診斷步驟)
  router: → dispatch_agent

✦ = current_step
```

### 知識進化閉環

```
完工回報 (技師填寫):
  工單 WO-20260403-001
  原始假設: comm_board (45%), cable_loose (30%)
  實際根因: cable_loose (排線接觸不良)
  實際解法: 重新固定排線 + 更換排線扣
  費用: $800 (低於通訊板更換的 $3,500)

案例庫更新:
  case_library.insert({
    fault_tree: "FT-HW-003",
    symptoms: [fingerprint, bluetooth],
    predicted: "comm_board (45%)",
    actual: "cable_loose",
    model: "dormakaba DP850"
  })

故障樹權重修正 (定期批次):
  FT-HW-003 中 dormakaba DP850 的歷史:
    cable_loose: 84/211 = 40% (原 30% → 上調)
    comm_board:  85/211 = 40% (原 45% → 下調)
    → 故障樹更新: cable_loose 和 comm_board 對 DP850 權重拉平

下次遇到同樣症狀 + DP850:
  "根據歷史維修紀錄，dormakaba DP850 這個症狀 40% 是排線問題（維修 $800），
   40% 是通訊板問題（維修 $3,500）。建議先到府檢測確認。"
```

### 設計原則

```
task_decompose 是唯一的「理解」節點，內部兩層各司其職:
  Tier 1 (所有查詢): 意圖分類 — 決定「問誰」
  Tier 2 (僅技術診斷): 症狀分析 + 根因假設 — 決定「為什麼壞」
  非診斷查詢不付診斷成本。簡單問題走快速路徑。

Router 是純粹的「派發」節點:
  只做 intent → agent 的 config mapping。零 LLM，100% 確定性。

知識資產各司其職:
  KA-1 故障樹回答「為什麼壞」(因果) — 診斷推理引擎用
  KA-2 SOP 回答「怎麼處理」(流程) — 跨輪次任務用
  KA-3 案例庫回答「上次怎麼修」(經驗) — 故障樹權重修正 + agent RAG

知識是活的:
  每一張完工回報都在修正故障樹的機率權重。
  系統越用越準，因為它在持續學習老師傅們的集體經驗。
```

### 資訊流（V1.0 + V2.0 統一路徑）

```
User Message
  │
  ▼
[pre_process] → [manage_memory] → [rewrite_query]
  │                                   ↑ LLM 將口語改寫為精確檢索句
  ▼
[task_decompose]
  │
  │  Tier 1 — 意圖分類 (所有查詢，~1.5s)
  │  ├─ 非技術意圖 → intents 確定，直接派發
  │  └─ 技術意圖 → 進入 Tier 2 診斷推理引擎 ↓
  │
  │  Tier 2 — 診斷推理引擎 (所有技術性查詢，Software 3.0 PDCA)
  │  ├─ Python: load Tier 1/2 knowledge → inject into LLM prompt
  │  ├─ LLM: Symptom 提取 → Failure 識別 → FM 假設 → 驗證問題選擇
  │  ├─ LLM 輸出 diagnosis_status:
  │  │    confident → 給結論 + CA
  │  │    need_more_info → 注入 next_action → agent 追問
  │  │    recommend_dispatch → 建議到府檢測
  │  ├─ Python 安全網: 最多 3 輪追問，超過強制 recommend_dispatch
  │  └─ 每輪更新 ProblemCard (PDCA loop)
  │
  │  輸出: intents, category, symptoms
  │        + (技術查詢): failure_id, fm_hypotheses, verification_next_step
  │        + (跨輪次):   subtasks, current_step
  │
  │  對應診斷架構: Layer 1 (Symptom) → Layer 2 (Failure) → Layer 3 (FM)
  │  詳見 diagnostic-intelligence-architecture.md §4
  │
  ▼
[router] ─── 確定性派發 (零 LLM)
  │  intents → config lookup → next_agents
  │
  ▼ Send() fan-out
[agent subgraph] → [merge] → [post_process] → 回覆
  │
  │  技術類 agent 收到:             非技術類 agent 收到:
  │    symptoms +                    正常 user query
  │    fm_hypotheses +               (無額外診斷資訊)
  │    verification_next_step +
  │    CA (臨時對策，如有)
  │
  ▼ 完工回報後 (僅維修類)
[case_library] → 修正故障樹權重 (KA-3 → KA-1 閉環)
```

#### 與 Entropy (L8) 的協作

L8 entropy_check 監測兩種知識缺口：

```
缺口 1: SOP 未覆蓋
  偵測: "藍牙配對失敗" 近 7 天 transfer_rate = 45% (閾值 20%)
  原因: 現有 SOP 無 "bluetooth_pairing_failure" 流程
  → 觸發 sop_generator → 產出 SOP-APP-003 草稿
  → 人工審核後加入 knowledge/sop/ (JSON 檔案)

缺口 2: 故障樹未覆蓋的症狀組合
  偵測: "指紋+密碼同時失效" 無匹配故障樹，agent 回覆不一致
  原因: 新症狀組合，現有故障樹無此 pattern
  → 標記為待建故障樹，通知維修部提供因果分析
  → 老師傅補充根因假設 → 建立新故障樹文件
  → 加入 knowledge/fault_trees/ (JSON 檔案)

缺口 3: 故障樹權重偏差
  偵測: 案例庫回饋顯示 FT-HW-003 的 comm_board 預測 45%
        但實際根因 cable_loose 占比已達 50%
  → 觸發故障樹權重修正批次作業
  → 更新 FT-HW-003 的 hypotheses 機率
```

### 冷啟動策略：知識資產從零到自轉的路徑

上述設計假設故障樹已存在、案例庫有足夠樣本、SOP 已數位化。但 Day 1 現實是：

```
Day 1 真實狀態:
  故障樹    = 0 份 (老師傅經驗在腦中，未結構化)
  案例庫    = 0 筆 (V2.0 派工流程未上線，無完工回報機制)
  SOP      = 紙本/Word 檔 (未結構化，未轉為 JSON)
  症狀詞表  = 已建立 (symptoms.toml)，但未經實戰驗證
```

**如果跳過冷啟動直接開 Tier 2，故障樹搜不到東西，等於沒有。**

#### 三階段冷啟動路徑

```
Phase 0 — 收集期 (V1.0，系統上線)
  ┌──────────────────────────────────────────────────┐
  │  Tier 2 關閉。系統只跑 Tier 1 意圖分類。             │
  │                                                    │
  │  但 V1.0 已經在默默收集建構知識資產的原料：              │
  │                                                    │
  │  L7 Observability 收集:                             │
  │    · 每次對話的 symptoms (Tier 1 提取，即使不觸發 Tier 2)│
  │    · 哪些症狀組合頻繁共現                              │
  │    · 各 agent 的回覆結果和用戶滿意信號                   │
  │    · transfer_to_human 時的症狀上下文                  │
  │                                                    │
  │  L8 Entropy 監測:                                   │
  │    · 高頻 unknown 症狀 → 詞表補充候選                  │
  │    · 高轉人率的症狀組合 → 故障樹建立候選                 │
  │                                                    │
  │  人工客服記錄:                                       │
  │    · 轉人後，真人客服/技師的解決方案                     │
  │    · 這是最寶貴的原料 — 等同老師傅的診斷紀錄             │
  └──────────────────────────────────────────────────┘
        │ 累積 4-8 週數據後
        ▼
Phase 1 — 建構期 (V1.x → V2.0 過渡)
  ┌──────────────────────────────────────────────────┐
  │  專家 + 數據 → 建立初始知識資產                       │
  │                                                    │
  │  故障樹建立 (由維修專家主導):                          │
  │    1. 匯出 L7 數據: 高頻症狀組合 TOP 20                │
  │    2. 匯出轉人案例: 真人客服/技師怎麼處理的              │
  │    3. 維修專家審閱 → 為每個高頻組合建立故障樹            │
  │    4. 初始機率權重由專家經驗估算 (非案例庫統計)           │
  │    5. 加入 knowledge/fault_trees/ (JSON)           │
  │                                                    │
  │  SOP 數位化 (由營運團隊主導):                          │
  │    1. 收集現有紙本/Word SOP                           │
  │    2. 轉換為結構化 markdown 格式                      │
  │    3. 加入 knowledge/sop/ (JSON)                   │
  │                                                    │
  │  目標: 10-20 份故障樹 + 5-10 份 SOP 覆蓋 80% 場景     │
  └──────────────────────────────────────────────────┘
        │ V2.0 派工上線後
        ▼
Phase 2 — 自轉期 (V2.0+)
  ┌──────────────────────────────────────────────────┐
  │  Tier 2 開啟。知識資產開始自我進化。                    │
  │                                                    │
  │  案例庫啟動:                                        │
  │    完工回報 → case_library 持續累積                   │
  │    n > 50 筆/故障樹 → 統計權重取代專家估算              │
  │                                                    │
  │  故障樹自動修正:                                     │
  │    案例庫批次分析 → 權重偏差 > 10% → 自動更新          │
  │    新症狀組合 → L8 偵測 → 專家建立新故障樹             │
  │                                                    │
  │  飛輪: 用越多 → 案例越多 → 故障樹越準 → 診斷越好       │
  │        → 用戶更願意用 → 用越多 ...                    │
  └──────────────────────────────────────────────────┘
```

#### 各知識資產的成熟時間線


| 知識資產       | Phase 0 狀態          | Phase 1 來源          | Phase 2 進化機制 | 預計可用時間     |
| ---------- | ------------------- | ------------------- | ------------ | ---------- |
| **症狀詞表**   | 已建立 (symptoms.toml) | L8 unknown 頻率 → 補充  | 持續新增         | Day 1      |
| **SOP 流程** | 紙本/Word 存在          | 營運團隊數位化             | 業務調整時人工更新    | V2.0 上線前   |
| **故障樹**    | 不存在                 | 維修專家 + L7 數據 → 人工建立 | 案例庫統計修正權重    | V2.0 上線時   |
| **案例庫**    | 不存在                 | V2.0 完工回報累積         | 自動累積，無需人工    | V2.0 上線後持續 |


#### Phase 0 的關鍵：V1.0 要收集什麼給未來的專家用

V1.0 不開 Tier 2，但必須有意識地為 Phase 1 儲備原料：

```toml
# config.toml — V1.0 即啟用的收集機制
[harness.observability]
trace_enabled = true
# Phase 0 數據收集，供 Phase 1 故障樹建構使用
collect_symptom_pairs = true       # 記錄每次對話提取的 symptoms 組合
collect_transfer_context = true    # 記錄轉人時的完整症狀 + 對話摘要
collect_artifacts = true           # 保存對話紀錄 + 用戶上傳的照片/影片到 case_artifacts

[harness.observability.artifact_storage]
backend = "s3"                     # "s3" | "minio" | "local"
bucket  = "case-artifacts"
```

收集的數據結構 — 兩層：結構化摘要 + 原始素材引用。

> **Phase 0 存儲選擇**：symptom_log 和 case_artifacts 是 runtime 寫入資料（每次對話都產生），不適合用靜態 JSON 檔案。Phase 0 可用 JSONL 日誌檔（append-only），Phase 2 遷移至 PostgreSQL。下方以 SQL 表達 schema 定義，實際 Phase 0 實作為 JSONL。

```sql
-- 層 1: 結構化案件紀錄 (L7 自動寫入)
-- Phase 0: JSONL 檔案 (data/logs/symptom_log.jsonl)
-- Phase 2: PostgreSQL 表
CREATE TABLE symptom_log (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL,           -- 對話 session，串接完整對話紀錄
    timestamp       TIMESTAMPTZ NOT NULL,
    user_id         TEXT NOT NULL,
    symptoms        TEXT[] NOT NULL,          -- 標準 symptom_id
    device_model    TEXT,
    device_brand    TEXT,
    agent           TEXT NOT NULL,            -- 處理的 agent
    resolved        BOOLEAN NOT NULL,
    transferred     BOOLEAN NOT NULL,         -- 是否轉人
    transfer_reason TEXT,                     -- 轉人原因摘要
    problem_card_id TEXT                      -- 關聯的 ProblemCard (如有)
);

-- 層 2: 案件附件 (對話紀錄 + 多媒體素材)
CREATE TABLE case_artifacts (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES symptom_log(session_id),
    artifact_type   TEXT NOT NULL,            -- 'conversation' | 'photo' | 'video' | 'voice' | 'document'
    source          TEXT NOT NULL,            -- 'line_chat' | 'user_upload' | 'technician_upload' | 'agent_log'
    storage_url     TEXT NOT NULL,            -- S3/MinIO URL 或內部路徑
    description     TEXT,                     -- 素材摘要
    uploaded_at     TIMESTAMPTZ DEFAULT NOW()
);
-- 索引: 按 session_id 快速撈出某案件的所有附件
CREATE INDEX idx_artifacts_session ON case_artifacts(session_id);
```

```
案件完整視圖 (後台管理 UI 呈現):

┌─ 案件 #2026041002 ─────────────────────────────────────────────┐
│                                                                 │
│  症狀: [fingerprint_no_response, bluetooth_disconnected]        │
│  型號: dormakaba DP850     品牌: dormakaba                          │
│  Agent: hardware_tech    結果: 轉人                             │
│  轉人原因: AI 無法判定根因，用戶要求真人協助                       │
│                                                                 │
│  ┌─ 附件 ──────────────────────────────────────────────────┐   │
│  │                                                          │   │
│  │  [conversation] 完整 AI 對話紀錄                          │   │
│  │    → AI: "請問螢幕有亮嗎？"                               │   │
│  │    → 用戶: "螢幕正常，就是指紋和藍牙不行"                   │   │
│  │    → AI: "建議轉接專人為您進一步診斷..."                    │   │
│  │                                                          │   │
│  │  [conversation] 真人客服/技師對話紀錄                      │   │
│  │    → 技師: "這個通常是排線問題，你把後蓋打開..."              │   │
│  │    → 用戶: "打開了，排線看起來有點鬆"                       │   │
│  │    → 技師: "把排線重新壓緊試試"                            │   │
│  │    → 用戶: "好了！指紋和藍牙都恢復了"                       │   │
│  │                                                          │   │
│  │  [photo] 用戶上傳的門鎖照片 (2 張)                        │   │
│  │    → door_lock_front.jpg — 門鎖正面外觀                   │   │
│  │    → cable_loose.jpg — 排線鬆脫近照                       │   │
│  │                                                          │   │
│  │  [video] LINE 通話錄影片段 (技師遠端指導)                  │   │
│  │    → remote_diagnosis_001.mp4 — 技師指導拆後蓋             │   │
│  │                                                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─ 專家審查區 (Phase 1 後台 UI) ──────────────────────────┐   │
│  │                                                          │   │
│  │  根因判定: [cable_loose ▼]  (下拉選單，從 fault_trees 拉)  │   │
│  │  是否需要新故障樹: [○ 否  ● 是 → 建立 FT-HW-XXX]         │   │
│  │  是否需要新症狀標籤: [○ 否  ● 是 → 新增到 symptoms.toml]  │   │
│  │  備註: [排線扣老化，DP850 常見問題，建議加入故障樹______]    │   │
│  │                                                          │   │
│  │  [提交審查結果]                                           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

```
Phase 0 數據流:

LINE 對話 → agent 處理 → L7 寫入 symptom_log
                       → 對話紀錄存入 case_artifacts (type=conversation)
         → 用戶上傳照片/影片 → 存入 case_artifacts (type=photo/video)
         → 轉人後 → 真人對話紀錄存入 case_artifacts (type=conversation, source=technician)

Phase 1 專家審查:
  後台 UI 列出高頻症狀組合 TOP 20
  → 專家點進每個案件 → 看完整對話 + 照片 + 影片
  → 標註根因 → 建立/強化故障樹
  → 系統自動將審查結果寫入 fault_trees 表
```

4-8 週後匯出給維修專家的不是一張表，而是**帶完整原始素材的案件包**：

```
匯出: "fingerprint + bluetooth 共現 47 次，其中 32 次轉人"

專家看到的不只是統計數字，而是:
  → 47 個案件各自的完整對話紀錄
  → 用戶上傳的照片/影片 (如有)
  → 真人技師的診斷過程和解決方案
  → 每個案件的設備型號、症狀細節

這些就是專家建立故障樹的第一手證據。
```

#### 故障樹初始權重：專家估算 vs 數據統計

Phase 1 建立的故障樹，機率權重來自**專家經驗估算**，不是統計：

```markdown
# FT-HW-003 Phase 1 版本 (專家估算)

## hypotheses
| rank | root_cause         | probability | confidence_source       |
|------|--------------------|-------------|-------------------------|
| 1    | comm_board_failure | 40%         | 張師傅估算 (20年經驗)       |
| 2    | cable_loose        | 35%         | 張師傅估算                  |
| 3    | mainboard_power    | 20%         | 產品技術文件                 |
| 4    | other              | 5%          | 預留                       |

→ Phase 2 案例庫累積 n>50 後，統計權重自動取代專家估算
```

這些初始權重「不精確但有用」— 比沒有故障樹好 100 倍。

#### 冷啟動期的降級行為

```
V1.0 (Phase 0): Tier 2 運作但知識資產有限
  所有技術查詢仍進入診斷推理引擎
  有 JSON 故障樹匹配 → 帶假設 + 驗證鏈派給 agent
  無匹配故障樹 → LLM 基於 prompt 通用診斷邏輯追問 (graceful degradation)
  → L7 記錄每次診斷路徑，L8 監測高頻未匹配症狀組合

V2.0 早期 (Phase 1 → Phase 2 過渡): 故障樹覆蓋逐步擴大
  專家持續建立新的 JSON 故障樹 → Git commit → 系統載入
  案例庫開始累積 → Phase 2 觸發條件漸近
```

不需要等故障樹 100% 覆蓋才開診斷推理。有一棵就比沒有好，缺的部分 LLM 自動降級處理。

---

## 7. V1.0 即時優化清單 (P0/P1)

### P0: 直接影響用戶體驗


| 項目                       | 改動                                            | 效果        |
| ------------------------ | --------------------------------------------- | --------- |
| **debounce 降到 2-3s**     | config.toml `buffer_wait = 2.0`               | 回覆速度 -3s  |
| **pgvector score gate**  | pgvector_store.py 加 similarity threshold 0.85 | 過濾低品質結果   |
| **seed data 灌入**         | 確認 200+ 案例 + 手冊 PDF 已進 pgvector               | L1 命中率核心  |
| **agent prompt 加 L3 指令** | "查不到就承認不知道並轉接"                                | 避免 LLM 編造 |


### P1: 改善延遲


| 項目                       | 改動                                      | 效果         |
| ------------------------ | --------------------------------------- | ---------- |
| **update_profile async** | 不阻塞回覆，背景更新                              | 回覆速度 -1s   |
| **L7 @traced 啟用**        | 所有 node 加 decorator                     | 獲得量化數據     |
| **L8 async 背景**          | entropy_check 不在 request path           | 零延遲影響      |
| **fallback_tools**       | config.toml [[agents]] 加 fallback_tools | L2 cascade |


---

## 8. 架構 vs Claude Code / Codex 設計對比

### Claude Code 的 Agent Loop

```
while not done:
    think(context)     → 分析當前狀態
    select_tool()      → 選擇行動
    execute_tool()     → 執行並觀察結果
    evaluate()         → 結果好嗎？
    adjust()           → 不好就換策略
```

### 本系統的 Agent Loop

```
task_decompose (LLM 分類) → router (config 派發) → agent → tool → LLM → 回覆
```

關鍵差異：Claude Code 有 evaluate + adjust loop，本系統沒有。

### 為什麼不照搬 Claude Code 的 loop


|      | Claude Code        | 本系統                |
| ---- | ------------------ | ------------------ |
| 使用者  | 開發者 (高容錯)          | 消費者 (零容錯)          |
| 回合數  | 可以 loop 20+ 次      | 必須 1-2 次內回覆        |
| 等待容忍 | 分鐘級                | 秒級                 |
| 成本敏感 | 每 loop 一次 LLM call | 每次對話 2-4 LLM calls |


### 正確的借鑑

```
不需要 Claude Code 的「無限 loop 直到成功」。
需要的是「1 次嘗試 + 1 次 fallback + 1 次轉人」的三層保底。

Agent 內部:
  L1 (primary tool) → miss → L2 (fallback tools) → miss → L3 (transfer)

跨 Agent (V1.2+):
  L5 verify: 評分低 → retry 1 次 → 仍低 → 放行 (不無限 loop)
```

---

## 9. 數據驅動決策：L7 Observability 要量化什麼

啟用 L7 `@traced` 後，收集以下指標作為其他 harness 層啟用依據：

### 延遲指標


| 指標                   | 收集點            | 用途                        |
| -------------------- | -------------- | ------------------------- |
| `total_latency_ms`   | post_process   | 端到端延遲 baseline            |
| `task_decompose_ms`  | task_decompose | 分類 + SOP 檢索耗時 (唯一 LLM)    |
| `router_dispatch_ms` | router         | config lookup 耗時 (應 ~0ms) |
| `agent_latency_ms`   | agent subgraph | 單 agent 耗時                |
| `tool_latency_ms`    | execute_tools  | pgvector 查詢耗時             |


### 品質指標


| 指標                   | 收集點                      | 用途          |
| -------------------- | ------------------------ | ----------- |
| `l1_hit_rate`        | pgvector score ≥ 0.85 比例 | 知識庫品質       |
| `l2_fallback_rate`   | L1 miss → L2 觸發比例        | cascade 必要性 |
| `l3_transfer_rate`   | transfer_to_human 觸發比例   | 自助解決率       |
| `agent_distribution` | next_agents 統計           | 哪個 agent 最忙 |


### 啟用決策矩陣

```
IF l1_hit_rate < 60%:
    → 檢查 seed data 品質 (不是開 L2 context_assemble)

IF l3_transfer_rate > 30%:
    → 檢查 agent prompt + fallback_tools 設定 (不是開 L5 verify)

IF total_latency_ms > 8000:
    → 檢查哪個 node 最慢 (不是關功能)

IF accuracy < 80% (SOW 標準):
    → THEN 考慮啟用 L5 verify (有數據支撐)
```

---

## 10. 時程對齊


| 階段           | 期間     | 做什麼                                                  | Harness 狀態                                                      | 冷啟動 Phase                          |
| ------------ | ------ | ---------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------- |
| **V1.0 P0**  | 立即     | debounce 2s + score gate + seed data + async profile | L1 lite + router (config) + L3/L6 regex + L7 @traced + L8 async | Phase 0: L7 收集 symptoms 組合 + 轉人上下文 |
| **V1.0 UAT** | W13-15 | 50 題測試 + L7 數據收集                                     | 根據數據決定是否開更多層                                                    | Phase 0: 累積數據，識別高頻症狀組合             |
| **V1.1**     | W16+   | 若 L7 數據顯示品質不足 → 啟用 L2/L5                             | 數據驅動啟用                                                          | Phase 0→1: 匯出 L7 數據給維修專家           |
| **V1.x**     | W17+   | 維修專家建立 TOP 20 故障樹 + SOP 數位化                          | 故障樹/SOP 建為 JSON 檔案，Git 管理                                       | **Phase 1: 知識資產建構**                |
| **V2.0**     | W18+   | 派工流程上線 + 完工報告系統 + 案例庫 PostgreSQL                     | 診斷推理自然加深 (更多故障樹 + 案例統計)                                         | Phase 1→2: 知識閉環啟動                  |
| **V2.x**     | W22+   | 案例庫 n>50/故障樹 → 統計權重取代專家估算                            | 知識進化閉環啟動                                                        | **Phase 2: 自轉期**                   |


---

## 11. 文件索引


| 文件                                            | 內容                                | 關係            |
| --------------------------------------------- | --------------------------------- | ------------- |
| 本文件 (optimization-strategy.md)                | 什麼該開什麼不開 + 為什麼                    | 決策依據          |
| `**diagnostic-intelligence-architecture.md`** | **六層診斷架構 + 推理引擎 + 知識閉環**          | **§6 核心模組設計** |
| `harness-architecture.md`                     | 8 層理論框架                           | 理論基礎          |
| `gap-analysis.md`                             | 8 層 vs 現有成熟度                      | 現狀盤點          |
| `migration-roadmap.md`                        | H-Stage 0-6 路線圖                   | 實作時程          |
| `poc-spec.md`                                 | 電子鎖匠 POC 測試計畫                     | 驗證方法          |
| `graph-flow-redesign.md`                      | 新舊 graph flow 對照                  | 架構參考          |
| `problem-card-spec.md`                        | ProblemCard data model            | 資料模型          |
| `config-evolution.md`                         | config.toml 擴展規格                  | 設定參考          |
| **`wbs-harness-development.md`** | **WBS 工作分解 + 時程 + Critical Path** | **專案管理** |
| **`diagnostic-state-machine-spec.md`** | **狀態機規格：10 狀態 + 轉移規則 + PDCA 生命週期** | **狀態管理** |


