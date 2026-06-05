"""Ops Alert Bridge — PagerDuty Events API v2 integration sample。

從 check_monitors_health.py 的 exit code 接到 PagerDuty incident。

使用：
  # 1. 跑健康檢查（or 用 check_monitors_health.py output）
  python scripts/ops/check_monitors_health.py --host ... --token ... --json > /tmp/health.json
  EXIT_CODE=$?

  # 2. 若 unhealthy → 發 PagerDuty
  if [ "$EXIT_CODE" != "0" ]; then
    cat /tmp/health.json | python scripts/ops/alert_pagerduty.py \\
      --routing-key $PD_ROUTING_KEY \\
      --severity error \\
      --source $ENVIRONMENT
  fi

整合 GitHub Actions monitors-health.yml or k8s liveness 失敗 hook。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


PD_EVENTS_API_V2 = "https://events.pagerduty.com/v2/enqueue"


def build_payload(
    *,
    routing_key: str,
    source: str,
    health_payload: dict,
    severity: str = "error",
) -> dict:
    """構造 PagerDuty Events API v2 payload。"""
    monitors = health_payload.get("monitors", {})
    summary_dict = health_payload.get("summary", {})

    # 列 unhealthy
    unhealthy = [
        (name, info.get("state", "unknown"))
        for name, info in monitors.items()
        if info.get("state") != "running"
    ]
    summary_text = (
        f"{len(unhealthy)}/{summary_dict.get('total', 0)} monitors unhealthy: "
        + ", ".join(f"{n}={s}" for n, s in unhealthy[:5])
    )

    return {
        "routing_key": routing_key,
        "event_action": "trigger",
        "dedup_key": f"smart-lock-monitors-{source}",
        "payload": {
            "summary": summary_text[:1024],
            "source": source,
            "severity": severity,
            "component": "background-monitors",
            "group": "smart-lock-api",
            "class": "lifespan-health",
            "custom_details": {
                "total_monitors": summary_dict.get("total"),
                "by_state": summary_dict.get("by_state"),
                "unhealthy_count": len(unhealthy),
                "unhealthy_list": [f"{n}: {s}" for n, s in unhealthy],
                "runbook": (
                    "docs/_ops/background-monitors-runbook.md §4"
                ),
            },
        },
    }


def send_alert(payload: dict, timeout: int = 10) -> tuple[int, str]:
    """送 alert 到 PagerDuty。回 (status_code, body)。"""
    req = urllib.request.Request(
        PD_EVENTS_API_V2,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert PagerDuty on monitors health")
    parser.add_argument("--routing-key", required=True, help="PagerDuty Events API v2 routing key")
    parser.add_argument("--source", required=True, help="staging | production")
    parser.add_argument(
        "--severity", default="error",
        choices=["critical", "error", "warning", "info"],
    )
    parser.add_argument(
        "--health-json",
        help="path to JSON file from check_monitors_health.py --json; if omitted reads stdin",
    )
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只印 payload 不真送",
    )
    args = parser.parse_args()

    # 讀 health payload
    try:
        if args.health_json:
            with open(args.health_json) as f:
                health = json.load(f)
        else:
            health = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    payload = build_payload(
        routing_key=args.routing_key,
        source=args.source,
        health_payload=health,
        severity=args.severity,
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    try:
        status, body = send_alert(payload, args.timeout)
        print(f"✅ PagerDuty event sent (status={status})")
        return 0 if status == 202 else 1
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.reason}", file=sys.stderr)
        return 2
    except urllib.error.URLError as e:
        print(f"❌ Network: {e.reason}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"❌ {type(e).__name__}: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
