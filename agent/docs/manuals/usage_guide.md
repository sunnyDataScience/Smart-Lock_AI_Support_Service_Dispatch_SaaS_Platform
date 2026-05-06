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

技能按品牌→型號→功能組織，`brands` / `models` 從目錄路徑自動推斷（不寫在 frontmatter）：

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
├── Dormakaba/_all-models/      # 7 個品牌專屬故障排除 + ss-dormakaba
├── Chatlock/
│   ├── _all-models/            # Chatlock 全型號通用
│   └── AI-99/                  # AI-99 專屬（app-* 系列）
├── Philips/_all-models/
├── Kaadas/_all-models/
├── Milre/_all-models/
├── AiLock/_all-models/
├── 3E/_all-models/
└── Waferlock/_all-models/
```

**路徑推斷規則**：
| 路徑 | brands | models |
|------|--------|--------|
| `_common/{skill}/` | None（通用） | None |
| `{Brand}/_all-models/{skill}/` | `[Brand]` | None |
| `{Brand}/{Model}/{skill}/` | `[Brand]` | `[Model]` |

**Profile 載入規則**（`skills/__init__.py:filter_skills`）：
| Profile 狀態 | 可載入清單 |
|------|---------|
| brand+model 齊備 | _common + brand-wide + model-specific |
| brand 已知、model 未知 | _common + brand-wide（回覆需附「通用建議」免責聲明）|
| brand 未知 / 無對應資料 | 只 _common（觸發 Quick Reply 收品牌或路徑 C 警語） |

### 技能總數：67 個

| 分類 | 數量 | 說明 |
|------|------|------|
| _common | 7 | troubleshoot / dispatch-guide / store-info 等通用技能 |
| Chatlock | 23 | 故障排除 + APP + 系統設定（含 AI-99 專屬 app-*）|
| Dormakaba | 7 | 7 個故障排除 + ss-dormakaba 系統設定 |
| 其他品牌 | 30 | Philips / Kaadas / Milre / AiLock / 3E / Waferlock 各 5 |

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

**注意**：`brands` 和 `models` 從目錄路徑自動推斷，**不需寫在 frontmatter**。

### 工具

| 工具名稱 | 說明 |
|----------|------|
| `load_skill` | 載入指定技能的完整 SOP 內容（支援前綴比對） |
| `update_user_info` | 更新用戶品牌/型號，驗證後寫入 DB 並刷新可用技能清單 |
| `transfer_to_human` | 轉接真人客服，自動帶入已知用戶資料（守門：非明確轉接意圖時阻擋）|

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

## 5. 新增 SKILL.md

### 步驟

1. 依目錄結構決定歸屬：

```bash
# 通用技能（_common，永遠顯示）
mkdir -p agent/skills/data/_common/my-new-skill
touch agent/skills/data/_common/my-new-skill/SKILL.md

# 品牌全型號通用
mkdir -p agent/skills/data/Dormakaba/_all-models/ts-new-issue-dormakaba
touch agent/skills/data/Dormakaba/_all-models/ts-new-issue-dormakaba/SKILL.md

# 品牌+型號專屬（如 Chatlock AI-99 的 APP 設定）
mkdir -p agent/skills/data/Chatlock/AI-99/app-new-feature
touch agent/skills/data/Chatlock/AI-99/app-new-feature/SKILL.md
```

2. SKILL.md 內容：

```markdown
---
name: ts-new-issue-dormakaba
description: "Dormakaba 某類問題的故障排除SOP"
trigger_keywords:
  - "關鍵詞1"
  - "關鍵詞2"
category: troubleshoot
severity: 4
---

# 標題

## 必須收集的資訊
...

## SOP 步驟
...

## 需派工的條件
...
```

3. 同步更新型號清單：
   - `docs/brand_model_list.md` 加入新型號
   - `agent/config.toml` 的 `[quick_reply]` 區段新增 LINE Quick Reply 按鈕

4. 重啟 agent，新 SKILL.md 自動載入。`python main.py` 跑 LLM smoke test，或執行 quality_check 確認 skill 命中正確。

### 撰寫要點

- `name` 用 `ts-*` / `app-*` / `ss-*` 子技能前綴 → 不顯示在頂層清單，由母技能 SOP 引導載入
- 例外：`app-guide` / `ss-dormakaba` 仍列頂層
- `description` 要點出該 skill 的差異化情境（如「Dormakaba 鎖舌縮不回去」），協助 LLM 從多個 skill 中選對
- `trigger_keywords` 取自客戶常用語，前 5 個會在 [可用技能] 清單以括號顯示給 LLM
- SOP 步驟逐字記錄按鍵與語音提示（如「按【1】（新增普通用戶）」），不省略次序與按鍵
- 故障排除類 (`category: troubleshoot`) 必填 `severity` 1-5，影響派工建議分流
