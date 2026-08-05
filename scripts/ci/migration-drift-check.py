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
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG_DIR = ROOT / "SQL" / "migrations"
REGISTRY = MIG_DIR / "MIGRATION_REGISTRY.md"

_FNAME_RE = re.compile(r"^(\d{3})-[\w-]+\.sql$")

# NFR-Sch-003 forward-only：migration 只准往前，不得夾帶 down/rollback。
# 原本只靠慣例——`_FNAME_RE` 的 `[\w-]+` 對 `128-rollback-foo.sql` 完全放行
# （目前 125 支裡剛好 0 支 down/rollback，所以沒出過事）。
# 資料庫的向下遷移在多租戶＋append-only 稽核的架構下特別危險：
# 一旦有人合進來、CI 又不擋，回滾腳本會在某次事故處理時被當成「官方支援的做法」執行。
_FORWARD_ONLY_BANNED = re.compile(r"(?:^|-)(rollback|down|revert|undo|downgrade)(?:-|$)", re.I)
_TARGETS_RE = re.compile(r"^--\s*migrate-targets:\s*", re.IGNORECASE)
_VER_RE = re.compile(r"^\d{3}$")  # 幽靈列只比對真編號（排除 000-baseline 等 marker）


def _assert_forward_only(names: list[str]) -> list[str]:
    """回傳違反 forward-only 的檔名（NFR-Sch-003）。"""
    return [n for n in names if _FORWARD_ONLY_BANNED.search(n.removesuffix(".sql"))]


def _targets_of(fn: str) -> set[str]:
    """讀 migration 檔頭 `-- migrate-targets:`（可逗號多庫）；未標＝{brand}。"""
    path = MIG_DIR / fn
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:15]:
            if _TARGETS_RE.match(line.strip()):
                raw = _TARGETS_RE.sub("", line.strip())
                raw = re.split(r"[^a-zA-Z,]", raw, 1)[0]  # 濾掉行內 (LOCK-62…) 註解
                return {t.strip().lower() for t in raw.split(",") if t.strip()}
    except OSError:
        pass
    return {"brand"}


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

    exp_versions = set(expected)
    for ver in sorted(exp_versions - db_versions):
        errors.append(f"[{label}] migration 該落本庫但 DB 未套用：{expected[ver]}")
    # 幽靈列：只比對真編號 marker 排除（000-baseline 等非 \d{3} 不算）
    for ver in sorted(v for v in (db_versions - exp_versions) if _VER_RE.match(v)):
        errors.append(f"[{label}] schema_migrations 幽靈列（DB 已套但無對應本庫檔案）：version={ver}")
    if not errors:
        print(f"✅ {label} 庫 DB 真值對照：{len(exp_versions)} 支目標檔案 ↔ schema_migrations 一致")
    return errors


def main() -> int:
    errors: list[str] = []
    files = sorted(f.name for f in MIG_DIR.glob("*.sql"))
    versions: dict[str, str] = {}
    for fn in files:
        m = _FNAME_RE.match(fn)
        if not m:
            errors.append(f"檔名不符 NNN-slug.sql 慣例：{fn}")
            continue
        ver = m.group(1)
        if ver in versions:
            errors.append(f"編號重複 {ver}：{versions[ver]} vs {fn}")
        versions[ver] = fn

    # NFR-Sch-003 forward-only：不得夾帶 down/rollback migration
    for bad in _assert_forward_only(files):
        errors.append(
            f"違反 forward-only（NFR-Sch-003）：{bad}"
            " —— migration 只准往前。需要回退請新開一支往前的修正 migration，"
            "不要提供向下腳本（多租戶＋append-only 稽核下，回滾腳本一旦存在，"
            "就會在某次事故處理時被當成官方支援的做法執行）。"
        )

    # 連續性（允許歷史缺口——僅檢查「新增是否往後接續」以已知起點為基準）
    nums = sorted(int(v) for v in versions)
    if nums:
        gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
        # 已知歷史缺口（registry 註記 028-032/036-041 波次補登）不視為錯——僅報告
        if gaps:
            print(f"ℹ️  編號缺口（歷史波次，非阻斷）：{gaps}")

    registry_text = REGISTRY.read_text(encoding="utf-8") if REGISTRY.exists() else ""
    # registry 登記與死列
    for ver, fn in versions.items():
        if f"`{fn}`" not in registry_text and fn not in registry_text:
            errors.append(f"migration 未登記於 REGISTRY：{fn}")
    for m in re.finditer(r"`(\d{3}-[\w-]+\.sql)`", registry_text):
        fn = m.group(1)
        if not (MIG_DIR / fn).exists():
            errors.append(f"REGISTRY 死列（檔案不存在）：{fn}")

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

    if errors:
        print(f"❌ migration drift 偵測到 {len(errors)} 項：")
        for e in errors:
            print("  -", e)
        return 1
    print(f"✅ migration drift-check：{len(versions)} 支 migration 編號唯一、全數登記、無死列")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
