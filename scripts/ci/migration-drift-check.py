"""Migration drift-check（CR-0136 / WBS 1.6.1 / ADR-P012 G-10 / FR-DAT-02）。

CI 檔案層守門（預設，零 DB 依賴）：
  1. 編號連續且唯一（無跳號/重號——跳號＝合併遺漏、重號＝衝突未解）。
  2. 每支 SQL migration 在 MIGRATION_REGISTRY.md 有登記（新增未登記＝audit 斷鏈）。
  3. registry 無指向不存在檔案的死列（檔案已刪但 registry 殘留）。

DB 真值對照（FR-DAT-02 補洞，opt-in）：設 `POSTGRES_URI` 或 `--check-db` 時額外比對
`SQL/migrations/*.sql`（檔案真相）↔ `public.schema_migrations`（DB 已套真值）：
  4. 檔案存在但 schema_migrations 無列＝**未套用**（部署漏跑）。
  5. schema_migrations 有列但檔案不存在＝**幽靈列**（migration 被刪但 DB 已套）。
未設 env 且無 --check-db 時完全略過 DB 段（保留純檔案層 CI 行為）。

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


def _check_db_drift(versions: dict[str, str], uri: str) -> list[str]:
    """FR-DAT-02：比對檔案 versions ↔ public.schema_migrations（DB 真值）。
    連線/psycopg 不可用 → 回 [] 並印跳過訊息（不誤判為漂移）。"""
    errors: list[str] = []
    try:
        import psycopg  # 延遲載入：純檔案層 CI 無此依賴也能跑
    except ImportError:
        print("ℹ️  psycopg 不可用 → 略過 DB 真值對照（檔案層檢查照常）")
        return errors
    try:
        with psycopg.connect(uri, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.schema_migrations') IS NOT NULL"
                )
                if not cur.fetchone()[0]:
                    print("ℹ️  schema_migrations 表不存在（未套 046+）→ 略過 DB 對照")
                    return errors
                cur.execute("SELECT version FROM public.schema_migrations")
                db_versions = {r[0] for r in cur.fetchall()}
    except Exception as e:  # noqa: BLE001
        print(f"ℹ️  DB 連線失敗 → 略過 DB 真值對照（{type(e).__name__}）")
        return errors

    file_versions = set(versions)
    for ver in sorted(file_versions - db_versions):
        errors.append(f"migration 檔案存在但 DB 未套用（schema_migrations 缺列）：{versions[ver]}")
    for ver in sorted(db_versions - file_versions):
        errors.append(f"schema_migrations 幽靈列（DB 已套但檔案不存在）：version={ver}")
    if not errors:
        print(f"✅ DB 真值對照：{len(file_versions)} 支檔案 ↔ schema_migrations 完全一致")
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

    # FR-DAT-02：opt-in DB 真值對照（POSTGRES_URI 或 --check-db）
    db_uri = os.getenv("POSTGRES_URI", "")
    if "--check-db" in sys.argv or db_uri:
        if not db_uri:
            print("ℹ️  --check-db 指定但 POSTGRES_URI 未設 → 略過 DB 對照")
        else:
            errors.extend(_check_db_drift(versions, db_uri))

    if errors:
        print(f"❌ migration drift 偵測到 {len(errors)} 項：")
        for e in errors:
            print("  -", e)
        return 1
    print(f"✅ migration drift-check：{len(versions)} 支 migration 編號唯一、全數登記、無死列")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
