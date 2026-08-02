---
id: CR-0200
title: agent workspace 全域 history.jsonl 會把 A 客人的對話注入 B 客人的 system prompt
status: awaiting-decision
created: 2026-08-02
author: Claude（web/agent/SQL 全維度掃描）
triggers: [Architecture boundary, Domain model]
related: [CR-0167, ADR-032, ADR-0107]
---

# CR-0200 — workspace 全域 history 造成跨使用者對話洩漏

## 1. 一句話

`line_gateway.py` 為**整個 process** 建立一個 workspace，而
`ContextBuilder.build_system_prompt` 會把該 workspace 的 `memory/history.jsonl`
無條件注入成「# Recent History」——**所有 LINE 使用者共用同一份**，
A 客人被歸檔的對話會出現在 B 客人的 system prompt 裡。

---

## 2. 事實（皆已讀 code 確認）

| 事實 | 位置 |
|---|---|
| 整個 process 只建一個 workspace | `scripts/line_gateway.py`：`workspace = Path(tempfile.mkdtemp(...))` |
| history 檔綁 workspace，非綁使用者 | `lockcore/agent/memory.py:56`：`self.history_file = self.memory_dir / "history.jsonl"` |
| 讀取時**只用 cursor 過濾，無使用者過濾** | `memory.py:318-320`：`read_unprocessed_history(since_cursor)` |
| 無條件注入 system prompt | `lockcore/agent/context.py:115-122` |
| 寫入來源 | `memory.py:663`（consolidation 摘要）、`memory.py:421`（append_history） |

## 3. 觸發門檻（這是嚴重度的關鍵）

寫入 history 需要先觸發 consolidation，門檻是
`context_window_tokens`（`lockcore/config/schema.py:99`，**預設 65_536**）。

也就是**單一客人的對話累積超過約 6.5 萬 tokens** 才會歸檔一次。
一般客服對話難以達到，但：

- 長期未清理的 session 會累積
- `Session.enforce_file_cap(on_archive=...)` 是另一條寫入路徑
- 一旦寫入，`dream cursor` 在 gateway 從不前進（`/dream` 指令未被排程），
  所以那筆內容會**永久**留在注入範圍內（上限最近 50 筆 / 32k 字元）

**所以：機率低，但一旦發生就是持續性的跨客人 PII 洩漏，且不會自己好。**

## 4. 為什麼不直接修

三條路都動到架構，不適合在缺陷修復裡順手做：

### 方案 A：per-user workspace

最符合直覺，但 `SkillSync`（CR-0167）綁定單一 workspace 做 skill 物化
（`workspace/skills/` overlay）。改成 per-user 就變成每個使用者一份 skill 複本，
記憶體與磁碟成本、以及 60s 輪詢的物化目標都要重新設計。

### 方案 B：關閉 workspace-global history 注入

本專案的 per-user 記憶**已經**走 `lockcore/agent/user_memory/`（memory_manager +
`memory_tenant`），workspace-global history 是 nanobot 單機私人助理的設計殘留，
對客服情境沒有用途。

但 `ContextBuilder.__init__` 沒有對應開關（簽名只有 workspace / timezone /
disabled_skills / memory_manager / tenant / skills_dir），要關掉得改 vendor code——
牴觸 CLAUDE.md 的 Architecture Lock 第 1 條。

### 方案 C：讓 dream cursor 永遠等於最新

副作用最小，但那是利用 cursor 語意做 workaround，
下一個讀 code 的人會看不懂為什麼要這樣。

## 5. 🛑 Human Decisions Required

- **D1**：走哪個方案？（A per-user workspace／B 加開關關閉注入／C cursor workaround）
- **D2**：B 需要改 vendor code（`lockcore/agent/context.py` 加一個
  `inject_workspace_history: bool = True` 參數）。這算不算違反 Architecture Lock
  第 1 條？我的判讀是「加參數不等於另寫核心」，但這需要業主確認邊界。
- **D3**：要不要先做一個**低成本的觀測**（在注入處記 log），確認 prod 到底有沒有
  真的發生過，再決定投入多少？

## 6. 暫時緩解（若決策需要時間）

`MemoryStore` 的 `max_history_entries` 可設 0——但要先確認 0 的語意是
「不保留」而非「不限制」（`memory.py:324` 是 `if self.max_history_entries <= 0: return`，
看起來 0 是「不 compact」而非「不保留」，所以**這條路不通**，需另尋）。

---

## 附錄：發現方式

2026-08-02 用 `defect-patterns.md` 對 `agent/` 做租戶隔離維度掃描時發現，
經對抗驗證確認 code 事實無誤。本 CR 只記錄，未動 code。
