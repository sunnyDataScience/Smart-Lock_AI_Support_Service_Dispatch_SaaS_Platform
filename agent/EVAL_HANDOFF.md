# Eval 迭代進度交接報告

> **建立時間**：2026-04-23 18:20
> **目的**：換電腦後可直接從這份繼續迭代，不需重新摸索
> **當前狀態**：第 1 輪迭代完成（小退步 −2 題），待修 3 處明確退步後跑第 2 輪

---

## TL;DR

- **Baseline**：41/60 pass (68.3%)
- **Iteration 1**：39/60 pass (65.0%)，淨 −2
  - 贏 6（結構改善生效）
  - 輸 8（其中 3 題 judge variance、4 題 prompt/skill 改動副作用、1 題 timeout）
- **下一步**：修 2 處明確退步（M-5 指紋錄入 + Y-1/Y-4 技能載入流程）→ 跑第 2 輪

---

## 一、系統架構速記（看完這段就能上手）

### Eval Pipeline
```
fixtures/golden.yaml (60 題) 
    ──runner──► raw.json 
    ──judge──►  judged.json (Vertex AI Gemini 2.5 Pro 評分)
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
| X-* | 邊界題 | ~6 |

---

## 二、baseline 診斷（2026-04-23 15:45 跑的）

**結果**：41/60 (68.3%)、19 題失敗

**失敗分三類主題**：

1. **①不知品牌就卡住不診斷**（7 題）：agent 只會反問品牌，沒給任何初步建議
   - 樣本：H-10, W-4, W-6, W-8, Y-8, X-03, X-05
2. **②手冊/步驟沒載入就自己編**（6 題）：該 load_skill 卻直接憑空答
3. **③品牌專屬技能沒觸發**（6 題）：agent 沒把型號→品牌正確推論

使用者選了**先修 ①**。

---

## 三、Iteration 1 改動（已套用、已測）

### 3.1 檔案：`agent/skills/data/_common/troubleshoot/SKILL.md`

**改動意圖**：強制「先給初步建議、再問品牌型號」，取代原本「純反問」。

**新增內容**：
- 「🚫 絕對禁止的回覆樣式」區塊（三種純追問模式禁止）
- 「✅ 正確回覆模板」：`[A] 承認 → [B] 2-3 點通用排查 → [C] 問型號`
- 「通用急救表」quick-fix 表（電池/門外無法開/指紋失敗/網路/雙重認證）
- 「不在此表的症狀禁止猜測」警語（避免 agent 把「嗶嗶叫」等同「低電量」）

### 3.2 檔案：`agent/prompts/system.md`

**改動意圖**：當客戶只報型號沒報品牌（如 Y-8 的「AI-99 開鎖紀錄」），agent 要自行推論品牌 + 呼叫 update_user_info，不要反問。

**新增內容**：末段「型號→品牌對照表」，列出：
- AI-99/A90/AI-88 → Chatlock
- AS701/AS901/DP850/...RL599/FSL800/Rose → Dormakaba
- 7300/Alpha/702E/9200/9300 → Philips
- 藍寶堅尼 → Kaadas
- 6500F/6500S/7150+ → Milre
- 七合一旗艦款 → AiLock
- F(T7) → 3E

並指示「禁止反問品牌」「立即 update_user_info 把品牌+型號一起寫入」。

---

## 四、Iteration 1 結果（2026-04-23 17:33 跑的）

### 4.1 整體
| 指標 | Baseline | Iter1 | Δ |
| :--- | :---: | :---: | :---: |
| 總通過率 | 41/60 (68.3%) | 39/60 (65.0%) | −2 |

### 4.2 分類對照
| 類別 | Baseline | Iter1 | Δ | 判讀 |
| :--- | :---: | :---: | :---: | :--- |
| app_specialist (Y-*) | 5/10 | **2/10** | **−3** | **退步最嚴重** |
| sales_rep (S-*) | 8/10 | 9/10 | +1 | 輕微改善 |
| store_assistant (W-*) | 7/10 | 8/10 | +1 | 輕微改善 |
| hardware_technician (H-*) | 11/20 | 12/20 | +1 | 輕微改善 |
| multi_intent (M-*) | 5/5 | **3/5** | **−2** | 退步 |
| guardrails (G-*) | 5/5 | 5/5 | 0 | 不變 |

### 4.3 贏 6 題（結構生效）
S-6, W-4, W-8, X-03, X-04, X-05

### 4.4 輸 8 題（分三類）

| 類別 | 題目 | 根因 | 優先級 |
| :--- | :--- | :--- | :---: |
| **真實退步（我的改動造成）** | **M-5** 老人家指紋 | 我在 troubleshoot quick-fix 表加「建議改用人臉/掌靜脈/密碼」，**蓋掉**了原本 expected 的「重複錄入技巧（指尖/指腹/側邊）」 | **高** |
| **model→brand 推論副作用** | **Y-1** (AS701 密碼登記)、**Y-4** (Dormakaba APP 遠端金鑰) | Baseline 會載 product-knowledge / app-guide 給手冊連結 + 步驟。現在 agent 做完 update_user_info 就**跳過 load_skill 直接轉接**。新 prompt 強化推論但沒強化「update 完**必須繼續載技能**」 | **高** |
| **Judge 變異 / 細節漂移** | W-3, X-07, X-10, M-2 | Baseline 與現在答案實質差不多，被 judge 打差 0.x 分；再跑可能翻回來 | 低（不動） |
| **基礎設施** | Y-10 | ReadTimeout（超過 180s），不是 agent 答錯 | 低（不動） |

---

## 五、下一步建議（iteration 2 計畫）

### 5.1 必做的 2 處修正

**Fix A — troubleshoot/SKILL.md 指紋行（for M-5）**
- 位置：通用急救表的「指紋感應失敗」那行
- 當前：「手指擦乾再試；若為長輩指紋較淺，建議改用人臉、掌靜脈或密碼...」
- 改為：「手指擦乾再試；若為長輩指紋較淺，**建議將同一根手指用不同角度（指尖/指腹/側邊）多登錄幾次**，或登錄紋路較清楚的不同手指；仍失敗可改用人臉、掌靜脈或密碼...」

**Fix B — system.md 型號→品牌對照表段（for Y-1, Y-4）**
- 問題：agent 現在會「推論品牌 → update_user_info → 直接轉接」
- 需補強：最後一段加「**推論完品牌並 update_user_info 後，必須繼續用 load_skill 載入對應技能回答原問題，禁止只推論完就轉接或回『請專人確認』**」

### 5.2 驗收
跑完 iter2 後比對：
- 目標：通過率 ≥ 42/60（追平 baseline 並超越）
- 若 Y-1 + Y-4 + M-5 都救回 → 42/60 (70%)
- 若 W-3/X-07/X-10 因 judge variance 也翻回 → 45/60 (75%)

### 5.3 iter2 完成後的分岔
- 若 **≥ 80%**：交給資料團隊補完「②手冊沒載入就編」的品牌專屬 SOP 缺漏
- 若 **70–80%**：再看要不要做結構 fix #4（新增 `_common/setup-guide` 統一所有「如何操作 X」類問題的入口）
- 若 **仍 < 70%**：回頭檢查 prompt → skill → data 哪一層是瓶頸

---

## 六、環境與執行命令（換電腦後的復原步驟）

### 6.1 前置需求
```bash
# Python 3.11
pip install requests pyyaml google-auth

# Docker 能跑
docker --version
```

### 6.2 關鍵環境變數（在 .env，需檢查 credentials.json 存在於專案根目錄）
```
VERTEX_PROJECT_ID="cedar-scope-489604-g3"
VERTEX_LOCATION="us-central1"
POSTGRES_URI=...
LINE_CHANNEL_SECRET=...
GCS_MEDIA_BUCKET=...
```

### 6.3 啟動 eval 用 agent 容器
```bash
# 在專案根目錄
PROJECT_DIR="$(pwd)"

# 建 image（若還沒建）
docker build -t smart-lock-agent ./agent

# 停舊容器
docker rm -f smart-lock-eval 2>/dev/null

# 啟動（掛載 skills/prompts/config，用 eval 版 config）
MSYS_NO_PATHCONV=1 docker run -d --name smart-lock-eval \
  -p 8080:8080 --env-file .env \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/creds.json \
  -v "$PROJECT_DIR/agent/config.eval.toml:/app/config.toml" \
  -v "$PROJECT_DIR/credentials.json:/tmp/creds.json" \
  -v "$PROJECT_DIR/agent/skills:/app/skills" \
  -v "$PROJECT_DIR/agent/prompts:/app/prompts" \
  smart-lock-agent

# 等 /health 回 200
curl http://localhost:8080/health
```

### 6.4 跑完整 eval
```bash
export PYTHONPATH="$(pwd)"
export PYTHONIOENCODING=utf-8
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/credentials.json"
export VERTEX_PROJECT_ID="cedar-scope-489604-g3"
export VERTEX_LOCATION="us-central1"

# 1. 跑 agent 取得回答（10–20 分鐘）
python -u -m agent.evals.runner --base-url http://localhost:8080

# 輸出：agent/evals/results/{timestamp}/raw.json
# 記下 timestamp，例如 20260424-1030

# 2. LLM 評分（5–10 分鐘）
python -u -m agent.evals.judge --run-dir agent/evals/results/20260424-1030

# 3. 出報告
python -u -m agent.evals.reporter --run-dir agent/evals/results/20260424-1030
```

### 6.5 快速比對新舊通過率
```bash
python << 'EOF'
import json
for run in ['20260423-154518', '20260423-173323', '新的timestamp']:
    try:
        d = json.load(open(f'agent/evals/results/{run}/judged.json', encoding='utf-8'))
        passed = sum(1 for r in d if r['judge']['pass'])
        print(f'{run}: {passed}/{len(d)} ({passed*100/len(d):.1f}%)')
    except: pass
EOF
```

### 6.6 只跑失敗題（debug 用）
```bash
# runner 支援 --limit N 只跑前 N 題
python -u -m agent.evals.runner --base-url http://localhost:8080 --limit 5

# judge 支援 --only-failed 只重跑上次 judge error
python -u -m agent.evals.judge --run-dir ... --only-failed
```

---

## 七、關鍵檔案索引

| 檔案 | 用途 |
| :--- | :--- |
| `agent/skills/data/_common/troubleshoot/SKILL.md` | 故障排除總入口，iter1 已改 |
| `agent/prompts/system.md` | 系統 prompt，iter1 已加型號→品牌對照表 |
| `agent/evals/runner.py` | 跑 agent |
| `agent/evals/judge.py` | LLM 評分（支援 Vertex + Gemini API） |
| `agent/evals/reporter.py` | 生 markdown 報告 |
| `agent/evals/fixtures/golden.yaml` | 60 題題庫 |
| `agent/evals/results/20260423-154518/` | **Baseline**（41/60） |
| `agent/evals/results/20260423-173323/` | **Iter1**（39/60） |
| `agent/config.eval.toml` | eval 用的 config（關掉 output_validator 加速） |

---

## 八、已知坑（換電腦要注意）

1. **credentials.json 要帶走**：整個 eval pipeline 靠它認 Vertex AI
2. **.env 的 POSTGRES_URI**：若換電腦沒 PG，改 `agent/config.eval.toml` 的 `[memory]` 為 `type = "memory"` 可暫時用記憶體
3. **ngrok URL**：這是 LINE webhook 用的，eval 不需要
4. **Windows 路徑**：docker run 要 `MSYS_NO_PATHCONV=1` 前綴，否則 Git Bash 會把 `/app/...` 翻譯成 Windows 路徑
5. **Unicode 輸出**：runner/judge 的 ✓/✗ 在 Windows console 需 `PYTHONIOENCODING=utf-8`
6. **Y-10 ReadTimeout**：`agent/config.eval.toml` 若需要可把 `request_timeout` 從 180 再加高，或接受這題 timeout（非 agent bug）

---

## 九、對話歷史重點（給未來的 Claude）

- 使用者 `sunny@funngo.ai`，是專案負責人
- V1 LINE Bot 已上線給甲方（客戶）測試，但沒有內部 eval 迴圈 → 現在在補這一塊
- 使用者偏好：做 1+2 看結果再決定是否做 3+4，不要一次全改
- 使用者問過「是資料問題還是結構問題」→ 我判定 structure 勉強 OK，主要是 data 不夠 + prompt 未補強

完工後把 task #7（「改 _common/troubleshoot/SKILL.md 並重起容器、跑驗證」）狀態改 completed，起 task #8「iter2：補 M-5 指紋錄入 + 強化 load_skill 流程」。
