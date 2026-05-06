#!/usr/bin/env bash
# scripts/dev/status.sh — Local development service status snapshot
#
# 配合 dev-up.sh / dev-up-gcp.sh：讀 .dev-logs/*.pid 與 docker DB container
# 判斷各服務當前狀態。
#
# Usage:
#   ./scripts/dev/status.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.dev-logs"

DB_CONTAINER="lock_AI"
DB_HOST_PORT="5433"
AGENT_PORT="8000"
API_PORT="8001"
WEB_PORT="3000"

if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'; C_BOLD=$'\033[1m'
else
  C_RESET=''; C_RED=''; C_GREEN=''; C_YELLOW=''; C_BOLD=''
fi

ok()   { printf '%s✓%s %s\n'  "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s⚠%s %s\n'  "$C_YELLOW" "$C_RESET" "$*"; }
err()  { printf '%s✗%s %s\n'  "$C_RED" "$C_RESET" "$*"; }

is_pid_alive() { [[ -n "${1:-}" ]] && kill -0 "$1" 2>/dev/null; }

check_host_proc() {
  local label="$1" port="$2" pidfile="$3" health_url="$4"
  if [[ -f "$pidfile" ]] && is_pid_alive "$(cat "$pidfile" 2>/dev/null)"; then
    local pid; pid=$(cat "$pidfile")
    if curl -fsS "$health_url" >/dev/null 2>&1; then
      ok "$label  運行中  (http://localhost:${port}, pid=$pid)"
    else
      warn "$label  Process 在跑但 HTTP 不通（編譯中 / 啟動中）pid=$pid"
    fi
  else
    err "$label  停止"
  fi
}

printf '\n%s=== Smart Lock 服務狀態 ===%s\n' "$C_BOLD" "$C_RESET"

# DB（docker container）
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${DB_CONTAINER}$"; then
  ok "DB     運行中  (postgresql://lock:0000@localhost:${DB_HOST_PORT}/lock_AI_data)"
else
  err "DB     停止"
fi

# Agent / API / Web — host process（dev-up.sh / dev-up-gcp.sh 都寫 .dev-logs/*.pid）
check_host_proc "Agent " "$AGENT_PORT" "$LOG_DIR/agent.pid" "http://localhost:${AGENT_PORT}/health"
check_host_proc "API   " "$API_PORT"   "$LOG_DIR/api.pid"   "http://localhost:${API_PORT}/health"
check_host_proc "Web   " "$WEB_PORT"   "$LOG_DIR/web.pid"   "http://localhost:${WEB_PORT}"

# cloud-sql-proxy（情境 B 才會啟）
if [[ -f "$LOG_DIR/cloud-sql-proxy.pid" ]] && is_pid_alive "$(cat "$LOG_DIR/cloud-sql-proxy.pid" 2>/dev/null)"; then
  ok "Proxy  運行中  (cloud-sql-proxy, pid=$(cat "$LOG_DIR/cloud-sql-proxy.pid"))"
fi

echo ""
echo "啟動：./scripts/dev/dev-up.sh [--full]   或   ./scripts/dev/dev-up-gcp.sh"
echo "停止：./scripts/dev/dev-down.sh [--multi]"
