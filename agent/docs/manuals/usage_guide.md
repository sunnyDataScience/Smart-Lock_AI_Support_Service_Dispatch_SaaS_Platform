# Agent Skills 使用手冊

## 目錄

1. [環境設定](#1-環境設定)
2. [啟動方式](#2-啟動方式)
3. [技能系統](#3-技能系統)
4. [品質檢測](#4-品質檢測)
5. [新增技能](#5-新增技能)

---

## 1. 環境設定

### 安裝依賴

```bash
cd agent_skills
pip install -r requirements.txt
```

### 設定 `.env`

在 `agent_skills/` 目錄下建立 `.env`：

```env
# Vertex AI
VERTEX_PROJECT_ID=your-gcp-project-id
VERTEX_LOCATION=us-central1

# LINE Bot
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token
```

### GCP 認證

擇一即可（優先順序由上至下）：

```bash
# 方式 A：Service Account（建議）
# 將 credentials.json 放在 agent/ 目錄下，程式會自動偵測使用

# 方式 B：ADC（備用）
gcloud auth application-default login
```

---

## 2. 啟動方式

### CLI 互動測試（不需要 LINE Bot）

```bash
cd agent_skills
python main.py
```

操作指令：
- 直接輸入文字 → 發送給 AI 客服
- `reset` → 重置對話歷史
- `quit` → 退出

### LINE Webhook 伺服器

```bash
cd agent_skills
uvicorn app:app --reload --port 8000
```

端點：
| 路徑 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 健康檢查 |
| `/chat?q=門打不開` | GET | HTTP 快速測試 |
| `/webhook` | POST | LINE Webhook（設定在 LINE Developers Console） |

### 生產部署

```bash
gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app:app
```

---

## 3. 技能系統

### 架構概覽

```
用戶訊息
  ↓
create_react_agent（system prompt 含 14 個技能摘要）
  ↓
LLM 判斷需要哪個技能
  ↓
呼叫 load_skill("troubleshoot")    ← 大類別
  ↓
SOP 指示呼叫 load_skill("ts-door-stuck")  ← 子技能
  ↓
依完整 SOP 步驟回覆 / 追問
```

### 技能清單

#### 大類別（6 個）

| 技能名稱 | 說明 |
|----------|------|
| `troubleshoot` | 故障排除總入口，依症狀分流到子技能 |
| `app-guide` | APP 配對、用戶管理、遠端開鎖、臨時密碼等 |
| `system-settings` | 音量、語言、常開模式、兒童鎖、雙重認證等 |
| `product-knowledge` | 品牌型號、電池規範、Wi-Fi、鎖匣類型等 |
| `store-info` | 營業時間、地址、電話、服務項目 |
| `dispatch-guide` | 派工判斷、安裝評估、報價邏輯 |

#### 故障排除子技能（8 個）

| 技能名稱 | 症狀 | 嚴重度 |
|----------|------|--------|
| `ts-door-stuck` | 門扇卡死無法開啟 | 5（最高） |
| `ts-auto-lock` | 自動上鎖失效 | 4 |
| `ts-alarm` | 異常警報聲響 | 3 |
| `ts-verification` | 驗證失敗與錯誤碼 | 3 |
| `ts-lock-tongue` | 鎖舌 / 受口片問題 | 4 |
| `ts-door-rebound` | 門扇反弓 | 3 |
| `ts-power-drain` | 異常耗電 | 2 |
| `ts-dual-auth` | 雙重認證誤觸 | 2 |

### 工具

| 工具名稱 | 說明 |
|----------|------|
| `load_skill` | 載入指定技能的完整 SOP 內容 |
| `transfer_to_human` | 轉接真人客服，回覆固定的聯絡資訊表單 |

---

## 4. 品質檢測

### 測試腳本

基於 `data/docs/manuals/測試手冊.md` 的 50 道題目，分 6 大類驗證回答品質。

### 執行方式

```bash
cd agent_skills

# 完整測試（Agent 回答 + LLM-as-Judge 評分）
python -m quality.quality_check

# 快速測試（Agent 回答 + 僅關鍵詞評分，省一半 API 費用）
python -m quality.quality_check --no-judge

# 重新評分（不呼叫 Agent，用上次的回答重跑 LLM Judge）
python -m quality.quality_check --judge-only
```

### 輸出檔案

| 檔案 | 說明 |
|------|------|
| `quality/quality_report.json` | 原始數據（每題回答、評分、skill 呼叫紀錄） |
| `quality/quality_report.html` | 視覺化報告，雙擊即可開啟 |

### 評分機制

| 層級 | 說明 |
|------|------|
| 關鍵詞命中 | 每題定義核心關鍵詞，統計命中數 |
| LLM-as-Judge | Gemini 判定 pass / partial / fail |
| Skill 追蹤 | 記錄每題載入了哪些 skill |

### 報告內容

- **Summary Cards** — Pass / Partial / Fail / Error 數量
- **Category Bar Chart** — 6 大分類通過率
- **Results Table** — 50 題明細，可按 verdict 篩選

---

## 5. 新增技能

### 步驟

1. 在 `skills/data/` 下建立新目錄：

```bash
mkdir skills/data/my-new-skill
```

2. 建立 `SKILL.md`：

```markdown
---
name: my-new-skill
description: 一句話描述此技能的用途和觸發場景
user-invocable: true
---

# 技能標題

## 必須收集的資訊

| 欄位 | 追問話術 | 必要性 |
|------|---------|--------|
| 品牌 | 「請問您的電子鎖是什麼品牌？」 | 必要 |

## SOP 步驟

### Step 1：...
### Step 2：...

## 需派工的條件

- ...
```

3. 重啟 agent，新技能自動載入。

### SKILL.md 格式規範

- **frontmatter**（YAML）：`name`（技能名稱）、`description`（摘要，會注入 system prompt）
- **body**（Markdown）：完整 SOP，agent 呼叫 `load_skill` 時載入

### 撰寫要點

- `description` 要包含觸發關鍵詞，讓 LLM 能判斷何時該載入
- 每個 SOP 步驟要有明確的分支判斷（成功 → 下一步、失敗 → 另一路徑）
- 資訊不足時寫明追問話術，讓 agent 知道該問什麼
- 跨技能引用用 `load_skill("skill-name")` 格式

---

## 檔案結構

```
agent_skills/
├── .env                    # 環境變數（不進版控）
├── app.py                  # FastAPI LINE Webhook
├── agent.py                # create_react_agent + system prompt
├── main.py                 # CLI 互動測試
├── requirements.txt        # Python 依賴
├── quality/
│   ├── quality_check.py    # 50 題品質檢測
│   ├── quality_report.json # 檢測結果（自動生成）
│   └── quality_report.html # 視覺化報告（自動生成）
├── skills/
│   ├── __init__.py         # SKILL.md 解析器
│   ├── tools.py            # load_skill + transfer_to_human
│   └── data/               # 14 個 SKILL.md
│       ├── troubleshoot/
│       ├── ts-door-stuck/
│       ├── ...
│       ├── app-guide/
│       ├── store-info/
│       └── dispatch-guide/
└── docs/
    └── manuals/
        └── usage_guide.md  # 本文件
```
