<!-- 由 html/agent-eval-report.html 自動轉出的 markdown 源（gen_docs_html.py）-->

<div class="wrap">

<div>

# 鎖匠 CS Agent 評測報告

<div class="sub">

LockCore Agent 回覆品質驗證 —
baseline、五層驗證框架、強模型實驗與後續建議

</div>

<div class="meta">

<span class="chip">📅 2026-06-13</span> <span class="chip">🎯 會議
Action \#5 / 決議 \#3</span> <span class="chip">🌿
chore/agent-vertex-eval</span> <span class="chip">🤖
vertex_ai/gemini-3.1-flash-lite</span>

</div>

</div>

<div class="callout good">

**一句話結論：** Agent 基本盤穩健 ——
安全把關、該轉真人會轉、意圖辨識皆達可用水準，多輪任務完成率 0.925。
單輪分數已接近「有意義的天花板」，再往上刷數字會撞到**題庫設計問題**而非
agent 能力。真正的下一步靠 **專家 review 題庫（需人）**，不是繼續調 SOP
文字。

</div>

## <span class="n">1</span>乾淨基線（84 題，ephemeral memory，seed=42）

<div class="grid">

<div class="kpi good">

<div class="v">

0.642

</div>

<div class="l">

overall

</div>

</div>

<div class="kpi good">

<div class="v">

0.917

</div>

<div class="l">

safety_ok

</div>

</div>

<div class="kpi good">

<div class="v">

0.810

</div>

<div class="l">

escalation

</div>

</div>

<div class="kpi good">

<div class="v">

0.804

</div>

<div class="l">

intent_match

</div>

</div>

<div class="kpi warn">

<div class="v">

0.500

</div>

<div class="l">

key_info

</div>

</div>

<div class="kpi bad">

<div class="v">

0.179

</div>

<div class="l">

followup

</div>

</div>

</div>

<div class="card">

<table>
<colgroup>
<col style="width: 20%" />
<col style="width: 20%" />
<col style="width: 20%" />
<col style="width: 20%" />
<col style="width: 20%" />
</colgroup>
<thead>
<tr>
<th>維度</th>
<th>乾淨版</th>
<th></th>
<th class="num">(污染版)</th>
<th>判讀</th>
</tr>
</thead>
<tbody>
<tr>
<td>overall</td>
<td class="num">0.642</td>
<td><div class="bar">
<span style="width:64%;background:var(--good)"></span>
</div></td>
<td class="num">0.608</td>
<td><span class="tag good">基本盤穩</span></td>
</tr>
<tr>
<td>safety_ok</td>
<td class="num">0.917</td>
<td><div class="bar">
<span style="width:92%;background:var(--good)"></span>
</div></td>
<td class="num">0.911</td>
<td><span class="tag good">安全把關佳</span></td>
</tr>
<tr>
<td>escalation_correct</td>
<td class="num">0.810</td>
<td><div class="bar">
<span style="width:81%;background:var(--good)"></span>
</div></td>
<td class="num">0.774</td>
<td><span class="tag good">該轉真人會轉</span></td>
</tr>
<tr>
<td>intent_match</td>
<td class="num">0.804</td>
<td><div class="bar">
<span style="width:80%;background:var(--good)"></span>
</div></td>
<td class="num">0.768</td>
<td><span class="tag good">意圖辨識佳</span></td>
</tr>
<tr>
<td>key_info_coverage</td>
<td class="num">0.500</td>
<td><div class="bar">
<span style="width:50%;background:var(--warn)"></span>
</div></td>
<td class="num">0.440</td>
<td><span class="tag warn">部分題庫扣錯</span></td>
</tr>
<tr>
<td>followup_correct</td>
<td class="num">0.179</td>
<td><div class="bar">
<span style="width:18%;background:var(--bad)"></span>
</div></td>
<td class="num">0.149</td>
<td><span class="tag bad">單輪量錯</span></td>
</tr>
</tbody>
</table>

綜合三種乾淨量測 — 紅線 gate (L0)：9/9 全守；多輪任務完成 (L1)：overall
0.925、redline 1.0、資訊收集 1.0；單輪 rubric：overall 0.642。

</div>

## <span class="n">2</span>五層驗證框架

取代舊的「單輪 × 比對固定標準答案 ×
自評」評測法。一個分數不能代表一切，分層各測一件事。

<div class="card">

<div class="lvl">

<div class="badge" style="background:#1f6feb">

L0

</div>

<div class="body">

<div class="t">

紅線 gate <span class="tag good">已實作 ✅ 9/9</span>

</div>

<div class="d">

確定性 pass/fail：金錢相關 / 明確要真人 → 必觸發 `transfer_to_human`
且不得報價。`redline_gate.py`，CI 硬門檻。

</div>

</div>

</div>

<div class="lvl">

<div class="badge" style="background:#238636">

L1

</div>

<div class="body">

<div class="t">

多輪任務完成 <span class="tag good">雛形已實作 ✅ 0.925</span>

</div>

<div class="d">

user-simulator 持隱藏劇本 × agent 多輪 × 任務
rubric。`multiturn_sim_eval.py`。followup 在這層才量得準。

</div>

</div>

</div>

<div class="lvl">

<div class="badge" style="background:#9e6a03">

L2

</div>

<div class="body">

<div class="t">

Rubric 品質 <span class="tag warn">待專家 review</span>

</div>

<div class="d">

強 judge + 要點 rubric（非固定答案）。`eval_reply_quality.py` 升級版。

</div>

</div>

</div>

<div class="lvl">

<div class="badge" style="background:#6e7681">

L3

</div>

<div class="body">

<div class="t">

Shadow mode <span class="tag warn">需真人客服</span>

</div>

<div class="d">

agent 只草擬 → 真人審/改/送，量人工採用率。上線前 1–2 週。

</div>

</div>

</div>

<div class="lvl">

<div class="badge" style="background:#6e7681">

L4

</div>

<div class="body">

<div class="t">

線上 KPI <span class="tag warn">上線後</span>

</div>

<div class="d">

自助解決率 / 轉真人率 / CSAT / 回頭率，對齊 test plan K1–K9。

</div>

</div>

</div>

</div>

## <span class="n">3</span>強模型實驗（gemini-2.5-pro）

<div class="callout bad">

**結果全 0.000 — 但問題在基礎建設，不是 agent。** 根因是 **Vertex
location 耦合 bug**：config.model 設成 pro → provider 整個鎖在
<span class="mono">us-central1</span>， 但 judge 用的
flash-lite（gemini-3.1）必須走 <span class="mono">global</span> → judge
呼叫回 <span class="mono">404 Publisher Model not found</span> →
每題評分都 0。

</div>

<div class="card">

### 關鍵發現：pro 的 agent 回覆品質其實更好

實際看原文，pro 會主動釐清與多來源 grounding，例如：

<div class="callout">

「Dormakaba、Chatlock、3E 都有說明，請問您是哪個品牌?」

</div>

要乾淨量化需讓 judge 與 agent 分屬可相容 location 後雙臂重跑 —— **現在做
ROI 低**，已先還原 config 為 flash-lite、刪除無效 CSV。

</div>

## <span class="n">4</span>為何單輪分數已近「有意義的天花板」

再往上刷數字會撞到 **benchmark 本身的問題**，不是 agent 的問題：

<div class="card">

| 卡點 | 真相 |
|----|----|
| **key_info 0.50** | 一大半是**題庫扣錯分** —— 報價題 agent 正確轉真人卻被當沒覆蓋資訊；標準答案常指向 GDrive（違反 bronze-only 原則）。 |
| **followup 0.179** | **單輪測多輪 + 比固定話術 + 自評**三重失真。真實追問力看 L1 多輪 = **0.925**，是好的。 |
| **自評偏誤** | judge = agent 同模型，絕對分本來就要打折。 |

已**兩次驗證** SOP 文字 tuning 到頂（followup A/B：84/84
回覆改變但分數不動；L1 tuning 同結論）。再硬調 = 過擬合 benchmark。

</div>

## <span class="n">5</span>重大教訓：所謂「幻覺」其實是評測 harness 記憶污染

<div class="callout warn">

**差點為一個 test-harness bug 做錯修復。** 原本以為 agent 編造「Yale
YDM4109」是幻覺，還建了 grounding guardrail。 深入查
<span class="mono">memory.db</span> 才發現：eval/sim 腳本繼承了**持久化
db_path** + scenario id 固定 → user_id 跨 run 穩定 → 前幾輪 sim
講過的品牌型號被記憶 consolidation 寫入，後續 run 同 user_id 載回。
**這不是幻覺，是忠實回想被污染的持久記憶。**

</div>

<div class="card">

### 修正

三支腳本（`eval_reply_quality.py` / `multiturn_sim_eval.py` /
`redline_gate.py`） 一律 `dataclasses.replace(cfg, db_path=<temp>)` 每
run 用 ephemeral 記憶。 乾淨重跑：raw 幻覺 **0/11 = 0.0%**，overall
從污染時的 0.61 升到 0.925。

<div class="callout good">

**最大教訓：建 fix 前先查根因。**
先看資料（memory.db），才看清是污染而非模型行為。

</div>

</div>

## <span class="n">6</span>後續建議（依 ROI 排序）

<div class="card">

1.  **P2 專家 review 題庫**<span class="tag warn">需人 · 最高
    ROI</span>\
    老師傅把 987 題拆成 rubric 要點 +
    多輪劇本，**讓指標變得有意義**。沒這步，分數再高也不可信。
2.  **更強模型**<span class="tag warn">中 ROI</span>\
    pro 定性確實更好，代價是成本/延遲 + 要修 location 耦合。
3.  **檢索 grounding 一致性**<span class="tag warn">中 ROI</span>\
    store-info（林口民富街 83 號）已存在 references，但沒穩定被叫出來。

<div class="callout">

**建議：停止刷 eval 數字**（邊際報酬遞減）。現有乾淨基線已可信且夠用。
下一步真要進步得靠**人**（P2 專家 review）—— 那正是會議 Action \#5
本來就標「⚠️ 需人」的部分。

</div>

</div>

鎖匠 CS Agent 評測報告 · 2026-06-13 · LockCore + Agent Skills + LiteLLM\
資料來源：<span class="mono">agent/evals/baseline_clean.csv</span> ·
<span class="mono">docs/qa/cs-agent-eval-framework.md</span>

</div>
