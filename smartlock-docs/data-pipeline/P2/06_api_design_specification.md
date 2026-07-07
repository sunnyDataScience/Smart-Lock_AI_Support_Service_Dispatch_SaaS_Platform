# 介面契約規格 — data-pipeline

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 建立日期 | 2026-07-07 |
| 狀態 | 草稿（現況 baseline）|
| 負責人 | 平台架構師（多 agent 排查綜合）|
| 適用系統 | `data/`（離線數據中台）+ `SQL/`（DB schema / migration / 三庫）|
| 佐證來源 | `data/config.toml`、`data/pipeline/*`、`data/llms/__init__.py`、`SQL/Schema.sql`、`SQL/migrations/MIGRATION_REGISTRY.md`、`scripts/db/*`、`scripts/deploy/agent.sh` |

> ⚠️ **本系統無 REST API。** data-pipeline 是離線批次 + 持久層，對外「介面」是**契約而非端點**。本文件定義 5 類介面契約：
> 1. **Pipeline stage 契約**（§1）：4 階段 CLI / config 輸入輸出
> 2. **資料 schema 契約**（§2）：bronze / silver JSON 攤平格式
> 3. **DB migration 契約**（§3）：`NNN-domain-feature.sql` 命名 + registry 認領 + `schema_migrations` 真相源
> 4. **pgvector 檢索介面**（§4）：`manual_chunks` / `case_entries` 向量查詢
> 5. **三庫連線契約**（§5）：`POSTGRES_URI` / `TECH_POSTGRES_URI` / `PLATFORM_POSTGRES_URI`
>
> ⚠️ 契約 §1.4（silver_to_skill）的輸出目標**已斷開**（寫入不存在目錄）；本文件如實記載該契約的「宣稱行為」並標示斷點。凡未能由 code 證實者標 `[待確認]`。

---

## 1. Pipeline Stage 契約（4 階段）

每階段一個資料源一個腳本（config-driven），設定集中於 `data/config.toml`（`lockcore` 無關；由 pipeline 自己以 `tomllib` 載入）。全部 LLM 階段走 Vertex `gemini-2.5-flash`。

### 1.0 config.toml schema

`data/config.toml` 以 `[pipelines.<name>]` section 組織，每 section 對應一個階段/資料源。實測 section 與欄位：

| Section | 關鍵欄位 | 值（實測）|
|---|---|---|
| `[pipelines.video]` | `llm_provider` / `llm_model` / `temperature` | `vertexai` / `gemini-2.5-flash` / `0.3` |
| `[pipelines.video_asr]` | `model_type` / `fp16` | `medium` / `false`（Whisper）|
| `[pipelines.line_chat]` | `llm_provider` / `llm_model` / `temperature` / `auto_reply_patterns[]` | `vertexai` / `gemini-2.5-flash` / `0.3` / 2 pattern |
| `[pipelines.youtube_fetch]` | `playlists[]` | 6 個 YouTube playlist URL |
| `[pipelines.youtube_vision]` | `llm_provider` / `llm_model` / `temperature` | `vertexai` / `gemini-2.5-flash` / `0.1` |
| `[pipelines.youtube_silver]` | 同上 | `.../.../0.3` |
| `[pipelines.website]` | 同上 | `.../.../0.3` |
| `[pipelines.gdrive]` | `service_account_file` / `scopes[]` | `../credentials.json` / drive.readonly |
| `[pipelines.gdrive_silver]` | 同上 | `.../.../0.3` |
| `[pipelines.silver_to_skill]` | `llm_provider` / `llm_model` / `temperature` / `skills_dir` / `drafts_dir` | `vertexai` / `gemini-2.5-flash` / `0.2` / **`../agent/skills/data`（⚠️ 死目錄）** / `storage/skill_drafts`（⚠️ 不存在）|

> **契約約束**：機密（`GEMINI_API_KEY` / `credentials.json`）**不入 toml**，放 `.env` 或 gitignore 檔（CLAUDE.md config pattern）。`service_account_file` 只放路徑指標，不放內容。

### 1.1 階段：source_to_raw

| 契約項 | 內容 |
|---|---|
| 進入點 | `data/pipeline/source_to_raw/process_youtube.py`（僅 youtube 有此階段）|
| 輸入 | `[pipelines.youtube_fetch].playlists[]`（config）|
| 動作 | yt-dlp 下載 |
| 輸出 | `data/storage/raw/youtube/`（原始檔 / 索引）|
| 狀態 | ✅ 運作 |

### 1.2 階段：raw_to_bronze

| 契約項 | 內容 |
|---|---|
| 進入點 | `data/pipeline/raw_to_bronze/process_{youtube,video,website,line,gdrive}.py` |
| 輸入 | `raw/` 原始檔 + config（LLM/ASR 設定）|
| 動作 | YouTube→Vision LLM 逐幀；Video→Whisper ASR；Website→bs4+markdownify 去噪；GDrive→Drive API 索引；Line→CSV 清洗 |
| 輸出 | `data/storage/bronze/{source}/`（YouTube→.json、Video→.txt、Website→.md、GDrive→.json、Line→.csv）|
| 狀態 | ✅ 運作（bronze 約 115 檔）|

### 1.3 階段：bronze_to_silver

| 契約項 | 內容 |
|---|---|
| 進入點 | `data/pipeline/bronze_to_silver/process_{youtube,video,website,line,gdrive}.py` |
| 輸入 | `bronze/{source}/` 檔 + config |
| 動作 | 冪等性檢查 → LLM 扮「資深電子鎖技術編輯」語音糾錯 + 去冗 + 語意切塊 → 產 JSON array → **Python 強制覆寫 `source`/`source_type`（防幻覺）**（`架構書.md:139-144`）|
| 輸出 | `data/storage/silver/{source}/`（攤平 JSON array，schema 見 §2.2）|
| 狀態 | ✅ 運作 |

### 1.4 階段：silver_to_skill ⚠️（產出目標斷開）

三步 CLI（`data/README.md:99-127`、`架構書.md:146-166`）：

| 步驟 | 進入點 | 輸入 | 動作 | 輸出 | 狀態 |
|---|---|---|---|---|---|
| classify | `classify_documents.py` | silver + 26 既有 skill | Tier1（category+關鍵字快篩）+ Tier2（LLM 語意）| `classification.json` | ⚠️ 依賴 26-skill 舊架構 |
| generate | `generate_drafts.py` | classification.json | 對應 skill → LLM append-only 合併；≥3 chunks 建新 SKILL.md；<3 歸 unclassified | `storage/skill_drafts/*.draft`（**目錄不存在**）| ⚠️ 寫入不存在目錄 |
| approve | `approve_drafts.py` | drafts | `--dry-run` 預覽 diff / `--confirm` 備份+寫入；驗 YAML frontmatter + `$ARGUMENTS` | `../agent/skills/data/`（**死目錄**，`config.toml:57`）| ✖ **斷鏈** |

> **契約現況（誠實）**：此階段的 CLI 契約仍在 code 中，但其輸出目標 `../agent/skills/data`、`storage/skill_drafts/` 皆不存在（實測 `ls: No such file or directory`）。`_skill_registry.py:77-83` 的 router 結構（`ts-*`→troubleshoot、`app-*`→app-guide）綁定 2026-06-04 已被 LockCore superseded 的 26-skill ReAct 架構。**照此契約執行 `approve_drafts.py --confirm` 會嘗試寫入死目錄。** 修復方向見 P1/05 §9。

### 1.5 Pipeline LLM Factory 介面（data/llms/）

`data/llms/` 是 pipeline 專屬 LLM provider factory，**與 agent LockCore LiteLLMProvider 完全獨立**（`data/llms/__init__.py`）：

| 契約項 | 內容 |
|---|---|
| Registry | `LLM_REGISTRY = {vertexai, openai, anthropic, ollama}`；`VISION_REGISTRY = {vertexai}`（`__init__.py:10-19`）|
| 工廠函式 | `get_llm(provider, model) -> generate_json(prompt, system_prompt, schema) -> dict`（閉包，開閉原則，`架構書.md:106-109`）|
| 實作檔 | `vertexai.py` / `openai_llm.py` / `anthropic_llm.py` / `ollama_llm.py` / `langchain_adapter.py` |
| 允許直接 import SDK | ✅ **是**（Architecture Lock 只禁 agent runtime code 直接 import 各家 SDK；`data/` 是離線 pipeline，非 agent runtime）|

**輸出契約**：`generate_json` 回傳符合傳入 `schema` 的 dict（結構化輸出）。

---

## 2. 資料 Schema 契約（bronze / silver JSON）

### 2.1 Bronze 格式（每源不同）

| 源 | 格式 | 契約欄位（實測）|
|---|---|---|
| YouTube | `.json` | `video_id` / `url` / `title` / `transcript`（Vision LLM 逐幀 markdown）|
| Video | `.txt` | Whisper ASR 逐字稿純文字 |
| Website | `.md` | markdownify 去噪後 markdown |
| GDrive | `.json` | Drive API 索引（**PDF 只引 URL 不抄內容**）|
| LINE | `.csv` | LINE 對話匯出 |

樣本（`data/storage/bronze/youtube/-ZLd3d8EMTk.json`）：`{video_id, url, title:"AI-99 內外鏡頭確認教學", transcript}`。

### 2.2 Silver 格式（統一攤平 JSON — 核心契約）

**所有源的 silver 統一為攤平 JSON array，每元素一個知識點。** 這是 pipeline 對下游的**唯一標準化資料契約**（`架構書.md:121-125`）。

```jsonc
// data/storage/silver/{source}/{id}.json — JSON list，每元素：
{
  "content":      "string",   // 知識點正文（LLM 結構化重寫後）
  "brand":        "string",   // 品牌，如 "Chatlock"
  "model":        "string",   // 型號，如 "AI-99"
  "category":     "string",   // 類別，如 "knowledge"
  "source_type":  "string",   // 源類型，如 "youtube"（Python 強制覆寫，防幻覺）
  "source":       "string",   // 源標識（Python 強制覆寫）
  "url":          "string",   // 原始 URL
  "chunk_index":  0            // 攤平序號
}
```

**契約約束：**
- `source` / `source_type` **由 Python 強制覆寫客觀事實**，不信任 LLM 輸出（防 provenance 幻覺）。
- `content` 內容必須源自 bronze（**bronze-only sourcing**）；PDF（GDrive）只可引 `url`，不可抄入 `content`。
- 樣本（`data/storage/silver/youtube/-ZLd3d8EMTk.json`，len=5）：`brand="Chatlock", model="AI-99", category="knowledge", source_type="youtube"`。

### 2.3 下游期望格式（references — 設計 vs 現況）

| 面向 | 設計（pipeline 宣稱產出）| 現況（agent 實際使用）|
|---|---|---|
| 格式 | `SKILL.md`（26-skill router 結構）| `references/{Brand}/{Model}.md`（Agent Skills 標準）|
| frontmatter | YAML + `$ARGUMENTS` 佔位符 | `brand` / `model` / `description`（`Dormakaba/ML660.md:1-5`）|
| 位置 | `agent/skills/data/`（死目錄）| `agent/lockcore/skills/locksmith-product-knowledge/references/`（6 品牌 45 檔）|
| 產出方式 | `approve_drafts.py --confirm` 自動寫入 | **手工整編**（非本管線）|

> ⚠️ silver 契約（§2.2）與現行 references 格式（§2.3 右欄）**無自動轉換橋接**。若採 P1/05 §9 方案 A 修復，需在 `silver_to_skill` 新增 silver→references 轉換器（brand/model 已在 silver 欄位中，理論上可映射到 `{Brand}/{Model}.md` 路徑）。

---

## 3. DB Migration 契約

### 3.1 命名契約

| 契約項 | 規則 | 依據 |
|---|---|---|
| 檔名格式 | `NNN-domain-feature.sql`（三位數編號 + kebab 描述）| `MIGRATION_REGISTRY.md:1-5` |
| 編號認領 | 平行 worktree 開發前**先在 `MIGRATION_REGISTRY.md` 認領編號**再開檔（防撞號）| `MIGRATION_REGISTRY.md:2` |
| 套用方式 | `psql "$POSTGRES_URI" -f SQL/migrations/NNN-*.sql` | `MIGRATION_REGISTRY.md:5` |
| 遷移工具 | **純 SQL，非 Alembic**（無 ORM 版本鏈）| 見 ADR-002 |
| 方向 | **forward-only（不可逆）**，無 down migration | 見 ADR-002 |
| 冪等 | `ADD COLUMN IF NOT EXISTS` / `DO $$ 查 pg_constraint $$` / `ON CONFLICT DO NOTHING` | `MIGRATION_REGISTRY.md:4` |

### 3.2 套用順序契約

`scripts/db/apply-schema-prod.sh:47-57`：

```
1. SQL/Schema.sql              （基底 22 表）
2. SQL/Schema_*.sql            （字母序，9 個擴充檔）
3. SQL/migrations/*.sql        （編號序，000..089）
4. 回填 public.schema_migrations
```

- `ON_ERROR_STOP=0`：容忍 benign「already exists」（因 idempotent 重跑）；**結尾 grep 攔真 ERROR**。
- prod 套用經 cloud-sql-proxy；**套前須先建 Cloud SQL 備份**（`gcloud sql backups create`，腳本僅提醒，非自動）。

### 3.3 套用真相源契約（CRITICAL）

| 契約項 | 內容 |
|---|---|
| **唯一真相源** | `public.schema_migrations` 表（046 建）：`SELECT version, applied_at, note FROM schema_migrations ORDER BY version;` |
| registry「狀態」欄 | **人工「意圖」，非「事實」**（`MIGRATION_REGISTRY.md:7`，CR-0038 階段0）|
| 已知漂移 | 035/045 標 🟢 idempotent 但 dev 未套（已補）；017-027 標 🟡 pending 但 dev 已存在（`MIGRATION_REGISTRY.md:13-14`）|
| 046 前歷史 | 多為事後回填，**早期套用時間點不可考** |

> **語意釐清**（`MIGRATION_REGISTRY.md:11`）：🟢 idempotent =「設計可安全重套」，**≠「已套用」**。查某環境真實狀態一律以該環境 `schema_migrations` 為準。

### 3.4 POSTGRES_URI 構建契約（禁手動）

| 契約項 | 內容 |
|---|---|
| **禁止** | 永不手動構建 `POSTGRES_URI` |
| **必用** | `./scripts/deploy/agent.sh --update-db-uri`（自動 URL-encode + round-trip 驗證）| 

依據：CLAUDE.md「永不手動構建 POSTGRES_URI」。

---

## 4. pgvector 檢索介面契約

`CREATE EXTENSION vector`（`000-extensions.sql:18`、`Schema.sql:42`）。兩個向量欄位並存（雙知識系統）：

| 契約項 | `manual_chunks` | `case_entries` |
|---|---|---|
| 向量欄位 | `embedding VECTOR(768)`（`Schema.sql:334`）| `embedding VECTOR(768)`（`Schema.sql:369`）|
| 維度來源 | Google `text-embedding-004`（768 維）| 同 |
| 索引 | HNSW（m=16, ef_construction=64, `vector_cosine_ops`）（`Schema.sql:1007-1013`）| 同 |
| 檢索算子 | `ORDER BY embedding <=> query_vec`（cosine 距離）（`015-kb-v2-expand.sql:93-94`）| 同 |
| 命中門檻 | L2 手冊語義搜尋 | L1 案例庫，相似度 **≥0.85** |
| 向量化狀態 | `[待確認]` | `case_entries.embedding_status`（async，`Schema_api_phase1.sql:55`）|
| 軟刪 | `deleted_at` + partial index `WHERE deleted_at IS NULL`（015）| 同 |

**檢索介面契約（概念）：**
```sql
-- L1 案例庫檢索（相似度 ≥0.85 命中）
SELECT id, content, 1 - (embedding <=> :query_vec) AS similarity
FROM case_entries
WHERE deleted_at IS NULL
ORDER BY embedding <=> :query_vec
LIMIT :k;
```

> ⚠️ **消費者契約落差**：此 pgvector 介面由 **web/api 後台 KB 模組**呼叫（CR-0005/015 KB v2）。**現行 LINE agent 不查 pgvector**（走 filesystem references，SKILL.md 明寫「no database needed」）。兩套知識系統無收斂（見 P1/05 §5.3）。措辭不一：015 註提 ivfflat，但 `Schema.sql` 實建 HNSW（同欄位、同 pgvector，僅索引描述措辭漂移）。

---

## 5. 三庫連線契約

| DB | 連線環境變數 | 實例名（範例）/ Port | schema 內容 | 依據 |
|---|---|---|---|---|
| **品牌庫** | `POSTGRES_URI` | `lock_AI_data` / :5433 | 全 schema（~100 表，public/saas/agent）| 主 schema，一品牌一 DB（CR-0110）|
| **技師庫（權威）** | `TECH_POSTGRES_URI` | `lock_tech` / :5434 | 品牌庫子集 6-7 表（技師身分域）| CR-0112（`split-tech-db.sh`）|
| **平台庫** | `PLATFORM_POSTGRES_URI` | `lock_platform` / :5435 | 獨立 3 表（users/revoked_jti/brand_applications）| CR-0114（`Schema_platform.sql`）|

### 5.1 連線契約規則

- **技師庫 = 權威**；品牌庫保留技師列當**投影**；一致性靠 api **雙寫鏡射（tech_mirror）** + `--verify` 比對（`split-tech-db.sh:5-8,38-55`）。無跨庫交易。
- **`TECH_POSTGRES_URI` 未設 → 靜默 fallback 回主連線**（品牌庫），退化為單庫（`00_platform/P2/09 §3` 備註；雲端目前即單庫）。此為已知風險（見 P3/13）。
- 平台庫 `users` 欄位對齊品牌庫 `users` 子集（含 084 帳號安全欄），使 `core/auth.py` lockout 查詢跨庫共用（`Schema_platform.sql:24-31`）。
- 建庫腳本：品牌庫 `apply-schema-prod.sh`、平台庫 `init-platform-db.sh`、技師庫 `split-tech-db.sh`（`--verify` 對帳）。

### 5.2 連線守衛建議（缺口）

> `[待確認]` 目前**無啟動守衛檢查三庫 URI 完整性**；漏設 `TECH_POSTGRES_URI` 會靜默漂移退回單庫（`00_platform/P2/09 §6 R-05`）。建議部署啟動時斷言三庫連線可達。

---

## 6. 介面契約總表（速查）

| # | 契約類型 | 定義位置 | 消費者 | 現況 |
|---|---|---|---|---|
| 1 | Pipeline stage（4 階段 CLI + config）| `data/config.toml`、`data/pipeline/*` | 知識工程師 | ⚠️ silver→skill 斷開 |
| 2 | Silver 攤平 JSON schema | `架構書.md:121-125` + silver 樣本 | 下游知識產出 | ✅（但下游橋接斷）|
| 3 | Migration `NNN-*.sql` + registry + `schema_migrations` | `MIGRATION_REGISTRY.md`、`apply-schema-prod.sh` | DBA / 後端 | ⚠️ registry 雙向漂移 |
| 4 | pgvector 檢索（768 維 HNSW cosine）| `Schema.sql:334,369,1007-1013` | web/api KB（非 agent）| ✅（雙知識未收斂）|
| 5 | 三庫連線（3 個 `*_POSTGRES_URI`）| `scripts/db/*`、`Schema_platform.sql` | api 三面 | ✅（TECH 漏設靜默退化）|

---

*文件結尾 — data-pipeline / P2 / 06_api_design_specification.md v1.0 / 2026-07-07*
