#!/usr/bin/env bash
# scripts/dev/dev-up-gcp.sh — 情境 B（開發 + GCP Cloud SQL）一鍵啟動
#
# 對應 scripts/README.md「情境 B」流程：
#   cloud-sql-proxy → agent (8000) → api (8001) → web (3000)
# 三個服務全部背景跑，PID 寫進 .dev-logs/{agent,api,web}.pid
#
# 前置條件（必須）：
#   1. gcloud auth login                       # 互動式登入
#   2. gcloud auth application-default login   # ADC（cloud-sql-proxy 要）
#   3. .env.gcp 存在且 POSTGRES_URI 已是真值（用 --fetch 自動補）
#
# Usage:
#   ./scripts/dev/dev-up-gcp.sh                   # 預設：proxy + agent + api + web 全起
#   ./scripts/dev/dev-up-gcp.sh --fetch           # 先從 Secret Manager 拉最新 secret
#   ./scripts/dev/dev-up-gcp.sh --no-web          # 跳過 next.js（純後端）
#   ./scripts/dev/dev-up-gcp.sh --no-api          # 跳過 api（只 agent）
#   ./scripts/dev/dev-up-gcp.sh --agent-only      # 只 agent
#
# 收尾用 ./scripts/dev/dev-down.sh

set -euo pipefail

# ── 路徑 ──────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

# ── Ports（README 情境 B 一致）──
AGENT_PORT="8000"
API_PORT="8001"
WEB_PORT="3000"
PROXY_PORT="5432"

# ── CLI flags ──
FETCH=0
NO_WEB=0
NO_API=0
AGENT_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --fetch)      FETCH=1 ;;
    --no-web)     NO_WEB=1 ;;
    --no-api)     NO_API=1 ;;
    --agent-only) NO_WEB=1; NO_API=1; AGENT_ONLY=1 ;;
    -h|--help)    sed -n '2,21p' "$0"; exit 0 ;;
    *)  echo "[dev-up-gcp] 未知參數: $arg"; echo "  用 -h 看說明"; exit 1 ;;
  esac
done

# ── Logging helpers ──
log()  { printf '\033[36m[dev-up-gcp]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[dev-up-gcp]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[dev-up-gcp]\033[0m %s\n' "$*" >&2; }

need() { command -v "$1" >/dev/null 2>&1 || { err "missing tool: $1"; exit 1; }; }

# ── Preflight ─────────────────────────────────────────────────────────
log "preflight 檢查"

need gcloud
need uv
need docker  # cloud-sql-proxy 不要 docker，但 web 開發/Dockerfile 需要
[ "$NO_WEB" -eq 1 ] || need npm

# gcloud 登入狀態
if ! gcloud auth print-access-token >/dev/null 2>&1; then
  err "gcloud 未登入。請執行: gcloud auth login"
  exit 1
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  err "ADC 未設定。請執行: gcloud auth application-default login"
  exit 1
fi

# 5432 / 8000 / 8001 / 3000 是否被占
check_port() {
  local port="$1" label="$2"
  if ss -tln 2>/dev/null | grep -q ":$port "; then
    err "port $port ($label) 已被占用，請先停掉占用者或改 port"
    ss -tln | grep ":$port " | head -3 >&2
    return 1
  fi
}
check_port "$PROXY_PORT" cloud-sql-proxy
[ "$AGENT_ONLY" -eq 1 ] || true
check_port "$AGENT_PORT" agent
[ "$NO_API" -eq 1 ] || check_port "$API_PORT" api
[ "$NO_WEB" -eq 1 ] || check_port "$WEB_PORT" web

# 確保 .venv 存在（uv 主導的依賴解決）
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  log "no .venv — running 'uv sync' (首次啟動會下載 deps)"
  (cd "$PROJECT_ROOT" && uv sync) || { err "uv sync failed"; exit 1; }
fi

# ── Step 1: env 切到 GCP（可選 fetch） ────────────────────────────────
log "step 1: 切 .env 到 GCP 模式"
if [ "$FETCH" -eq 1 ]; then
  "$PROJECT_ROOT/scripts/env/use-gcp.sh" --fetch
else
  if [ ! -f "$PROJECT_ROOT/.env.gcp" ]; then
    err ".env.gcp 不存在"
    err "請執行: $0 --fetch"
    exit 1
  fi
  # 只在 POSTGRES_URI / PG_VECTOR_URI 兩行檢查 placeholder（避免誤判註解）
  if grep -E "^(POSTGRES_URI|PG_VECTOR_URI)=" "$PROJECT_ROOT/.env.gcp" | grep -q "<PASSWORD>"; then
    err ".env.gcp 的 POSTGRES_URI / PG_VECTOR_URI 仍含 <PASSWORD> placeholder"
    err "請執行: $0 --fetch（從 Secret Manager 拉真實密碼）"
    exit 1
  fi
  "$PROJECT_ROOT/scripts/env/use-gcp.sh"
fi

# 確認 .env 有 api 服務必要的 JWT 簽名 key（不是 DB 相關，是 api 本地簽名用）
# 沒這個 key 的話 /api/v1/auth/login 會在簽 token 時 500
if [ "$NO_API" -ne 1 ] && ! grep -qE '^API_JWT_SECRET_KEY="?[^<"]+' "$PROJECT_ROOT/.env"; then
  err ".env 缺 API_JWT_SECRET_KEY（或仍是 placeholder）"
  err "  生成方式: openssl rand -hex 32"
  err "  範例: echo \"API_JWT_SECRET_KEY=\\\"\$(openssl rand -hex 32)\\\"\" >> .env.gcp"
  err "  再重跑 $0"
  exit 1
fi

# ── Step 2: cloud-sql-proxy ───────────────────────────────────────────
log "step 2: 啟 cloud-sql-proxy"
"$PROJECT_ROOT/scripts/dev/proxy-up.sh"

# 從 PID file 確認 proxy 仍在
if [ ! -f "$LOG_DIR/cloud-sql-proxy.pid" ] || ! kill -0 "$(cat "$LOG_DIR/cloud-sql-proxy.pid")" 2>/dev/null; then
  err "cloud-sql-proxy 啟動失敗，檢查 $LOG_DIR/cloud-sql-proxy.log"
  exit 1
fi

# ── Step 3: agent (port 8000) ─────────────────────────────────────────
log "step 3: 啟 agent on :$AGENT_PORT"
(
  cd "$PROJECT_ROOT/agent"
  nohup uv run uvicorn app:app --host 127.0.0.1 --port "$AGENT_PORT" \
    > "$LOG_DIR/agent.log" 2>&1 &
  echo $! > "$LOG_DIR/agent.pid"
)

# 等 /health
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$AGENT_PORT/health" >/dev/null 2>&1; then
    log "  ✓ agent ready ($i sec)"
    break
  fi
  sleep 1
  if (( i == 60 )); then
    err "agent 60s 內未 ready，看 log: $LOG_DIR/agent.log"
    tail -20 "$LOG_DIR/agent.log" >&2
    exit 1
  fi
done

# ── Step 4: api (port 8001) ───────────────────────────────────────────
if [ "$NO_API" -ne 1 ]; then
  log "step 4: 啟 api on :$API_PORT"
  (
    cd "$PROJECT_ROOT/api"
    nohup uv run uvicorn main:app --host 127.0.0.1 --port "$API_PORT" \
      > "$LOG_DIR/api.log" 2>&1 &
    echo $! > "$LOG_DIR/api.pid"
  )

  for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1; then
      log "  ✓ api ready ($i sec)"
      break
    fi
    sleep 1
    if (( i == 30 )); then
      err "api 30s 內未 ready，看 log: $LOG_DIR/api.log"
      tail -20 "$LOG_DIR/api.log" >&2
      exit 1
    fi
  done
fi

# ── Step 5: web (port 3000) ───────────────────────────────────────────
if [ "$NO_WEB" -ne 1 ]; then
  log "step 5: 啟 web (next.js dev) on :$WEB_PORT"
  if [ ! -d "$PROJECT_ROOT/web/node_modules" ]; then
    log "  no node_modules — running 'npm install'..."
    (cd "$PROJECT_ROOT/web" && npm install) || { err "npm install failed"; exit 1; }
  fi
  (
    cd "$PROJECT_ROOT/web"
    nohup npm run dev > "$LOG_DIR/web.log" 2>&1 &
    echo $! > "$LOG_DIR/web.pid"
  )

  for i in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:$WEB_PORT" >/dev/null 2>&1; then
      log "  ✓ web ready ($i sec)"
      break
    fi
    sleep 1
    if (( i == 60 )); then
      warn "web 60s 內未 ready（next dev 首次編譯較慢，可能仍在 compile）"
      warn "  log: $LOG_DIR/web.log"
      break
    fi
  done
fi

# ── Summary ───────────────────────────────────────────────────────────
echo ""
log "═══════════════════════════════════════════════"
log " 情境 B 啟動完成（連 GCP Cloud SQL）"
log "═══════════════════════════════════════════════"
log "  cloud-sql-proxy : pid $(cat "$LOG_DIR/cloud-sql-proxy.pid")"
log "  agent           : pid $(cat "$LOG_DIR/agent.pid")  http://127.0.0.1:$AGENT_PORT"
[ "$NO_API" -ne 1 ] && log "  api             : pid $(cat "$LOG_DIR/api.pid")  http://127.0.0.1:$API_PORT"
[ "$NO_WEB" -ne 1 ] && log "  web             : pid $(cat "$LOG_DIR/web.pid")  http://127.0.0.1:$WEB_PORT"
log ""
log "驗證："
log "  curl http://127.0.0.1:$AGENT_PORT/health"
[ "$NO_API" -ne 1 ] && log "  curl http://127.0.0.1:$API_PORT/health"
[ "$NO_API" -ne 1 ] && log "  open http://127.0.0.1:$API_PORT/docs"
[ "$NO_WEB" -ne 1 ] && log "  open http://127.0.0.1:$WEB_PORT/dashboard"
log ""
log "⚠️  連的是 GCP Cloud SQL prod 資料！"
log "    禁忌：clean_data.py / quality_check / 真實 LINE webhook"
log ""
log "收尾：./scripts/dev/dev-down.sh --multi --use-local"
log "═══════════════════════════════════════════════"
