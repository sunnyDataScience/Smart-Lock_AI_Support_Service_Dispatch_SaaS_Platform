---
title: "ADR-021: psycopg3 raw SQL + 純 SQL forward-only migration"
version: 1.0
status: active
owner: api / data 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/api/P2/04_adr/ADR-002_psycopg3_raw_SQL_與純SQL_migration.md
  - smartlock-docs/data-pipeline/P2/04_adr/ADR-002_純SQL_forward-only_migration_不用Alembic.md
---

# ADR-021: psycopg3 raw SQL + 純 SQL forward-only migration

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（api / data）|
| 關聯 ADR | [ADR-020](./ADR-020_三庫物理隔離租戶模型.md) · [ADR-003](./ADR-003_工程治理排程_API收斂_migration_CD.md) |

## Context（背景與問題）

api 是派工營運控制平面：~100 張表跨 `public` / `saas` / `agent` 三 namespace，大量金流 / 結算 / 對帳 / 派工 SQL（多為複雜聚合與狀態機更新）。schema 高速演進（80+ migration），開發採平行 worktree（易撞編號）、部署為多庫（品牌 ×N + 技師 + 平台，[ADR-020](./ADR-020_三庫物理隔離租戶模型.md)）。需決定資料存取層與 migration 策略。

## Decision（決策）

### 資料存取：psycopg3 raw SQL（無 ORM）

- service 直接寫參數化 SQL（`%s` + tuple 綁定，防注入）；不引入 SQLAlchemy。
- `core/db.py` 提供**三條懶連線**（品牌 `POSTGRES_URI` / 技師 `TECH_POSTGRES_URI` / 平台 `PLATFORM_POSTGRES_URI`），單一共享 `AsyncConnection` + `autocommit=True`、閒置斷線透明重連；service 慣例 `_ensure_conn()` + 模組級 `db_module._conn`（84/90 service 採此 pattern）。
- DB image = `pgvector/pgvector:pg17`；extensions：vector（RAG embedding）、pg_trgm（中文子字串）、pgcrypto、uuid-ossp。
- `POSTGRES_URI` 一律經部署腳本 `--update-db-uri` 設定（自動 URL-encode + round-trip 驗證），不手動構建。

### migration：純編號 SQL、forward-only、idempotent

- 命名 `NNN-domain-feature.sql`（`SQL/migrations/`）；平行 worktree 開發前**先在 `MIGRATION_REGISTRY.md` 認領編號**防撞號。
- **冪等**：`ADD COLUMN IF NOT EXISTS`、`DO $$ 查 pg_constraint $$`、`ON CONFLICT DO NOTHING`——同一 migration 可對多庫、多環境安全重套。
- **套用順序**（`scripts/db/apply-schema-prod.sh`）：`Schema.sql` → `Schema_*.sql`（字母序）→ `migrations/*.sql`（編號序）→ 回填 `schema_migrations`；prod 經 cloud-sql-proxy，套前建 Cloud SQL 備份。
- **真相源**：`public.schema_migrations` 表為「已套用」唯一真相；`MIGRATION_REGISTRY.md` 僅為人工意圖註記，非權威。

## Alternatives（考量的選項）

- **A：psycopg3 raw SQL + 純 SQL migration（採用）** — 直控複雜金流 SQL、`psql -f` 即套、工具鏈一致（Python + uv + psql）。
- **B：SQLAlchemy 2.0 ORM + Alembic** — repository 邊界天然、可 downgrade；但複雜金流聚合用 ORM 繞路、無 ORM model 可 autogenerate、平行分支 revision 鏈易衝突。
- **C：SQLAlchemy Core / Flyway / Liquibase** — 介於兩者或引入 JVM 工具鏈，收益有限。

## Consequences（後果）

**正面**：複雜金流 / 結算 / 對帳聚合直接寫；agent 與 api 同一連線模式心智；migration `psql -f` 可套用、idempotent 可重跑；平行開發編號認領不撞號。
**風險（明確接受的代價）**：
- **無 repository 抽象**：單元測試須 monkeypatch `db_module._conn`；driver 替換影響全 service。
- **單一共享連線非池**：高併發序列化瓶頸——連線池為 [ADR-006](./ADR-006_即時高併發骨幹_Kafka_Redis_讀寫分離.md) Phase 1 項目。
- **全域 autocommit 無交易邊界**：多語句一致性（雙簽、月結）靠應用層保證。
- **無 down migration**：套錯只能 forward-fix；回滾靠備份還原。
- **多庫手動套用**：一致性靠人工——drift-check CI 為 [ADR-003](./ADR-003_工程治理排程_API收斂_migration_CD.md) 優先序 1。
**影響範圍**：`api/core/db.py`、全 service SQL、`SQL/migrations/*`、三庫套用腳本。
**重評觸發**：mock repository 需求上升 → 先加薄 DAL 層；壓測證實單連線瓶頸 → `AsyncConnectionPool`；跨語句一致性事故 → 顯式交易；migration / 多庫規模不可控 → 輕量 migration runner。

## Status 附註

- API schema（`models/generated.py`，Pydantic v2，由 openapi.yaml 生成）與 DB schema 分離、非同源，須人工保持一致（漂移風險列管）。
- 🔜 規劃中：drift-check CI、真 ERROR 阻斷（不被 benign 「already exists」淹沒）、套用前自動備份。
