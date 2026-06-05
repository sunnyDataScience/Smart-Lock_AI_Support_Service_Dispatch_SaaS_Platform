"""Export FastAPI OpenAPI schema to JSON for web client codegen.

Sprint 1-5 BUILD 時 web 端用 `openapi-typescript` 從本 script 產出的
JSON 自動 gen `web/src/types/api.generated.ts`，避免手寫 type drift。

對齊：
  - web/src/components/phase-ii/types.ts (本檔 type 為 Sprint pre-build，
    可逐步 migrate 到 auto-gen)
  - docs/_ops/wbs-100-closeout-plan.md §1.2

Usage:
    cd <project_root>
    python scripts/ops/export_openapi.py [--output PATH] [--pretty]

Default output: docs/architecture/api/openapi-runtime.json (gitignored or
committed for diff tracking — 由 ops 決定)

Web 端 codegen 範例 (Sprint BUILD 時用):
    cd web
    npx openapi-typescript \
      ../docs/architecture/api/openapi-runtime.json \
      -o src/types/api.generated.ts
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
API_DIR = PROJECT_ROOT / "api"


def _load_app():
    """Import api.main:app；handle import failures gracefully."""
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(API_DIR))
    # 設 dummy env vars 避免 startup-time validation fail
    os.environ.setdefault("POSTGRES_URI", "postgresql://dummy:dummy@localhost/dummy")
    os.environ.setdefault("LOCK_AI_API_KEY", "dummy-export-only")
    os.environ.setdefault("LINE_CHANNEL_ACCESS_TOKEN", "dummy")
    os.environ.setdefault("LINE_CHANNEL_SECRET", "dummy")
    os.environ.setdefault("OPENAPI_EXPORT_MODE", "1")  # 給 main.py 看的 hint

    try:
        from api.main import app  # type: ignore
        return app
    except Exception as e:  # noqa: BLE001
        print(f"[error] cannot import api.main:app — {e}", file=sys.stderr)
        print("[hint] ensure `uv sync` ran successfully", file=sys.stderr)
        raise


def export_schema(output_path: Path, pretty: bool = True) -> dict:
    """Export OpenAPI schema to JSON file."""
    app = _load_app()
    schema = app.openapi()

    # 補 metadata for web codegen consumers
    schema.setdefault("info", {})
    info = schema["info"]
    info.setdefault("title", "Smart Lock SaaS API")
    info.setdefault("version", "phase-ii-9fr")
    info["x-exported-at"] = _now_iso()
    info["x-exported-by"] = "scripts/ops/export_openapi.py"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(schema, f, ensure_ascii=False, indent=2, sort_keys=True)
        else:
            json.dump(schema, f, ensure_ascii=False, separators=(",", ":"))

    return {
        "output": str(output_path),
        "size_bytes": output_path.stat().st_size,
        "endpoint_count": _count_endpoints(schema),
        "schema_count": len(schema.get("components", {}).get("schemas", {})),
    }


def _count_endpoints(schema: dict) -> int:
    """Count total endpoints (path × method)."""
    n = 0
    for path_item in schema.get("paths", {}).values():
        for method in ("get", "post", "put", "patch", "delete"):
            if method in path_item:
                n += 1
    return n


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "docs/architecture/api/openapi-runtime.json",
        help="Output JSON path",
    )
    parser.add_argument("--pretty", action="store_true", default=True)
    parser.add_argument("--compact", dest="pretty", action="store_false")
    args = parser.parse_args()

    summary = export_schema(args.output, pretty=args.pretty)
    print(f"[ok] exported {summary['endpoint_count']} endpoints / "
          f"{summary['schema_count']} schemas to {summary['output']} "
          f"({summary['size_bytes']:,} bytes)")


if __name__ == "__main__":
    main()
