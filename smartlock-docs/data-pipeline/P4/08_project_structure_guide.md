# 08 專案結構指南 — data-pipeline

| 欄位 | 內容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-07-07 |
| 狀態 | 草稿（現況 baseline）|
| 負責人 | 平台架構師（多 agent 排查綜合）|
| 適用範圍 | `data/`（離線數據中台）+ `SQL/`（schema/migration/三庫）|

> ⚠️ **本系統的結構盤點必須誠實標示「死目錄」與「superseded 文件」。** data-pipeline 有一組**設計上存在、實際不存在**的路徑（`agent/skills/data/`、`data/storage/skill_drafts/`），以及一組**描述已被 superseded 舊架構**的文件（`data/README.md`、`data/docs/manuals/架構書.md`）。§4 專門盤點這些。

---

## 1. 設計原則

### 1.1 本系統實際遵循的原則

| 原則 | 說明 | 實踐情形 |
|---|---|---|
| Medallion 分層 | `raw→bronze→silver→skill` 逐層品質提升 | 前三層實踐；skill 層產出鏈斷開 |
| config-driven | 設定集中 `data/config.toml`，改設定不改 code | 實踐（但 `skills_dir` 指向死目錄未更新）|
| 一源一腳本 | 每資料源在每階段各一腳本（`process_{source}.py`）| 完整實踐 |
| bronze-only sourcing | 知識真相源限 bronze；PDF 只引 URL | 完整實踐（CLAUDE.md 硬約束）|
| provenance 不信任 LLM | Python 強制覆寫 source/source_type | 完整實踐 |
| LLM 工廠模式 | `data/llms/get_llm` 閉包，開閉原則 | 完整實踐（與 agent LiteLLM 獨立）|
| Migration forward-only | 純 SQL、不可逆、idempotent 可重跑 | 完整實踐（代價見 ADR-002）|
| 編號認領防撞號 | 平行 worktree 先在 registry 認領編號 | 實踐（但 registry 狀態欄漂移）|

### 1.2 與理想的差距

1. **產出鏈斷開（最大差距）**：Medallion 設計上應閉環到 agent skill，但 `silver_to_skill` 目標 `agent/skills/data/` 不存在，管線在 silver 後即斷。
2. **文件描述 superseded 世界**：`data/README.md` / `架構書.md` 描述「26-skill ReAct Agent」，該架構 2026-06-04 已被 LockCore 刪除，文件未標 status。
3. **兩套知識系統無單一真相**：pipeline（設計上游）與現行 references（手工整編）+ pgvector（後台）三者無收斂。
4. **migration 無 ORM 版本鏈**：純 SQL 便於手動套用，但犧牲回滾與自動 drift 檢測。
5. **`data/` 與 `SQL/` 職責相鄰但分離**：兩者同屬持久層職責、共處一份 SAD，但執行時零耦合（pipeline 不寫 DB）。

---

## 2. 現有頂層結構

```
Smart-Lock.../
├── data/                              # 離線 Medallion 數據中台（本系統）
│   ├── README.md                      # ⚠️ 描述 superseded 26-skill ReAct 架構（tier-4）
│   ├── config.toml                    # pipeline 集中設定（tomllib 載入）
│   ├── pyproject.toml                 # data pipeline 依賴（uv）
│   ├── pipeline/                      # 4 階段處理腳本
│   ├── llms/                          # pipeline 專屬 LLM 工廠（與 agent 獨立）
│   ├── storage/                       # Medallion 檔案系統（raw/bronze/silver）
│   └── docs/                          # pipeline 文件（含 superseded 架構書）
│
└── SQL/                               # 關聯式 schema / migration / 三庫（本系統）
    ├── Schema.sql                     # 基底 22 表（1013 行）
    ├── Schema_*.sql                   # 9 個擴充 schema 檔
    ├── migrations/                    # 87 個 forward-only migration + registry
    ├── platform/                      # 平台庫獨立 schema（3 表）
    └── seeds/                         # 20 個種子檔（PII 禁入）
```

> DB 三庫（品牌/技師/平台）非目錄，是部署形態；建庫腳本在 `scripts/db/`。

---

## 3. 原始碼結構分析

### 3.1 `data/` 結構（ASCII Tree + 職責）

```
data/
├── README.md                          # ⚠️ superseded：描述 ReAct Agent + 26 skill 產出鏈
├── config.toml                        # [pipelines.*] section；含 skills_dir=死目錄(:57)
├── pyproject.toml                     # uv 依賴（yt-dlp/whisper/playwright/bs4/vertexai…）
│
├── pipeline/                          # 4 階段，config-driven，一源一腳本
│   ├── source_to_raw/
│   │   └── process_youtube.py         # yt-dlp 下載（僅 youtube 有此階段）
│   ├── raw_to_bronze/                 # 清洗/轉錄 → bronze（真相源）
│   │   ├── process_youtube.py         # Vision LLM 逐幀
│   │   ├── process_video.py           # Whisper ASR
│   │   ├── process_website.py         # bs4 + markdownify 去噪
│   │   ├── process_line.py            # LINE CSV 清洗
│   │   └── process_gdrive.py          # Drive API 索引（PDF 只引 URL）
│   ├── bronze_to_silver/              # LLM 語意 chunking → 攤平 JSON
│   │   ├── process_youtube.py
│   │   ├── process_video.py
│   │   ├── process_website.py
│   │   ├── process_line.py
│   │   └── process_gdrive.py
│   └── silver_to_skill/               # ⚠️ 產出鏈斷開（目標死目錄）
│       ├── __init__.py
│       ├── classify_documents.py      # Tier1 快篩 + Tier2 LLM 分類（比對 26 skill）
│       ├── generate_drafts.py         # LLM append-only 合併 / 建新 SKILL.md
│       ├── approve_drafts.py          # --dry-run / --confirm 寫入（死目錄）
│       ├── _classifier.py             # 分類器內部
│       ├── _loaders.py                # silver 載入（含 problem_cards）
│       ├── _merger.py                 # append-only 合併邏輯
│       ├── _prompts.py                # LLM prompt 模板
│       ├── _schemas.py                # 結構化輸出 schema
│       └── _skill_registry.py         # ⚠️ 26-skill router（ts-*/app-* 舊架構:77-83）
│
├── llms/                              # pipeline 專屬 LLM 工廠（≠ agent LockCore）
│   ├── __init__.py                    # LLM_REGISTRY / VISION_REGISTRY / get_llm
│   ├── vertexai.py                    # 主力（gemini-2.5-flash）
│   ├── openai_llm.py
│   ├── anthropic_llm.py
│   ├── ollama_llm.py
│   └── langchain_adapter.py
│
├── storage/                           # Medallion 檔案系統
│   ├── raw/{youtube,website,video,gdrive,line_chat}/    # 近空殼（各源 1-2 檔）
│   ├── bronze/{youtube,website,video,gdrive,line_chat}/ # ★ 真相源（約 115 檔）
│   ├── silver/{youtube,website,video,gdrive,line_chat}/ # 攤平 JSON 知識點
│   └── skill_drafts/                  # ✖ 不存在（config 宣稱但無此目錄）
│
└── docs/
    ├── manuals/
    │   ├── 架構書.md                   # ⚠️ superseded：開宗明義「供 ReAct Agent 載入」(:4)
    │   ├── 執行手冊.md
    │   ├── 測試手冊.md
    │   ├── YouTube處理流程.md
    │   ├── Video處理流程.md
    │   ├── Website處理流程.md
    │   ├── Line_Chat處理流程.md
    │   └── INDEX.md
    ├── conversations/INDEX.md
    └── assets/architecture.mmd
```

### 3.2 `SQL/` 結構（ASCII Tree + 職責）

```
SQL/
├── Schema.sql                         # 基底 22 表（1013 行）；含 users/work_orders/
│                                      # manual_chunks(VECTOR768)/case_entries(VECTOR768)/HNSW
├── Schema_v2_extensions.sql           # v2 擴充
├── Schema_api_phase1.sql              # api phase1（含 case_entries.embedding_status:55）
├── Schema_media.sql                   # 媒體/evidence 治理
├── Schema_rbac_dynamic.sql            # 動態 RBAC
├── Schema_tech_schedule.sql           # 技師排程
├── Schema_work_order_events.sql       # 工單事件
├── Schema_doc_numbering.sql           # 文件編號（agent_outbox）
├── Schema_harness_migration.sql       # harness_traces/user_facts
├── Schema_cr0001_integration_gaps.sql # CR-0001 整合缺口
│
├── migrations/                        # 87 個 forward-only migration
│   ├── 000-extensions.sql             # vector/pg_trgm/pgcrypto/uuid-ossp
│   ├── 001-cancellation-6stage.sql
│   ├── 004-config-m18.sql             # 建 saas schema + saas.tenant
│   ├── ...                            # 002..089（含 004-rls/008-rls 預留 🔒）
│   ├── 033-agent-memory-schema.sql    # 建 agent schema（memory_entry/escalation）
│   ├── 046-*.sql                      # 建 schema_migrations（套用真相源）
│   ├── 089-*.sql                      # 最新（technician_kyc）
│   └── MIGRATION_REGISTRY.md          # 編號登記簿（狀態欄「意圖非事實」）
│
├── platform/
│   └── Schema_platform.sql            # 平台庫獨立 schema（users/revoked_jti/brand_applications, 91 行）
│
└── seeds/                             # 20 個種子檔（PII 禁入）
    ├── _admin_user.sql
    ├── conversations.sql
    ├── ...
    └── README.md                      # 明令 PII 禁入；demo 帳號硬編（見 P3/13 B-09）
```

**相關腳本（在 `scripts/db/`，非 `SQL/`）：**
- `apply-schema-prod.sh`：品牌庫套用（Schema→Schema_*→migrations→回填 schema_migrations；`ON_ERROR_STOP=0`）
- `init-platform-db.sh`：平台庫建庫
- `split-tech-db.sh`：技師庫切分（`--verify` 對帳）

### 3.3 與 Medallion 理想的 Gap 分析

| Medallion 層 | 現況 | 理想 | Gap |
|---|---|---|---|
| Raw | 各源 1-2 檔（佔位/索引）| 完整原始資產留存 | 近空殼；原始影片/CSV 留存 `[待確認]`，bronze 可能無法從頭重建 |
| Bronze | 約 115 檔，真相源 | 同 | ✅ 符合理想（bronze-only sourcing）|
| Silver | 攤平 JSON，schema 統一 | 同 | ✅ 符合理想 |
| Skill | ✖ 產出目標死目錄 | 閉環到 agent 可載入格式 | **完全斷裂**；設計終點不存在 |
| 下游整合 | 手工整編 references + pgvector 各自為政 | 單一真相源雙產出 | 無收斂機制 |

---

## 4. ⚠️ 死目錄與 superseded 文件盤點（誠實記錄）

> 本節是本系統結構文件最重要的部分：明列哪些路徑**設計上存在但實際不存在**、哪些文件**描述已被 superseded 的舊世界**。後人若照這些操作會失敗。

### 4.1 死目錄（設計宣稱、實際不存在）

| 路徑 | 宣稱來源 | 實測 | 影響 |
|---|---|---|---|
| `agent/skills/` | `config.toml:57`（父路徑）| ✖ `ls: No such file or directory` | 整個舊 skill 根目錄不存在 |
| `agent/skills/data/` | `config.toml:57` `skills_dir`、`架構書.md:53`、`README.md:125` | ✖ 不存在 | `silver_to_skill` 產出終點死目錄 |
| `data/storage/skill_drafts/` | `config.toml:58` `drafts_dir`、`README.md:20` | ✖ 不存在 | `generate_drafts.py` 草稿目標不存在 |

### 4.2 描述 superseded 舊架構的文件

| 文件 | 問題 | 佐證 | 正確替代 |
|---|---|---|---|
| `data/README.md` | 描述「26 skill + 產出到 agent/skills/data」| `README.md:125` | 現行知識走 lockcore references（手工整編）|
| `data/docs/manuals/架構書.md` | 開宗明義「供 agent 的 **ReAct Agent** 載入」| `架構書.md:4,53` | ReAct 2026-06-04 已被 LockCore 刪除 |
| `data/pipeline/silver_to_skill/_skill_registry.py` | 綁定 26-skill router（`ts-*`→troubleshoot、`app-*`→app-guide）| `_skill_registry.py:77-83` | Agent Skills 標準只有 2 builtin skill |
| `SQL/migrations/*-rls.sql`（004-rls/008-rls）| RLS 預留骨架，實務改物理隔離 | `MIGRATION_REGISTRY.md:24,29` | 一品牌一 DB（CR-0110，ADR-003）|

### 4.3 死碼 / 半成品欄位

| 欄位 / 結構 | 狀態 | 佐證 |
|---|---|---|
| `public.work_orders.tenant_id` | 死碼（標 single-tenant，multi-tenant 預留未用）| `Schema.sql:496`（CR-0031）|
| `saas.tenant` FK target | 半成品（RLS 未落地，物理隔離取代）| `004-config-m18.sql`（最小 FK target）|
| RLS 7 表 policy | 預留未落地（須先過 ADR-0030）| `MIGRATION_REGISTRY.md:24,29` 🔒 |

> **處理建議**：見 §6 重構建議與 ADR-003。死碼應標註或清除，避免誤導開發者以為「多租戶邏輯隔離已就緒」。

---

## 5. 命名慣例

### 5.1 Pipeline

| 類型 | 慣例 | 範例 |
|---|---|---|
| 階段目錄 | `{from}_to_{to}` | `raw_to_bronze/`、`bronze_to_silver/` |
| 處理腳本 | `process_{source}.py` | `process_youtube.py`、`process_gdrive.py` |
| 三步腳本 | `{verb}_{noun}.py` | `classify_documents.py`、`generate_drafts.py` |
| 內部私有模組 | `_{role}.py`（底線前綴）| `_classifier.py`、`_merger.py`、`_skill_registry.py` |
| config section | `[pipelines.{name}]` | `[pipelines.youtube_vision]`、`[pipelines.silver_to_skill]` |
| LLM 工廠 | `{provider}_llm.py` / `{provider}.py` | `vertexai.py`、`anthropic_llm.py` |

### 5.2 SQL / Migration

| 類型 | 慣例 | 範例 |
|---|---|---|
| 基底 schema | `Schema.sql` / `Schema_{domain}.sql` | `Schema.sql`、`Schema_media.sql` |
| Migration | `NNN-domain-feature.sql`（三位數 + kebab）| `004-config-m18.sql`、`033-agent-memory-schema.sql` |
| 預留編號 | `NNN-domain.sql` 標 🔒 於 registry | `004-rls`、`008-rls`、`010-quote` |
| schema namespace | `public` / `saas` / `agent` | `saas.reconciliation`、`agent.memory_entry` |
| 種子 | `{table}.sql` | `conversations.sql`、`invoices.sql` |
| 建庫腳本 | `{action}-{target}-db.sh` | `apply-schema-prod.sh`、`split-tech-db.sh` |

---

## 6. 重構建議

依「風險低 → 效益高」排序。

### 建議一：止血 — 標記 superseded 或修復產出鏈（優先 1）

**現況問題**：`data/` 文件描述死目錄與 superseded 架構，後人照 README 跑會寫入不存在目錄。

**方案 B（退役，先做）**：
```
1. data/README.md 與 架構書.md frontmatter 加 status: superseded
   + superseded_by: 指向本文件 / lockcore references 說明
2. config.toml [pipelines.silver_to_skill] 加註解說明目標已退役
```
**方案 A（修復，後評估）**：
```
1. silver_to_skill 新增 silver→references 轉換器
   （brand/model 已在 silver 欄位，映射到 {Brand}/{Model}.md）
2. config.toml skills_dir 改指 lockcore references 目錄
3. approve_drafts 產出 Agent Skills 標準 frontmatter（brand/model/description）
```

**預期效益**：文件不再誤導；自動化知識更新（方案 A）恢復價值。與 `00_platform/P2/09 §5.1` 一致。

### 建議二：Migration drift CI（優先 2）

**現況問題**：registry 狀態「意圖非事實」雙向漂移；046 前歷史不可考；多庫手動套用無比對。

**具體行動**：
```
1. CI job 對每環境跑 SELECT version FROM schema_migrations
2. 比對 migrations/ 目錄檔案清單 vs schema_migrations
3. drift（檔案有但未套 / 套了但無檔）→ CI 告警
4. 改善 apply-schema-prod.sh：真 ERROR 阻斷（非只結尾 grep）
```

**預期效益**：migration 真相可查；部分套用失敗不被 benign 警告淹沒（P3/13 DA-03）。

### 建議三：清算租戶隔離死碼（優先 3）

**現況問題**：`tenant_id`/`saas.tenant`/RLS 骨架成死碼，誤導開發者。

**具體行動**：
```
1. 過 ADR-0030 tier-1 裁決：RLS 是否永久放棄
2. 若放棄：work_orders.tenant_id 等死碼加明確 DEPRECATED COMMENT
   或評估移除；004-rls/008-rls 預留標 archived
3. 文件明載「隔離策略 = 一品牌一 DB 物理隔離」（見 ADR-003）
```

**預期效益**：消除「多租戶邏輯隔離已就緒」的誤解。

### 建議四：備份/還原文件 + 原始資產保存（優先 4）

**現況問題**：forward-only 無回滾，卻無備份/還原文件；raw 近空殼，bronze 可能無法重建。

**具體行動**：
```
1. 撰寫三庫備份 SOP（品牌×N/技師/平台）+ RTO/RPO
2. apply-schema-prod.sh 前置改為自動建備份（非僅提醒）
3. 確認並文件化原始影片/CSV 保存位置（若不在 repo）
```

**預期效益**：forward-only 有補救網（P3/13 DA-02）。

---

## 7. 演進路線

### Phase 1：止血與誠實（低風險，1-2 週）

| 任務 | 行動 | 驗收 |
|---|---|---|
| 文件標 superseded | `data/README.md`/`架構書.md` 加 status | frontmatter 有 status；後人不再誤跑 |
| config 加註 | `[pipelines.silver_to_skill]` 註明退役 | 註解說明死目錄 |
| 死碼標註 | `work_orders.tenant_id` 等加 COMMENT | schema 內死碼有明確標示 |

**風險評估**：極低（不改執行邏輯）。

### Phase 2：真相化與健壯（中風險，3-4 週）

| 任務 | 行動 | 驗收 |
|---|---|---|
| Migration drift CI | CI 比對 registry vs schema_migrations | drift 告警 |
| 三庫 URI 守衛 | 啟動斷言三庫可達 | 漏設 TECH_URI 啟動失敗 |
| 備份/還原文件 | 三庫備份 SOP + 一次演練 | 有還原記錄 |

**風險評估**：中（需協調三庫 + 部署腳本）。

### Phase 3：收斂與自動化（高價值，6 週+）

| 任務 | 行動 | 驗收 |
|---|---|---|
| 知識系統收斂 | 單一真相源（bronze）→ references + pgvector 雙產出 + 同源 CI | 兩套知識同源可驗 |
| 產出鏈修復（方案 A）| silver→references 轉換器 | 跑 pipeline 自動更新 references |
| pgvector 自動 embedding | bronze/silver → embedding + embedding_status 監控 | KB 自動向量化 |

**風險評估**：高（跨 pipeline + agent + api；建議先過 ADR）。

---

*文件結尾 — data-pipeline / P4 / 08_project_structure_guide.md v1.0 / 2026-07-07*
