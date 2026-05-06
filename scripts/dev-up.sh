#!/usr/bin/env bash
# dev-up.sh — Local development startup orchestrator
#
# 一鍵啟動本地開發環境：
#   1. PostgreSQL 容器 (pgvector/pg17) — 冪等 (run / start / no-op)
#   2. 等待 DB 就緒 (pg_isready)
#   3. ngrok HTTP tunnel — 背景執行，自動偵測 public URL
#   4. uvicorn (agent/app.py) — 前景執行，Ctrl+C 即停止
#
# Ctrl+C 後會自動清理 ngrok；DB 容器保留 (手動 docker stop lock_AI)。
#
# Usage:
#   ./scripts/dev-up.sh              # 預設：起 DB + ngrok + uvicorn
#   ./scripts/dev-up.sh --no-ngrok   # 跳過 ngrok (純本地測試)
#   ./scripts/dev-up.sh --db-only    # 只起 DB，不跑 uvicorn / ngrok

set -euo pipefail

# ── Constants ──────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_DIR="$PROJECT_ROOT/agent"
LOG_DIR="$PROJECT_ROOT/.dev-logs"

DB_CONTAINER="lock_AI"
DB_IMAGE="pgvector/pgvector:pg17"
DB_USER="lock"
DB_PASS="0000"
DB_NAME="lock_AI_data"
DB_PORT="5433"

APP_PORT="8000"
NGROK_API="http://127.0.0.1:4040/api/tunnels"

# ── CLI flags ──────────────────────────────────────────────────────────────
NO_NGROK=0
DB_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-ngrok) NO_NGROK=1 ;;
    --db-only)  DB_ONLY=1 ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | grep -E '^# ' | sed 's/^# //'
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# ── Logging helpers ────────────────────────────────────────────────────────
log()  { printf '\033[36m[dev-up]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev-up]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[dev-up]\033[0m %s\n' "$*" >&2; }

# ── Preflight ──────────────────────────────────────────────────────────────
need() { command -v "$1" >/dev/null 2>&1 || { err "missing tool: $1"; exit 1; }; }
need docker
[ "$NO_NGROK" -eq 1 ] || need ngrok

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  err ".env not found at $PROJECT_ROOT/.env (copy from .env.example)"
  exit 1
fi

mkdir -p "$LOG_DIR"

# ── 1. Ensure DB container ─────────────────────────────────────────────────
ensure_db() {
  if docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
    log "db container '$DB_CONTAINER' already running on :$DB_PORT"
    return
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
    log "starting existing container '$DB_CONTAINER'"
    docker start "$DB_CONTAINER" >/dev/null
    return
  fi
  log "creating new container '$DB_CONTAINER' from $DB_IMAGE"
  docker run --name "$DB_CONTAINER" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASS" \
    -e POSTGRES_DB="$DB_NAME" \
    -p "$DB_PORT:5432" \
    -d "$DB_IMAGE" >/dev/null
}

wait_db() {
  log "waiting for postgres ready on :$DB_PORT (max 30s)"
  for i in $(seq 1 30); do
    if docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" -q 2>/dev/null; then
      log "postgres ready (took ${i}s)"
      return
    fi
    sleep 1
  done
  err "postgres did not become ready within 30s — check: docker logs $DB_CONTAINER"
  exit 1
}

# ── 2. ngrok (background) ──────────────────────────────────────────────────
NGROK_PID=""
start_ngrok() {
  if pgrep -f "ngrok http $APP_PORT" >/dev/null 2>&1; then
    warn "ngrok already running on :$APP_PORT — skipping launch"
    detect_ngrok_url
    return
  fi
  log "starting ngrok http $APP_PORT (log: $LOG_DIR/ngrok.log)"
  ngrok http "$APP_PORT" --log=stdout >"$LOG_DIR/ngrok.log" 2>&1 &
  NGROK_PID=$!
  detect_ngrok_url
}

detect_ngrok_url() {
  for i in $(seq 1 15); do
    sleep 1
    local url
    url=$(curl -fsS "$NGROK_API" 2>/dev/null \
      | grep -oE '"public_url":"https://[^"]+"' \
      | head -1 \
      | sed 's/"public_url":"//;s/"$//')
    if [ -n "$url" ]; then
      log "ngrok tunnel: $url"
      log "  webhook URL: ${url}/webhook"
      return
    fi
  done
  warn "ngrok URL not detected within 15s — inspect: tail -f $LOG_DIR/ngrok.log"
}

# ── 3. Cleanup trap ────────────────────────────────────────────────────────
cleanup() {
  echo
  log "shutting down..."
  if [ -n "$NGROK_PID" ] && kill -0 "$NGROK_PID" 2>/dev/null; then
    kill "$NGROK_PID" 2>/dev/null || true
    log "ngrok stopped (pid=$NGROK_PID)"
  fi
  log "db container kept running — stop manually: docker stop $DB_CONTAINER"
}
trap cleanup EXIT INT TERM

# ── 4. Run ─────────────────────────────────────────────────────────────────
ensure_db
wait_db

if [ "$DB_ONLY" -eq 1 ]; then
  log "--db-only: skipping ngrok & uvicorn"
  trap - EXIT INT TERM   # 不需要 cleanup ngrok
  exit 0
fi

[ "$NO_NGROK" -eq 0 ] && start_ngrok

log "starting uvicorn — http://127.0.0.1:$APP_PORT  (Ctrl+C to stop)"
log "  health:  curl http://127.0.0.1:$APP_PORT/health"
log "  test:    curl 'http://127.0.0.1:$APP_PORT/chat?q=門打不開'"
echo

cd "$AGENT_DIR"
uvicorn app:app --reload --port "$APP_PORT"
