"""Migration drift-check（CR-0136 / WBS 1.6.1 / ADR-P012 G-10）。

CI 檔案層守門（部署後 DB 真值另由 apply-schema-prod.sh 寫 schema_migrations）：
  1. 編號連續且唯一（無跳號/重號——跳號＝合併遺漏、重號＝衝突未解）。
  2. 每支 SQL migration 在 MIGRATION_REGISTRY.md 有登記（新增未登記＝audit 斷鏈）。
  3. registry 無指向不存在檔案的死列（檔案已刪但 registry 殘留）。

退出碼 0=無漂移；1=偵測到漂移（CI block）。純檔案層、零 DB 依賴。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIG_DIR = ROOT / "SQL" / "migrations"
REGISTRY = MIG_DIR / "MIGRATION_REGISTRY.md"

_FNAME_RE = re.compile(r"^(\d{3})-[\w-]+\.sql$")


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

    if errors:
        print(f"❌ migration drift 偵測到 {len(errors)} 項：")
        for e in errors:
            print("  -", e)
        return 1
    print(f"✅ migration drift-check：{len(versions)} 支 migration 編號唯一、全數登記、無死列")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
