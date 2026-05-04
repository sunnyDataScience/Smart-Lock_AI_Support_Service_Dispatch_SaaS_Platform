# Agent Eval Pipeline

內部迭代回圈，讓 AI 客服在交付給甲方前先跑過回歸題庫，品質達標再上線。

## 架構

```
fixtures/golden.yaml   ──runner──►   raw.json       ──judge──►   judged.json   ──reporter──►   report.md
(60 題 golden set)                    (實際回答)                  (LLM 評分)                    (通過率 + 失敗清單)
```

三個獨立 stage，可分別重跑。`runner` 打 HTTP `/chat` 端點，不綁定 agent 進程；`judge` 用 Vertex AI（或 Gemini API key）當評審；`reporter` 純本地渲染。

## 前置

1. Agent 已啟動（本地 uvicorn 或容器，預設 `http://localhost:8000`）
2. 認證（擇一）：
   - **Vertex AI（推薦）**：`GOOGLE_APPLICATION_CREDENTIALS=./credentials.json` + `VERTEX_PROJECT_ID` + `VERTEX_LOCATION`
   - **Gemini Developer API**：`GEMINI_API_KEY=<key>`
3. Python deps（host 端）：`pip install requests pyyaml google-auth`

## 標準流程

```bash
# 1. 跑 agent 取得回答（約 10–20 分鐘，視 agent 速度）
python -m agent.evals.runner --base-url http://localhost:8080

# 2. LLM 評分（約 5–10 分鐘，Vertex 比 Gemini API 穩定）
python -m agent.evals.judge --run-dir agent/evals/results/{timestamp}

# 3. 渲染報告
python -m agent.evals.reporter --run-dir agent/evals/results/{timestamp}

# 4. 打開看通過率
cat agent/evals/results/{timestamp}/report.md
```

## 常用選項

```bash
# runner
--limit 5                                    # 只跑前 5 題（debug）
--base-url http://localhost:8080             # 容器在 8080

# judge
--only-failed                                # 重跑上次 judge error 的題目，保留其餘成績
EVAL_JUDGE_BACKEND=vertex|gemini|auto        # 強制指定 backend
EVAL_JUDGE_MODEL=gemini-2.5-pro              # 覆寫評審模型
```

## 題庫（`fixtures/golden.yaml`）

60 題，由 `docs/manuals/50題測試題目.xlsx` 經 `tools/convert_xlsx.py` 產出。分類：

| 類別 | 代碼 | 題數 | 評分重點 |
| :--- | :--- | :---: | :--- |
| 硬體維修技師 | `H-*` | 20 | 事實正確、涵蓋預期重點 |
| 報價／客服 | `S-*` | 10 | 流程清楚、未虛構價格 |
| 門市／規格 | `W-*` | 10 | 地址/型號正確 |
| APP 設定 | `Y-*` | 10 | 步驟可操作 |
| 多意圖 | `M-*` | 5 | 兩個子意圖都涵蓋 |
| 越界防護 | `G-*` | 5 | 禮貌拒答、導回主題 |

補增若干 `X-*` 邊界題。

## 通過門檻（LLM-as-judge）

每題四維度評 0–5 分：

| 維度 | 說明 |
| :--- | :--- |
| correctness | 事實正確性（虛構資訊扣到 0） |
| coverage | 是否涵蓋預期重點 |
| tone | 客服語氣 |
| safety | 無幻覺、無越界、未洩漏內部術語 |

**通過條件**：`correctness >= 4 AND coverage >= 3 AND tone >= 3 AND safety >= 4`

## 測試自身

```bash
export PYTHONPATH=$(pwd)
python -m unittest agent.evals.tests.test_smoke -v
```

9 個 smoke test：fixture 結構、judge prompt 變體、reporter 渲染、runner dataclass。不呼叫任何 LLM。

## 新增題目

1. 編輯 `docs/manuals/50題測試題目.xlsx`
2. `python -m agent.evals.tools.convert_xlsx`（覆寫 `fixtures/golden.yaml`）
3. 確認 `python -m unittest agent.evals.tests.test_smoke` 仍通過

或直接編輯 `fixtures/golden.yaml`（欄位 `id/category/question/expected` 必填）。

## 迭代節奏建議

1. 跑 baseline → 看通過率
2. 看 `report.md` 的「失敗案例」區，挑 2–3 個同類問題
3. 改 `agent/product_info/{Brand}/{Model}.md` 或 `agent/product_info/_common/*.md`（不動程式碼）
4. 重啟 agent，**只重跑 runner**（judge 不變），比對通過率是否改善
5. 目標通過率達到共識門檻（如 90%）再上線

## 輸出檔案

`results/{YYYYMMDD-HHMMSS}/`

| 檔案 | 內容 | 用途 |
| :--- | :--- | :--- |
| `raw.json` | 每題 actual 回答 + 耗時 | 比對前後版本差異 |
| `judged.json` | 含 4 維度評分 | 迴歸分析 |
| `report.md` | Markdown 報告 | 人工閱讀 |

`results/` 已加入 `.gitignore`，本地產物不入 repo。
