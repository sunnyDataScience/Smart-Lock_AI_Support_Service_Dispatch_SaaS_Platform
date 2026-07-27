#!/usr/bin/env python3
"""輸出目前 runtime route 的 ADR-035 ownership matrix JSON。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "api"
sys.path.insert(0, str(API_ROOT))

from fastapi.routing import APIRoute  # noqa: E402
from main import app  # noqa: E402
from core.resource_ownership import is_governed_route, matrix_record  # noqa: E402

records = []
for route in app.routes:
    if not isinstance(route, APIRoute):
        continue
    methods = set(route.methods or ())
    if is_governed_route(methods, route.path):
        records.append(matrix_record(methods, route.path))

json.dump(
    sorted(records, key=lambda item: (item["path"], item["methods"])),
    sys.stdout,
    ensure_ascii=False,
    indent=2,
)
sys.stdout.write("\n")
