#!/usr/bin/env bash
# Ops Alert Drill Test — 用 fake health JSON 練習 alert pipeline。
#
# 不需要連到真 API；用本地構造的 mock health payload 跑 classify + alert
# 全用 --dry-run 模式不真發；ops 可拿去練習 / staging 部署前驗 setup。
#
# 對齊 docs/_ops/alert-receivers-comparison.md §5 step 4 「Drill test」。
#
# Usage:
#   bash scripts/ops/alert_drill_test.sh
#
# 跑完顯示每個 scenario 的 expected severity + dry-run payload。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

run_scenario() {
    local name="$1"
    local expected_sev="$2"
    local health_json="$3"

    echo "==========================================================="
    echo "Scenario: $name"
    echo "Expected severity: $expected_sev"
    echo "==========================================================="

    local health_file="$TMP_DIR/$name.json"
    echo "$health_json" > "$health_file"

    # classify
    local actual_sev
    actual_sev=$(python "$SCRIPT_DIR/classify_severity.py" --health-json "$health_file")

    if [ "$actual_sev" = "$expected_sev" ]; then
        echo "✅ classify_severity: $actual_sev (matches expected)"
    else
        echo "❌ classify_severity: $actual_sev (expected $expected_sev)"
    fi

    # dry-run alert
    if [ "$actual_sev" = "info" ]; then
        echo "→ no alert (severity=info)"
    else
        echo ""
        echo "--- Slack payload (dry-run) ---"
        python "$SCRIPT_DIR/alert_slack.py" \
            --webhook-url "https://hooks.slack.com/test" \
            --source "drill-test" \
            --severity "$actual_sev" \
            --health-json "$health_file" \
            --dry-run | head -30
        echo ""
        echo "--- PagerDuty payload (dry-run) ---"
        python "$SCRIPT_DIR/alert_pagerduty.py" \
            --routing-key "test-routing-key" \
            --source "drill-test" \
            --severity "$actual_sev" \
            --health-json "$health_file" \
            --dry-run | head -30
    fi
    echo ""
}

# ---- Scenario 1: all healthy ----
run_scenario "all-healthy" "info" '{
  "monitors": {
    "inventory": {"state": "running"},
    "sla": {"state": "running"},
    "gdpr_hard_delete": {"state": "running"}
  },
  "summary": {"total": 3, "by_state": {"running": 3}, "all_running": true}
}'

# ---- Scenario 2: one crashed ----
run_scenario "one-crashed" "error" '{
  "monitors": {
    "inventory": {"state": "running"},
    "sla": {"state": "running"},
    "gdpr_hard_delete": {"state": "crashed"}
  },
  "summary": {"total": 3, "by_state": {"running": 2, "crashed": 1}, "all_running": false}
}'

# ---- Scenario 3: half crashed → critical ----
run_scenario "half-crashed" "critical" '{
  "monitors": {
    "a": {"state": "crashed"},
    "b": {"state": "crashed"},
    "c": {"state": "running"},
    "d": {"state": "running"}
  },
  "summary": {"total": 4, "by_state": {"running": 2, "crashed": 2}, "all_running": false}
}'

# ---- Scenario 4: import_error → critical ----
run_scenario "import-error" "critical" '{
  "monitors": {
    "broken_module": {"state": "import_error", "error": "ModuleNotFoundError"}
  },
  "summary": {"total": 1, "by_state": {"import_error": 1}, "all_running": false}
}'

# ---- Scenario 5: lifespan not started → critical ----
run_scenario "lifespan-not-started" "critical" '{
  "monitors": {},
  "summary": {"total": 0, "by_state": {}, "all_running": true}
}'

# ---- Scenario 6: stopping → warning ----
run_scenario "stopping-warning" "warning" '{
  "monitors": {
    "inventory": {"state": "running"},
    "sla": {"state": "stopping"}
  },
  "summary": {"total": 2, "by_state": {"running": 1, "stopping": 1}, "all_running": false}
}'

echo "==========================================================="
echo "Drill test complete. Review payloads above to validate"
echo "PagerDuty + Slack integration before going live."
echo "Reference: docs/_ops/alert-receivers-comparison.md §5"
echo "==========================================================="
