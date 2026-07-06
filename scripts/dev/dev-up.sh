#!/usr/bin/env bash
# scripts/dev/dev-up.sh — Local development startup orchestrator
#
# 一鍵啟動本地開發環境（情境 A：本機 docker DB + 假資料）：
#   1. PostgreSQL 容器 (pgvector/pg17) — 冪等 (run / start / no-op)
#   2. 等待 DB 就緒 (pg_isready)
#   3. ngrok HTTP tunnel — 背景執行，自動偵測 public URL
#   4. agent LINE gateway (agent/scripts/line_gateway.py) — LockCore 架構入口（取代已刪的
#      agent/app.py）；aiohttp webhook :8000/callback。需 LINE_CHANNEL_SECRET/TOKEN，
#      缺則自動略過 agent（仍可只跑 api/web）。
#   5. （選用）uvicorn (api/main.py) on :8001
#   6. （選用）next dev (web/) on :3000
#
# CR-0022：agent 轉真人會旁路建 AI 草擬問題卡。本 script 會把 INTERNAL_API_TOKEN
# 同步給 api 與 agent（預設 dev-internal-token，可用環境變數覆蓋）。
#
# 收尾：./scripts/dev/dev-down.sh（多服務模式請用 --gcp 或 PID file 收）
#
# Usage:
#   ./scripts/dev/dev-up.sh                # 預設：DB + ngrok + agent (前景)
#   ./scripts/dev/dev-up.sh --no-ngrok     # 跳過 ngrok
#   ./scripts/dev/dev-up.sh --db-only      # 只起 DB
#   ./scripts/dev/dev-up.sh --with-api     # +api on :8001（agent / api 全背景）
#   ./scripts/dev/dev-up.sh --with-web     # +web on :3000
#   ./scripts/dev/dev-up.sh --full         # = --with-api --with-web（全棧）

set -euo pipefail

# ── Constants ──────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
AGENT_DIR="$PROJECT_ROOT/agent"
API_DIR="$PROJECT_ROOT/api"
WEB_DIR="$PROJECT_ROOT/web"
LOG_DIR="$PROJECT_ROOT/.dev-logs"

DB_CONTAINER="lock_AI"
DB_IMAGE="pgvector/pgvector:pg17"
DB_USER="lock"
DB_PASS="0000"
DB_NAME="lock_AI_data"
DB_PORT="5433"

AGENT_PORT="8000"
API_PORT="8001"
WEB_PORT="3000"
NGROK_API="http://127.0.0.1:4040/api/tunnels"

# CR-0022：service-to-service internal token（api 驗證 / agent 旁路同步用同一把）。
# 可用環境變數覆蓋；export 讓背景啟動的 api / agent 子行程都繼承到同一值。
export INTERNAL_API_TOKEN="${INTERNAL_API_TOKEN:-dev-internal-token}"
export LOCK_API_BASE_URL="${LOCK_API_BASE_URL:-http://127.0.0.1:$API_PORT}"
# CR-0022/方案A：agent 送的 tenant 是別名（如 "locksmart"），API ingest 端據此對應到
# 實際租戶 UUID（否則 psycopg 對 uuid 欄位丟 500）。dev 預設指向 seed 租戶。
export AGENT_TENANT_ID="${AGENT_TENANT_ID:-00000000-0000-0000-0000-000000000001}"

# ── CLI flags ──────────────────────────────────────────────────────────────
NO_NGROK=0
DB_ONLY=0
WITH_API=0
WITH_WEB=0
for arg in "$@"; do
  case "$arg" in
    --no-ngrok) NO_NGROK=1 ;;
    --db-only)  DB_ONLY=1 ;;
    --with-api) WITH_API=1 ;;
    --with-web) WITH_WEB=1 ;;
    --full)     WITH_API=1; WITH_WEB=1 ;;
    -h|--help)
      sed -n '2,/^set -euo/p' "$0" | grep -E '^# ' | sed 's/^# //'
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# 多服務模式（agent / api / web 並存）→ agent 切背景，避免 Ctrl+C 把 api/web 留下來
MULTI_SERVICE=0
[ "$WITH_API" -eq 1 ] || [ "$WITH_WEB" -eq 1 ] && MULTI_SERVICE=1

# ── Logging helpers ────────────────────────────────────────────────────────
log()  { printf '\033[36m[dev-up]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev-up]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[dev-up]\033[0m %s\n' "$*" >&2; }

# ── Preflight ──────────────────────────────────────────────────────────────
need() { command -v "$1" >/dev/null 2>&1 || { err "missing tool: $1"; exit 1; }; }
need docker
[ "$NO_NGROK" -eq 1 ] || need ngrok
[ "$DB_ONLY" -eq 1 ] || need uv
[ "$WITH_WEB" -eq 1 ] && need npm

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  err ".env not found at $PROJECT_ROOT/.env (copy from .env.example)"
  exit 1
fi

# 確保 .venv 存在；若無則自動 uv sync（首次啟動）
if [ "$DB_ONLY" -ne 1 ] && [ ! -d "$PROJECT_ROOT/.venv" ]; then
  log "no .venv — running 'uv sync' (首次啟動會下載 deps，約 1–2 分鐘)"
  (cd "$PROJECT_ROOT" && uv sync) || { err "uv sync failed"; exit 1; }
fi

# 多服務模式：先檢查 port 衝突
if [ "$MULTI_SERVICE" -eq 1 ]; then
  check_port() {
    local port="$1" label="$2"
    if ss -tln 2>/dev/null | grep -q ":$port "; then
      err "port $port ($label) 已被占用，請先停掉占用者"
      ss -tln | grep ":$port " | head -3 >&2
      exit 1
    fi
  }
  check_port "$AGENT_PORT" agent
  [ "$WITH_API" -eq 1 ] && check_port "$API_PORT" api
  [ "$WITH_WEB" -eq 1 ] && check_port "$WEB_PORT" web
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
  if pgrep -f "ngrok http $AGENT_PORT" >/dev/null 2>&1; then
    warn "ngrok already running on :$AGENT_PORT — skipping launch"
    detect_ngrok_url
    return
  fi
  log "starting ngrok http $AGENT_PORT (log: $LOG_DIR/ngrok.log)"
  ngrok http "$AGENT_PORT" --log=stdout >"$LOG_DIR/ngrok.log" 2>&1 &
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

# ── 3. 背景啟動服務（多服務模式用） ────────────────────────────────────
start_bg_service() {
  local name="$1" cwd="$2" cmd="$3" port="$4"
  log "starting $name on :$port (background)"
  (
    cd "$cwd"
    nohup bash -c "$cmd" > "$LOG_DIR/${name}.log" 2>&1 &
    echo $! > "$LOG_DIR/${name}.pid"
  )
  for i in $(seq 1 60); do
    # 連得上即算 ready（不限 2xx）—— agent LINE gateway 只有 POST /callback，
    # GET / 會回 404，故用 -s 不用 -f（404 也代表 port 已起）。
    if curl -s -o /dev/null "http://127.0.0.1:$port" 2>/dev/null \
       || curl -sf "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      log "  ✓ $name ready ($i sec)"
      return 0
    fi
    sleep 1
  done
  err "$name 60s 內未 ready，看 log: $LOG_DIR/${name}.log"
  tail -20 "$LOG_DIR/${name}.log" >&2
  return 1
}

# ── 4. Cleanup trap（前景模式用） ──────────────────────────────────────
cleanup() {
  echo
  log "shutting down..."
  if [ -n "$NGROK_PID" ] && kill -0 "$NGROK_PID" 2>/dev/null; then
    kill "$NGROK_PID" 2>/dev/null || true
    log "ngrok stopped (pid=$NGROK_PID)"
  fi
  log "db container kept running — stop manually: docker stop $DB_CONTAINER"
}
[ "$MULTI_SERVICE" -eq 0 ] && trap cleanup EXIT INT TERM

# ── 5. Run ─────────────────────────────────────────────────────────────────
ensure_db
wait_db

if [ "$DB_ONLY" -eq 1 ]; then
  log "--db-only: skipping ngrok & uvicorn"
  trap - EXIT INT TERM
  exit 0
fi

[ "$NO_NGROK" -eq 0 ] && start_ngrok

# agent LINE gateway 需 LINE_CHANNEL_SECRET（env 或 agent/.env）。缺則無法起 gateway。
agent_has_line_creds() {
  [ -n "${LINE_CHANNEL_SECRET:-}" ] && return 0
  grep -qE '^LINE_CHANNEL_SECRET=.+' "$AGENT_DIR/.env" 2>/dev/null
}
AGENT_CMD="PORT=$AGENT_PORT uv run python scripts/line_gateway.py"

# ── 5a. 單一服務模式：agent 前景跑（LockCore LINE gateway）─────────────
if [ "$MULTI_SERVICE" -eq 0 ]; then
  if ! agent_has_line_creds; then
    err "agent LINE gateway 需 LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN（放 agent/.env）。"
    err "若只想跑 api/web，用：./scripts/dev/dev-up.sh --full（無 LINE 憑證會自動略過 agent）。"
    exit 1
  fi
  log "starting agent LINE gateway — http://127.0.0.1:$AGENT_PORT/callback  (Ctrl+C to stop)"
  log "  webhook: 把 ngrok https URL + /callback 填進 LINE Developers ▸ Messaging API"
  log "  測試:    用 LINE 對官方帳號傳「請派師傅來修」即可觸發轉真人 → AI 草擬問題卡"
  echo
  cd "$AGENT_DIR"
  exec env PORT="$AGENT_PORT" uv run python scripts/line_gateway.py
fi

# ── 5b. 多服務模式：全部背景 + summary ────────────────────────────────
AGENT_STARTED=0
if agent_has_line_creds; then
  start_bg_service agent "$AGENT_DIR" "$AGENT_CMD" "$AGENT_PORT"
  AGENT_STARTED=1
else
  log "⚠ 未偵測到 LINE_CHANNEL_SECRET（agent/.env）— 略過 agent LINE gateway，只起 api/web。"
fi

if [ "$WITH_API" -eq 1 ]; then
  start_bg_service api "$API_DIR" \
    "uv run uvicorn main:app --host 127.0.0.1 --port $API_PORT" "$API_PORT"
fi

if [ "$WITH_WEB" -eq 1 ]; then
  if [ ! -d "$WEB_DIR/node_modules" ]; then
    log "no node_modules — running 'npm install'..."
    (cd "$WEB_DIR" && npm install) || { err "npm install failed"; exit 1; }
  fi
  start_bg_service web "$WEB_DIR" \
    "npm run dev -- --port $WEB_PORT" "$WEB_PORT"
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
log "═══════════════════════════════════════════════"
log " 情境 A 啟動完成（本機 docker DB）"
log "═══════════════════════════════════════════════"
log "  db (docker)     : $DB_CONTAINER on :$DB_PORT"
[ "$AGENT_STARTED" -eq 1 ] && log "  agent (gateway) : pid $(cat "$LOG_DIR/agent.pid")  http://127.0.0.1:$AGENT_PORT/callback"
[ "$WITH_API" -eq 1 ] && log "  api             : pid $(cat "$LOG_DIR/api.pid")  http://127.0.0.1:$API_PORT"
[ "$WITH_WEB" -eq 1 ] && log "  web             : pid $(cat "$LOG_DIR/web.pid")  http://127.0.0.1:$WEB_PORT"
log "  internal token  : INTERNAL_API_TOKEN=$INTERNAL_API_TOKEN（api / agent 共用）"
log ""
log "驗證："
[ "$AGENT_STARTED" -eq 1 ] && log "  agent 用 LINE 傳「請派師傅來修」→ 後台 /problem-cards 選「AI 草擬」看草擬卡"
[ "$WITH_API" -eq 1 ] && log "  open http://127.0.0.1:$API_PORT/docs"
[ "$WITH_API" -eq 1 ] && log "  ADMIN_EMAIL=test@lock-ai.com ADMIN_PASSWORD=changeme123 ./tests/smoke/api.sh"
[ "$WITH_WEB" -eq 1 ] && log "  open http://127.0.0.1:$WEB_PORT/dashboard"
log ""
log "收尾：./scripts/dev/dev-down.sh --multi             # 停 agent / api / web"
log "      ./scripts/dev/dev-down.sh --multi --stop-db    # 連 docker DB 一起停"
log "═══════════════════════════════════════════════"
