#!/usr/bin/env bash
# Ops Alert Pipeline — 完整 health → severity → routed alert 一鍵跑。
#
# 對齊 docs/_ops/alert-receivers-comparison.md §2.2 雙路徑 strategy:
#   critical → PagerDuty (24/7 oncall)
#   error/warning → Slack (#ops-alerts / #ops-info)
#   info → log only (不發 alert)
#
# Usage:
#   export API_HOST=https://api.example.com
#   export API_TOKEN=admin-jwt
#   export ENVIRONMENT=production
#   export PD_ROUTING_KEY=...        # PagerDuty Events v2 routing key
#   export SLACK_WEBHOOK_URL=...     # Slack Incoming Webhook
#   export SLACK_CHANNEL_ALERTS=#ops-alerts
#   export SLACK_CHANNEL_INFO=#ops-info
#
#   bash scripts/ops/alert_pipeline.sh
#
# Exit codes:
#   0 — healthy (info)
#   1 — alert sent (error/warning/critical)
#   2 — script / network error

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HEALTH_JSON="/tmp/monitors_health.$$.json"
trap 'rm -f "$HEALTH_JSON"' EXIT

# ---- Required env ----
: "${API_HOST:?API_HOST not set}"
: "${API_TOKEN:?API_TOKEN not set}"
: "${ENVIRONMENT:?ENVIRONMENT not set (staging|production)}"

# ---- Step 1: Fetch health ----
echo "[1/4] Fetching monitors health from ${API_HOST}..."
python "$SCRIPT_DIR/check_monitors_health.py" \
    --host "$API_HOST" \
    --token "$API_TOKEN" \
    --timeout 15 \
    --json > "$HEALTH_JSON"

# ---- Step 2: Classify severity ----
echo "[2/4] Classifying severity..."
SEVERITY=$(python "$SCRIPT_DIR/classify_severity.py" --health-json "$HEALTH_JSON")
echo "    → severity=$SEVERITY"

# ---- Step 3: Route alert ----
echo "[3/4] Routing alert..."
case "$SEVERITY" in
  critical)
    if [ -z "${PD_ROUTING_KEY:-}" ]; then
      echo "  ⚠️ PD_ROUTING_KEY not set, fallback to Slack" >&2
      python "$SCRIPT_DIR/alert_slack.py" \
        --webhook-url "$SLACK_WEBHOOK_URL" \
        --source "$ENVIRONMENT" \
        --severity critical \
        --channel "${SLACK_CHANNEL_ALERTS:-#ops-alerts}" \
        --health-json "$HEALTH_JSON"
    else
      python "$SCRIPT_DIR/alert_pagerduty.py" \
        --routing-key "$PD_ROUTING_KEY" \
        --source "$ENVIRONMENT" \
        --severity critical \
        --health-json "$HEALTH_JSON"
    fi
    EXIT_CODE=1
    ;;
  error)
    python "$SCRIPT_DIR/alert_slack.py" \
      --webhook-url "$SLACK_WEBHOOK_URL" \
      --source "$ENVIRONMENT" \
      --severity error \
      --channel "${SLACK_CHANNEL_ALERTS:-#ops-alerts}" \
      --health-json "$HEALTH_JSON"
    EXIT_CODE=1
    ;;
  warning)
    python "$SCRIPT_DIR/alert_slack.py" \
      --webhook-url "$SLACK_WEBHOOK_URL" \
      --source "$ENVIRONMENT" \
      --severity warning \
      --channel "${SLACK_CHANNEL_INFO:-#ops-info}" \
      --health-json "$HEALTH_JSON"
    EXIT_CODE=1
    ;;
  info)
    echo "    → all healthy, no alert sent"
    EXIT_CODE=0
    ;;
  *)
    echo "  ❌ Unknown severity: $SEVERITY" >&2
    EXIT_CODE=2
    ;;
esac

# ---- Step 4: Summary ----
echo "[4/4] Summary"
echo "    Environment: $ENVIRONMENT"
echo "    Severity:    $SEVERITY"
echo "    Exit code:   $EXIT_CODE"

exit $EXIT_CODE
