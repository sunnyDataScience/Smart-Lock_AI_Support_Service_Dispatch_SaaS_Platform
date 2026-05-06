#!/usr/bin/env bash
# down.sh — 一鍵停止全部組件
#
# 預設：停 web + agent + api container；DB container 不停（重啟很快）
# --all：連 DB container 一起停
# --purge：連 DB volume 一起砍（資料會清掉，慎用）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"

STOP_DB=0; PURGE=0

for arg in "$@"; do
  case "$arg" in
    --all)   STOP_DB=1 ;;
    --purge) STOP_DB=1; PURGE=1 ;;
    -h|--help)
      grep -E "^# " "$0" | sed 's/^# //'
      exit 0
      ;;
  esac
done

log_title "停止 Smart Lock 服務"

# 1. Web (host process)
if [[ -f "$WEB_PID_FILE" ]]; then
  pid=$(cat "$WEB_PID_FILE")
  if is_pid_alive "$pid"; then
    log_step "停止 Web dev server (pid=$pid)"
    kill "$pid" 2>/dev/null || true
    sleep 1
    is_pid_alive "$pid" && kill -9 "$pid" 2>/dev/null || true
    log_ok "Web 已停止"
  fi
  rm -f "$WEB_PID_FILE"
else
  log_info "Web 未在運行（無 pid file）"
fi

# 2. Agent (host process)
if [[ -f "$AGENT_PID_FILE" ]]; then
  pid=$(cat "$AGENT_PID_FILE")
  if is_pid_alive "$pid"; then
    log_step "停止 Agent (pid=$pid)"
    kill "$pid" 2>/dev/null || true
    sleep 1
    is_pid_alive "$pid" && kill -9 "$pid" 2>/dev/null || true
    log_ok "Agent 已停止"
  fi
  rm -f "$AGENT_PID_FILE"
else
  log_info "Agent 未在運行（無 pid file）"
fi

# 3. API container
if docker ps --format '{{.Names}}' | grep -q "^${API_CONTAINER}$"; then
  log_step "停止 API container"
  docker stop "$API_CONTAINER" >/dev/null
  log_ok "API 已停止"
else
  log_info "API container 未在運行"
fi

# 4. DB container（選用）
if (( STOP_DB == 1 )); then
  if docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
    log_step "停止 DB container"
    docker stop "$DB_CONTAINER" >/dev/null
    log_ok "DB 已停止"
  fi

  if (( PURGE == 1 )); then
    log_warn "─── PURGE 模式：將刪除 DB container 與 volume，資料會全部清空 ───"
    read -r -p "確定要繼續？輸入 yes 確認：" CONFIRM
    if [[ "$CONFIRM" == "yes" ]]; then
      docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
      docker volume rm lock_AI_data >/dev/null 2>&1 || true
      log_ok "DB container 與 volume 已刪除"
    else
      log_info "取消 purge"
    fi
  fi
else
  log_info "DB container 保留運行（用 --all 一起停）"
fi

echo ""
log_ok "Done"
