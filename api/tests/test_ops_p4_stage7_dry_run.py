"""P4 Stage 7 v1 deletion dry-run — pure function tests."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _mod():
    from scripts.ops import p4_stage7_delete_v1_dry_run
    return p4_stage7_delete_v1_dry_run


def test_load_safe_list_plain_lines(tmp_path):
    mod = _mod()
    f = tmp_path / "safe.txt"
    f.write_text(
        "GET /api/v1/foo\n"
        "POST /api/v1/bar\n"
        "# comment ignored\n"
        "\n"
    )
    items = mod.load_safe_list(f)
    assert "GET /api/v1/foo" in items
    assert "POST /api/v1/bar" in items
    assert len(items) == 2


def test_load_safe_list_markdown_backticks(tmp_path):
    mod = _mod()
    f = tmp_path / "safe.md"
    f.write_text(
        "| Endpoint | total_hits |\n"
        "|---|---|\n"
        "| `GET /api/v1/abc` | 0 |\n"
        "| `POST /api/v1/xyz` | 0 |\n"
    )
    items = mod.load_safe_list(f)
    assert "GET /api/v1/abc" in items
    assert "POST /api/v1/xyz" in items


def test_load_safe_list_missing_file(tmp_path):
    mod = _mod()
    items = mod.load_safe_list(tmp_path / "missing.txt")
    assert items == []


def test_parse_main_py_finds_v1_imports(tmp_path):
    mod = _mod()
    main = tmp_path / "main.py"
    main.write_text(
        "from fastapi import FastAPI\n"
        "from routers import notifications as notifications_router\n"
        "from routers import work_orders_v2 as work_orders_v2_router\n"
        "from routers import auth as auth_router  # legacy\n"
        "app = FastAPI()\n"
        "app.include_router(notifications_router.router, tags=['m'])\n"
        "app.include_router(work_orders_v2_router.router)\n"
        "app.include_router(auth_router.router)\n"
    )
    info = mod.parse_main_py(main)
    aliases = [i["alias"] for i in info["imports"]]
    assert "notifications_router" in aliases
    assert "auth_router" in aliases
    # v2 should be skipped
    assert "work_orders_v2_router" not in aliases

    # includes captured (both v1 and v2 because pattern matches all)
    inc_aliases = [i["alias"] for i in info["includes"]]
    assert "notifications_router" in inc_aliases
    assert "auth_router" in inc_aliases


def test_find_router_files_only_existing(tmp_path):
    mod = _mod()
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "alpha.py").write_text("# alpha")
    (routers / "beta.py").write_text("# beta")
    found = mod.find_router_files(routers, ["alpha", "beta", "ghost"])
    names = [p.name for p in found]
    assert "alpha.py" in names
    assert "beta.py" in names
    assert "ghost.py" not in names


def test_render_report_safe_list_in_output(tmp_path):
    mod = _mod()
    routers = tmp_path / "routers"
    routers.mkdir()
    (routers / "alpha.py").write_text("# alpha")

    info = {
        "imports": [{"line": 2, "module": "alpha",
                     "alias": "alpha_router"}],
        "includes": [{"line": 5, "alias": "alpha_router",
                      "raw": "app.include_router(alpha_router.router)"}],
        "v1_modules": ["alpha"],
    }
    files = [routers / "alpha.py"]
    safe = ["GET /api/v1/alpha"]

    report = mod.render_report(info, files, safe, routers)
    assert "alpha" in report
    assert "GET /api/v1/alpha" in report
    assert "Stage 7" in report
    assert "§4 後續真實刪除 PR 步驟" in report


def test_render_report_warns_when_no_safe_list(tmp_path):
    mod = _mod()
    report = mod.render_report(
        {"imports": [], "includes": [], "v1_modules": []},
        [],
        [],
        tmp_path,
    )
    assert "不可執行真實刪除" in report
