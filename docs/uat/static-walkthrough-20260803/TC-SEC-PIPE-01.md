# TC-SEC-PIPE-01

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未觸發 GitHub Actions；另在 scratchpad 複本上實跑 drift-check 並注入探針） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `scripts/ci/migration-drift-check.py`、`.github/workflows/migration-drift-check.yml`、`scripts/db/apply-schema-routed.sh`、`SQL/migrations/MIGRATION_REGISTRY.md`、`SQL/migrations/*.sql`（125 支） |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準兩段。「CI 失敗阻斷」在 drift-check 腳本層可驗且本次以探針實測成立（注入未登記 migration → exit 1，見「逐層走查／步驟 3」）；但 GitHub Actions 的 job 只執行**檔案層**比對（`.github/workflows/migration-drift-check.yml:30-31`，未設任何 `POSTGRES_URI` / `TECH_POSTGRES_URI` / `PLATFORM_POSTGRES_URI`），而 TC 步驟指名的「registry 與 `schema_migrations` 不一致」屬 DB 真值對照段，該段在 CI 中不會執行（`scripts/ci/migration-drift-check.py:122-130` 的 opt-in 條件不成立）；`.github/workflows/migration-drift-check.yml:8` 亦自述「CI 此 job 僅跑檔案層」。DB 真值對照僅在 `scripts/db/apply-schema-routed.sh:160-168` 的套用後自我驗證中被呼叫。「套用時真 ERROR 不被 benign 警告淹沒」在 `scripts/db/apply-schema-routed.sh:150-151` 有對應實作（`grep -viE "already exists|does not exist, skipping"`），阻斷則由 `psql -v ON_ERROR_STOP=1` 與 `exit 1` 承擔（`:71`、`:123-132`）。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | CI 環境 |
| 步驟 | 注入 migration drift（registry 與 schema_migrations 不一致） |
| 預期結果（判定基準） | CI 失敗阻斷；套用時真 ERROR 不被 benign 警告淹沒 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-DAT-02、NFR-Sch-002 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:338`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 存在 migration drift 檢查 | `scripts/ci/migration-drift-check.py` | 一致 |
| 存在 CI workflow 觸發該檢查 | `.github/workflows/migration-drift-check.yml:20-31` | 一致 |
| 檔案層 drift（未登記 / 死列 / 重號）→ exit 1 | `scripts/ci/migration-drift-check.py:93-113`、`:132-136`；探針實測 exit 1 | 一致 |
| registry ↔ `schema_migrations` 對照的實作 | `scripts/ci/migration-drift-check.py:50-80`、`:115-130` | 一致 |
| 該對照在 CI 中執行 | `.github/workflows/migration-drift-check.yml:24-31` 未設任何 DB URI；`:8` 自述「CI 此 job 僅跑檔案層」 | 不一致 |
| DB 連線失敗 → 阻斷 | `scripts/ci/migration-drift-check.py:68-70`：印訊息後 `return errors`（空），不計為漂移 | 不一致 |
| `schema_migrations` 表不存在 → 阻斷 | `scripts/ci/migration-drift-check.py:62-64`：略過 | 不一致 |
| psycopg 不可用 → 阻斷 | `scripts/ci/migration-drift-check.py:55-58`：略過 | 不一致 |
| 編號缺口 → 阻斷 | `scripts/ci/migration-drift-check.py:99-103`：僅印 `ℹ️`，不計為錯 | 不一致（設計上為非阻斷，註解 `:101-102` 記載理由） |
| 套用失敗即中止 | `scripts/db/apply-schema-routed.sh:71`（`ON_ERROR_STOP=1`）、`:123-127`（`exit 1`） | 一致 |
| 記帳失敗即中止 | `scripts/db/apply-schema-routed.sh:128-132` | 一致 |
| 真 ERROR 不被 benign 警告淹沒 | `scripts/db/apply-schema-routed.sh:150-151` | 一致 |
| 套用後自我驗證含 DB 真值對照 | `scripts/db/apply-schema-routed.sh:160-168` | 一致 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 開發者 | push 未登記於 REGISTRY 的 migration | `CiBlocked` | 全數登記 | `scripts/ci/migration-drift-check.py:107-109`、`:132-136` | 印錯誤清單並 `return 1`（探針實測） |
| 開發者 | REGISTRY 留下已刪檔的死列 | `CiBlocked` | 無死列 | `scripts/ci/migration-drift-check.py:110-113` | 計為 error |
| 開發者 | 兩支同編號 migration | `CiBlocked` | 編號唯一 | `scripts/ci/migration-drift-check.py:93-95` | 計為 error |
| 開發者 | 編號跳號 | `CiBlocked` | 連續 | `scripts/ci/migration-drift-check.py:99-103` | 只印 `ℹ️`，不阻斷 |
| CI | 比對 registry ↔ `schema_migrations` | `DriftDetected` | DB 真值 | `.github/workflows/migration-drift-check.yml:24-31` | **不執行**：workflow 未提供任何 DB URI |
| 部署腳本 | 套用後自我驗證 | `DriftDetected` | 三庫對照 | `scripts/db/apply-schema-routed.sh:162-167` | 呼叫 drift-check（env 已帶三庫 URI），非 0 即 `exit 1` |
| 部署腳本 | 某支 migration 執行出錯 | `ApplyAborted` | `ON_ERROR_STOP` | `scripts/db/apply-schema-routed.sh:71`、`:123-127` | 不記帳、`exit 1` |
| 部署腳本 | 掃 log ERROR | `ErrorsSurfaced` | 過濾 benign | `scripts/db/apply-schema-routed.sh:151` | `grep -iE "^ERROR\|ERROR:" \| grep -viE "already exists\|does not exist, skipping"` |

---

## 逐層走查

### 步驟 1 — drift-check 的三段檢查與其阻斷性

`scripts/ci/migration-drift-check.py:1-19`：

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
多庫（LOCK-62）：`POSTGRES_URI`=品牌庫、`TECH_POSTGRES_URI`=技師庫、`PLATFORM_POSTGRES_URI`=平台庫。
migration 檔頭 `-- migrate-targets: brand|tech|platform`（未標＝brand）決定該檔應落哪些庫——
CI 依此對每個已設 URI 的庫各自對照，抓 089/090/035/105 類「該落技師庫卻沒套」漂移。
未設任何 URI 且無 --check-db 時完全略過 DB 段（保留純檔案層 CI 行為）。

退出碼 0=無漂移；1=偵測到漂移（CI block）。
"""
```

編號缺口的非阻斷處理在 `scripts/ci/migration-drift-check.py:97-103`：

```python
    # 連續性（允許歷史缺口——僅檢查「新增是否往後接續」以已知起點為基準）
    nums = sorted(int(v) for v in versions)
    if nums:
        gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
        # 已知歷史缺口（registry 註記 028-032/036-041 波次補登）不視為錯——僅報告
        if gaps:
            print(f"ℹ️  編號缺口（歷史波次，非阻斷）：{gaps}")
```

登記與死列檢查在 `scripts/ci/migration-drift-check.py:105-113`：

```python
    registry_text = REGISTRY.read_text(encoding="utf-8") if REGISTRY.exists() else ""
    # registry 登記與死列
    for ver, fn in versions.items():
        if f"`{fn}`" not in registry_text and fn not in registry_text:
            errors.append(f"migration 未登記於 REGISTRY：{fn}")
    for m in re.finditer(r"`(\d{3}-[\w-]+\.sql)`", registry_text):
        fn = m.group(1)
        if not (MIG_DIR / fn).exists():
            errors.append(f"REGISTRY 死列（檔案不存在）：{fn}")
```

退出碼在 `scripts/ci/migration-drift-check.py:132-138`：

```python
    if errors:
        print(f"❌ migration drift 偵測到 {len(errors)} 項：")
        for e in errors:
            print("  -", e)
        return 1
    print(f"✅ migration drift-check：{len(versions)} 支 migration 編號唯一、全數登記、無死列")
    return 0
```

### 步驟 2 — DB 真值對照段的觸發條件與略過路徑

`scripts/ci/migration-drift-check.py:115-130`：

```python
    # FR-DAT-02 + LOCK-62：opt-in 多庫 DB 真值對照（依 migrate-targets 分流）
    targets_by_ver = {ver: _targets_of(fn) for ver, fn in versions.items()}
    db_uris = {
        "brand": os.getenv("POSTGRES_URI", ""),
        "tech": os.getenv("TECH_POSTGRES_URI", ""),
        "platform": os.getenv("PLATFORM_POSTGRES_URI", ""),
    }
    any_uri = any(db_uris.values())
    if "--check-db" in sys.argv or any_uri:
        if not any_uri:
            print("ℹ️  --check-db 指定但無任何庫 URI（POSTGRES_URI/TECH_POSTGRES_URI/PLATFORM_POSTGRES_URI）→ 略過 DB 對照")
        for label, uri in db_uris.items():
            if not uri:
                continue
            expected = {ver: fn for ver, fn in versions.items() if label in targets_by_ver[ver]}
            errors.extend(_check_db_drift(label, uri, expected))
```

三條略過路徑在 `scripts/ci/migration-drift-check.py:50-70`：

```python
def _check_db_drift(label: str, uri: str, expected: dict[str, str]) -> list[str]:
    """比對「target 含本庫的檔案」↔ 本庫 public.schema_migrations（DB 真值）。
    connect/psycopg 不可用 → 回 [] 並印跳過訊息（不誤判為漂移）。expected: {ver: fn}。"""
    errors: list[str] = []
    try:
        import psycopg  # 延遲載入：純檔案層 CI 無此依賴也能跑
    except ImportError:
        print(f"ℹ️  psycopg 不可用 → 略過 {label} 庫 DB 真值對照")
        return errors
    try:
        with psycopg.connect(uri, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.schema_migrations') IS NOT NULL")
                if not cur.fetchone()[0]:
                    print(f"ℹ️  {label} 庫 schema_migrations 表不存在（未 baseline）→ 略過")
                    return errors
                cur.execute("SELECT version FROM public.schema_migrations")
                db_versions = {r[0] for r in cur.fetchall()}
    except Exception as e:  # noqa: BLE001
        print(f"ℹ️  {label} 庫連線失敗 → 略過 DB 真值對照（{type(e).__name__}）")
        return errors
```

兩類漂移的判定在 `scripts/ci/migration-drift-check.py:72-79`：

```python
    exp_versions = set(expected)
    for ver in sorted(exp_versions - db_versions):
        errors.append(f"[{label}] migration 該落本庫但 DB 未套用：{expected[ver]}")
    # 幽靈列：只比對真編號 marker 排除（000-baseline 等非 \d{3} 不算）
    for ver in sorted(v for v in (db_versions - exp_versions) if _VER_RE.match(v)):
        errors.append(f"[{label}] schema_migrations 幽靈列（DB 已套但無對應本庫檔案）：version={ver}")
```

### 步驟 3 — 探針：注入檔案層 drift

**此探針不在 repo 內**：將 `SQL/migrations/`（125 支）與 `scripts/ci/migration-drift-check.py` 複製到 scratchpad 的同構目錄後執行，repo 內原始碼與 SQL 未被修改。

基準（未注入）：

```
$ cd <scratchpad>/pipe_probe && python scripts/ci/migration-drift-check.py
ℹ️  編號缺口（歷史波次，非阻斷）：[11, 12, 13]
✅ migration drift-check：125 支 migration 編號唯一、全數登記、無死列
EXIT=0
```

注入一支未登記於 REGISTRY 的 migration（`999-probe-unregistered.sql`）後：

```
$ python scripts/ci/migration-drift-check.py
ℹ️  編號缺口（歷史波次，非阻斷）：[11, 12, 13, 128, 129, ... 998]
❌ migration drift 偵測到 1 項：
  - migration 未登記於 REGISTRY：999-probe-unregistered.sql
EXIT=1
```

### 步驟 4 — 探針：DB 真值對照

同一 scratchpad 複本，帶本機測試庫 URI 執行：

```
$ POSTGRES_URI=<本機測試庫> python scripts/ci/migration-drift-check.py
ℹ️  編號缺口（歷史波次，非阻斷）：[11, 12, 13]
❌ migration drift 偵測到 1 項：
  - [brand] schema_migrations 幽靈列（DB 已套但無對應本庫檔案）：version=121
EXIT=1
```

該筆的成因可由檔案本身讀出——`SQL/migrations/121-service-principal-credentials.sql:1`：

```sql
-- migrate-targets: platform
```

該支的 target 為 `platform`，故不在 `brand` 的 expected 集合內；本機測試庫（由 `scripts/db/make-test-db.sh` 建立的 scratch 庫）的 `schema_migrations` 中登記了 121。此為本機測試庫的狀態，非 repo 檔案狀態。

### 步驟 5 — CI workflow 的實際執行範圍

`.github/workflows/migration-drift-check.yml:1-31`：

```yaml
name: Migration Drift Check

# CR-0136 / WBS 1.6.1 / ADR-P012 G-10：SQL migration 檔案層守門——編號唯一、
# 全數登記 REGISTRY、無死列。純檔案層零 DB 依賴（CI 無 prod DB）。
# LOCK-62：drift-check 另支援**多庫 DB 真值對照**（依 migration 檔頭 migrate-targets
# 對品牌/技師/平台三庫各自比對 schema_migrations，抓「該落技師庫卻沒套」漂移）——
# opt-in，需 POSTGRES_URI/TECH_POSTGRES_URI/PLATFORM_POSTGRES_URI；由 apply-schema-routed.sh
# 套用後自我驗證，或部署 gate 帶 secrets 執行。CI 此 job 僅跑檔案層。
on:
  push:
    branches: [dev, main, dev-ding]
    paths:
      - 'SQL/migrations/**'
      - 'scripts/ci/migration-drift-check.py'
      - '.github/workflows/migration-drift-check.yml'
  pull_request:
    paths:
      - 'SQL/migrations/**'

jobs:
  drift-check:
    name: Migration 檔案層漂移守門
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Run migration drift-check
        run: python scripts/ci/migration-drift-check.py
```

該 step 無 `env:` 區塊，亦無 `--check-db` 參數。

TC 步驟寫「注入 migration drift（registry 與 schema_migrations 不一致）」並期望「CI 失敗阻斷」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:338`）／CI job 只跑檔案層，`schema_migrations` 對照段因無 DB URI 而不執行（`.github/workflows/migration-drift-check.yml:8`、`scripts/ci/migration-drift-check.py:122-130`）。此處僅並陳，不裁定。

### 步驟 6 — 套用時的錯誤處理

`scripts/db/apply-schema-routed.sh:70-72`：

```bash
apply_file() {  # $1=uri $2=file
    psql "$1" -v ON_ERROR_STOP=1 -f "$2" >> "${LOG_FILE}" 2>&1
}
```

`scripts/db/apply-schema-routed.sh:122-133`：

```bash
        if [[ "${DRY_RUN}" -eq 0 ]]; then
            if ! apply_file "$u" "$f"; then
                echo "FAIL: target=${t} migration=${base} 套用失敗；未登記 schema_migrations"
                echo "log: ${LOG_FILE}"
                exit 1
            fi
            if ! record "$u" "$ver" "$base"; then
                echo "FAIL: target=${t} migration=${base} 套用成功但記帳失敗"
                echo "log: ${LOG_FILE}"
                exit 1
            fi
            APPLIED_COUNT=$((APPLIED_COUNT + 1))
        fi
```

benign 過濾在 `scripts/db/apply-schema-routed.sh:149-152`：

```bash
    echo "== 掃 log ERROR（忽略 already exists）=="
    grep -iE "^ERROR|ERROR:" "${LOG_FILE}" | grep -viE "already exists|does not exist, skipping" | head -40 || true
    echo "log: ${LOG_FILE}"
```

該行末的 `|| true` 使此段不改變腳本退出碼；阻斷由前述 `exit 1` 路徑承擔。

log 檔預建的理由記在 `scripts/db/apply-schema-routed.sh:66-68`：

```bash
# 先建檔：全數跳過時沒有任何 psql 輸出重導進來，後面掃 ERROR 的 grep 會噴
# "No such file or directory" 而看起來像失敗。
: > "${LOG_FILE}"
```

### 步驟 7 — 套用後的自我驗證

`scripts/db/apply-schema-routed.sh:160-168`：

```bash
if [[ "${DRY_RUN}" -eq 0 ]]; then
    echo ""
    echo "== 自我驗證：多庫 migration drift-check（依 migrate-targets 對三庫比對）=="
    # POSTGRES_URI/TECH_POSTGRES_URI/PLATFORM_POSTGRES_URI 已在 env → 直接對照各庫
    if ! python3 "${PROJECT_ROOT}/scripts/ci/migration-drift-check.py"; then
        echo "FAIL: drift-check 報漂移；本次 migration 發布證據不得標記成功"
        exit 1
    fi
fi
```

未設 URI 的 target 於 `scripts/db/apply-schema-routed.sh:154-158` 只印 WARN，不影響退出碼：

```bash
for t in brand tech platform; do
    case "${SKIPPED_TARGETS}" in
        *"|$t|"*) echo "WARN: target=$t 有 migration 但 URI 未設，未套用該庫";;
    esac
done
```

---

## 既有測試證據

`api/tests/` 中無針對 `scripts/ci/migration-drift-check.py` 的 pytest；其驗證方式為 CI workflow 直接執行腳本（`.github/workflows/migration-drift-check.yml:30-31`）。

repo 原地執行（未注入）：

```
$ python scripts/ci/migration-drift-check.py
ℹ️  編號缺口（歷史波次，非阻斷）：[11, 12, 13]
✅ migration drift-check：125 支 migration 編號唯一、全數登記、無死列
```

`SQL/migrations/MIGRATION_REGISTRY.md` 為登記表，例如 `:156` 對 103 的登記行。

---

## 事實結論

1. drift-check 腳本有五類檢查：編號唯一、編號連續、REGISTRY 登記、REGISTRY 死列、DB 真值對照（未套用／幽靈列），前四類為檔案層（`scripts/ci/migration-drift-check.py:87-113`），第五類為 opt-in（`:115-130`）。
2. 編號缺口只印 `ℹ️` 不阻斷（`scripts/ci/migration-drift-check.py:99-103`）；其餘四類計入 `errors` 並使腳本 `return 1`（`:132-136`）。
3. GitHub Actions 的 job 執行 `python scripts/ci/migration-drift-check.py` 且未提供任何 DB URI 與 `--check-db`（`.github/workflows/migration-drift-check.yml:24-31`），workflow 註解自述「CI 此 job 僅跑檔案層」（`:8`）。
4. DB 真值對照在 psycopg 不可用、連線失敗、或 `schema_migrations` 表不存在時皆印訊息後回空 error 清單（`scripts/ci/migration-drift-check.py:55-70`）。
5. 探針實測（scratchpad 複本，**不在 repo 內**）：注入未登記 migration → exit 1；帶本機測試庫 URI 執行 → 偵測到幽靈列 version=121 並 exit 1。121 的 `migrate-targets` 為 `platform`（`SQL/migrations/121-service-principal-credentials.sql:1`）。
6. 套用腳本以 `psql -v ON_ERROR_STOP=1` 執行每支 migration，失敗即 `exit 1` 且不記帳（`scripts/db/apply-schema-routed.sh:71`、`:123-127`）；記帳失敗亦 `exit 1`（`:128-132`）。
7. 套用後掃 log 時過濾 `already exists` 與 `does not exist, skipping` 兩類 benign 訊息（`scripts/db/apply-schema-routed.sh:151`）；該行帶 `|| true`，不影響退出碼。
8. 套用腳本結尾呼叫 drift-check 作為自我驗證，非 0 即 `exit 1`（`scripts/db/apply-schema-routed.sh:162-167`）；此時三庫 URI 已在 env，DB 真值對照段會執行。
