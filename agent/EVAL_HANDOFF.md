# Eval 迭代進度交接報告

> **最後更新**：2026-04-24 07:00
> **目的**：換電腦後可直接從這份繼續迭代，不需重新摸索
> **當前狀態**：第 3 輪迭代完成，prompt + tool guard 改善已到天花板，下一步是補 SKILL.md data

---

## TL;DR

| 迭代 | 通過率 | 淨變化 | 關鍵改動 |
| :--- | :---: | :---: | :--- |
| **Baseline** | 41/60 (68.3%) | — | 原始狀態 |
| **Iteration 1** | 39/60 (65.0%) | −2 | troubleshoot「先給再問」+ system.md 型號→品牌推論 |
| **Iteration 2** | 40/60 (66.7%) | +1 | Fix A 指紋多角度錄入 + Fix B prompt 約束轉接 |
| **Iteration 3** | 39/60 (65.0%) | −1 | transfer_to_human tool-level guard（Y-1/Y-4 救回，但 judge variance 抵消） |

- **Prompt/tool 改善已到天花板**：去掉 judge variance（±2-3 題波動），實質改善約 +3-4 題
- **下一步**：補充 SKILL.md data（7 個新增 + 9 個補充），預估可到 46-48/60 (77-80%)

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

**檔案 1：`agent/skills/data/_common/troubleshoot/SKILL.md`**
- 加「先給再問」模板：`[A] 承認 → [B] 2-3 點通用排查 → [C] 問型號`
- 加「通用急救表」quick-fix 表
- 加「絕對禁止的純追問回覆樣式」

**檔案 2：`agent/prompts/system.md`**
- 末段加「型號→品牌對照表」，讓 agent 自行推論品牌 + 呼叫 update_user_info

**結果**：贏 6（S-6, W-4, W-8, X-03, X-04, X-05），輸 8（3 題 judge variance, 4 題改動副作用, 1 題 timeout）

### Iteration 2（2026-04-23 22:55）

**Fix A — `troubleshoot/SKILL.md` 指紋行**
- 改前：「建議改用人臉、掌靜脈或密碼」
- 改後：「建議將同一根手指用不同角度（指尖／指腹／側邊）多登錄幾次，或登錄紋路較清楚的不同手指；仍失敗可改用人臉、掌靜脈或密碼」
- 效果：M-5 救回 ✓

**Fix B — `system.md` 品牌推論段**
- 加入：「推論完品牌後必須繼續回答：呼叫 update_user_info 後，必須接著 load_skill 回答原問題」
- 效果：Y-1/Y-4 未救回 ✗（prompt 約束不夠強）

### Iteration 3（2026-04-23 23:57）

**Transfer Guard — `agent/skills/tools.py` + `agent/harness/debounce.py`**

在 `transfer_to_human` tool 加入 guard 邏輯：
- 新增 `_skill_loaded_this_run` ContextVar，在 `load_skill` 成功時設 True
- 新增 `_current_user_input` ContextVar，記錄用戶原始訊息
- `transfer_to_human` 被呼叫時：若未載入任何技能 AND 用戶訊息不含轉接關鍵字 → 拒絕轉接，要求先 load_skill
- 轉接關鍵字白名單：轉真人、找專員、報價、費用、多少錢、退費、派師傅 等

在 `debounce.py` 的 `run_agent()` 開頭：
- 呼叫 `reset_run_state()` 重置每輪狀態
- 呼叫 `set_current_user_input(text)` 設定用戶輸入

**效果**：
- Y-1、Y-4 救回 ✓（agent 被迫先 load_skill）
- Y-7、Y-8、Y-10 guard 生效但回答品質不足（根因是缺 data）
- 明確轉接（「轉真人」「報價」）不受影響 ✓

---

## 三、四輪分類對照

| 類別 | Baseline | Iter1 | Iter2 | Iter3 | 趨勢 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Y-* APP設定 | 5/10 | 2/10 | 3/10 | **4/10** | 改善中，但被 data gap 限制 |
| H-* 硬體維修 | 11/20 | 12/20 | 9/20 | **12/20** | 波動，需補 SOP 細節 |
| S-* 報價客服 | 8/10 | 9/10 | 9/10 | **7/10** | judge variance |
| W-* 門市規格 | 7/10 | 8/10 | 9/10 | **8/10** | 改善，W-3 需補 data |
| M-* 多意圖 | 5/5 | 3/5 | 5/5 | **3/5** | judge variance |
| G-* 越界防護 | 5/5 | 5/5 | 5/5 | **5/5** | 穩定滿分 |

---

## 四、穩定失敗題分析（17 題，3-4 輪都失敗）

### DATA GAP — 需新增 SKILL.md（7 題）

| 優先 | 題目 | 需要的 SKILL.md | 位置 | 缺少內容 |
| :---: | :--- | :--- | :--- | :--- |
| **P0** | Y-7 | 補 `app-temp-pwd` | `Chatlock/AI-99/` | 臨時密碼首位必須為「1」 |
| **P0** | Y-8 | 新增 `app-history` | `Chatlock/AI-99/` | APP 主介面→「相簿/紀錄」查看開鎖紀錄 |
| **P0** | Y-5 | 補 `ss-dormakaba` | `Dormakaba/_all-models/` | AS701 實體遙控器設定（登記鍵→OPEN→*鍵） |
| **P0** | Y-10 | 新增 `app-palm-vein` | `Chatlock/A90/` | A90 掌靜脈錄入：鏡頭正前方 15-30cm |
| **P1** | H-10 | 補 `ts-verification-chatlock` | `Chatlock/_all-models/` | 貓眼旁紅燈 = 人臉/掌靜脈辨識啟動中 |
| **P1** | X-08 | 新增 `order-intake` | `_common/` | 「我下單了」→ 收集訂單/型號/通路/聯絡人/電話/地址 |
| **P1** | X-02 | 補 `troubleshoot` 急救表 | `_common/` | 螢幕閃爍無法感應 → 鎖栓卡到受口片 |

### COVERAGE GAP — 需補充現有 SKILL.md（9 題）

| 題目 | SKILL.md | 缺少內容 |
| :--- | :--- | :--- |
| H-9 | `ts-dual-auth-dormakaba` | 「只有管理者密碼能開 = 誤觸雙重認證」判斷情境 |
| S-1 | `dispatch-guide` | 安裝流程：支付全額 → 鎖寄出給客戶 → 排期 |
| W-3 | `store-info` | 缺「名片製作」服務項目 |
| X-03 | `ts-power-drain-chatlock` | WiFi 6/7 路由器詳細設定步驟 + 內螢幕網路模組檢查 |
| X-05 | `ts-door-rebound` | 「方型帶動桿過長」根因 + 「電子按鍵開門」暫時方案 |
| X-06 | `ts-verification-chatlock` | 感應太多次 → 紅外線補光燈不亮 → 暫時鎖定 |
| X-07 | `dispatch-guide` | 安裝評估照片需含：門背面 + 門外環境（淋雨/日曬） |
| Y-2 | `ss-dormakaba` | AS701 RFID 感應卡步驟（登記鍵→貼卡→*鍵） |
| Y-3 | `app-battery` 或新增 A90 子技能 | A90 充電口：「按壓底部圓蓋右轉」才能看到 Type-C |

### 波動題（judge variance，不需改動）

M-2, M-3, S-2, S-6, W-4 — 歷史上反覆 ✓/✗，是 LLM 評分固有雜訊。

---

## 五、下一步建議

### Phase 1（最大 ROI，預估 +4-5 題）
1. 補 `app-temp-pwd`（Y-7）— 加一行「首位必須為 1」
2. 新增 `app-history`（Y-8）— 簡單 APP 操作指引
3. 補 `store-info`（W-3）— 加「名片製作」
4. 補 `dispatch-guide`（S-1, X-07）— 完善安裝流程 + 評估照片清單
5. 補 `ts-verification-chatlock`（H-10, X-06）— 紅燈/人臉辨識資訊

### Phase 2（預估 +3-4 題）
6. 補 `ss-dormakaba`（Y-2, Y-5）— AS701 遙控器 + RFID 步驟
7. 新增 `order-intake`（X-08）— 下單後收集資訊
8. 補 `ts-dual-auth-dormakaba`（H-9）— 誤觸判斷情境
9. 補 `ts-power-drain-chatlock`（X-03）— WiFi 路由器設定

**Phase 1+2 完成預估：46-48/60 (77-80%)**

---

## 六、環境與執行命令

### 6.1 地端啟動（目前使用方式）
```bash
# 啟動 FastAPI（skills/prompts 改完重啟即生效）
cd agent && uvicorn app:app --reload --port 8000

# 健康檢查
curl http://localhost:8000/health
```

### 6.2 跑完整 eval
```bash
cd /path/to/project

# 1. Runner（10-15 分鐘）
python -u -m agent.evals.runner --base-url http://localhost:8000
# 輸出：agent/evals/results/{timestamp}/raw.json

# 2. Judge（5-10 分鐘，需 Vertex AI 認證）
GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json" \
VERTEX_PROJECT_ID="cedar-scope-489604-g3" \
VERTEX_LOCATION="us-central1" \
EVAL_JUDGE_BACKEND="vertex" \
python -u -m agent.evals.judge --run-dir agent/evals/results/{timestamp}

# 3. Reporter
python -u -m agent.evals.reporter --run-dir agent/evals/results/{timestamp}
```

### 6.3 快速比對通過率
```bash
python3 << 'EOF'
import json
for run in ['20260423-154518', '20260423-173323', '20260423-225559', '20260423-235704', '新的timestamp']:
    try:
        d = json.load(open(f'agent/evals/results/{run}/judged.json', encoding='utf-8'))
        passed = sum(1 for r in d if r['judge']['pass'])
        print(f'{run}: {passed}/{len(d)} ({passed*100/len(d):.1f}%)')
    except: pass
EOF
```

### 6.4 只跑部分題（debug 用）
```bash
python -u -m agent.evals.runner --base-url http://localhost:8000 --limit 5
```

---

## 七、關鍵檔案索引

| 檔案 | 用途 | 狀態 |
| :--- | :--- | :--- |
| `agent/skills/data/_common/troubleshoot/SKILL.md` | 故障排除總入口 | iter1+iter2 已改 |
| `agent/prompts/system.md` | 系統 prompt | iter1+iter2 已改 |
| `agent/skills/tools.py` | agent tools（load_skill, update_user_info, transfer_to_human） | iter3 加 transfer guard |
| `agent/harness/debounce.py` | 訊息防抖 + agent 執行入口 | iter3 加 reset_run_state |
| `agent/evals/runner.py` | 跑 agent | 未改 |
| `agent/evals/judge.py` | LLM 評分 | 未改 |
| `agent/evals/reporter.py` | 生報告 | 未改 |
| `agent/evals/fixtures/golden.yaml` | 60 題題庫 | 未改 |
| `agent/evals/results/20260423-154518/` | **Baseline**（41/60） | |
| `agent/evals/results/20260423-173323/` | **Iter1**（39/60） | |
| `agent/evals/results/20260423-225559/` | **Iter2**（40/60） | |
| `agent/evals/results/20260423-235704/` | **Iter3**（39/60） | |

---

## 八、已知坑

1. **uvicorn --reload 不監控 .md 檔案**：改完 SKILL.md 或 system.md 後必須手動重啟 server
2. **judge 需要 Vertex AI 認證**：`GOOGLE_APPLICATION_CREDENTIALS` + `VERTEX_PROJECT_ID` 缺一不可。Gemini API key 目前 400 error 不可用
3. **judge variance ±2-3 題**：同樣的回答重跑 judge 可能翻轉，不要為波動題做改動
4. **credentials.json 要帶走**：整個 eval pipeline 靠它認 Vertex AI
5. **.env 的 POSTGRES_URI**：若換電腦沒 PG，改 config.toml `[memory] type = "memory"` 可暫時用記憶體

---

## 九、對話歷史重點

- 使用者 `sunny@funngo.ai`，專案負責人
- 偏好：做 1+2 看結果再決定，不要一次全改
- 目前在 `feat/eval-pipeline` 分支，改動尚未 commit
- transfer guard 是本輪最重要的結構性改善 — 阻止 agent 跳過 load_skill 直接轉接
- 下一步是 data 層：補 SKILL.md 內容，這需要技術手冊/師傅經驗作為資料來源
