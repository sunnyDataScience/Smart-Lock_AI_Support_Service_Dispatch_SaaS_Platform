# Live Eval 結果（2026-06-20，Vertex gemini-3.1-flash-lite）

業主提供 Vertex 憑證（cedar-scope-489604-g3 / location=global）後實機跑三套 eval：

| Eval | 對應 TI | 結果 |
|---|---|---|
| `redline_gate.py`（9 紅線案例） | TI-A05-01 / AIOPS-02 | **9/9 全守線**（詢價/退款/付款/真人 → 全部 transfer_to_human 且零報價數字）|
| `multiturn_sim_eval.py`（5 劇本，LLM-as-Judge） | TI-A09-01 | **overall 0.975**（info 1.0 / outcome 0.9 / redline 1.0 / efficiency 1.0；幻覺 0/12）|
| `eval_reply_quality.py`（15 題抽樣） | TI-AIOPS-08 | overall 0.560（safety 0.90 / escalation 0.70 / intent 0.70；followup 0.067 偏低=單輪 Q&A 不利追問）|

**結論**：紅線守線與多輪任務完成度 live 驗證良好；單輪 reply followup 偏低為已知（單輪評測不利追問決策），屬模型行為觀察非缺陷。eval 套件三支皆可實機跑（needs_external 段已驗）。

執行指令（需 Vertex 憑證）：
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"
export VERTEX_PROJECT_ID="cedar-scope-489604-g3" VERTEX_LOCATION="global"
../.venv/bin/python scripts/redline_gate.py
../.venv/bin/python scripts/multiturn_sim_eval.py
../.venv/bin/python scripts/eval_reply_quality.py --total 15
```
