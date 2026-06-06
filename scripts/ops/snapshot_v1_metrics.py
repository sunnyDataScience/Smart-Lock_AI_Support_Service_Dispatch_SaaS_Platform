"""P4 Cutover — periodically snapshot in-memory v1 hit metrics to persistent JSON.

對齊：
  - docs/_audit/P4-stage-2-7-prep-checklists.md Stage 6 (30 day 觀察)
  - api/routers/deprecation_metrics.py (in-memory hit counter)
  - 業主待裁決事項 1 P4 Stage 7 v1 router 刪除

問題：deprecation middleware 是 in-memory counter, server 重啟即清空。
30 day 觀察期需要 persistent trail 確保「真 0 traffic」判斷不被
重啟事件遮蔽。

策略：cron 每小時 GET /admin/deprecation/v1-metrics + /admin/v1-inventory/
no-traffic, 寫到 snapshot file (rotate by day)。30 day 後 aggregate
script 從 720 個 hourly snapshot 重建總命中數。

Usage:
    export SNAPSHOT_BASE_URL=https://api.lock-ai.example
    export SNAPSHOT_AUTH_TOKEN=<admin token>
    export SNAPSHOT_OUTPUT_DIR=./snapshots
    uv run python scripts/ops/snapshot_v1_metrics.py

部署為 cron (每小時)：
    0 * * * * cd /path/to/repo && SNAPSHOT_BASE_URL=... \
        SNAPSHOT_AUTH_TOKEN=... uv run python scripts/ops/snapshot_v1_metrics.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _http_get(url: str, token: str, timeout: float = 10.0) -> tuple[int, str]:
    """Returns (status, body)."""
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body
    except TimeoutError:
        return 599, ""
    except Exception as e:  # noqa: BLE001
        return 598, f"network error: {e}"


def take_snapshot(base_url: str, token: str, timeout: float = 10.0) -> dict:
    """Capture current state from 3 P4 endpoints."""
    now = datetime.now(timezone.utc)
    snapshot = {
        "captured_at": now.isoformat(),
        "captured_at_epoch": int(now.timestamp()),
        "base_url": base_url,
        "endpoints": {},
    }

    targets = [
        ("v1_metrics", "/admin/deprecation/v1-metrics"),
        ("v1_inventory", "/admin/v1-inventory"),
        ("no_traffic", "/admin/v1-inventory/no-traffic"),
    ]
    for name, path in targets:
        status, body = _http_get(f"{base_url}{path}", token, timeout=timeout)
        ep: dict = {"status": status, "path": path}
        if 200 <= status < 300:
            try:
                ep["data"] = json.loads(body)
            except Exception:  # noqa: BLE001
                ep["data"] = None
                ep["raw"] = body[:500]
        else:
            ep["error_body"] = body[:500]
        snapshot["endpoints"][name] = ep

    return snapshot


def write_snapshot(snapshot: dict, output_dir: Path) -> Path:
    """Write under output_dir/YYYY-MM-DD/HH.json (rotate by day)."""
    captured = datetime.fromtimestamp(
        snapshot["captured_at_epoch"], tz=timezone.utc,
    )
    day_dir = output_dir / captured.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    file_path = day_dir / f"{captured.strftime('%H-%M')}.json"
    with open(file_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    return file_path


def summarize(snapshot: dict) -> str:
    """Single-line human summary for cron log."""
    eps = snapshot.get("endpoints", {})
    metrics = eps.get("v1_metrics", {}).get("data", {}) or {}
    inv = eps.get("v1_inventory", {}).get("data", {}) or {}
    nt = eps.get("no_traffic", {}).get("data", {}) or {}

    total_hits = sum(
        item.get("count", 0)
        for item in metrics.get("items", [])
    )
    return (
        f"v1_hits={total_hits} "
        f"v1_endpoints={inv.get('total_endpoints', '?')} "
        f"no_traffic_routes={nt.get('total_routes', '?')}"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("SNAPSHOT_BASE_URL"))
    parser.add_argument("--auth-token", default=os.getenv("SNAPSHOT_AUTH_TOKEN"))
    parser.add_argument("--output-dir", default=os.getenv(
        "SNAPSHOT_OUTPUT_DIR", "./snapshots/v1-metrics",
    ))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not args.base_url or not args.auth_token:
        print(
            "[error] SNAPSHOT_BASE_URL / _AUTH_TOKEN required "
            "(via env or --flag)",
            file=sys.stderr,
        )
        sys.exit(2)

    base = args.base_url.rstrip("/")
    output_dir = Path(args.output_dir)

    snapshot = take_snapshot(base, args.auth_token, timeout=args.timeout)
    file_path = write_snapshot(snapshot, output_dir)

    if not args.quiet:
        print(f"[ok] {snapshot['captured_at']} → {file_path}")
        print(f"     {summarize(snapshot)}")

    # 任一 endpoint fail 不算總體 fail (snapshot 是 best-effort)
    # 但全 fail 提示
    failures = [
        name for name, ep in snapshot["endpoints"].items()
        if ep["status"] >= 400
    ]
    if len(failures) == len(snapshot["endpoints"]):
        print(f"[warn] all {len(failures)} endpoints failed", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
