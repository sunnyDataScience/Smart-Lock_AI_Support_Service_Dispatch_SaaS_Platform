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

### 優化後

```
debounce wait          2.0s   ← 降到 2 秒 (省 3s)
pre_process            0.1s
manage_memory          0.1s
router                 1.5s
agent (tool + LLM)     3.0s
merge_answers          0.1s
update_profile         ---    ← 改 async 背景 (省 1s)
post_process           0.1s
───────────────────────────────
優化後:                2.0 + 4.9 = ~7s
```

**從 11-20s 降到 ~7s**。差距來自：砍 debounce 3s + async profile 1s + 不開 harness nodes。

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

| 機制 | 解決什麼問題 | 延遲成本 | V1.0 啟用？ |
|---|---|---|---|
| **Multi-Agent Fan-out** | 問誰 (意圖→知識庫) | 0s (平行) | **Yes** |
| **Three-Layer Cascade** | 答不出來怎麼辦 (L1→L2→L3) | +1-3s (worst case) | **Yes (agent 內部)** |
| **Harness L5 Verify** | 答得好不好 (品質閘門) | +1.5-5s | **No (V1.2)** |

### 資訊流

```
User Message
  │
  ▼
[debounce 2s] → [pre_process] → [manage_memory] → [router: LLM 意圖分類]
  │
  ▼ Send() fan-out
┌─────────────── Agent Subgraph (each) ───────────────┐
│                                                      │
│  agent_llm → tool call:                              │
│    L1: pgvector search (similarity ≥ 0.85)           │
│      ├─ HIT → 用 context 生成回覆                     │
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

| Layer | 元件 | 啟用？ | 理由 |
|---|---|---|---|
| L1 Task | task_decompose | **No** | Router 已處理多意圖；+1.5s 延遲無感知改善 |
| L2 Context | context_assemble | **No** | 理論改善未驗證；manage_memory 已夠用 |
| L3 Governance | ToolRegistry risk levels | **Yes (輕量)** | 不用 LLM，regex + config 判斷，成本 ~0 |
| L4 State | memory + profiles | **Already on** | 核心功能 |
| L5 Feedback | verify_answer | **No** | +1.5-5s 延遲，品質提升 vs 速度損失不划算 |
| L6 Safety | safety_gate | **Yes (regex)** | regex 攔截危險指令，不用 LLM，成本 ~0 |
| L7 Observability | @traced | **Yes** | decorator 不影響延遲，提供量化數據 |
| L8 Entropy | entropy_check | **Yes (async)** | 不在 request path，背景執行零延遲影響 |

### V1.1 (Harness H-Stage 1-3)：有 data 證明再開

| Layer | 啟用條件 | 量化依據 |
|---|---|---|
| L1 Task | V2.0 派工上線時 (跨輪次工單追蹤) | 工單流程需要進度追蹤 |
| L2 Context | L7 數據顯示 context 品質是瓶頸 | L1 命中率 < 60% 且非 seed data 問題 |
| L5 Feedback | L7 數據顯示回覆品質低於 SOW 標準 | 準確率 < 80% 且非知識庫覆蓋問題 |

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

## 6. task_decompose 的正確使用時機

### V1.0 客服場景：不需要

| 場景 | Router 夠嗎 | task_decompose 有用嗎 |
|---|---|---|
| 一句多意圖 ("鎖壞了+APP連不上+營業時間") | **夠** (多 intent fan-out) | 多此一舉 |
| 單意圖單步驟 ("怎麼換電池") | **夠** (1 agent 直接答) | 多此一舉 |
| 單意圖多步驟 ("幫我診斷然後預約維修") | **夠** (agent LLM 一次回覆多步驟) | 多此一舉 |

Router 已經處理多意圖 → 多 agent fan-out → merge。task_decompose 和 router 對客服場景做的是同一件事，多花 1.5 秒。

### V2.0 派工場景：需要

```
第 1 輪: "我的鎖壞了" → AI 診斷 → ProblemCard
第 2 輪: "幫我叫師傅" → 建立 WorkOrder → 報價
第 3 輪: "好，我確認" → 派工 → 技師匹配
第 4 輪: "師傅什麼時候到？" → 查 WorkOrder 狀態
```

跨輪次工單追蹤需要 task_decompose 記錄「做到哪了、下一步是什麼」。這是 V2.0 的問題。

### 決策

```
task_decompose 不是用來拆「一句話裡的多個問題」的。
它是用來追蹤「跨多輪對話的複雜任務進度」的。
V1.0 沒有這種任務。V2.0 才有。
```

---

## 7. V1.0 即時優化清單 (P0/P1)

### P0: 直接影響用戶體驗

| 項目 | 改動 | 效果 |
|---|---|---|
| **debounce 降到 2-3s** | config.toml `buffer_wait = 2.0` | 回覆速度 -3s |
| **pgvector score gate** | pgvector_store.py 加 similarity threshold 0.85 | 過濾低品質結果 |
| **seed data 灌入** | 確認 200+ 案例 + 手冊 PDF 已進 pgvector | L1 命中率核心 |
| **agent prompt 加 L3 指令** | "查不到就承認不知道並轉接" | 避免 LLM 編造 |

### P1: 改善延遲

| 項目 | 改動 | 效果 |
|---|---|---|
| **update_profile async** | 不阻塞回覆，背景更新 | 回覆速度 -1s |
| **L7 @traced 啟用** | 所有 node 加 decorator | 獲得量化數據 |
| **L8 async 背景** | entropy_check 不在 request path | 零延遲影響 |
| **fallback_tools** | config.toml [[agents]] 加 fallback_tools | L2 cascade |

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
router → agent → tool → LLM → 回覆
```

關鍵差異：Claude Code 有 evaluate + adjust loop，本系統沒有。

### 為什麼不照搬 Claude Code 的 loop

| | Claude Code | 本系統 |
|---|---|---|
| 使用者 | 開發者 (高容錯) | 消費者 (零容錯) |
| 回合數 | 可以 loop 20+ 次 | 必須 1-2 次內回覆 |
| 等待容忍 | 分鐘級 | 秒級 |
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

| 指標 | 收集點 | 用途 |
|---|---|---|
| `total_latency_ms` | post_process | 端到端延遲 baseline |
| `router_latency_ms` | router | 意圖分類耗時 |
| `agent_latency_ms` | agent subgraph | 單 agent 耗時 |
| `tool_latency_ms` | execute_tools | pgvector 查詢耗時 |

### 品質指標

| 指標 | 收集點 | 用途 |
|---|---|---|
| `l1_hit_rate` | pgvector score ≥ 0.85 比例 | 知識庫品質 |
| `l2_fallback_rate` | L1 miss → L2 觸發比例 | cascade 必要性 |
| `l3_transfer_rate` | transfer_to_human 觸發比例 | 自助解決率 |
| `agent_distribution` | next_agents 統計 | 哪個 agent 最忙 |

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

| 階段 | 期間 | 做什麼 | Harness 狀態 |
|---|---|---|---|
| **V1.0 P0** | 立即 | debounce 2s + score gate + seed data + async profile | L3/L6 regex + L7 @traced + L8 async |
| **V1.0 UAT** | W13-15 | 50 題測試 + L7 數據收集 | 根據數據決定是否開更多層 |
| **V1.1** | W16+ | 若 L7 數據顯示品質不足 → 啟用 L2/L5 | 數據驅動啟用 |
| **V2.0** | W18+ | 派工流程上線 → 啟用 L1 task_decompose | 跨輪次任務追蹤 |

---

## 11. 文件索引

| 文件 | 內容 | 關係 |
|---|---|---|
| 本文件 (optimization-strategy.md) | 什麼該開什麼不開 + 為什麼 | 決策依據 |
| `harness-architecture.md` | 8 層理論框架 | 理論基礎 |
| `gap-analysis.md` | 8 層 vs 現有成熟度 | 現狀盤點 |
| `migration-roadmap.md` | H-Stage 0-6 路線圖 | 實作時程 |
| `poc-spec.md` | 電子鎖匠 POC 測試計畫 | 驗證方法 |
| `graph-flow-redesign.md` | 新舊 graph flow 對照 | 架構參考 |
| `problem-card-spec.md` | ProblemCard data model | 資料模型 |
| `config-evolution.md` | config.toml 擴展規格 | 設定參考 |
