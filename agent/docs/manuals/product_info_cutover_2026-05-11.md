# Product Info Cutover Audit — 2026-05-11

**範圍**：把 dev agent 從 `skills/data/*/SKILL.md` 切到 `product_info/{Brand}/{Model}.md` mega-doc 的完整紀錄。
**分支**：`refactor/agent-port`
**參與 commits**：5 個（Stage 0 + A-1 + A-2 + A-3a + A-3b）
**對應 ADR**：[ADR-0008](../../../docs/1-decisions/ADR-0008-product-info-architecture-canonical.md)

---

## 1. 時間線

| Commit | 時間 | 階段 | 動作 |
| --- | --- | --- | --- |
| `6787843` | 2026-05-11 18:45 | Stage 0 | port agent_v2 product_info DB 基礎建設（startup cache + filter_loadable）|
| `d9edd3f` | 2026-05-11 19:xx | A-1 | 新增 `load_product_info` tool；**load_skill 並存**（agent 可選） |
| `5d46160` | 2026-05-11 20:xx | A-2 | system prompt catalog block 從 `[可用技能]` 切 `[可用產品資料]`；skills catalog 保留 fallback |
| `0eac531` | 2026-05-11 21:xx | A-3a | 退場 `load_skill` tool（從 `agent.py` tools list 拿掉）；`skills/data/` **保留**待確認 |
| `e6ed743` | 2026-05-11 22:xx | A-3b | 刪除 `agent/skills/data/` 全部 69 個 SKILL.md |

合計 5 個 commit，4 個多小時內收完整個切換。

---

## 2. 切換動機

### 2.1 上游決定

dev branch（agent-improvements / main）於 2026-05-09 早上由原作者寫 ADR-0008 宣告「`product_info/` 為唯一正典」。同日 14:42 經團隊重新協商，以 force-push 改回 skills/ 架構，並在 ADR-0008 加 SUPERSEDED 附註。

### 2.2 本 branch 重新走向 product_info

`refactor/agent-port` 分支自 5/9 後獨立演化，2026-05-11 因「新需求《AI客服 Harness 設計策略 Hypothesis-Driven 架構》」需要把 agent_v2 已驗證的 product_info 知識庫挪過來，又走回 product_info canonical 路線。

**但本 branch 的 ADR-0008 仍標 SUPERSEDED**（commit history 沒人改），text 與實際 code 狀態不一致。Code 比 ADR 真實。

> 註：上游 ADR-0008 SUPERSEDED 附註本身**只標 ADR 失效，未否定 product_info 路線本身的正確性**。本 branch 5/11 的 A-1~A-3b 是「沿用 ADR-0008 原始決議重新執行」，不是新走向。

---

## 3. 各階段細節

### 3.1 Stage 0 — `6787843`（基礎建設）

新增（port 自 agent_v2）：

- `agent/product_info/__init__.py` — `load_all_docs()` / `filter_loadable()` / `get_doc(name)` / `has_brand(brand)`
- `agent/product_info/{Brand}/*.md` mega-doc（共 45 份，業主驗證）
- `agent/product_info/_common/*.md`（4 份通用）
- DB 暫不引入（只 in-memory startup cache）

未動：
- `agent/skills/` 完整保留
- `agent/agent_tools/`（當時還沒拆出）
- system prompt prefix 仍是 `[可用技能]`

### 3.2 A-1 — `d9edd3f`（並存階段，新增 tool）

新增：
- `agent/agent_tools/load_product_info.py` — 業務邏輯（含 strict profile gate）
- `agent.py` tools list 加入 `load_product_info`

**並存策略**：
- `load_skill` 仍在 tools list（agent 還能用）
- 兩個 tool 同時對 LLM 可見，prompt 沒指引選哪個 → LLM 通常會優先用第一個（load_product_info）
- 風險：LLM 可能還是叫 `load_skill`，會 fallback 到舊 SKILL.md

### 3.3 A-2 — `5d46160`（catalog 切換）

改：
- `prompt_builder.py` 把 `[可用技能]` block 換成 `[可用產品資料]`
- skills catalog 改成 fallback：`if not product_info_catalog` 才用

**並存 fallback 策略**：
- 預期 product_info 永遠有東西（45 份 mega-doc 是穩定的）
- skills fallback 只是萬一 load_all_docs 失敗時兜底，實際不會觸發
- 沒走 hard switch 因為 A-3 還沒做，怕 LLM 看不到 skills 又看不到 product_info

### 3.4 A-3a — `0eac531`（退場 tool）

改：
- `agent.py` tools list 移除 `load_skill`
- `agent/agent_tools/__init__.py` 不再 export `load_skill`
- `skills/data/` 完整保留（防 rollback）

風險檢查：
- system prompt catalog 已切 product_info (A-2)
- LLM 看不到 load_skill 就不會嘗試呼叫
- skills/data/ 還在 → 萬一要 rollback 一行 import 就回來

### 3.5 A-3b — `e6ed743`（資料刪除）

刪：
- `agent/skills/data/` 全部 69 個 SKILL.md
- `agent/skills/data/_common/` 內所有檔
- `agent/skills/data/{Brand}/` 整個目錄

保留：
- `agent/skills/__init__.py`、`agent/skills/tools.py`（被其他 import chain 引用，刪掉會炸）
- 但 `tools.py` 不再被 `agent.py` 載入

刪除後資料夾狀態：
```
agent/skills/
├── __init__.py    （still here, but skills/data/ is empty）
├── tools.py       （still here, dead code）
└── data/           （現在是空目錄）
```

---

## 4. 與 dev branch（agent-improvements）的關係

| 分支 | skills/data | product_info | load_skill tool | load_product_info tool |
| --- | --- | --- | --- | --- |
| `main` | ✅ 有檔 | ❌ 無 | ✅ 用 | ❌ |
| `refactor/agent-improvements` | ✅ 有檔 | ✅ 有檔（業主驗證 45 份）| ✅ 用 | ❌ 未接 |
| `refactor/agent-port`（本 branch） | ❌ 已刪 | ✅ 有檔（從 agent_v2 port） | ❌ 已退場 | ✅ 用 |
| `feat/hermes-customer-service` | n/a | ✅ 用 PG 表（不存地端 .md） | n/a | ✅ 用 |

本 branch 對 dev 是「**領先 cutover 一步**」狀態。dev 仍跑 skills/，本 branch 已切完 product_info。

---

## 5. 切換後的 LLM 行為差異

### 5.1 catalog 顯示

**之前**：

```
[可用技能]
- _common.troubleshoot — 通用症狀分流
- Dormakaba._all-models.app-guide — Dormakaba App 操作
- Dormakaba.AS850.ts-door-stuck — AS850 鎖體卡住
...
（每個品牌可能 5-10 個 skill）
```

**之後**：

```
[可用產品資料]
- _common/troubleshoot
- _common/dispatch
- Dormakaba/AS850
- Dormakaba/AS901
- ...
（一個型號一個 mega-doc）
```

平均 LLM 看到的 catalog 行數從 ~70 行降到 ~25 行（**省 token + 簡化選擇**）。

### 5.2 tool call 行為

**之前**（skills）：
- LLM 可能連續叫 `load_skill("ts-door-stuck")` + `load_skill("app-guide")`
- 每個 SKILL.md 只 100-300 行，要組合多份才有完整答案

**之後**（mega-doc）：
- LLM 一次叫 `load_product_info("Dormakaba/AS850")` 拿到 800-1500 行
- mega-doc 內部已含 troubleshoot / spec / app / dispatch 全段
- iters 從 2-3 降到 1-2，省一個 ReAct loop

### 5.3 quality_check 影響

| 67 共同題 | skills (dev baseline) | product_info (本 branch) |
| --- | --- | --- |
| LLM-judge strict pass | 56/67 (83.6%) | 60/67 (89.6%) |
| pass + partial | 66/67 (98.5%) | 67/67 (100.0%) |
| fail | 1 | 0 |

**89.6% 中含 Belief-Augmented ReAct 加成**。純 product_info 切換的貢獻不能單獨剝離（沒跑 turn_cycle=off 的 product_info-only 對打），但 catalog 簡化的效益肯定 ≥ 0。

---

## 6. Rollback 程序（萬一）

若需 rollback 到 skills：

```bash
# 1. 還原 SKILL.md 檔案
git checkout 0eac531^ -- agent/skills/data/

# 2. 還原 load_skill tool 註冊
git checkout 0eac531^ -- agent/agent_tools/__init__.py agent.py

# 3. 還原 catalog block
git checkout 5d46160^ -- agent/prompts/system.md agent/harness/skills_prefix.py

# 4. （可選）反轉 product_info — 不建議，留著當 fallback
```

但實際不需 rollback：
- 67 共同題 0 fail
- catalog 行數降低（觀察體驗顯著）
- mega-doc 由業主自己審稿，更新流程比 skills 簡單

---

## 7. 後續

- [ ] 把 `agent/skills/__init__.py` + `agent/skills/tools.py` 內 dead code 標 deprecated（或乾脆刪，看 import chain 是否真不會炸）
- [ ] dev branch 是否跟進 cutover：待後續路線決議（目前 roadmap 走向為 hermes-cs，dev 可能直接砍 agent/）
- [ ] mega-doc 撰寫指南 (`product_info_authoring_guide.md`) 在 dev branch 是 active 的，本 branch 在 cutover 過程中曾被刪除，未來若要保留本 branch 為 archive 候選需 restore 該檔

---

## 8. 相關文件

- [ADR-0008 — Product Info Architecture Canonical](../../../docs/1-decisions/ADR-0008-product-info-architecture-canonical.md) — 原始決議（本 branch 上仍標 SUPERSEDED，但 code 已重新對齊原始決議方向）
- [Turn Cycle / Belief-Augmented ReAct](turn_cycle_belief_augmented_react.md) — 同日 Stage B 的另一條改造線
- `agent/quality/reports/quality_report_2026-05-11_2*.md` — 對打報告
