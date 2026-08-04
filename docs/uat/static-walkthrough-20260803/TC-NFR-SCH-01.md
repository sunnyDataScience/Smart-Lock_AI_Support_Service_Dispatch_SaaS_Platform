# TC-NFR-SCH-01 — migrations 可重套、drift 被擋、forward-only

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 + 本機測試庫實跑（重套探針與 drift-check） |
| 走查基準 | commit `2cfeca92` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |

判定理由（事實）：TC 判定基準四項中，「migrations 可重套」有落點且實跑驗證（125 支 migration 全數帶 `IF NOT EXISTS` 或等效冪等寫法，抽 4 支對測試庫各套兩次皆 exit 0，步驟 3）；「drift 被擋」有專屬 CI 腳本且實跑偵測到一項漂移並回 exit 1（步驟 4）；「只允許 forward 演進」在檔案層可觀測（`SQL/migrations/` 無任何 down/rollback 檔，步驟 5）——但該約束為檔案慣例，repo 內無阻止 down migration 的程式化 gate。「備份/還原證據可回查」在 repo 內僅有一支一次性還原腳本與 apply 腳本的註解式提醒，無備份紀錄或證據帳本（步驟 6）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 13. 追溯缺口收斂案例（TC-AGT / TC-NFR / TC-UAT） |
| 前置 | 空庫、升級庫、已套 migration 與 drift fixture |
| 步驟 | 逐庫套用、重套、注入 schema drift、嘗試 down migration |
| 預期結果（判定基準） | migrations 可重套、drift 被擋、只允許 forward 演進；備份/還原證據可回查 |
| 路徑類型 | failure＋recovery |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | NFR-Sch-001、NFR-Sch-003 |
| 屬於哪條旅程腳本 | — |

需求原文（`smartlock-docs/enterprise/05_NFR.md:181`、`:183`）：

```
| NFR-Sch-001 | Migration 可重套 | 100% idempotent（`ADD COLUMN IF NOT EXISTS` 等）| 重套測試 | 營運目標 |
| NFR-Sch-003 | 演進策略 | forward-only（無 down migration）；破壞性變更走新 migration + 備份還原 | 流程稽核 | 營運目標 |
```

同段 `:182`（NFR-Sch-002，本 TC 未列但為 drift 判定的正典依據）：「套用真相可查｜`schema_migrations` 表為唯一真相；registry drift CI 告警（🔜 規劃中）」。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| migration 全數冪等 | 掃描結果見步驟 2（125 支，0 支缺 `IF NOT EXISTS`） | 有落點 |
| 重套不失敗（實跑） | 步驟 3（抽 4 支各套 2 次） | 有落點 |
| 套用真相落 DB | `SQL/migrations/046-schema-migrations-tracking.sql:14-19` | 有落點 |
| 逐庫套用（分流） | `scripts/db/apply-schema-routed.sh:9-11`、`:55-61` | 有落點 |
| 套用後記帳 | `scripts/db/apply-schema-routed.sh:91-93`、`scripts/db/apply-schema-prod.sh:72-78` | 有落點 |
| drift 偵測（檔案層） | `scripts/ci/migration-drift-check.py:83-113` | 有落點 |
| drift 偵測（DB 真值層） | `scripts/ci/migration-drift-check.py:50-80`、`:115-130` | 有落點 |
| drift 被擋（exit 1） | `scripts/ci/migration-drift-check.py:132-136` | 有落點；實跑回 1（步驟 4） |
| 無 down migration | `SQL/migrations/` 檔名掃描（步驟 5） | 有落點（檔案層） |
| 阻止 down migration 的 gate | — | **無對應**（步驟 5） |
| 備份/還原證據可回查 | `scripts/db/apply-schema-prod.sh:27`（註解）、`scripts/ops/opsday-20260802-restore-from-cost-shutdown.sh` | **部分**（步驟 6） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 部署者 | 對空庫套用全部 schema | `SchemaApplied` | 固定順序 | `scripts/db/apply-schema-prod.sh:57-67` | Schema.sql → Schema_*.sql → platform → migrations 編號序 |
| 部署者 | 對已套庫重套 | `SchemaApplied(no-op)` | 冪等 | 各 migration 的 `IF NOT EXISTS` | 實跑 4 支×2 次皆 exit 0 |
| 部署者 | 逐庫套用 | `SchemaApplied(per target)` | `-- migrate-targets:` 分流 | `scripts/db/apply-schema-routed.sh:55-61` | 讀檔頭決定落哪些庫 |
| 系統 | 套用成功後記帳 | `MigrationRecorded` | `schema_migrations` 為唯一真相 | `scripts/db/apply-schema-routed.sh:91-93` | `INSERT ... ON CONFLICT DO NOTHING` |
| CI | 跑 drift-check | `DriftDetected(exit 1)` | 編號唯一／全登記／無死列／DB 真值一致 | `scripts/ci/migration-drift-check.py:83-138` | 實跑偵測 1 項（幽靈列 121） |
| 開發者 | 嘗試 down migration | `Rejected` | forward-only | — | **找不到**：無程式化 gate；`SQL/migrations/` 無 down 檔 |
| 營運 | 查備份/還原證據 | `BackupEvidenceRetrieved` | 破壞性變更走備份還原 | — | **找不到**：無備份紀錄表／清單；只有註解提醒與一支一次性腳本 |

---

## 逐層走查

### 步驟 1 — 套用腳本：單庫與多庫

單庫 `scripts/db/apply-schema-prod.sh:2-27`（檔頭）：

```
#   把完整 schema（Schema.sql + Schema_*.sql + migrations/*.sql）依正規順序
#   套用到**單一目標 DB**。全部 idempotent（ADD COLUMN IF NOT EXISTS 等），已存在的略過。
#   **不灌 demo seed**（prod 只補 schema，不動業務資料）。
#
#   ⚠️ 多庫（品牌/技師/平台）分流請改用 apply-schema-routed.sh（LOCK-62 item 2）——
#      本單庫腳本把所有 migration 套同一庫，是 0724/0725「該落技師庫卻只套品牌庫」地雷
#      的根源。routed 版讀 migration 檔頭 `-- migrate-targets:` 分流並逐庫記帳。
...
# 安全：執行前請先建 Cloud SQL 備份（gcloud sql backups create --instance=lock-ai）。
```

錯誤處理策略 `scripts/db/apply-schema-prod.sh:43-52`：

```bash
# ON_ERROR_STOP=0：idempotent 重跑時容忍 benign 警告（already exists）；
# 真正錯誤會留在 log，結尾用 grep 攔出來人工確認。
apply() {
    local f="$1"
    [[ -f "$f" ]] || return 0
    echo "  → ${f}"
    echo "===== ${f} =====" >> "${LOG_FILE}"
    psql "${POSTGRES_URI}" -v ON_ERROR_STOP=0 -f "$f" >> "${LOG_FILE}" 2>&1
}
```

多庫 `scripts/db/apply-schema-routed.sh:9-11`：

```
#   -- migrate-targets: brand            → 只套品牌庫（預設；未標注 = brand，向下相容）
#   -- migrate-targets: tech             → 只套技師庫
#   -- migrate-targets: brand,tech,platform  → 三庫都套（如動 users 這種各庫皆有的表）
```

routed 版使用 `ON_ERROR_STOP=1`（`scripts/db/apply-schema-routed.sh:71`、`:91`），與單庫版不同；已登記版本預設跳過（`:22`、`:73`、`:87`）。

記帳語句 `scripts/db/apply-schema-routed.sh:91-93`：

```bash
    psql "$1" -v ON_ERROR_STOP=1 -c \
        "CREATE TABLE IF NOT EXISTS public.schema_migrations(version TEXT PRIMARY KEY, filename TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now(), note TEXT);
         INSERT INTO public.schema_migrations(version,filename,note) VALUES ('$2','$3','applied') ON CONFLICT (version) DO NOTHING;" \
```

套用失敗時不記帳，`scripts/db/apply-schema-routed.sh:124`：

```bash
                echo "FAIL: target=${t} migration=${base} 套用失敗；未登記 schema_migrations"
```

### 步驟 2 — 冪等性靜態掃描

以「含 `CREATE TABLE|INDEX|UNIQUE INDEX|SCHEMA` 但整檔無 `IF NOT EXISTS`」為條件掃 `SQL/migrations/*.sql`：

```
for f in SQL/migrations/*.sql; do
  if grep -qiE "CREATE (TABLE|INDEX|UNIQUE INDEX|SCHEMA)" "$f" && ! grep -qi "IF NOT EXISTS" "$f"; then echo "$f"; fi
done
count=0
```

零命中。含 `DROP TABLE` / `DROP COLUMN` 的 migration 僅 2 支：

```
git grep -ln "DROP TABLE\|DROP COLUMN" -- SQL/migrations
SQL/migrations/034-role-permissions-tenant-id.sql
SQL/migrations/093-pc-dual-gate.sql
```

trigger 的冪等寫法為 `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER`，例 `SQL/migrations/113-purge-audit-ledger.sql:48-51`：

```sql
DROP TRIGGER IF EXISTS trg_purge_audit_append_only ON saas.purge_audit;
CREATE TRIGGER trg_purge_audit_append_only
    BEFORE UPDATE OR DELETE ON saas.purge_audit
    FOR EACH ROW EXECUTE FUNCTION saas.purge_audit_immutable();
```

函式為 `CREATE OR REPLACE FUNCTION`（`113-purge-audit-ledger.sql:41`、`100-audit-events-append-only.sql:21`）。

`MIGRATION_REGISTRY.md` 對各支 migration 標註冪等狀態，例 `SQL/migrations/MIGRATION_REGISTRY.md:174`：

```
| 113 | `113-purge-audit-ledger.sql` | NFR-Priv-008 / FR-API-16 | 🟢 idempotent（CREATE TABLE/INDEX IF NOT EXISTS + CREATE OR REPLACE FUNCTION + DROP/CREATE TRIGGER，拋棄式 PG16 驗證 2026-07-21） | ...
```

### 步驟 3 — 重套實跑（本機測試庫）

對本機測試庫（`smartlock-test-db`，PostgreSQL 17.10）抽 4 支 migration 各套兩次，`ON_ERROR_STOP=1`：

```
for i in 1 2; do
  docker exec -i -e PGPASSWORD=0000 smartlock-test-db \
    psql -U lock -d lock_scratch_test -v ON_ERROR_STOP=1 -q -f - < SQL/migrations/113-purge-audit-ledger.sql
done
--- pass 1 ---
psql:<stdin>:31: NOTICE:  relation "purge_audit" already exists, skipping
psql:<stdin>:33: NOTICE:  relation "idx_purge_audit_subject" already exists, skipping
psql:<stdin>:34: NOTICE:  relation "idx_purge_audit_request" already exists, skipping
exit=0
--- pass 2 ---
（同上三則 NOTICE）
exit=0
```

其餘三支：

```
=== SQL/migrations/066-media-legal-hold.sql x2 ===
pass1 exit=0
pass2 exit=0
=== SQL/migrations/100-audit-events-append-only.sql x2 ===
pass1 exit=0
pass2 exit=0
=== SQL/migrations/046-schema-migrations-tracking.sql x2 ===
pass1 exit=0
pass2 exit=0
```

四支涵蓋 `CREATE TABLE IF NOT EXISTS`+index+trigger（113）、`ADD COLUMN IF NOT EXISTS`+COMMENT（066）、`CREATE OR REPLACE FUNCTION`+`DROP/CREATE TRIGGER`（100）、`CREATE TABLE IF NOT EXISTS`+COMMENT（046）四種寫法。

### 步驟 4 — drift 偵測

`scripts/ci/migration-drift-check.py:1-18`（檔頭）：

```python
"""Migration drift-check（CR-0136 / WBS 1.6.1 / ADR-P012 G-10 / FR-DAT-02）。

CI 檔案層守門（預設，零 DB 依賴）：
  1. 編號連續且唯一（無跳號/重號——跳號＝合併遺漏、重號＝衝突未解）。
  2. 每支 SQL migration 在 MIGRATION_REGISTRY.md 有登記（新增未登記＝audit 斷鏈）。
  3. registry 無指向不存在檔案的死列（檔案已刪但 registry 殘留）。

DB 真值對照（FR-DAT-02 補洞 + LOCK-62 多庫，opt-in）：設對應庫 URI 時額外比對
`SQL/migrations/*.sql`（檔案真相，依 `-- migrate-targets:` 分流）↔ 各庫
`public.schema_migrations`（DB 已套真值）：
  4. 檔案（target 含該庫）存在但該庫 schema_migrations 無列＝**未套用**（部署漏跑）。
  5. 該庫 schema_migrations 有編號列但檔案不存在＝**幽靈列**（migration 被刪但 DB 已套）。
...
退出碼 0=無漂移；1=偵測到漂移（CI block）。
"""
```

兩類 DB 漂移的判定 `scripts/ci/migration-drift-check.py:72-77`：

```python
    exp_versions = set(expected)
    for ver in sorted(exp_versions - db_versions):
        errors.append(f"[{label}] migration 該落本庫但 DB 未套用：{expected[ver]}")
    # 幽靈列：只比對真編號 marker 排除（000-baseline 等非 \d{3} 不算）
    for ver in sorted(v for v in (db_versions - exp_versions) if _VER_RE.match(v)):
        errors.append(f"[{label}] schema_migrations 幽靈列（DB 已套但無對應本庫檔案）：version={ver}")
```

**實跑（純檔案層，無 DB URI）**：

```
python scripts/ci/migration-drift-check.py
ℹ️  編號缺口（歷史波次，非阻斷）：[11, 12, 13]
✅ migration drift-check：125 支 migration 編號唯一、全數登記、無死列
（exit 0）
```

**實跑（接本機測試庫）**：

```
POSTGRES_URI=<本機測試庫> python scripts/ci/migration-drift-check.py
ℹ️  編號缺口（歷史波次，非阻斷）：[11, 12, 13]
❌ migration drift 偵測到 1 項：
  - [brand] schema_migrations 幽靈列（DB 已套但無對應本庫檔案）：version=121
（exit 1）
```

該筆漂移的成因：`SQL/migrations/121-service-principal-credentials.sql:1` 的檔頭為

```
-- migrate-targets: platform
```

即該支的目標庫是平台庫，但本機測試庫（以 brand 身分連線）的 `schema_migrations` 有 `version=121` 的列——腳本依 `_targets_of()`（`:36-47`）判定該檔不屬 brand 期望集，故列為幽靈列並以 exit 1 阻斷。

`scripts/db/apply-schema-routed.sh:162` 於套用結束後自呼此檢查：

```bash
    echo "== 自我驗證：多庫 migration drift-check（依 migrate-targets 對三庫比對）=="
```

### 步驟 5 — forward-only 與 down migration

`SQL/migrations/` 內無任何 down/rollback 檔：

```
ls SQL/migrations | grep -i "down\|rollback"
（無輸出）
```

檔名格式由 drift-check 強制，`scripts/ci/migration-drift-check.py:31`：

```python
_FNAME_RE = re.compile(r"^(\d{3})-[\w-]+\.sql$")
```

不符者列為錯誤（`:88-91`）：

```python
        m = _FNAME_RE.match(fn)
        if not m:
            errors.append(f"檔名不符 NNN-slug.sql 慣例：{fn}")
            continue
```

該 regex 不排斥名為 `128-rollback-xxx.sql` 的檔案——它只約束編號前綴與 slug 字元集，不含語意判斷。`schema_migrations` 表（`SQL/migrations/046-schema-migrations-tracking.sql:14-19`）亦無「已回滾」狀態欄：

```sql
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version     TEXT PRIMARY KEY,              -- migration 編號前綴，如 '045'
    filename    TEXT NOT NULL,                 -- 完整檔名，如 '045-technician-payout-rule.sql'
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    note        TEXT                           -- 'baseline'（建表前回填）/ 'applied' / 人工備註
);
```

TC 步驟寫「嘗試 down migration」、判定基準寫「只允許 forward 演進」（出處：批次 A TC 原文第 119-120 行）／程式碼中無阻止 down migration 的執行期或 CI gate；forward-only 由「目錄內無 down 檔」與 NFR-Sch-003 的流程規範共同體現。此處僅並陳，不裁定。

### 步驟 6 — 備份／還原證據

repo 內與備份還原相關的檔案：

```
find scripts -iname "*backup*" -o -iname "*restore*"
scripts/ops/opsday-20260802-restore-from-cost-shutdown.sh
```

`scripts/db/apply-schema-prod.sh:27` 以註解要求人工先建備份：

```
# 安全：執行前請先建 Cloud SQL 備份（gcloud sql backups create --instance=lock-ai）。
```

`scripts/db/apply-schema-prod.sh:39-42` 產生套用 log：

```bash
LOG_DIR="${PROJECT_ROOT}/.dev-logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/apply-schema-prod-$(date +%Y%m%d-%H%M%S).log"
echo "套用 log → ${LOG_FILE}"
```

`.dev-logs/` 為本機目錄。repo 內無備份紀錄表、備份清單檔或備份證據帳本。

TC 判定基準寫「備份/還原證據可回查」（出處：批次 A TC 原文第 120 行）／repo 內可回查的是 migration 套用記帳（`public.schema_migrations`）與本機套用 log；備份本身為 `gcloud sql backups create` 的人工步驟，還原有一支一次性腳本。此處僅並陳，不裁定。

### 步驟 7 — 套用真相的唯一來源

`SQL/migrations/046-schema-migrations-tracking.sql:2-12`（檔頭）記錄該表的引入原因：

```
-- CR-0038 階段0：建立 migration 套用追蹤表，根治「registry 標記 ≠ 各環境實際套用」雙向漂移。
--
-- 背景（2026-06-19 對抗式盤點 CR-0038 發現）：
--   MIGRATION_REGISTRY.md 把 035/045 標 🟢 idempotent，但 dev DB 實際無此兩表
--   （test_password_reset / test_cr_0037 直接 UndefinedTable FAIL）；
--   反之 017-027 標 🟡 pending 卻早已套用。registry 是人工維護的「意圖」，非「事實」。
--   本表讓 apply 腳本（scripts/db/apply-schema-prod.sh）每套一支即留痕，
--   `SELECT version FROM schema_migrations` 才是各環境的真實狀態。
```

---

## 既有測試證據

本 TC 的驗證方式為腳本實跑，非 pytest。三次實跑結果已記於步驟 3（重套 4 支×2 次，皆 exit 0）與步驟 4（drift-check 檔案層 exit 0、接 DB 後 exit 1 偵測到幽靈列）。

`api/tests/` 中無測試檔涵蓋 migration 重套或 drift 偵測（`ls api/tests | grep -i "migration\|schema"` 零命中）。

重套探針以 `docker exec` 對測試容器執行，未修改 repo 內任何檔案。

---

## 事實結論

1. `SQL/migrations/` 共 125 支，全數帶 `IF NOT EXISTS` 或等效冪等寫法；以掃描條件檢出的非冪等 DDL 為 0 支。
2. 抽 4 支涵蓋 4 種 DDL 寫法的 migration 對測試庫各套兩次，`ON_ERROR_STOP=1` 下皆 exit 0，重複套用只產生 `already exists, skipping` 的 NOTICE。
3. `public.schema_migrations` 為套用真相表，由兩支 apply 腳本以 `INSERT ... ON CONFLICT DO NOTHING` 記帳；routed 版於套用失敗時不記帳。
4. 多庫分流以 migration 檔頭 `-- migrate-targets:` 決定，未標註者預設 brand。
5. drift-check 有 5 類檢查（3 類檔案層、2 類 DB 真值層），偵測到漂移回 exit 1；接本機測試庫實跑偵測到 1 項幽靈列（version=121，該檔 target 為 platform）。
6. 兩支 apply 腳本的錯誤處理不同：單庫版 `ON_ERROR_STOP=0`（容忍 benign 警告、事後 grep），routed 版 `ON_ERROR_STOP=1`。
7. `SQL/migrations/` 無 down/rollback 檔；檔名 regex 只約束編號與 slug 字元集，`schema_migrations` 表無回滾狀態欄，無程式化的 down migration 阻擋。
8. 備份為 apply 腳本註解中的人工前置步驟；repo 內有一支一次性還原腳本，無備份證據帳本或紀錄表。
