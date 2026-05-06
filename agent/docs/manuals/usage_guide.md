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
filter_loadable(brand, model) → 動態決定可載入的 mega-doc 清單
  ↓
注入 [可用產品資料] + [用戶資料] + [用戶訊息] 前綴
  ↓
create_react_agent（system prompt 指示從 [可用產品資料] 中選擇）
  ↓
LLM 呼叫 load_product_info("_common/troubleshoot") → 取得症狀分流路由
  ↓
LLM 呼叫 load_product_info("Dormakaba/AS850") → 依 mega-doc 內容回覆
```

### 品牌感知目錄結構

每個（品牌, 型號）一份 self-contained mega-doc。`brand` / `model` 來自檔案 frontmatter（不從路徑推斷）。

```
agent/product_info/
├── _common/
│   ├── troubleshoot.md          # 通用症狀分流路由
│   ├── dispatch.md              # 派工 SOP / 安裝預約 / 保固政策
│   ├── general-knowledge.md     # 電子鎖通用知識（電池/Wi-Fi/門框等）
│   └── store-info.md            # 店家資訊 / 服務區域 / 服務項目
├── Chatlock/
│   ├── A90.md                   # brand=Chatlock, model=A90
│   ├── AI-88.md
│   └── AI-99.md
├── Dormakaba/                   # 16 mega-docs：AS701/AS850/.../Rose
├── Philips/
├── Kaadas/
├── Milre/
├── AiLock/
└── 3E/
```

**Profile 載入規則**（`product_info/__init__.py:filter_loadable`）：
| Profile 狀態 | 可載入清單 |
|------|---------|
| brand+model 齊備 | `{Brand}/{Model}` + 全部 `_common/*` |
| brand 只齊備 model 缺 | 只 `_common/*`（回覆需附「通用建議」免責聲明）|
| 全未知 | 只 `_common/*` + Quick Reply 收品牌 |

### Mega-doc 總數：36 份

| 分類 | 數量 | 說明 |
|------|------|------|
| _common | 4 | troubleshoot / dispatch / general-knowledge / store-info |
| Chatlock | 3 | A90 / AI-88 / AI-99 |
| Dormakaba | 16 | AS701/AS850/AS901/DP850/FA9000/FSL800/GL220/ML550/ML660/ML770/MP750/RL320/RL360/RL360V/RL599/Rose |
| 其他品牌 | 13 | Philips/Kaadas/Milre/AiLock/3E |

### Mega-doc 格式

```yaml
---
brand: Dormakaba                  # 或 _common
model: AS850                      # _common 文件設為 null
description: "Dormakaba AS850 推拉式四合一智慧電子鎖（密碼／卡片／指紋／鑰匙）操作與故障排除"
---

# Dormakaba AS850

## 產品概述
...

## 操作步驟
...

## 故障排除
...

## 相關手冊
- WiFi 設定說明書: https://drive.google.com/file/d/...
- ...

## 相關影片
- ...
```

**Frontmatter 欄位**：
| 欄位 | 必填 | 說明 |
|------|------|------|
| `brand` | ✅ | 品牌名（或 `_common`）|
| `model` | ✅ | 型號名（`_common` 文件設為 null）|
| `description` | ✅ | Agent 選文件的主要依據（[可用產品資料] 條列說明）|

**Bronze-only 強制規則**：mega-doc 內容**只能**整理自 `data/storage/bronze/`（YouTube 字幕、website、video transcript）。GDrive PDF **不可信**，僅在「相關手冊」段以**連結**形式收錄，不引用 PDF 內容當操作步驟。

### 工具

| 工具名稱 | 說明 |
|----------|------|
| `load_product_info` | 載入指定 mega-doc（嚴格 profile gating，不可跨品牌載入）|
| `update_user_info` | 更新用戶品牌/型號，驗證後寫入 DB 並刷新可用產品資料清單 |
| `transfer_to_human` | 轉接真人客服，自動帶入已知用戶資料（守門：未載入產品資料且非明確轉接意圖時阻擋）|

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

## 5. 新增 Mega-Doc

### 步驟

1. 決定 mega-doc 的歸屬：

```bash
# 通用文件（_common）
touch agent/product_info/_common/my-new-doc.md

# 品牌+型號 mega-doc
touch agent/product_info/Chatlock/AI-77.md
touch agent/product_info/Dormakaba/AS999.md
```

2. 從 `data/storage/bronze/` 整理內容（嚴禁從舊 SKILL.md 二次處理、嚴禁引用 PDF 內容）：

```markdown
---
brand: Dormakaba
model: AS999
description: "Dormakaba AS999 ... 一句話描述產品定位與主要功能"
---

# Dormakaba AS999

## 產品概述
（從 bronze/website/ 或 YouTube 字幕整理產品定位、外觀、解鎖方式等）

## 操作步驟
### 管理者密碼設定
（從 YouTube 字幕逐字整理，不可臆測）

### 卡片設定
...

## 故障排除
（從 bronze/video/ 跨型號通用排查，或品牌專屬影片字幕）

## 相關手冊
- 完整說明書: https://drive.google.com/file/d/...
（PDF 連結 only，禁止引用 PDF 內容當操作步驟依據）

## 相關影片
- 操作示範: https://www.youtube.com/watch?v=...
```

3. 同步更新型號清單：
   - `docs/brand_model_list.md` 加入新型號
   - `agent/config.toml` 的 `[quick_reply]` 區段新增 LINE Quick Reply 按鈕

4. 重啟 agent，新 mega-doc 自動載入。`python main.py` 跑 smoke test 確認 loader 找到新文件、`filter_loadable()` gating 正確。

### Bronze-only 鐵律

- ✅ 來源：`data/storage/bronze/youtube/*.json`、`bronze/video/*.txt`、`bronze/website/*.md`
- ❌ 禁止：`data/storage/bronze/gdrive/*.pdf` 內容（PDF 業主判定不可信）
- ❌ 禁止：從舊 `agent/skills/data/` 或既有 mega-doc 抄錄非 bronze 的內容
- ❌ 禁止：憑常識編造「應該是這樣」的步驟

### 撰寫要點

- `description` 要點出產品差異化（如「無觸控螢幕、語音引導」），協助 LLM 從多份 mega-doc 中選對
- 操作步驟逐字記錄按鍵與語音提示（如「按【1】（新增普通用戶）」），不省略次序與按鍵
- 故障排除段先寫**通用**再寫**品牌專屬**（先列「先確認電池」這類大原則，再列具體型號排查）
- 「相關手冊」段：DDL App 對應的 PDF 連結與 SmartLocky App 對應的不同，需逐型號核對 App 版本（避免錯連結）
