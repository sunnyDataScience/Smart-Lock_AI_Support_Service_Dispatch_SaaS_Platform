#!/usr/bin/env bash
# status.sh — 查看四個組件目前狀態
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

log_title "Smart Lock 服務狀態"

# DB
if docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
  log_ok "DB         運行中  (postgresql://lock:0000@localhost:${DB_HOST_PORT}/lock_AI_data)"
else
  log_err "DB         停止"
fi

# API
if docker ps --format '{{.Names}}' | grep -q "^${API_CONTAINER}$"; then
  if curl -fsS "http://localhost:${API_HOST_PORT}/health" >/dev/null 2>&1; then
    log_ok "API        運行中  (http://localhost:${API_HOST_PORT})"
  else
    log_warn "API        Container 起來但 /health 不通"
  fi
else
  log_err "API        停止"
fi

# Web
if [[ -f "$WEB_PID_FILE" ]] && is_pid_alive "$(cat "$WEB_PID_FILE")"; then
  pid=$(cat "$WEB_PID_FILE")
  if curl -fsS "http://localhost:${WEB_PORT}" >/dev/null 2>&1; then
    log_ok "Web        運行中  (http://localhost:${WEB_PORT}, pid=$pid)"
  else
    log_warn "Web        Process 在跑但 HTTP 不通（編譯中？）pid=$pid"
  fi
else
  log_err "Web        停止"
fi

# Agent
if [[ -f "$AGENT_PID_FILE" ]] && is_pid_alive "$(cat "$AGENT_PID_FILE")"; then
  pid=$(cat "$AGENT_PID_FILE")
  if curl -fsS "http://localhost:${AGENT_PORT}/health" >/dev/null 2>&1; then
    log_ok "Agent      運行中  (http://localhost:${AGENT_PORT}, pid=$pid)"
  else
    log_warn "Agent      Process 在跑但 /health 不通  pid=$pid"
  fi
else
  log_err "Agent      停止"
fi

echo ""
echo "啟動：./scripts/setup/up.sh"
echo "停止：./scripts/setup/down.sh"
