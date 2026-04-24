# Agent 使用手冊

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
cd agent
pip install -r requirements.txt
```

### 環境設定

所有設定檔統一放在**專案主目錄**：

```bash
# 1. 建立 .env
cp .env.example .env
# 編輯 .env 填入實際值（Vertex AI、LINE Bot、PostgreSQL 等）

# 2. GCP 認證（擇一）
# 方式 A：Service Account（建議）— 將 credentials.json 放在專案主目錄下
# 方式 B：ADC（備用）— gcloud auth application-default login
```

---

## 2. 啟動方式

### CLI 互動測試（不需要 LINE Bot）

```bash
cd agent
python main.py
```

操作指令：
- 直接輸入文字 → 發送給 AI 客服
- `reset` → 重置對話歷史
- `quit` → 退出

### LINE Webhook 伺服器

```bash
cd agent
uvicorn app:app --reload --port 8000
```

端點：
| 路徑 | 方法 | 說明 |
|------|------|------|
| `/health` | GET | 健康檢查 |
| `/chat?q=門打不開` | GET | HTTP 快速測試 |
| `/webhook` | POST | LINE Webhook（設定在 LINE Developers Console） |

### Docker 部署

參考 `docs/manuals/docker_guide.md` 和 `docs/manuals/cloud_run_deploy.md`。

---

## 3. 技能系統

### 架構概覽

```
用戶訊息
  ↓
debounce.run_agent()
  ↓
載入用戶 facts → 推斷 device_brand / device_model
  ↓
filter_skills(brand, model) → 動態過濾技能清單
  ↓
注入 [可用技能] + [用戶資料] + [用戶訊息] 前綴
  ↓
create_react_agent（system prompt 指示從 [可用技能] 中選擇）
  ↓
LLM 呼叫 load_skill("troubleshoot") → 路由到品牌版子技能
  ↓
LLM 呼叫 load_skill("ts-door-stuck-dormakaba") → 依 SOP 回覆
```

### 品牌感知目錄結構

技能按品牌→型號→功能組織，brands/models 從目錄路徑自動推斷：

```
skills/data/
├── _common/                    # 通用技能（不分品牌，永遠顯示）
│   ├── store-info/
│   ├── dispatch-guide/
│   ├── product-knowledge/
│   ├── update-profile/
│   ├── troubleshoot/           # 故障排除路由器
│   ├── ts-auto-lock/
│   └── ts-door-rebound/
├── Dormakaba/
│   └── _all-models/
│       ├── ts-door-stuck-dormakaba/
│       ├── ts-alarm-dormakaba/
│       └── ...（7 個品牌專屬技能）
├── Chatlock/
│   ├── _all-models/            # Chatlock 全型號通用（9 個）
│   └── AI-99/                  # AI-99 專屬（10 個）
├── Philips/
├── Kaadas/
├── Milre/
├── AiLock/
├── 3E/
└── Waferlock/
```

**路徑推斷規則**：
| 路徑 | 推斷結果 |
|------|---------|
| `_common/{skill}/` | 通用（永遠顯示） |
| `{Brand}/_all-models/{skill}/` | 該品牌全型號 |
| `{Brand}/{Model}/{skill}/` | 該品牌特定型號 |

### 技能總數：67 個

| 分類 | 數量 | 說明 |
|------|------|------|
| _common | 7 | 通用技能（store-info, dispatch-guide 等） |
| Dormakaba | 7 | 故障排除 + 系統設定 |
| Chatlock | 23 | 故障排除 + APP + 系統設定（含 WiFi/人臉子技能） |
| 其他品牌 | 30 | Philips/Kaadas/Milre/AiLock/3E/Waferlock 各 5 |

### SKILL.md 格式

```yaml
---
name: ts-door-stuck-dormakaba
description: "Dormakaba 門扇卡死無法開啟的故障排除SOP"
trigger_keywords:
  - "門打不開"
  - "鎖卡住"
category: troubleshoot        # troubleshoot | teaching | reference | router
severity: 5                   # 1-5（僅 troubleshoot 類）
---

# 標題

## 必須收集的資訊
...
## SOP 步驟
...
## 需派工的條件
...
```

**Frontmatter 欄位**：
| 欄位 | 必填 | 說明 |
|------|------|------|
| `name` | ✅ | 技能唯一識別名 |
| `description` | ✅ | Agent 選技能的主要依據 |
| `trigger_keywords` | ✅ | 觸發關鍵詞（顯示在 [可用技能] 清單） |
| `category` | ✅ | troubleshoot / teaching / reference / router |
| `severity` | 選填 | 1-5（僅 troubleshoot 類） |

**注意**：`brands` 和 `models` 從目錄路徑自動推斷，不需寫在 frontmatter。

### 工具

| 工具名稱 | 說明 |
|----------|------|
| `load_skill` | 載入指定技能的完整 SOP 內容（支援前綴比對） |
| `update_user_info` | 更新用戶品牌/型號，驗證後寫入 DB 並刷新技能清單 |
| `transfer_to_human` | 轉接真人客服，自動帶入已知用戶資料 |

### 特殊關鍵字攔截

| 關鍵字 | 行為 | 設定 |
|--------|------|------|
| `#資料修正` | 跳過 Agent，將當前對話上下文（對話歷史 + 用戶資料）寫入 `data_corrections` 表，回覆確認訊息 | `config.toml [data_correction]` |

- 支援前綴匹配：`#資料修正 品牌應該是Dormakaba` → `note` 欄位存入「品牌應該是Dormakaba」
- 不影響對話上下文：訊息不進入 checkpoint，用戶可繼續正常對話
- 僅在 LINE webhook 路徑觸發（`/chat` 測試端點不觸發）

---

## 4. 品質檢測

### 測試案例

67 道測試題目，分 7 大類驗證回答品質：

| 類別 | 數量 | 說明 |
|------|------|------|
| 硬體維修 (H/E) | 21 | 故障排除場景 |
| 報價客服 (S) | 10 | 安裝/保固/派工流程 |
| 門市規格 (W) | 10 | 店家資訊/規格查詢 |
| APP 設定 (Y) | 10 | APP 操作教學 |
| 多意圖 (M) | 5 | 一次問多個問題 |
| 圍籬測試 (G) | 5 | 領域外問題拒絕 |
| 品牌路由 (B) | 6 | 驗證品牌過濾是否正確載入對應技能 |

### 執行方式

```bash
cd agent

# 完整測試（Agent 回答 + LLM-as-Judge 評分）
python -m quality.quality_check

# 快速測試（Agent 回答 + 僅關鍵詞評分）
python -m quality.quality_check --no-judge

# 重新評分（不呼叫 Agent，用上次的回答重跑 LLM Judge）
python -m quality.quality_check --judge-only

# 只重測上次非 pass 的案例，合併結果
python -m quality.quality_check --retry-failed
```

### 測試特性

- **品牌注入**：TestCase 可設 `device_brand` / `device_model`，自動注入 `[可用技能]` + `[用戶資料]` 前綴
- **多輪模擬**：TestCase 可設 `auto_reply`，agent 追問後自動回覆第二輪（需 MemorySaver）
- **LLM**：Agent 使用 `gemini-2.5-pro`，Judge 使用 `gemini-2.5-flash`

### 輸出檔案

| 檔案 | 說明 |
|------|------|
| `quality/quality_report.json` | 原始數據（每題回答、評分、skill 呼叫紀錄） |
| `quality/quality_report.html` | 視覺化報告 |

---

## 5. 新增技能

### 步驟

1. 決定技能的品牌歸屬，在對應目錄下建立：

```bash
# 通用技能
mkdir skills/data/_common/my-new-skill

# 品牌專屬技能
mkdir skills/data/Dormakaba/_all-models/my-new-skill

# 型號專屬技能
mkdir skills/data/Chatlock/AI-99/my-new-skill
```

2. 建立 `SKILL.md`：

```markdown
---
name: my-new-skill
description: "一句話描述此技能的用途和觸發場景"
trigger_keywords:
  - "關鍵詞1"
  - "關鍵詞2"
category: troubleshoot
severity: 3
---

# 技能標題

## 必須收集的資訊

| 欄位 | 追問話術 | 必要性 |
|------|---------|--------|
| 品牌 | 「請問您的電子鎖是什麼品牌？」 | ✅ 必要 |

## SOP 步驟

### Step 1：...
### Step 2：...

## 需派工的條件

- ❌ ...
```

3. 重啟 agent，新技能自動載入（brands/models 從目錄路徑推斷）。

### Body 模板（依 category）

| category | 結構 |
|----------|------|
| troubleshoot | 資訊收集表 → SOP 步驟 → 派工條件 |
| teaching | 前置條件 → 操作步驟 → 常見問題 |
| reference | 查詢指引 → 主題區塊 |
| router | 路由表 |

### 撰寫要點

- `description` 要包含觸發關鍵詞，讓 LLM 能判斷何時該載入
- `trigger_keywords` 會顯示在 `[可用技能]` 清單中輔助 Agent 匹配
- 每個 SOP 步驟要有明確的分支判斷
- 跨技能引用用 `load_skill("skill-name")` 格式
