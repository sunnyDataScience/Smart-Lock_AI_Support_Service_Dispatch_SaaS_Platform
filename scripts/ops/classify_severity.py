"""Ops Severity Classifier — health JSON → severity 字串。

對齊 docs/_ops/alert-receivers-comparison.md §3 severity classification table。

從 check_monitors_health.py --json 接 stdin → 輸出 severity 字串
（critical/error/warning/info）給後續 alert_pagerduty.py 或 alert_slack.py
作為 --severity 參數。

Pipeline 範例：

  python check_monitors_health.py --host ... --token ... --json > /tmp/h.json
  SEVERITY=$(cat /tmp/h.json | python classify_severity.py)
  if [ "$SEVERITY" = "critical" ]; then
    cat /tmp/h.json | python alert_pagerduty.py \\
      --routing-key $PD_KEY --severity $SEVERITY --source prod
  else
    cat /tmp/h.json | python alert_slack.py \\
      --webhook-url $SLACK --severity $SEVERITY --source prod
  fi
"""

from __future__ import annotations

import argparse
import json
import sys


def classify_severity(health_payload: dict) -> str:
    """從 health JSON → severity 字串。

    對齊 alert-receivers-comparison.md §3:
      - by_state.crashed >= total/2 → critical
      - import_error >= 1            → critical (部署檔損壞)
      - total == 0                   → critical (lifespan not started)
      - by_state.crashed >= 1        → error
      - by_state.stopping >= 1       → warning
      - all running                  → info
    """
    summary = health_payload.get("summary", {})
    total = summary.get("total", 0)
    by_state = summary.get("by_state", {})
    crashed = by_state.get("crashed", 0)
    import_error = by_state.get("import_error", 0)
    stopping = by_state.get("stopping", 0)
    not_started = by_state.get("not_started", 0)

    # 關鍵案例優先
    if total == 0:
        return "critical"
    if import_error >= 1:
        return "critical"
    if crashed >= max(1, total // 2):
        return "critical"

    # 其次
    if crashed >= 1:
        return "error"
    if stopping >= 1 or not_started >= 1:
        return "warning"

    return "info"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify monitors health JSON → severity 字串",
    )
    parser.add_argument(
        "--health-json",
        help="path to JSON file from check_monitors_health.py --json; "
             "if omitted reads stdin",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="額外印 reasoning 到 stderr",
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

    sev = classify_severity(health)
    print(sev)

    if args.verbose:
        summary = health.get("summary", {})
        print(
            f"[debug] total={summary.get('total')} "
            f"by_state={summary.get('by_state')} "
            f"→ severity={sev}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
