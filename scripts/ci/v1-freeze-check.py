#!/usr/bin/env python3
"""v1 API 凍結守門(WBS 2.5.1 Gate-1/CR-0145/ADR-003)。

ADR-003 凍結→遷移→移除:凍結自宣告以來無 enforce,期間 CR-0114/0116/0118
仍新增 v1 端點(稽核 2026-07-10 查實)。本 gate 以 baseline 快照硬凍結:

  runtime openapi 的 /api/v1/* (method, path) 集合
    - 新增(不在 baseline)→ exit 1(新面一律走 v2/tenant-scoped)
    - 減少(移除)→ 通過並提示更新 baseline(收斂是目標)

用法:uv run python scripts/ci/v1-freeze-check.py [--update-baseline]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "scripts" / "ci" / "v1-freeze-baseline.json"
_METHODS = {"get", "post", "put", "patch", "delete"}


def runtime_v1_ops() -> list[str]:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "ops" / "export_openapi.py"),
         "--output", tmp],
        capture_output=True, text=True, cwd=ROOT / "api", check=True,
    )
    spec = json.loads(Path(tmp).read_text(encoding="utf-8"))
    Path(tmp).unlink(missing_ok=True)
    ops = []
    for path, item in spec.get("paths", {}).items():
        if not path.startswith("/api/v1"):
            continue
        for method in item:
            if method in _METHODS:
                ops.append(f"{method.upper()} {path}")
    return sorted(ops)


def main() -> int:
    ops = runtime_v1_ops()
    if "--update-baseline" in sys.argv:
        BASELINE.write_text(
            json.dumps({"frozen_at": "2026-07-10", "cr": "CR-0145",
                        "ops": ops}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        print(f"✅ baseline 更新:{len(ops)} 個 v1 操作")
        return 0

    if not BASELINE.exists():
        print("❌ baseline 不存在,先跑 --update-baseline", file=sys.stderr)
        return 1
    frozen = set(json.loads(BASELINE.read_text(encoding="utf-8"))["ops"])
    current = set(ops)
    added = sorted(current - frozen)
    removed = sorted(frozen - current)
    if added:
        print(f"❌ v1 凍結違規:新增 {len(added)} 個 /api/v1 操作(新面一律 v2):",
              file=sys.stderr)
        for op in added:
            print(f"   + {op}", file=sys.stderr)
        return 1
    if removed:
        print(f"ℹ️  v1 收斂 {len(removed)} 個操作(移除方向正確)——請一併跑 "
              "--update-baseline 鎖新水位")
    print(f"✅ v1 凍結守門:{len(current)} 個操作,無新增(baseline {len(frozen)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
