"""P4 Stage 7 — v1 router deletion dry-run (執行前 audit)。

業主簽 Stage 7 後 ops 跑此 script 取得「刪除衝擊評估」報告 (dry-run
不真改 code), 確認:
  - 哪些 v1 router 檔案被列為刪除候選 (依 aggregate report §1 安全集)
  - 哪些 main.py 行需註解或移除 (import + include_router)
  - 哪些測試 / docs / OpenAPI 參考要同步處理
  - blast radius (相依 module / import)

不做任何修改, 純 read + report。執行流程:
  1. business 簽 Stage 7 後 ops 拿 aggregate report 的 §1 safe list
  2. 跑本 script with --safe-list <file>
  3. Review report → 若 OK, ops 走真實刪除 PR (不在本 script 內)

Usage:
    uv run python scripts/ops/p4_stage7_delete_v1_dry_run.py \\
        --main-py api/main.py \\
        --safe-list reports/p4-stage7-safe-list.txt \\
        --output reports/p4-stage7-deletion-plan.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def load_safe_list(path: Path) -> list[str]:
    """Load endpoint list from aggregate report or plain file.

    Accept formats:
    - "GET /api/v1/foo" (per line, from aggregate §1 markdown)
    - markdown table row "| GET /api/v1/foo | ..."
    - plain "/api/v1/foo"
    """
    items: list[str] = []
    if not path.exists():
        return items
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # markdown table row → extract inside backticks
        m = re.search(r"`([A-Z]+ +/api/v\d+/[^`]+)`", line)
        if m:
            items.append(m.group(1))
            continue
        # bare "METHOD /path" or "/path"
        if "/api/v" in line:
            items.append(line.strip("| "))
    return items


def parse_main_py(main_py: Path) -> dict:
    """Find v1 router imports + include_router lines + tags."""
    text = main_py.read_text()
    lines = text.splitlines()
    info: dict = {"imports": [], "includes": [], "v1_modules": set()}

    # v1 router import pattern: 不帶 _v2 後綴
    import_re = re.compile(
        r"^from routers import (\w+) as (\w+_router)\s*(?:#.*)?$"
    )
    include_re = re.compile(
        r"app\.include_router\(\s*(\w+_router)\.router"
    )
    for i, line in enumerate(lines, start=1):
        m = import_re.match(line.strip())
        if m:
            module, alias = m.group(1), m.group(2)
            if not module.endswith("_v2") and not module.endswith("_v3"):
                info["imports"].append({
                    "line": i, "module": module, "alias": alias,
                })
                info["v1_modules"].add(module)
        m2 = include_re.search(line)
        if m2:
            alias = m2.group(1)
            info["includes"].append({
                "line": i, "alias": alias, "raw": line.strip(),
            })
    info["v1_modules"] = sorted(info["v1_modules"])
    return info


def find_router_files(routers_dir: Path, v1_modules: list[str]) -> list[Path]:
    candidates = []
    for mod in v1_modules:
        p = routers_dir / f"{mod}.py"
        if p.exists():
            candidates.append(p)
    return candidates


def render_report(
    main_info: dict,
    router_files: list[Path],
    safe_list: list[str],
    routers_dir: Path,
) -> str:
    lines = [
        "# P4 Stage 7 — v1 Router 刪除計畫 (Dry-Run)",
        "",
        f"Safe list endpoints: {len(safe_list)}",
        f"v1 router modules in main.py: {len(main_info['v1_modules'])}",
        f"v1 router files found: {len(router_files)}",
        "",
        "## §1 候選刪除檔案",
        "",
    ]
    if not router_files:
        lines.append("_(無檔案候選)_")
    else:
        for p in router_files:
            rel = p.relative_to(p.parents[2]) if len(p.parents) >= 3 else p
            size_kb = p.stat().st_size / 1024
            lines.append(f"- `{rel}` ({size_kb:.1f} KB)")

    lines += [
        "",
        "## §2 main.py 需修改的行",
        "",
        "### Import 行",
        "",
    ]
    if not main_info["imports"]:
        lines.append("_(無 v1 import)_")
    else:
        for imp in main_info["imports"]:
            lines.append(
                f"- L{imp['line']}: `from routers import {imp['module']} "
                f"as {imp['alias']}`"
            )

    lines += [
        "",
        "### Include_router 行",
        "",
    ]
    if not main_info["includes"]:
        lines.append("_(無 include_router)_")
    else:
        for inc in main_info["includes"]:
            lines.append(f"- L{inc['line']}: `{inc['raw']}`")

    lines += [
        "",
        "## §3 業主簽核對應 safe list",
        "",
    ]
    if safe_list:
        lines.append("業主已簽 Stage 7 安全可刪 endpoints:")
        for ep in safe_list[:50]:  # 截斷避免過長
            lines.append(f"- `{ep}`")
        if len(safe_list) > 50:
            lines.append(f"- ... 共 {len(safe_list)} 個")
    else:
        lines.append("⚠️ 未提供 safe list — 不可執行真實刪除")

    lines += [
        "",
        "## §4 後續真實刪除 PR 步驟（非本 script）",
        "",
        "1. 開 branch `chore/p4-stage7-delete-v1-routers`",
        "2. 依 §1 刪除 router 檔案",
        "3. 依 §2 移除 main.py import + include_router 行",
        "4. 刪除 router 對應 test 檔案 (`api/tests/test_*_v1.py` 等)",
        "5. 更新 `docs/architecture/api/openapi.yaml` 移除 v1 path",
        "6. 跑 `.venv/bin/pytest api/tests/` 確認無 regression",
        "7. 跑 `scripts/ops/smoke_test_production.py` 確認 v2 全綠",
        "8. 開 PR + reference ADR (新立 ADR 記錄 Stage 7 完成)",
        "9. Merge 後 push, ops 觀察 24h",
        "",
        "## §5 Risk Mitigation",
        "",
        "- ❗ **若 safe list 與 router files 不對應**: 不可執行刪除",
        "  → 業主重簽 / 重跑 aggregate report",
        "- ❗ **若 main.py import 在 §3 之外仍被引用**: dead code, 刪後",
        "  Python import error → run 完整 pytest 抓",
        "- ❗ **若 v1 router 與 v2 共用 service**: 安全 (service 不刪)",
        "- ❗ **若 v1 router 有獨有 helper**: 移到對應 v2 router 或共用 lib",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-py", type=Path, default=Path("api/main.py"))
    parser.add_argument("--routers-dir", type=Path,
                        default=Path("api/routers"))
    parser.add_argument("--safe-list", type=Path, default=None,
                        help="Path to safe-list file (one endpoint per line "
                             "or markdown table)")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if not args.main_py.exists():
        print(f"[error] main.py not found: {args.main_py}", file=sys.stderr)
        sys.exit(2)
    if not args.routers_dir.exists():
        print(f"[error] routers dir not found: {args.routers_dir}",
              file=sys.stderr)
        sys.exit(2)

    main_info = parse_main_py(args.main_py)
    router_files = find_router_files(args.routers_dir, main_info["v1_modules"])
    safe_list = load_safe_list(args.safe_list) if args.safe_list else []

    report = render_report(main_info, router_files, safe_list,
                           args.routers_dir)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report)
        print(f"[ok] dry-run plan → {args.output}")
        print(f"     v1 modules: {len(main_info['v1_modules'])}, "
              f"router files: {len(router_files)}, "
              f"safe list: {len(safe_list)}")
    else:
        print(report)


if __name__ == "__main__":
    main()
