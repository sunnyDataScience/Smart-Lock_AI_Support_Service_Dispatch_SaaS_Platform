# Knowledge Base & Tools（細節）

> 主檔 `CLAUDE.md` 已鎖死「正典是 `product_info/` mega-doc、bronze-only」兩條硬約束。
> 這份補載入機制、目錄結構、tools 行為、Turn Cycle module 清單。以 code 為準，本檔作地圖。

## Product Info Knowledge Base (`agent/product_info/`)

**兩階段載入：**
1. **Startup**：`load_all_docs()` 掃 `product_info/` 的 `.md`，解析 YAML frontmatter（`brand`, `model`, `description`），建記憶體索引
2. **Per-request**：`filter_loadable(brand, model)` 決定可載入哪些 → catalog 以 `[可用產品資料]` 前綴注入 user message

**目錄結構（每 brand+model 一份 mega-doc，外加 `_common/*`）：**

```
agent/product_info/
├── _common/                # brand=_common, model=None
│   ├── troubleshoot.md
│   ├── dispatch.md
│   ├── general-knowledge.md
│   └── store-info.md
├── Chatlock/{A90,AI-88,AI-99}.md
├── Dormakaba/              # 16 mega-docs：AS701/AS850/AS901/DP850/...
└── {Philips,Kaadas,Milre,AiLock,3E}/
```

**Strict profile gating**（`product_info/__init__.py:filter_loadable`）：brand+model 齊備 → 可載 `{Brand}/{Model}` + 全部 `_common/*`；否則只能載 `_common/*`。

完整切換紀錄見 [Product Info Cutover Audit 2026-05-11](../../agent/docs/manuals/product_info_cutover_2026-05-11.md)（A-1～A-3b 階段）。

## Tools (`agent/agent_tools/tools.py`)

3 個 agent tool，全用 `ContextVar` 做 async per-request 隔離：

| Tool | 用途 | 關鍵行為 |
|------|------|---------|
| `load_product_info` | 載入 mega-doc | Strict profile gate — 拒絕 `{brand}/{model} + _common/*` 以外的載入 |
| `update_user_info` | 設定 brand/model | 經 `match_brand()`/`match_model()` 驗證、正規化大小寫、寫 DB（SCD Type 2）、更新 ContextVar、回傳刷新後的 product info catalog |
| `transfer_to_human` | 轉真人 | 自動填入已知 facts（phone, address, device）到表單模板；受 `_doc_loaded_this_run` gate 防過早 escalate |

## Belief-Augmented ReAct (Turn Cycle, optional)

本 branch 新增實驗模組。**預設關閉**（`[turn_cycle].enabled=false`）。

- `agent/belief.py` — `BeliefState` v2 schema：`primary_intent` / `hypotheses[]`（含 `likely_misframe`）/ `confidence` / `ownership_status` / `next_action` 等
- `agent/belief_store.py` — PostgreSQL 持久化（`belief_states` 表，每 session 一筆，按 turn append）
- `agent/hypothesize.py` — Hypothesize meta-skill：渲染對話歷史 + facts → 呼 LLM → JSON parse → 回 `Hypothesis[]`
- `agent/policy.py` — Action Decision Policy（`decide()`）：BeliefState + threshold（HIGH=0.55 / GAP=0.15）→ COMMIT / PROBE / EXPLORE / ESCALATE
- `agent/calibrate.py` — Calibrate signal classifier：客戶下輪回應分類為 DENY / CONFIRM / ADD / SHIFT / IMPATIENT / NEUTRAL，回灌 Hypothesize
- `agent/harness/turn_cycle.py` / `turn_cycle_runner.py` — orchestrator + LLM caller wrapper
- `agent/harness/belief_hint.py` — render `(BeliefState, ActionDecision)` 為 `[Belief Hint]` 注入 prompt prefix

手冊：[Turn Cycle manual](../../agent/docs/manuals/turn_cycle_belief_augmented_react.md)。決議：[ADR-0010](../../docs/1-decisions/ADR-0010-belief-augmented-react.md)。閾值理由：[Action Policy Thresholds](../../agent/docs/manuals/action_policy_thresholds.md)。
