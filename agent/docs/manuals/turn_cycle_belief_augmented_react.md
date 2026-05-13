# Turn Cycle / Belief-Augmented ReAct 手冊

**版本**: v1（對應 2026-05-11 Stage B 系列 commits：6f7f722 ~ 10c1f7d）
**狀態**: 實驗（`[turn_cycle].enabled=false` 預設）
**對應 ADR**: [ADR-0010](../../../docs/1-decisions/ADR-0010-belief-augmented-react.md)
**對應分支**: `refactor/agent-port`（其他 branch 無此模組）

---

## 1. 概念

把 LLM 的「ReAct」（Reason → Act）外面再包一層**對客戶情境的明確 belief**：

```
[原 ReAct]                       [Belief-Augmented ReAct，本 branch]

  user input                       user input
       ↓                                ↓
   LLM 自由 reason                 ┌─ Hypothesize (LLM) ──→ BeliefState
   LLM 選 tool 用                 │       ↓
   LLM 回答                       ├─ Decide (rule) ──→ ActionDecision
                                  │       ↓
                                  ├─ render [Belief Hint] prefix
                                  │       ↓
                                  │  原 ReAct（LLM 看到 hint 再 reason）
                                  │       ↓
                                  └─ Calibrate (LLM, post-reply) ──→
                                     CalibrationSignal → 下輪 Hypothesize 修正
```

**核心思想**：LLM 隱性決策（「金錢字眼一律轉真人」之類）在邊界判斷不穩定 — 文不對題、追問沒給答案、過早派工等情況都出現過。改用「LLM 提議 + 規則層 sanity check」混合策略，把「決定下一步動作」這件事從 LLM 自由發揮拉回受控的 four-action policy。

---

## 2. 為什麼是「實驗」

詳見 [ADR-0010 §3](../../../docs/1-decisions/ADR-0010-belief-augmented-react.md)。三個原因：

1. **預設關**：`config.toml [turn_cycle].enabled=false` 是 hard default。歷史上有過「打開 feature flag 直接上 production」導致需要回退的事件，這次設計上維持保守。
2. **未對 production**：本 branch 跑出 67-case strict 89.6% / 100% pass+partial / 0 fails，但目前 roadmap 走向為 `hermes-cs` 路線（見 `docs/_audit/runtime-architecture-comparison-2026-05-13-0125.md`），本 branch 暫為 archive 候選。
3. **fail_open 兜底**：Hypothesize 失敗 → 走原 ReAct 不影響使用者。

---

## 3. 七檔結構

| 檔 | 角色 |
| --- | --- |
| `agent/belief.py` | `Hypothesis` + `BeliefState` 純資料 dataclass（schema v2 含 `likely_misframe`） |
| `agent/belief_store.py` | PostgreSQL 持久化（`belief_states` 表），按 session × turn 累積 |
| `agent/hypothesize.py` | Hypothesize meta-skill：render → call LLM → parse JSON → `BeliefState` |
| `agent/policy.py` | `decide(belief) → ActionDecision` 規則層；HIGH=0.55 / GAP=0.15 |
| `agent/calibrate.py` | Calibrate signal classifier；輸入「prior belief + 客戶下一輪文字」，輸出 6 種 signal |
| `agent/harness/turn_cycle.py` | orchestrator：`run_pre_execute()` 拿 hint string；`TurnCycleContext` 跨步骤狀態 |
| `agent/harness/turn_cycle_runner.py` | LiteLLM/LangChain 包裝；`wrap_langchain_llm()` / `run_belief_cycle()` |
| `agent/harness/belief_hint.py` | render `(BeliefState, ActionDecision)` 成可讀字串注入 prompt |

---

## 4. Schema

### 4.1 `Hypothesis`

```python
@dataclass
class Hypothesis:
    description: str            # 自然語言，例：「客戶 AS850 鎖體卡住無法上下鎖」
    primary_intent: PrimaryIntent  # 7 個 Literal：troubleshoot / spec_question / ...
    confidence: float           # 0.0 ~ 1.0
    needs_probe: str | None     # 若 confidence 不夠，建議的追問題
    likely_misframe: str | None # v2 新增：LLM 認為這個 hypothesis 最可能誤解客戶哪件事
```

### 4.2 `BeliefState`

```python
@dataclass
class BeliefState:
    hypotheses: list[Hypothesis]  # 1-3 個 ranked by confidence
    turn_id: int                  # session 內 0-indexed
    belief_id: str                # 跨輪追溯 UUID
    primary_intent: PrimaryIntent # = hypotheses[0].primary_intent
    ownership_status: str         # AI_OWN / HUMAN_OWN / DISPATCH_OWN
    notes: str                    # LLM 自由 note
```

### 4.3 `ActionDecision`

```python
@dataclass
class ActionDecision:
    action: Literal["COMMIT", "PROBE", "EXPLORE", "ESCALATE"]
    probe_dimension: str | None   # PROBE 才有
    reason: str                   # 給人看的決策理由
```

### 4.4 `CalibrationSignal`

```python
CalibrationSignalType = Literal[
    "DENY",       # 否定上輪 top → 排除同方向 hypothesis
    "CONFIRM",    # 確認上輪方向 → 深化細節
    "ADD",        # 同主題擴充
    "SHIFT",      # 完全換方向 → reset hypothesis
    "IMPATIENT",  # 客戶不耐煩 → 規則層強制 ESCALATE
    "NEUTRAL",    # 沒明確信號 → 照常 Hypothesize
]
```

---

## 5. Action Decision Policy（規則層）

`agent/policy.py:decide()` 是純規則，無 LLM 介入。決策樹：

```
┌─── intent ∈ {quote_request, dispatch_request} → ESCALATE
│
├─── top.confidence ≥ 0.55 AND (top - runner_up) ≥ 0.15 → COMMIT
│
├─── top.confidence ≥ 0.4 → PROBE（拿 needs_probe 或自選 dimension）
│
└─── 其他 → EXPLORE（開放式追問）
```

**閾值由來**：B-fix-v2 commit `10c1f7d` 把 HIGH 從 0.7 降到 0.55、GAP 從 0.3 降到 0.15。詳見 [Action Policy Thresholds 手冊](action_policy_thresholds.md)。

**ownership_status 影響**：若 hypothesis 標 `HUMAN_OWN` 或 `DISPATCH_OWN`，規則層 override 成 ESCALATE，不用看 confidence。

---

## 6. Belief Hint Prefix 注入

`harness/belief_hint.py:render(belief, decision)` 產出類似：

```
[Belief Hint]
本輪假設：客戶詢問 AS850 加指紋步驟 (conf=0.78)
追問題（若需要）：要先確認管理員密碼是否設好
動作建議：COMMIT — 直接給 SOP
```

這段被 `harness/turn_cycle.py:_format_user_facts_block()` 一起組進 system prompt prefix 區，讓 LLM 在原 ReAct 中能參考但不強制照辦（fail-soft）。

---

## 7. 持久化

`belief_store.save_belief(session_id, belief)` 在每輪 Hypothesize 完成後寫入：

```sql
CREATE TABLE belief_states (
  belief_id UUID PRIMARY KEY,
  session_id UUID,
  turn_id INT,
  hypotheses JSONB,   -- list[Hypothesis] serialized
  primary_intent TEXT,
  ownership_status TEXT,
  created_at TIMESTAMPTZ
);
```

Calibrate 階段讀 prior belief 用 `belief_store.load_prior_belief(session_id)` 取最後一筆。

---

## 8. Config

```toml
[turn_cycle]
enabled       = false   # 預設關
fail_open     = true    # Hypothesize 失敗時走原 ReAct（production 永遠 true）
```

啟用方式：

```bash
# 本機切換（不上 production）
TURN_CYCLE_ENABLED=true cd agent && uv run python main.py
# 或改 config.toml 後重啟
```

---

## 9. quality_check A/B

```bash
# Baseline (turn_cycle off)
cd agent && uv run python -m quality.quality_check

# Belief-Augmented (turn_cycle on)
cd agent && uv run python -m quality.quality_check --turn-cycle
```

`--turn-cycle` flag 由 commit `04aa0b9` 加入，在跑前 monkey-patch `[turn_cycle].enabled=true`。

2026-05-11 對打結果（67 共同題）：

| 指標 | Baseline | --turn-cycle |
| --- | --- | --- |
| LLM-judge strict pass | 83.6% | **89.6%** |
| pass + partial | 98.5% | **100.0%** |
| fail | 1 | **0** |

詳細 raw JSON：`agent/quality/quality_report.baseline.json` 與 `quality_report.turncycle_v2.json`（未提交，本機）。

---

## 10. 已知限制 / 未做

- **belief_store 沒做 retention**：production 跑久了 `belief_states` 會無限長。需加 30-day TTL 或 archive 機制。
- **Hypothesize 沒做 streaming**：每輪會等 LLM 整個跑完才開始 ReAct，多一輪 latency（觀測約 +0.8s）。
- **Calibrate 在 post-reply 跑**：如果客戶連續發兩則訊息，第二則的 BeliefState 不會反映第一則的 Calibration（因為 Calibrate 還沒跑完）。production 化前需重新思考時序。
- **沒做 belief 視覺化工具**：debug 時要直接 SELECT belief_states 表。

---

## 11. 相關文件

- [ADR-0010 — Belief-Augmented ReAct](../../../docs/1-decisions/ADR-0010-belief-augmented-react.md) — 正式決議
- [Action Policy Thresholds](action_policy_thresholds.md) — B-fix-v2 閾值調整理由
- [Product Info Cutover Audit 2026-05-11](product_info_cutover_2026-05-11.md) — Stage A 變更
- `agent/quality/reports/quality_report_2026-05-11_2*.md` — 對打 raw report
