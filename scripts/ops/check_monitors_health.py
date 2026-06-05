"""Ops Smoke Script — 8-monitor health check (exit 0 全 running / 1 有 crashed)。

對齊 docs/_ops/background-monitors-runbook.md §3。

使用方式：
  uv run python scripts/ops/check_monitors_health.py \\
      --host https://api.example.com \\
      --token $ADMIN_JWT

CI/cron 跑用：exit code:
  0 = all_running=true
  1 = any crashed / import_error / stopping
  2 = network / auth error

可整合 GCP uptime check / GitHub Actions schedule / k8s liveness probe。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def fetch_health(host: str, token: str, timeout: int = 10) -> dict:
    """呼 /api/v1/admin/lifespan-monitors/health。"""
    url = f"{host.rstrip('/')}/api/v1/admin/lifespan-monitors/health"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def evaluate(payload: dict) -> tuple[int, str]:
    """回 (exit_code, summary_message)。"""
    monitors = payload.get("monitors", {})
    summary = payload.get("summary", {})
    total = summary.get("total", 0)
    by_state = summary.get("by_state", {})
    all_running = summary.get("all_running", False)

    if all_running and total > 0:
        return 0, f"✅ ALL {total} monitors running"

    # 列 unhealthy monitor 名稱
    unhealthy: list[tuple[str, str]] = []
    for name, info in monitors.items():
        state = info.get("state", "unknown")
        if state != "running":
            unhealthy.append((name, state))

    msg_lines = [
        f"❌ NOT ALL HEALTHY (total={total}, by_state={by_state})",
        "",
        "Unhealthy monitors:",
    ]
    for name, state in unhealthy:
        msg_lines.append(f"  - {name}: {state}")
    return 1, "\n".join(msg_lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Background monitors health smoke check",
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument(
        "--json", action="store_true",
        help="輸出原始 JSON 而非人類可讀格式",
    )
    args = parser.parse_args()

    try:
        payload = fetch_health(args.host, args.token, args.timeout)
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP error {e.code}: {e.reason}", file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"❌ Network error: {e.reason}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"❌ Unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    code, msg = evaluate(payload)
    if not args.json:
        print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())
