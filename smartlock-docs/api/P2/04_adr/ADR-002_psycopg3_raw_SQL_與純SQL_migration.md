# ADR-002: psycopg3 raw SQL 與純 SQL migration

**狀態：** 已接受（現況記錄）| **日期：** 2026-07-07 | **範圍：** api 子系統資料存取

---

## 1. 背景與問題

api 子系統是派工營運控制平面，涉及 ~100 張表（品牌庫 public/saas/agent 三 namespace）、大量金流/結算/對帳/派工 SQL，且與 agent 子系統共用 `.venv`（uv workspace）。設計初期需決定資料存取層策略：

- **ORM（SQLAlchemy）+ Alembic migration** 是 FastAPI 生態主流。
- 但 agent 子系統的 per-user 記憶層（`agent/profiles/`）已用 psycopg raw SQL + 單一共享 `AsyncConnection` 設計，Cloud SQL 閒置斷線可透明重連。
- 金流/結算 SQL 多為複雜聚合、狀態機更新，ORM 抽象反而增加心智負擔。

**問題核心**：資料存取用 ORM 抽象換取可移植性與 repository 邊界，還是用 raw SQL 換取直控與與 agent 一致的連線模式？migration 用 Alembic 版本鏈還是純 SQL 檔？

---

## 2. 考量的選項

### 選項 A：psycopg3 raw SQL + 純編號 SQL migration（採用）

| 面向 | 評估 |
|------|------|
| 資料存取 | psycopg3 `AsyncConnection`（`%s` 參數化）；service 慣例 `_ensure_conn()` + 模組級 `db_module._conn` |
| 連線 | 單一共享 AsyncConnection + autocommit + 閒置斷線透明重連（沿用 agent profiles）|
| migration | 純編號 `.sql`（`SQL/migrations/000..089`，87 檔）+ `MIGRATION_REGISTRY.md`；forward-only、idempotent |
| 缺點 | 無 repository 抽象；無 down migration；registry 意圖 vs 事實漂移 |

### 選項 B：SQLAlchemy 2.0 ORM + Alembic

| 面向 | 評估 |
|------|------|
| 資料存取 | ORM entity + session；repository 邊界天然 |
| migration | Alembic 版本鏈，可稽核、可 downgrade |
| 缺點 | 複雜金流聚合 SQL 用 ORM 表達繞路；與 agent raw SQL 模式不一致（兩套心智）；三庫多 namespace ORM 映射成本 |

### 選項 C：SQLAlchemy Core（不含 ORM）+ Alembic

| 面向 | 評估 |
|------|------|
| 資料存取 | Query builder，仍偏 SQL；比 raw 多一層 |
| migration | Alembic |
| 缺點 | 介於兩者之間，仍引入 SQLAlchemy 依賴與 metadata 維護，收益有限 |

---

## 3. 決策

**選擇：選項 A — psycopg3 raw SQL + 純 SQL migration。**

理由是「直控 + 與 agent 一致」：

- **無 SQLAlchemy**（全 `api/` grep 零命中）。service 直接寫參數化 SQL；`core/db.py` 提供三條懶連線（品牌 `POSTGRES_URI` / 技師 `TECH_POSTGRES_URI` / 平台 `PLATFORM_POSTGRES_URI`），單一共享 `AsyncConnection` + `autocommit=True`，閒置斷線透明重連（`db.py:37-59`）。fallback 安全閥：未設對應 URI 即回主連線，單庫行為不變。
- **無 Alembic**。migration = 純編號 `NNN-<short>.sql`（`SQL/migrations/`，87 檔）+ `MIGRATION_REGISTRY.md` 編號登記簿。forward-only、idempotent（`ADD COLUMN IF NOT EXISTS`、`DO $$ 查 pg_constraint $$`、`ON CONFLICT DO NOTHING`）達可重跑。套用真相源 = `public.schema_migrations` 表（migration 046 建）。
- DB = `pgvector/pgvector:pg17`（三 compose 一致）；extensions：vector（RAG embedding）、pg_trgm（中文子字串）、pgcrypto、uuid-ossp。

---

## 4. 後果

### 正面收益

- **直控 SQL**：複雜金流/結算/對帳聚合直接寫，無 ORM 抽象繞路。
- **與 agent 一致**：同一連線模式（單一共享 AsyncConnection + 透明重連），共用 uv workspace 心智一致。
- **migration 簡單**：`psql -f` 可套用，無 Alembic 版本鏈維護；idempotent 設計可重跑。
- **參數化防注入**：psycopg3 `%s` + tuple 綁定（P3/13 C-08）。

### 負面風險（誠實記載）

- **Repository 層缺失（P4 §3.2）**：90 service 直接 raw SQL，無抽象。單元測試須 monkeypatch `db_module._conn` 假連線（`db.py:39-41` 的 getattr 防禦專為此），無 mock repository 邊界；DB driver 替換影響全 service。
- **單一共享 connection 非池（P1/05 R-06）**：高併發下單連線序列化為瓶頸；`autocommit=True` 全域**無交易邊界**，多語句一致性（如雙簽、月結）靠應用層保證，非 DB 交易。
- **無 down migration**：forward-only 不可逆；回滾靠備份還原。
- **registry 意圖 vs 事實漂移**：`MIGRATION_REGISTRY.md` 自承狀態欄不可信（多筆 idempotent/pending 標記與各環境實況不符）；`schema_migrations` 046 才建，之前套用歷史多為事後回填 → 早期 migration 套用時間點不可考。缺 CI 自動比對 registry vs schema_migrations（平台 G-10）。
- **多庫手動套用擴散**：品牌×N + tech + platform 手動套用，一致性靠人工。

### 重新評估觸發條件

- service 單元測試需求上升到必須 mock repository（此時應先加建議一的 DAL 層）。
- 高併發壓測顯示單連線為明確瓶頸（改 psycopg `AsyncConnectionPool`）。
- 跨語句一致性事故（無交易邊界導致部分寫入）——需引入顯式交易。
- migration 數量或多庫數量成長到手動套用不可控（考慮輕量 migration runner）。

---

## 5. 執行計畫（現況已落地）

1. `core/db.py`：三條懶連線 + `_ensure_conn()` + autocommit + 自動重連 + fallback 安全閥。
2. service 慣例：`_ensure_conn()` + 模組級 `db_module._conn`（84/90 service 用此 pattern）。
3. `SQL/migrations/NNN-<short>.sql`：forward-only、idempotent；平行 worktree 開發前先在 `MIGRATION_REGISTRY.md` 認領編號防撞號。
4. prod 套用：`scripts/db/apply-schema-prod.sh`（`Schema.sql` → `Schema_*.sql` → `migrations/*.sql` → 回填 schema_migrations），經 cloud-sql-proxy，套前手動備份。

---

## 6. 選用影響區段

### 6.2 資料模型影響

- 三 schema namespace：`public.*`（主業務）、`saas.*`（治理/對帳結算 v2）、`agent.*`（per-user 記憶）。
- API schema（`models/generated.py` Pydantic v2）與 DB schema **分離**——前者由 openapi.yaml 生，後者由 SQL 定義，兩者非同源，須人工保持一致（漂移風險）。

### 6.4 效能影響

| 維度 | 現況 | 風險 |
|------|------|------|
| 連線 | 單一共享 AsyncConnection（非池）| 高併發序列化瓶頸（R-06）|
| 交易 | 全域 autocommit | 無交易邊界，多語句一致性靠應用層 |
| 向量檢索 | HNSW（m=16, ef_construction=64）| KB/case 語義搜尋加速 |

### 6.6 部署影響

- prod migration 手動 `psql -f` + 手動 `gcloud sql backups create`；無 CI drift 檢查、無自動備份/還原文件（P3/13 G-05/G-09）。
- **同步更新**：P1/05 §6 技術選型、P4 §3.2 Clean Arch gap、P3/13 §G-05；data-pipeline 子系統文件（DB schema 詳情）。
