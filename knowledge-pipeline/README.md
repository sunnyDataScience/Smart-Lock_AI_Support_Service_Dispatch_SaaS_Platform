# data — 數據中台 Pipeline

將多源異質資料（LINE 對話、影片、網頁、YouTube、Google Drive 手冊）轉化為 `agent` 的 **SKILL.md 技能文件**。

## 架構概覽

```
Raw (原始資料)
 ↓  source_to_raw    — yt-dlp / Playwright / Drive API
Bronze (粗抽取)
 ↓  raw_to_bronze     — Whisper ASR / Vision LLM / HTML 清理
Silver (結構化中台)
 ↓  bronze_to_silver  — LLM Semantic Pre-chunking + 結構化重寫
Skill (技能文件產出)
    silver_to_skill   — 分類 → 合併/新建 → 審核寫入 SKILL.md
```

詳細架構圖：[`docs/assets/architecture.mmd`](docs/assets/architecture.mmd)

## 目錄結構

```
data/
├── config.toml          # 所有 pipeline 設定（LLM 模型、參數、路徑）
├── pyproject.toml       # Python 依賴（uv workspace member）
├── llms/                # LLM 工廠（Vertex AI / Gemini）
├── pipeline/
│   ├── source_to_raw/   # 下載原始資料
│   ├── raw_to_bronze/   # 清洗、轉錄、結構化
│   ├── bronze_to_silver/ # LLM 語意切塊 + metadata 推斷
│   └── silver_to_skill/ # ★ 最終產出：分類 → SKILL.md
├── storage/             # 各層資料存放
│   ├── raw/             #   原始檔案
│   ├── bronze/          #   清洗後檔案
│   ├── silver/          #   Document JSON
│   └── skill_drafts/    #   SKILL.md 草稿 + diff
└── docs/
    ├── assets/          # 架構圖 (.mmd)
    └── manuals/         # 各資料源處理流程手冊
```

## 快速開始

### 環境設定

```bash
# 從專案根目錄一次裝齊三個 module 的 deps（uv workspace）
cd ..
uv sync
# 回到 data/，補裝 playwright 瀏覽器引擎
cd data
uv run playwright install chromium    # Website 爬取需要
```

環境設定（統一放在專案主目錄）：
- `.env`：複製 `.env.example` 並填入實際值（`cp .env.example .env`）
- `credentials.json`：GCP Service Account 金鑰檔（建議），或用 `gcloud auth application-default login`（備用）

### 執行 Pipeline

```bash
cd data

# === 資料擷取與清洗 ===
# 1. 下載 YouTube 影片
python pipeline/source_to_raw/process_youtube.py --verbose

# 2. 清洗（以 Video 為例）
python pipeline/raw_to_bronze/process_video.py --verbose

# 3. LLM 語意切塊
python pipeline/bronze_to_silver/process_video.py --verbose

# === SKILL.md 產出（三步驟）===
# Step 1: 分類 — silver docs → classification.json
python pipeline/silver_to_skill/classify_documents.py --verbose

# Step 2: 草稿 — 產出 SKILL.md.draft + diff
python pipeline/silver_to_skill/generate_drafts.py --verbose

# Step 3: 審核 — 預覽 diff / 確認寫入
python pipeline/silver_to_skill/approve_drafts.py --dry-run
python pipeline/silver_to_skill/approve_drafts.py --confirm
```

### 常用選項

```bash
# 只處理特定資料源
python pipeline/silver_to_skill/classify_documents.py --source video

# 只處理特定 skill
python pipeline/silver_to_skill/generate_drafts.py --skill ts-door-stuck

# 只審核特定 skill
python pipeline/silver_to_skill/approve_drafts.py --skill ts-door-stuck --dry-run
```

## Silver → Skill 流程說明

### Step 1: 文件分類 (`classify_documents.py`)

兩層分類策略：

| 層級 | 方法 | 適用場景 |
|------|------|---------|
| Tier 1 | `metadata.category` + 關鍵字比對 | 確定性高，免 LLM 呼叫 |
| Tier 2 | LLM 語意分類（比對 26 個 skill 清單） | Tier 1 無法判定時 |

產出 `storage/skill_drafts/classification.json`。

### Step 2: 草稿產出 (`generate_drafts.py`)

| 情境 | 處理方式 |
|------|---------|
| 對應到既有 SKILL.md | LLM **append-only** 合併（絕不刪改既有 SOP） |
| 無匹配 skill，>= 3 chunks | LLM 建立新 SKILL.md |
| 無匹配 skill，< 3 chunks | 跳過（歸入 unclassified） |

產出 `storage/skill_drafts/{skill-name}/SKILL.md.draft` + `diff.txt`。

### Step 3: 審核寫入 (`approve_drafts.py`)

- `--dry-run`：預覽 diff，不寫入
- `--confirm`：備份既有 SKILL.md（`.bak.{timestamp}`），寫入 `agent/skills/data/`
- 自動驗證 YAML frontmatter 格式、`$ARGUMENTS` 佔位符保留

## 資料源

| 資料源 | 擷取方式 | Pipeline |
|--------|---------|----------|
| LINE Chat | CSV 匯出 | `raw_to_bronze` → `bronze_to_silver` |
| 訓練影片 | .MOV / .mp4 | `raw_to_bronze`（Whisper ASR）→ `bronze_to_silver` |
| YouTube | yt-dlp 下載 | `source_to_raw` → `raw_to_bronze`（Vision LLM）→ `bronze_to_silver` |
| 鎖市官網 | Playwright 爬取 | `raw_to_bronze` → `bronze_to_silver` |
| Google Drive | Drive API | `raw_to_bronze` → `bronze_to_silver` |

## 文件

- [`docs/manuals/架構書.md`](docs/manuals/架構書.md) — 系統架構白皮書
- [`docs/manuals/執行手冊.md`](docs/manuals/執行手冊.md) — 所有 pipeline 執行指令
- [`docs/manuals/Video處理流程.md`](docs/manuals/Video處理流程.md) — ETL 處理邏輯
- [`docs/manuals/YouTube處理流程.md`](docs/manuals/YouTube處理流程.md) — ETL 處理邏輯
- [`docs/manuals/Website處理流程.md`](docs/manuals/Website處理流程.md) — ETL 處理邏輯
- [`docs/manuals/Line_Chat處理流程.md`](docs/manuals/Line_Chat處理流程.md) — ETL 處理邏輯
- [`docs/manuals/測試手冊.md`](docs/manuals/測試手冊.md) — Agent 手動測試案例
