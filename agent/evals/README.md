# Agent 回覆品質評測 — Baseline

> 對應 2026-06-10 lock-AI 會議 Action #5 / 決議 #3：舊版 Agent 線外先跑題庫評測，
> 確認 baseline 能力後再決定是否轉進 NanoBot source code（避免污染主系統）。

> **2026-07-08 清理**：本文提及的凍結 run 產物（`baseline_clean.csv`、`baseline_per3.csv`、
> `after_sop.csv`、`reply_quality_live_20260620.csv`、`LIVE_EVAL_RESULTS_20260620.md`）
> 已依 0707 決議移出工作區，需要時查 git 歷史。本 README 保留作為評測結果的紀錄；
> 數據摘要見下文。eval 腳本（`scripts/eval_reply_quality.py` 等）仍可重跑產出新結果。

## 跑法

```bash
# .env 的 GEMINI_API_KEY 已過期 → 改走 Vertex AI（ADC + config model = vertex_ai/）
cd agent
../.venv/bin/python scripts/eval_reply_quality.py --per-category 3 --output evals/baseline_per3.csv
# 全題庫：移除 --per-category（或加大）；--total N 依比例抽 N 題
```

LLM provider：`vertex_ai/gemini-3.1-flash-lite`（agent 與 judge 同模）。需 `gcloud
auth application-default login`（ADC）+ Vertex aiplatform API 啟用 + `openpyxl`。

## ⚠️ 重要：記憶污染更正（2026-06-13）

`baseline_per3.csv`（及早期 A/B、sim）跑在**持久 memory.db** 上,跨 run 記憶污染,
分數被低估。harness 已修為 per-run ephemeral db(見 docs/qa §8.6)。
**請以 `baseline_clean.csv` 為準。**

## Baseline（乾淨版,2026-06-13,ephemeral memory,84 題 seed=42）

`baseline_clean.csv` — 84 題 / 84 成功 / 0 錯誤。

| 維度 | 乾淨 | (污染版) |
|---|---|---|
| **overall** | **0.642** | 0.608 |
| intent_match | 0.804 | 0.768 |
| key_info_coverage | 0.500 | 0.440 |
| followup_correct | 0.179 | 0.149 |
| escalation_correct | 0.810 | 0.774 |
| safety_ok | 0.917 | 0.911 |

**解讀(綜合三種乾淨量測)**：
- **紅線 gate(L0)**：9/9 全守(金錢/要真人必轉、零報價)。
- **多輪任務完成(L1)**：clean overall 0.925、redline 1.0、資訊收集 1.0。
- **單輪 rubric**：overall 0.642;followup 0.179 偏低是**單輪量錯**(judge 比逐題追問話術 +
  judge 自評),真實追問能力看 L1。
- 結論:**agent 基本盤穩**(安全/轉接/意圖佳、會問品牌型號);最該補的是 key_info 覆蓋
  與弱分類知識,而非 followup 數字。

## (歷史,已作廢)污染版 Baseline 84 題

| 維度 | 分數 |
|---|---|
| **overall** | **0.608** |
| intent_match | 0.768 |
| key_info_coverage | 0.440 |
| followup_correct | 0.149 |
| escalation_correct | 0.774 |
| safety_ok | 0.911 |

**判讀**：
- 強：安全把關（0.91）、該轉真人會轉（0.77）、意圖辨識（0.77）。
- 弱：**多輪追問處理（followup 0.15）**為最大缺口；關鍵資訊覆蓋（0.44）次之。
- 分類最弱：品牌門市與企業客戶(0.37)、緊急開鎖(0.40)、多意圖/報價付款/完工售後(0.43)。
- 分類最強：問題卡與遠端處理(0.87)、APP 設定/連線(0.80)。

**轉進 NanoBot 前建議**：優先補「多輪追問 SOP」與弱分類（B2B/緊急開鎖/多意圖）的
knowledge/SOP;safety 與 escalation 已達可用水準。

## A/B：強化 CS SOP 追問收尾（v1.0.0 → v1.1.0，同 84 題 seed=42）

`after_sop.csv`。在 SKILL.md Step 3 加「回答型問題也要精簡收尾追問品牌型號+邀請照片」。

| 維度 | before | after | Δ |
|---|---|---|---|
| escalation_correct | 0.774 | 0.804 | **+0.030** |
| intent_match | 0.768 | 0.780 | +0.012 |
| key_info_coverage | 0.440 | 0.452 | +0.012 |
| followup_correct | 0.149 | 0.143 | −0.006 |
| overall | 0.608 | 0.618 | +0.010 |

**結論（重要）**：84/84 回覆都改變、agent 確實開始追問品牌型號（SOP 有生效），但
**followup 分數不動**。根因：judge 的 `followup_correct` 是**逐題比對該題的「缺資料追問規範」**
（有的要照片、有的僅問門型、有的要聯絡人、有的不需追問——彼此矛盾），**單一 SOP 規則
無法滿足逐題分歧的要求**;硬調 = 過擬合 benchmark。

→ **followup 卡 0.15 一半是 benchmark 設計問題（單輪測多輪 + 比固定話術 + 自評）**,
不是 agent 做差。驗證方式需重新設計,見 `docs/qa/cs-agent-eval-framework.md`。
