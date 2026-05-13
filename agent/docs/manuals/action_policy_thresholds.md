# Action Decision Policy Thresholds

**檔案位置**：`agent/policy.py`
**當前值**：`HIGH_CONFIDENCE = 0.55` / `GAP_TO_COMMIT = 0.15`
**最後調整**：commit `10c1f7d` (B-fix-v2, 2026-05-11 23:28)

---

## 1. 閾值用途

`policy.decide(belief)` 規則樹：

```
if intent ∈ {quote_request, dispatch_request}:
    → ESCALATE
elif top.confidence >= HIGH_CONFIDENCE AND (top.conf - runner_up.conf) >= GAP_TO_COMMIT:
    → COMMIT     # 高信心 + 與第二名差距大 → 直接答
elif top.confidence >= 0.4:
    → PROBE      # 中信心 → 拿 needs_probe 追問
else:
    → EXPLORE    # 低信心 → 開放式追問
```

**HIGH_CONFIDENCE**：判 COMMIT 的最低 top confidence
**GAP_TO_COMMIT**：top 與 runner-up 至少要差這麼多

---

## 2. 調整歷程

| 階段 | HIGH | GAP | 由來 |
| --- | --- | --- | --- |
| Initial (`6f7f722`) | 0.70 | 0.30 | 第一版直覺值，仿其他 belief 系統典型保守設定 |
| B-fix-v2 (`10c1f7d`) | **0.55** | **0.15** | 對打發現太緊 — 該答的還在反問 |

---

## 3. B-fix-v2 為何放寬

### 3.1 觀察

B-fix-v1（commit `4f251e2`）修了三個 prod-blocking 問題後，`quality_check --turn-cycle` 從 76% 回到 82%，但仍落後 baseline 85% **3pp**。

挖剩餘 6 筆 regression 全是「該答的還在反問」：

- Y-9「為什麼 X」→ 反問「想了解為什麼還是怎麼操作」
- M-4「FA9000 說明書 + 手機開門？」→ 反問「您遇到什麼狀況」
- B-5「鎖嗶嗶叫」→ 反問細節

### 3.2 推測根因

quality_check synthetic 模式不存 belief 到 DB，無法直接看 confidence 值。從 baseline.json 案件對應 Hypothesize 輸出推測：

- top conf 落在 **0.55-0.65** 區間
- 沒到 HIGH=0.70 → 走 PROBE
- LLM 照規則層動作 → 反問

### 3.3 設計原則

> Baseline 85% 已穩 → turn-cycle 應該「**不破壞 + 補強模糊情境**」，不是「比 baseline 更謹慎」。閾值應該**寬而非緊**。

具體理由：

1. **0.55 仍高於 LOW_CONFIDENCE=0.30** — 真正模糊（0.2-0.4）仍走 EXPLORE
2. **GAP 0.15 對多意圖友善**：兩個 hypothesis 都 0.6-0.55 也能 COMMIT，由 `system.md`「多意圖訊息要各自盡量回答」規則處理
3. **PROBE 已不純反問**（B-fix-v1 改成「追問 + 仍要把當下能答的部分答出來」），即使誤判 COMMIT → PROBE 也不再純空回，傷害比改前小

---

## 4. 對打驗證

| 階段 | 67-case strict pass | 對 baseline |
| --- | --- | --- |
| baseline (no turn-cycle) | 83.6% / 1 fail | — |
| turn-cycle off (control) | 83.6% | 持平 |
| turn-cycle on, HIGH=0.70 / GAP=0.30 | 82% / 3 fail | **-1.6pp** ❌ |
| turn-cycle on, HIGH=0.55 / GAP=0.15 | **89.6%** / 0 fail | **+6.0pp** ✅ |

**結論**：B-fix-v2 把 strict pass 從 82% 拉到 89.6%（超過 baseline 6pp），fail 從 3 歸 0。

---

## 5. 邊界條件 unit smoke

B-fix-v2 commit message 列出 4 個 smoke：

| 情境 | top.conf | runner_up.conf | gap | 預期 | 實際 |
| --- | --- | --- | --- | --- | --- |
| 高信心 + 差距大 | 0.60 | 0.30 | 0.30 | COMMIT | ✓ |
| 剛達 HIGH | 0.55 | 0.30 | 0.25 | COMMIT | ✓ |
| 中信心 | 0.50 | 0.30 | 0.20 | PROBE | ✓ |
| 中信心 + gap 小 | 0.45 | 0.40 | 0.05 | PROBE | ✓ |

`agent/policy.py` 開頭註解也明標「從 0.70 降到 0.55」「從 0.30 降到 0.15」便於追溯。

---

## 6. 調整 SOP

若日後要再調 HIGH / GAP，遵守：

1. **保留 baseline 對打資料**：跑 `quality_check`（不帶 --turn-cycle）拿純 baseline 數字，記在 `quality/reports/`
2. **A/B**：跑 `quality_check --turn-cycle` 對打舊閾值 vs 新閾值；至少 67 共同題
3. **檢查 fail 是否歸零**：fail 數比 partial 重要 — 客戶看到完全空回比看到部分回答差
4. **不要單獨改一個**：HIGH 與 GAP 互相耦合（高 HIGH + 低 GAP 等於只看 top；低 HIGH + 高 GAP 等於只看 ranked separation）。要動建議成對調
5. **新值要寫進 `policy.py` 開頭註解**：附舊值 + 對打結果，給未來人看
6. **在本檔追加一行** 到 §2 調整歷程表

---

## 7. 不要做

- ❌ **把 HIGH 拉到 0.85+**：top 永遠到不了，永遠走 PROBE，等於關掉 COMMIT
- ❌ **GAP 設成負值**：runner-up 比 top 高也算 commit → 邏輯破壞，policy 沒義意
- ❌ **依某一筆 case 微調**：閾值是統計而非 case-by-case；改了要全 67 題重跑
- ❌ **production 灰度**：本 branch 為實驗，閾值調整不該透過 production traffic 學

---

## 8. 相關文件

- [Turn Cycle / Belief-Augmented ReAct manual](turn_cycle_belief_augmented_react.md) — Policy 在整套架構中的位置
- [ADR-0010](../../../docs/1-decisions/ADR-0010-belief-augmented-react.md) — 為何規則層 sanity check
- `agent/policy.py` — 實作；開頭註解仍有 `從 0.70 降到 0.55` 訊息
- `agent/quality/reports/quality_report_2026-05-11_23{11,26,41}.md` — B-fix-v1/v2 對打 raw
