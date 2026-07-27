#!/usr/bin/env python3
"""建立可稽核的 rollback/forward-fix/restore drill 證據；不允許空白佔位。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drill-type", choices=("rollback", "forward-fix", "restore"), required=True)
    parser.add_argument("--environment", choices=("staging", "production"), required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--finished-at", required=True)
    parser.add_argument("--result", choices=("passed", "failed"), required=True)
    parser.add_argument("--evidence-url", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not args.evidence_url.startswith(("https://", "gs://")):
        raise SystemExit("evidence-url must be durable https:// or gs:// evidence")
    payload = {
        "schema_version": "1.0",
        "drill_type": args.drill_type,
        "environment": args.environment,
        "operator": args.operator,
        "release_id": args.release_id,
        "started_at": args.started_at,
        "finished_at": args.finished_at,
        "result": args.result,
        "evidence_url": args.evidence_url,
        "notes": args.notes,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
