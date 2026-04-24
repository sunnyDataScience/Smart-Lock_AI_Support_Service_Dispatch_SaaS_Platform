# Eval 迭代進度交接報告

> **最後更新**：2026-04-24 16:10
> **目的**：換電腦後可直接從這份繼續迭代，不需重新摸索
> **當前狀態**：第 4 輪迭代完成，通過率 46/60 (76.7%)，比 baseline +5 題

---

## TL;DR

| 迭代 | 通過率 | 淨變化 | 關鍵改動 |
| :--- | :---: | :---: | :--- |
| **Baseline** | 41/60 (68.3%) | — | 原始狀態 |
| **Iteration 1** | 39/60 (65.0%) | −2 | troubleshoot「先給再問」+ system.md 型號→品牌推論 |
| **Iteration 2** | 40/60 (66.7%) | +1 | 指紋多角度錄入 + prompt 約束轉接 |
| **Iteration 3** | 39/60 (65.0%) | −1 | transfer_to_human tool-level guard |
| **Iteration 4** | **46/60 (76.7%)** | **+7** | SKILL.md data 補充 + 品牌自動推論 + 技能拆分 |

- **最大改善**：Y-* APP 設定從 5/10 → 8/10（+3 題）
- **下一步**：剩餘 14 題失敗中，3 題需業務資料（S-1/X-05/X-08），5 題 judge variance，6 題 LLM 行為限制

---

## 一、系統架構速記

### Eval Pipeline
```
fixtures/golden.yaml (60 題) 
    ──runner──► raw.json（透過 /chat endpoint 呼叫 agent）
    ──judge──►  judged.json（Vertex AI Gemini 2.5 Pro 評分）
    ──reporter──► report.md
```

### 通過條件（judge 4 維度）
`correctness >= 4 AND coverage >= 3 AND tone >= 3 AND safety >= 4`

### 題庫分類（60 題）
| 代碼 | 類別 | 題數 |
| :--- | :--- | :---: |
| H-* | hardware_technician | 20 |
| S-* | sales_rep | 10 |
| W-* | store_assistant | 10 |
| Y-* | app_specialist | 10 |
| M-* | multi_intent | 5 |
| G-* | guardrails | 5 |

---

## 二、各迭代改動記錄

### Iteration 1（2026-04-23 17:33）

**troubleshoot/SKILL.md** — 加「先給再問」模板 + 通用急救表 + 禁止純追問
**system.md** — 加型號→品牌對照表，讓 agent 自行推論品牌

### Iteration 2（2026-04-23 22:55）

**troubleshoot/SKILL.md** — 指紋行補回「指尖/指腹/側邊多角度錄入」（M-5 救回）
**system.md** — 品牌推論段加「update_user_info 後必須繼續 load_skill」

### Iteration 3（2026-04-23 23:57）

**tools.py** — transfer_to_human 加 guard：未載入技能 + 非明確轉接 → 拒絕（Y-1/Y-4 救回）
**debounce.py** — run_agent 加 reset_run_state + set_current_user_input

### Iteration 4（2026-04-24 15:40）— 多項改善合併

**新增技能（4 個）：**
- `Chatlock/AI-99/app-history/SKILL.md` — 開鎖紀錄查看（Y-8）
- `Chatlock/A90/app-palm-vein/SKILL.md` — 掌靜脈錄入 15-30cm（Y-10）
- `Chatlock/_all-models/ts-wifi-chatlock/SKILL.md` — WiFi 網路斷線專用 SOP（X-03）
- `Chatlock/_all-models/ts-face-chatlock/SKILL.md` — 人臉/掌靜脈/紅燈專用 SOP（H-10/X-06）

**補充技能（5 個）：**
- `ts-verification-chatlock` — 貓眼紅燈含義 + 防回頭機制 + 感應失敗鎖定
- `ts-dual-auth-dormakaba` — 快速判斷「管理者密碼能開 = 雙重認證」
- `ts-power-drain-chatlock` — WiFi 路由器後台設定 802.11/頻寬/加密 + A90 圓蓋精確化
- `troubleshoot` — 急救表加「螢幕閃爍→鎖栓卡受口片」+ 路由拆分（人臉/WiFi 獨立）
- `store-info` — 印章/名片/貼紙合併為一行
- `app-guide` — 新增 app-history、app-palm-vein 路由

**Agent 架構改善（2 個）：**
- `line_ui_factory.py` — `infer_brand_from_text()` 從用戶輸入的型號或品牌名自動推論品牌
- `debounce.py` — run_agent 品牌未知時自動掃描用戶輸入，寫入 DB + ContextVar

---

## 三、五輪分類對照

| 類別 | Base | Iter1 | Iter2 | Iter3 | **Iter4** | Δ(0→4) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Y-* APP設定 | 5/10 | 2/10 | 3/10 | 4/10 | **8/10** | **+3** |
| H-* 硬體維修 | 11/20 | 12/20 | 9/20 | 12/20 | **11/20** | 0 |
| S-* 報價客服 | 8/10 | 9/10 | 9/10 | 7/10 | **9/10** | +1 |
| W-* 門市規格 | 7/10 | 8/10 | 9/10 | 8/10 | **9/10** | +2 |
| M-* 多意圖 | 5/5 | 3/5 | 5/5 | 3/5 | **4/5** | -1 |
| G-* 越界防護 | 5/5 | 5/5 | 5/5 | 5/5 | **5/5** | 0 |
| **合計** | **41/60** | 39/60 | 40/60 | 39/60 | **46/60** | **+5** |

---

## 四、剩餘失敗題分析（14 題）

### 需業務/師傅資料（3 題，bronze 無素材）

| 題目 | 缺少 | 來源 |
| :--- | :--- | :--- |
| S-1 | 安裝完整流程（支付全額→寄鎖→排期） | 業務流程 |
| X-05 | 方型帶動桿過長 + 電子按鍵暫時開門 | 師傅經驗 |
| X-08 | 「我下單了」→ 訂單資訊收集表單 | 業務流程 |

### LLM 行為限制（6 題，data 已有但 agent 不穩定使用）

| 題目 | 問題 |
| :--- | :--- |
| H-9 | 載了技能但 coverage 不夠，沒涵蓋「管理者密碼」判斷情境 |
| H-10 | 品牌推論成功但載了 product-knowledge 而非 ts-face-chatlock |
| X-06 | 品牌未知（題目沒提品牌），通用建議不夠深入 |
| X-07 | 遺漏「門背面」和「淋雨/日曬」評估照片 |
| X-10 | 遺漏充電燈號和充電時間 |
| Y-5 | 混淆實體遙控器與 APP 遠端功能 |

### Judge variance（5 題，不需改動）

H-7, H-8, M-3, W-5, X-04 — 歷史上反覆翻轉。

---

## 五、環境與執行命令

### 5.1 地端啟動
```bash
cd agent && uvicorn app:app --reload --port 8000
curl http://localhost:8000/health
```

### 5.2 跑完整 eval
```bash
cd /path/to/project

# 1. Runner（10-15 分鐘）
python -u -m agent.evals.runner --base-url http://localhost:8000

# 2. Judge（5-10 分鐘）
GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json" \
VERTEX_PROJECT_ID="cedar-scope-489604-g3" \
VERTEX_LOCATION="us-central1" \
EVAL_JUDGE_BACKEND="vertex" \
python -u -m agent.evals.judge --run-dir agent/evals/results/{timestamp}

# 3. Reporter
python -u -m agent.evals.reporter --run-dir agent/evals/results/{timestamp}
```

### 5.3 快速比對通過率
```bash
python3 << 'EOF'
import json
for run in ['20260423-154518', '20260423-173323', '20260423-225559', '20260423-235704', '20260424-154050']:
    try:
        d = json.load(open(f'agent/evals/results/{run}/judged.json', encoding='utf-8'))
        passed = sum(1 for r in d if r['judge']['pass'])
        print(f'{run}: {passed}/{len(d)} ({passed*100/len(d):.1f}%)')
    except: pass
EOF
```

---

## 六、關鍵檔案索引

| 檔案 | 用途 | 狀態 |
| :--- | :--- | :--- |
| `agent/skills/data/_common/troubleshoot/SKILL.md` | 故障排除總入口 | iter1-4 多次修改 |
| `agent/prompts/system.md` | 系統 prompt | iter1-2 已改 |
| `agent/skills/tools.py` | agent tools + transfer guard | iter3 已改 |
| `agent/harness/debounce.py` | agent 執行入口 + 品牌推論 | iter3-4 已改 |
| `agent/harness/line_ui_factory.py` | 品牌/型號匹配 + infer_brand_from_text | iter4 已改 |
| `agent/skills/data/Chatlock/_all-models/ts-wifi-chatlock/` | WiFi 專用 SOP | iter4 新增 |
| `agent/skills/data/Chatlock/_all-models/ts-face-chatlock/` | 人臉/紅燈專用 SOP | iter4 新增 |
| `agent/skills/data/Chatlock/AI-99/app-history/` | 開鎖紀錄 | iter4 新增 |
| `agent/skills/data/Chatlock/A90/app-palm-vein/` | 掌靜脈錄入 | iter4 新增 |
| `agent/evals/results/20260423-154518/` | Baseline（41/60） | |
| `agent/evals/results/20260423-173323/` | Iter1（39/60） | |
| `agent/evals/results/20260423-225559/` | Iter2（40/60） | |
| `agent/evals/results/20260423-235704/` | Iter3（39/60） | |
| `agent/evals/results/20260424-154050/` | **Iter4（46/60）** | |

---

## 七、已知坑

1. **uvicorn --reload 不監控 .md 檔案**：改完 SKILL.md 後必須手動重啟 server
2. **judge 需要 Vertex AI 認證**：`GOOGLE_APPLICATION_CREDENTIALS` + `VERTEX_PROJECT_ID`。Gemini API key 目前不可用
3. **judge variance ±2-3 題**：同樣的回答重跑可能翻轉，不要為波動題做改動
4. **credentials.json 要帶走**：eval pipeline 靠它認 Vertex AI
5. **.env 的 POSTGRES_URI**：若無 PG，改 config.toml `[memory] type = "memory"` 暫用記憶體

---

## 八、Iter4 之後的改動（非 eval 迭代）

### 急救表推拉方向修正（2026-04-24 16:30）

`troubleshoot/SKILL.md` 通用急救表「門打不開（門外）」原本模糊（「推緊再拉、拉緊再推」），改為依門的方向區分：向外拉的門→推緊門框再拉開；向內推的門→拉緊把手再推開。

### #資料修正 關鍵字攔截（2026-04-24 17:00）

新增 `harness/data_correction.py` 模組。使用者在 LINE 輸入 `#資料修正` 時，系統跳過 agent，將對話歷史 + 用戶資料寫入 `data_corrections` 表。訊息不進 checkpoint，不影響後續對話。

### Quick Reply 模糊匹配 + 循環修復（2026-04-24 17:25）

1. 品牌收集：`match_brand` 完全匹配失敗後，改用 `infer_brand_from_text()` 模糊匹配，避免循環
2. 型號收集：用戶選「其他型號，請直接回覆」時設 model="其他"，避免重複追問

---

## 九、對話歷史重點

- 使用者 `sunny@funngo.ai`，專案負責人
- 偏好：做 1+2 看結果再決定，不要一次全改
- 目前在 `feat/eval-pipeline` 分支
- 要突破 80% 需要：(1) 補 3 題業務資料 (2) 解決 LLM 路由不穩定問題
- 技能拆分策略有效 — 大技能拆成小技能後 agent 回答 coverage 顯著提升
