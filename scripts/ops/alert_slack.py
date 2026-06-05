"""Ops Alert Bridge — Slack Incoming Webhook integration sample。

從 check_monitors_health.py 的 exit code 接到 Slack channel。
替代/補充 alert_pagerduty.py — 有些團隊用 Slack 不用 PagerDuty。

使用：
  python scripts/ops/check_monitors_health.py --host ... --token ... --json | \\
    python scripts/ops/alert_slack.py \\
      --webhook-url $SLACK_WEBHOOK_URL \\
      --source $ENVIRONMENT \\
      --channel '#ops-alerts'
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


# Slack severity → emoji
_SEVERITY_EMOJI = {
    "critical": ":rotating_light:",
    "error": ":red_circle:",
    "warning": ":warning:",
    "info": ":information_source:",
}


def build_payload(
    *,
    source: str,
    health_payload: dict,
    severity: str = "error",
    channel: str | None = None,
) -> dict:
    """構造 Slack Incoming Webhook payload（Block Kit format）。"""
    monitors = health_payload.get("monitors", {})
    summary_dict = health_payload.get("summary", {})

    unhealthy = [
        (name, info.get("state", "unknown"))
        for name, info in monitors.items()
        if info.get("state") != "running"
    ]
    total = summary_dict.get("total", 0)
    emoji = _SEVERITY_EMOJI.get(severity, ":bell:")

    header_text = (
        f"{emoji} Monitors unhealthy on *{source}* "
        f"({len(unhealthy)}/{total})"
    )

    # Block Kit blocks
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header_text[:150]},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Environment:*\n{source}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity}"},
                {"type": "mrkdwn", "text": f"*Total monitors:*\n{total}"},
                {
                    "type": "mrkdwn",
                    "text": f"*By state:*\n{json.dumps(summary_dict.get('by_state', {}))}",
                },
            ],
        },
    ]

    if unhealthy:
        lines = "\n".join(f"• `{n}` — {s}" for n, s in unhealthy[:10])
        if len(unhealthy) > 10:
            lines += f"\n_... and {len(unhealthy) - 10} more_"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Unhealthy monitors:*\n{lines}",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": (
                ":book: Runbook: "
                "`docs/_ops/background-monitors-runbook.md` §4"
            ),
        }],
    })

    payload: dict = {"blocks": blocks}
    if channel:
        payload["channel"] = channel
    return payload


def send_alert(
    webhook_url: str, payload: dict, timeout: int = 10,
) -> tuple[int, str]:
    """送 alert 到 Slack。回 (status_code, body)。"""
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Alert Slack on monitors health")
    parser.add_argument("--webhook-url", required=True)
    parser.add_argument("--source", required=True, help="staging | production")
    parser.add_argument(
        "--severity", default="error",
        choices=["critical", "error", "warning", "info"],
    )
    parser.add_argument("--channel", help="override channel (e.g. #ops-alerts)")
    parser.add_argument("--health-json", help="path or stdin")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只印 payload 不真送",
    )
    args = parser.parse_args()

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
        source=args.source,
        health_payload=health,
        severity=args.severity,
        channel=args.channel,
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    try:
        status, body = send_alert(args.webhook_url, payload, args.timeout)
        if status == 200:
            print(f"✅ Slack alert sent (status={status})")
            return 0
        print(f"⚠️ Unexpected status={status} body={body[:200]}", file=sys.stderr)
        return 1
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
