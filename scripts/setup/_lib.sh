#!/usr/bin/env bash
# _lib.sh — 共用 helper（顏色、log、existence check）
# 不直接執行，由其他 setup 腳本 source 進來。

# === 顏色 ===
if [[ -t 1 ]]; then
  C_RESET='\033[0m'
  C_RED='\033[0;31m'
  C_GREEN='\033[0;32m'
  C_YELLOW='\033[0;33m'
  C_BLUE='\033[0;34m'
  C_BOLD='\033[1m'
else
  C_RESET=''; C_RED=''; C_GREEN=''; C_YELLOW=''; C_BLUE=''; C_BOLD=''
fi

# === Log helpers ===
log_info()  { printf "${C_BLUE}ℹ${C_RESET} %s\n" "$*"; }
log_ok()    { printf "${C_GREEN}✓${C_RESET} %s\n" "$*"; }
log_warn()  { printf "${C_YELLOW}⚠${C_RESET} %s\n" "$*"; }
log_err()   { printf "${C_RED}✗${C_RESET} %s\n" "$*" >&2; }
log_step()  { printf "\n${C_BOLD}${C_BLUE}▸ %s${C_RESET}\n" "$*"; }
log_title() { printf "\n${C_BOLD}=== %s ===${C_RESET}\n" "$*"; }

# === 工具檢測 ===
have() { command -v "$1" >/dev/null 2>&1; }

# === Repo root（呼叫此 lib 的腳本可用 $REPO_ROOT）===
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export REPO_ROOT

# === 容器名稱（全部腳本共用一致命名）===
DB_CONTAINER="lock_AI"
API_CONTAINER="smart-lock-api"

# === Port 對外配置 ===
DB_HOST_PORT=5433
API_HOST_PORT=8001
WEB_PORT=3000
AGENT_PORT=8000

# === PID / log 檔位置（前端 + agent 走 host 跑，需追蹤 PID）===
RUNTIME_DIR="$REPO_ROOT/.runtime"
mkdir -p "$RUNTIME_DIR"
WEB_PID_FILE="$RUNTIME_DIR/web.pid"
AGENT_PID_FILE="$RUNTIME_DIR/agent.pid"
WEB_LOG_FILE="$RUNTIME_DIR/web.log"
AGENT_LOG_FILE="$RUNTIME_DIR/agent.log"

# === 健康檢查 helper ===
wait_http() {
  local url="$1" timeout="${2:-30}" name="${3:-service}"
  local i=0
  while (( i < timeout )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log_ok "$name 健康檢查通過 ($url)"
      return 0
    fi
    sleep 1
    ((i++))
  done
  log_err "$name 健康檢查超時 ($url)，等了 ${timeout}s"
  return 1
}

is_pid_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}
