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
| **P1** ✅ | L1 多輪 user-simulator — **雛形已實作** `agent/scripts/multiturn_sim_eval.py`（5 劇本,customer-sim×agent 多輪×任務 rubric;首測 overall 0.80,redline 1.0,outcome_correct 0.60 揭露 agent 過度轉真人傾向）| 劇本種子 | ✅ 雛形完成 |
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

## 8.5 L1 tuning 實測心得（2026-06-13,基於真實對話）

跑 L1 雛形 + 用對話 dump 診斷 + 改 SOP 重測,學到三件事（避免後人重蹈）：

1. **n=5 太吵,別信小幅 before/after**：同設定兩次重跑,structural 一次 1.00 一次 0.38。
   sim+judge 皆 LLM,變異大 → **可靠測量需 ≥20 劇本 + 多次平均**;雛形只能定性,不能定量。
2. **SOP 文字 tuning 已到天花板**（第二次驗證,前有 followup A/B）：
   - ✅ 有效的:流程類規則(「先給排查步驟再升級」)——agent 行為確實變了。
   - ❌ 無效的:**幻覺類**。agent 持續講「您的 Yale YDM4109」+「之前的維修規劃」,SOP 文字擋不住。
     **（更正,見 §8.6：後來證明這不是幻覺,是評測 harness 記憶污染——持久 memory.db 跨 run 洩漏。
     乾淨記憶下 agent 不編造。此處保留為當時的(錯誤)觀察。）**
   - ⚠️ **反例會 priming**:在 SOP 寫「不要說 Yale YDM4109」反而把該 token 餵進 context,
     可能更常出現 → 負面範例別帶具體幻覺 token。
3. **幻覺/過度升級是模型層問題,需更高槓桿**(非 SOP 文字)：
   - top-level system-prompt 硬性 grounding(只引對話/檢索事實),或
   - 生成後 guardrail(偵測回覆出現客戶未提供的品牌型號 → 攔截/重生),或
   - 更強模型 / 檢索強制 grounding。

**結論**:L1 的價值是**揪出可操作的真缺口**(過度轉真人、編造品牌型號),不是用來刷分數。
後續修這些缺口應走「模型層 grounding」而非繼續改 SOP 文字。

## 8.6 ⚠️ 重大更正：所謂「幻覺」其實是評測 harness 記憶污染（2026-06-13）

> **前一版本(已作廢)宣稱**「agent 編造 Yale YDM4109 是幻覺,grounding guardrail 把幻覺
> 16.7%→0%」。**深入查 memory.db 後證明此結論錯誤。** 留此記錄為教訓。

**真因**：eval/sim 腳本繼承 `config.toml` 的 `db_path = "memory.db"`（**持久化**）,
且 scenario id 固定 → **user_id 跨 run 穩定**。於是：
- 前幾輪 sim 的 elock-conn,客戶(sim)講過品牌型號、預約過週三維修 → 經記憶 consolidation
  寫入 `memory.db`（`memory_entry` 235 筆,含 `[fact] 客人的電子鎖型號為 Yale YDM4109`）。
- 後續 run **同 user_id** 載回這些記憶 → agent 第一輪就「記得」品牌型號與舊預約。
- 這**不是幻覺,是忠實回想被污染的持久記憶**。escalation 偵測(`list_for_user`)同理被污染
  (讀到前次 run 的轉接,而非本輪)。

**證明**：把 db_path 改 **per-run ephemeral temp db** 後,clean 重跑(不開 guard)：
**raw 幻覺 0/11 = 0.0%**,且 elock-conn 第一輪改為**正確詢問**「請提供品牌與型號」;
clean overall **0.925**(污染時 0.61–0.85,污染一直在拉低分數)。

**修正**：`eval_reply_quality.py` / `multiturn_sim_eval.py` / `redline_gate.py` 一律
`dataclasses.replace(cfg, db_path=<temp>)` 每 run 用 ephemeral 記憶,確保乾淨評測。

**grounding guardrail 的定位更正**：它原本「修」的是污染造成的假幻覺,在 clean data 上
**無事可做**(0%)。`grounding_guard.py` 保留為**防禦性監測工具**(偵測未溯源型號代碼),
**不是**已驗證的幻覺修復;真實 agent 在乾淨記憶下不編造品牌型號。

**最大教訓**：**建 fix 前先查根因。** 差點為一個 test-harness 記憶隔離 bug 做了一個
模型層 guardrail。先看 memory.db(資料),才看清是污染而非模型行為。

## 9. 對現況的即時取捨

- **保留** SOP v1.1.0（escalation +0.03、行為更像真客服、無 regression）。
- **停止**為單輪 followup 硬調 SOP（過擬合）。
- 現有 84 題 baseline **轉用途**：當 L0 紅線/safety 的案例來源,不當 followup 優化靶。
