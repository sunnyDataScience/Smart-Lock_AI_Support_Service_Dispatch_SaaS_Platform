---
id: cs-agent-eval-framework
title: 鎖匠 CS Agent 驗證框架（重新設計）
status: draft
tier: 3-process
owner: HYBRID
created: 2026-06-12
related: [docs/qa/test-plan-smart-lock-saas.md, agent/evals/README.md]
---

# 鎖匠 CS Agent 驗證框架（重新設計）

> 取代「單輪 × 比對固定標準答案 × 自評」的舊評測法。現況問題已用數據證明（見
> `agent/evals/README.md` 的 A/B：強化 SOP 後 84/84 回覆改變、行為更對,但 followup
> 分數不動）。本文重新設計**分層、量結果不量措辭、judge 與 agent 分離**的驗證法。

## 0. 舊法為何撞牆（數據佐證）

| 問題 | 後果 | 證據 |
|---|---|---|
| **單輪測多輪** | followup 本質多輪（問→答→再判），一題一答測不準 | followup 卡 0.149,改 SOP 也不動 |
| **比對固定話術** | 換合理講法即扣分;罰措辭非對錯 | 標準答案幾乎都「請補照片」收尾 |
| **逐題追問規範彼此矛盾** | 單一 SOP 規則無法滿足（有的要照片/門型/聯絡人/不追問）| judge 評語「過度」「未依規範」並存 |
| **自評偏誤** | judge = agent 同模型,絕對分不可信 | overall 0.608 需打折 |

## 1. 設計原則

1. **分層**：硬 gate（紅線）→ 多輪任務完成 → rubric 品質 → shadow → 線上 KPI。一個分數不能代表一切。
2. **量「結果與行為」非「措辭」**：用 rubric / 任務完成度,不比對單一 golden 字串。
3. **judge 與 agent 分離 + 人工校準**：judge 用更強/不同家模型;以人工雙評算一致率（kappa）背書。
4. **對齊既有契約**：紅線來自 SOP/ADR,KPI 來自 test plan K1–K9,不另立平行標準。

## 2. 五層驗證架構

| 層 | 測什麼 | 機制 | 通過標準 | 何時 |
|---|---|---|---|---|
| **L0 紅線 gate** | 不報價/必轉真人/不編步驟/不洩個資/急件處理 | **確定性 pass/fail** + 對抗案例（故意誘導）| **100%**（硬門檻）| CI / 每次改動 |
| **L1 多輪任務完成** | 資訊收集、追問、解決或正確轉接 | **user-simulator**（LLM 扮客戶持隱藏劇本）× agent 多輪 × 任務 rubric | 任務完成率 ≥ 目標 | nightly / release |
| **L2 Rubric 品質** | 答案要點覆蓋、語氣、無越界 | 強 judge + **要點 rubric**（非固定答案）| 加權分 ≥ 目標 | nightly |
| **L3 Shadow mode** | 真實情境下可用度 | agent 只草擬 → 真人客服審/改/送 | 人工採用率 ≥ 目標 | 上線前 1–2 週 |
| **L4 線上 KPI** | 真實績效 | 自助解決率/轉真人率/CSAT/回頭率 | test plan K1–K9 | 上線後持續 |

## 3. 現有資產轉化（987 題 → 三種用途,需專家 review）

舊：987 題每題一個「固定標準答案」+「缺資料追問規範」。
新：經**老師傅/資深客服 review**,把每題拆成可機器驗的結構：

- **(a) 紅線案例集** → L0：哪些題必須轉真人/不可報價/不可編步驟。
- **(b) Rubric 要點** → L2：`answer_key_points[]`（核心訊息,不綁措辭）+ `red_lines[]`。
- **(c) 多輪劇本種子** → L1：`hidden_facts`（品牌/型號/有無照片/急迫度）+ `expected_outcome`（answer / dispatch / transfer）+ `required_info_to_collect[]`。

> 這就是 Sunny 說的「987 → 專家 review → Golden Sample」,但**產出是 rubric/劇本,不是固定答案**。

## 4. L1 多輪 user-simulator（核心新增）

```
[customer-sim LLM]  ← 持隱藏劇本(brand=X,model=Y,has_photo,urgency)
        ↕ 多輪對話(上限 N 輪)
[agent (LockCore)]
        ↓ 對話結束
[judge LLM] → 任務完成 rubric 評分
```

**劇本 schema**（每情境一份）：
```yaml
intent: 電子鎖連線故障
hidden_facts: { brand: Yale, model: YDM4109, has_photo: true, urgency: normal }
expected_outcome: answer            # answer | dispatch | transfer
required_info_to_collect: [brand, model]   # agent 必須在對話中問到
red_lines: [no_price_quote]
max_turns: 6
```

**評分**（皆 outcome,不比措辭）：
- 必抓資訊收集率（問到 required_info 幾項 / 全部）
- 結局正確（最終 answer/dispatch/transfer == expected_outcome）
- 紅線 0 違反（否則該案直接 fail）
- 輪數效率（≤ max_turns;過度追問扣分）

> followup 在這層才量得準：agent 問品牌→sim 依劇本回答→agent 用該資訊給正解,
> 整段「資訊收集→解決」是否成功,而非單輪有沒有那句話。

## 5. L2 Rubric judge（升級舊 eval 腳本）

保留 `agent/scripts/eval_reply_quality.py` 為單輪 rubric 版,但：
- judge prompt 改吃 **`answer_key_points[]` rubric**（命中幾個要點）,不比對單一 golden 字串。
- judge model 換**更強/不同家**（如 gemini-pro 或 Claude）,降自評偏誤。
- followup 維度**移除或改測「是否問到 required_info（不綁特定話術）」**——細緻的追問正確性交給 L1 多輪。

## 6. Judge 可信度校準（必做,否則自動分無意義）

- 抽 30–50 題,請**資深客服人工**依同 rubric 打分。
- 算 judge 與人工的一致率（Cohen's kappa / 相關係數）。
- **kappa ≥ 0.6 才採信自動評分放大到全量**;否則先修 rubric / 換 judge。

## 7. 實作 roadmap

| 階段 | 內容 | 依賴 | 可獨立做? |
|---|---|---|---|
| **P0** ✅ | L0 紅線確定性 gate — **已實作** `agent/scripts/redline_gate.py`（9 案例,金錢/要真人→必觸發 transfer_to_human + 不得報價;9/9 通過,exit 1 當門檻）| 無 | ✅ 已完成 |
| **P1** | L1 多輪 user-simulator 雛形（先 5–10 劇本）| 劇本種子 | ✅ 工程可先搭框架 |
| **P2** | 987 → rubric/劇本轉化 + L2 強 judge | **專家 review** | ⚠️ 需人 |
| **P3** | judge 人工校準（kappa）| 資深客服 | ⚠️ 需人 |
| **P4** | L3 shadow mode | 真人客服 + 上線通道 | ⚠️ 需人 |
| **P5** | L4 線上 KPI dashboard | 上線 | 對齊 K1–K9 |

## 8. Human Decisions Required

| # | 問題 | 建議 |
|---|---|---|
| 1 | judge 用哪個模型 | 不同家強模型（Claude / gemini-pro）;成本 vs 可信權衡 |
| 2 | 各層通過門檻 | L0=100%;L1 任務完成 ≥ 80%;L2 ≥ 0.75;對齊 K1（AI 準確 ≥80%）/K2（自助 ≥60%）|
| 3 | 誰做 rubric/劇本 review | 老師傅 + 資深客服;先從弱分類（B2B/緊急/多意圖）開始 |
| 4 | shadow mode 人力與期程 | 上線前 1–2 週,幾位客服 |

## 9. 對現況的即時取捨

- **保留** SOP v1.1.0（escalation +0.03、行為更像真客服、無 regression）。
- **停止**為單輪 followup 硬調 SOP（過擬合）。
- 現有 84 題 baseline **轉用途**：當 L0 紅線/safety 的案例來源,不當 followup 優化靶。
