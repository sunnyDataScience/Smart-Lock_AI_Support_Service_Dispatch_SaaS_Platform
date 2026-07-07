# ADR-002: 純 SQL forward-only migration（不用 Alembic）

**狀態：** 已接受（運作中；代價：無回滾、狀態靠人工 registry，見 §4）| **日期：** 2026-07-07（回溯記錄現況）

> ⚠️ 本 ADR 回溯記錄既有 migration 策略，並**誠實記載其代價**：forward-only 無回滾、registry「意圖非事實」雙向漂移、多庫手動套用一致性靠人工。

---

## 1. 背景與問題

Smart Lock 平台的 DB schema 龐大（~100 表跨 `public`/`saas`/`agent` 三 namespace）且**高速演進**（87 個 migration，從 000 到 089）。開發模式有兩個特徵放大了 migration 工具的選型壓力：

- **平行 worktree 開發**：多個功能分支同時開 migration，容易撞編號。
- **多庫部署**：品牌庫（一品牌一庫，×N）+ 技師庫 + 平台庫，同一 migration 需套到多個實例。
- **無 ORM 綁定**：api 用 psycopg3 raw SQL（非 SQLAlchemy ORM），沒有 ORM model 可供 Alembic autogenerate。

**問題核心**：在「無 ORM、平行開發、多庫部署」的條件下，如何管理 schema 演進，使其可重跑、可認領編號、套用狀態可查，且不引入 ORM 版本鏈的複雜度？

---

## 2. 考量的選項

### 選項 A：純 SQL 檔 + forward-only + idempotent（現行）

| 面向 | 評估 |
|---|---|
| **ORM 依賴** | 無；`psql -f` 直接套，與 psycopg3 raw SQL 一致 |
| **平行開發** | 靠 `MIGRATION_REGISTRY.md` 認領編號防撞號 |
| **可重跑** | idempotent（`ADD COLUMN IF NOT EXISTS` / `DO $$ 查 pg_constraint $$` / `ON CONFLICT`）|
| **多庫套用** | `psql -f` 對每庫跑，透明 |
| **缺點** | **無 down migration（不可逆）**；套用狀態需自建 `schema_migrations` 追蹤；狀態靠人工 registry 易漂移 |

### 選項 B：Alembic（SQLAlchemy migration）

| 面向 | 評估 |
|---|---|
| **ORM 依賴** | 需 SQLAlchemy model；但 api 是 raw SQL，無 model 可 autogenerate |
| **回滾** | 有 down migration（`downgrade()`）|
| **版本鏈** | 線性 revision 鏈，自動追蹤 head |
| **缺點** | 為無 ORM 的專案硬引入 SQLAlchemy 依賴；平行分支的 revision 鏈易衝突（需 merge revision）；raw SQL 手寫 upgrade/downgrade 反而更繁瑣 |

### 選項 C：Flyway / Liquibase（獨立 migration 工具）

| 面向 | 評估 |
|---|---|
| **ORM 依賴** | 無 |
| **回滾** | Liquibase 有 rollback；Flyway 社群版無 |
| **缺點** | 引入 JVM / 額外工具鏈；與 Python + `uv` + `psql` 的既有工具鏈不一致；學習成本 |

---

## 3. 決策

**選擇：選項 A — 純 SQL 檔 + forward-only + idempotent**

核心理由是「**與既有工具鏈一致（psql + raw SQL），且 idempotent 補足了可重跑需求**」：

- **命名**：`NNN-domain-feature.sql`（三位數編號 + kebab 描述）。
- **認領**：平行 worktree 開發前**先在 `MIGRATION_REGISTRY.md` 認領編號**再開檔（`MIGRATION_REGISTRY.md:2`）。
- **冪等**：靠 `ADD COLUMN IF NOT EXISTS`、`DO $$ 查 pg_constraint 是否存在 $$`、`ON CONFLICT DO NOTHING` 達成可安全重套。
- **套用順序**（`apply-schema-prod.sh:47-57`）：`Schema.sql` → `Schema_*.sql`（字母序）→ `migrations/*.sql`（編號序）→ 回填 `schema_migrations`。
- **真相源**：`public.schema_migrations` 表（046 建）為「是否已套用」唯一真相。

**主要 tradeoffs（明確接受的代價）：**
- **放棄回滾能力**：無 down migration。一旦套錯，只能寫新 migration 修正（forward-fix），不能 `downgrade`。
- **狀態追蹤靠自建**：`schema_migrations` 046 才建，之前歷史事後回填。
- **registry 是人工「意圖」**：狀態欄不保證與各環境實況一致。

---

## 4. 後果

### 正面收益

- **工具鏈一致**：`psql -f` 套用，無 ORM/JVM 依賴，與 api raw SQL 風格統一。
- **可重跑**：idempotent 設計讓同一 migration 可對多庫、多環境安全重套。
- **平行友善**：編號認領機制讓多 worktree 並行開發不撞號。

### ⚠️ 負面現況（誠實記錄）

- **無回滾**：forward-only 不可逆；套錯只能 forward-fix。生產套用前依賴**手動** Cloud SQL 備份（`apply-schema-prod.sh` 僅提醒 `gcloud sql backups create`，非自動）。
- **registry 雙向漂移**（`MIGRATION_REGISTRY.md:7-15`）：狀態欄「意圖非事實」。已確認漂移：
  - **035/045** 標 🟢 idempotent 但 dev **未套** → 測試 `UndefinedTable` FAIL（已補套）。
  - **017-027** 標 🟡 pending 但 dev **已存在**。
  - 語意易混：🟢 idempotent =「設計可安全重套」**≠「已套用」**。
- **046 前歷史不可考**：`schema_migrations` 046 才建，之前套用時間點多為事後回填。
- **`ON_ERROR_STOP=0` 容錯淹沒真錯**：容忍 benign「already exists」，靠**結尾 grep 攔真 ERROR**；真 ERROR 可能混在大量 benign 警告中被淹沒。
- **多庫手動套用擴散**：品牌×N + 技師 + 平台手動套用，一致性靠人工，無自動 drift CI。

### 影響範圍

- `SQL/migrations/*.sql`（87 檔）+ `MIGRATION_REGISTRY.md`
- `scripts/db/{apply-schema-prod,init-platform-db,split-tech-db}.sh`
- `public.schema_migrations`（真相源）
- 三庫套用一致性（P2/06 §5、P3/13 D-02）

### 重新評估觸發條件

- migration 數量或多庫實例數成長到人工 registry 不可維護 → 評估自建 migration runner（讀 `schema_migrations` 自動決定待套清單）。
- 若引入 ORM → 重估 Alembic。
- 頻繁需要回滾 → 評估在關鍵 migration 手寫配套 `down-NNN.sql`。

---

## 5. 執行計畫（現況 + 補強）

**現況（已落地）：**
1. `NNN-domain-feature.sql` 命名 + registry 認領。
2. idempotent 設計（`IF NOT EXISTS` / `pg_constraint` 查存在）。
3. `apply-schema-prod.sh` 套用順序 + `schema_migrations` 回填。

**補強（待實作，見 P3/13 DA-03、P4/08 §6 建議二）：**
1. **Migration drift CI**：CI 比對 `MIGRATION_REGISTRY.md` / `migrations/` 目錄 vs 各環境 `schema_migrations`，drift 告警。
2. **真 ERROR 阻斷**：改善 `apply-schema-prod.sh`，真 ERROR 不被 benign 淹沒（非只結尾 grep）。
3. **自動備份前置**：套用前自動建 Cloud SQL 備份（非僅提醒）。
4. **多庫套用統一**：三庫套用腳本統一入口 + `--verify` 對帳。

---

## 6. 選用影響區段

> 本決策改變資料模型演進方式與部署流程，填 6.2 / 6.6；效能未實質改變，略。

### 6.2 資料模型影響

- **migration 契約**（P2/06 §3）：`NNN-*.sql` 命名 + registry 認領 + `schema_migrations` 真相源。
- **無版本鏈**：不像 Alembic 有線性 revision head；靠編號序 + idempotent。
- **回滾策略**：無 down migration；forward-fix 為唯一補救。
- **同步更新**：P2/06 §3、P3/13 C-03/D-01/D-02、P4/08 §3.2。

### 6.6 部署影響

- **基礎設施**：prod 套用經 cloud-sql-proxy；三庫（品牌×N/技師/平台）各自 `psql -f`。
- **風險連動**：`TECH_POSTGRES_URI` 漏設靜默退回單庫（P3/13 D-02b）；無自動備份（P3/13 D-01）。
- **同步更新**：`00_platform/P2/09 §6 R-05`、P3/13 §D、P4/08 §6 建議二/四。
