#!/usr/bin/env bash
# scripts/dev/quickstart.sh
# 一鍵啟動本地展示環境：
#   1. PostgreSQL Docker (pgvector/pg17)
#   2. 套用 schema + migrations + 既有 seeds
#   3. 套用 realistic demo seed（真實感大量假資料）
#   4. 啟動 backend (uvicorn :8001)
#   5. 啟動 frontend (next dev :3000)
#   6. 印出網址，Ctrl+C 收乾淨
#
# Usage:
#   ./scripts/dev/quickstart.sh                # 完整啟動 (含 demo seed)
#   ./scripts/dev/quickstart.sh --fresh        # 砍掉重來 (drop DB + 重新 seed)
#   ./scripts/dev/quickstart.sh --no-seed      # 跳過 realistic demo seed
#   ./scripts/dev/quickstart.sh --backend-only # 只起 DB + backend
#
# 環境需求：docker / uv / npm

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

LOG_DIR="$PROJECT_ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

DB_CONTAINER="lock_AI"
DB_IMAGE="pgvector/pgvector:pg17"
DB_USER="lock"
DB_PASS="0000"
DB_NAME="lock_AI_data"
DB_PORT="5433"

API_PORT="8001"
WEB_PORT="3000"

FRESH=0
NO_SEED=0
BACKEND_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --fresh) FRESH=1 ;;
    --no-seed) NO_SEED=1 ;;
    --backend-only) BACKEND_ONLY=1 ;;
    -h|--help) sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[36m[quickstart]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[quickstart]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[quickstart]\033[0m %s\n' "$*" >&2; }
ok()   { printf '\033[32m[quickstart]\033[0m %s\n' "$*"; }

need() { command -v "$1" >/dev/null 2>&1 || { err "缺少工具: $1"; exit 1; }; }

# ── Preflight ──────────────────────────────────────────────────────────────
log "preflight..."
need docker
need uv
[ "$BACKEND_ONLY" -eq 1 ] || need npm
[ -f "$PROJECT_ROOT/.env" ] || { err ".env 不存在，請從 .env.example 複製"; exit 1; }

# CR-0022：internal service token，讓 backend 的 /internal/* ingest 端點可用（否則回 503）。
# 可用環境變數覆蓋；export 讓背景啟動的 backend 子行程繼承。
export INTERNAL_API_TOKEN="${INTERNAL_API_TOKEN:-dev-internal-token}"

# ── 1. DB ──────────────────────────────────────────────────────────────────
db_exec() { docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" "$@"; }
db_apply_file() {
  local f="$1"
  docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=0 < "$f" >/dev/null 2>>"$LOG_DIR/db-apply.log" || warn "  apply $f 有警告（已記錄到 $LOG_DIR/db-apply.log）"
}

if [ "$FRESH" -eq 1 ]; then
  log "--fresh 模式：移除舊 DB container"
  docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
fi

if docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  log "DB container 已運行 :$DB_PORT"
elif docker ps -a --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  log "啟動既有 container"
  docker start "$DB_CONTAINER" >/dev/null
else
  log "建立新 container ($DB_IMAGE)"
  docker run --name "$DB_CONTAINER" \
    -e POSTGRES_USER="$DB_USER" \
    -e POSTGRES_PASSWORD="$DB_PASS" \
    -e POSTGRES_DB="$DB_NAME" \
    -p "$DB_PORT:5432" \
    -d "$DB_IMAGE" >/dev/null
fi

log "等待 postgres ready"
for i in $(seq 1 30); do
  if docker exec "$DB_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" -q 2>/dev/null; then
    ok "postgres ready (${i}s)"
    break
  fi
  sleep 1
  [ "$i" = 30 ] && { err "postgres 30s 內未 ready"; exit 1; }
done

# ── 2. Apply schema (only if first run or --fresh) ─────────────────────────
SCHEMA_INITIALIZED=$(db_exec -tAc "SELECT to_regclass('users')" 2>/dev/null || echo "")
if [ -z "$SCHEMA_INITIALIZED" ] || [ "$SCHEMA_INITIALIZED" = "" ] || [ "$FRESH" -eq 1 ]; then
  log "套用 Schema.sql + Schema_*.sql + migrations/"
  db_apply_file "SQL/Schema.sql"
  for f in SQL/Schema_*.sql; do
    [ -f "$f" ] && db_apply_file "$f"
  done
  for f in SQL/migrations/*.sql; do
    [ -f "$f" ] && db_apply_file "$f"
  done
  ok "schema 套用完成"
else
  log "schema 已存在，跳過初始化（若需重做請加 --fresh）"
fi

# ── 3. Existing seeds (admin / technicians demo / ...) ─────────────────────
log "套用既有 seeds (admin + dispatcher + demo tech + ...)"
SEED_ORDER=(
  _admin_user.sql
  dispatcher_user.sql
  rbac_role_users.sql
  technicians.sql
  pricing_rules.sql
  inventory_items.sql
  manuals.sql
  conversations.sql
  problem_cards.sql
  work_orders.sql
  invoices.sql
  vouchers.sql
  warranty_claims.sql
  disputes.sql
  refund_requests.sql
  settlements.sql
  dispatch_logs.sql
  family_reviews.sql
  sentiment_alerts.sql
  sop_drafts.sql
)
for s in "${SEED_ORDER[@]}"; do
  [ -f "SQL/seeds/$s" ] && db_apply_file "SQL/seeds/$s"
done
ok "既有 seeds 完成"

# ── 4. Realistic demo seed ─────────────────────────────────────────────────
if [ "$NO_SEED" -ne 1 ]; then
  log "產生並套用 realistic demo seed（~50 客戶 / 80 工單 / 60 發票 / 30 保固 / 18 爭議 / 25 對帳結算 / 40 庫存 / 20 退款）"
  uv run python scripts/seed/realistic_demo_seed.py 2>"$LOG_DIR/seed.stderr" | db_exec >/dev/null 2>>"$LOG_DIR/seed.stderr" || warn "  seed 套用有警告（log: $LOG_DIR/seed.stderr）"
  ok "realistic demo seed 套用完成"
fi

# ── 5. Verify counts ───────────────────────────────────────────────────────
log "驗證資料量"
CNT=$(db_exec -tAc "SELECT
  (SELECT count(*) FROM users WHERE role='line_user') || ' 客戶 / ' ||
  (SELECT count(*) FROM technicians) || ' 技師 / ' ||
  (SELECT count(*) FROM work_orders) || ' 工單 / ' ||
  (SELECT count(*) FROM invoices) || ' 發票 / ' ||
  (SELECT count(*) FROM warranty_claims) || ' 保固 / ' ||
  (SELECT count(*) FROM disputes) || ' 爭議 / ' ||
  (SELECT count(*) FROM inventory_items) || ' 庫存品項'
" 2>/dev/null || echo "(統計失敗)")
ok "目前 DB: $CNT"

# ── 6. Backend ─────────────────────────────────────────────────────────────
start_bg() {
  local name="$1" cmd="$2" port="$3"
  log "啟動 $name (背景) on :$port"
  bash -c "$cmd" >"$LOG_DIR/${name}.log" 2>&1 &
  echo $! >"$LOG_DIR/${name}.pid"
  for i in $(seq 1 60); do
    if curl -sf "http://127.0.0.1:$port" >/dev/null 2>&1 \
       || curl -sf "http://127.0.0.1:$port/openapi.json" >/dev/null 2>&1; then
      ok "  $name ready ($i s)"
      return 0
    fi
    sleep 1
  done
  err "$name 60s 內未 ready，log: $LOG_DIR/${name}.log"
  tail -20 "$LOG_DIR/${name}.log" >&2
  return 1
}

# 確保 .venv 存在
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  log "首次啟動：uv sync"
  uv sync >>"$LOG_DIR/uv-sync.log" 2>&1
fi

API_PID=""
start_bg backend "cd '$PROJECT_ROOT/api' && uv run uvicorn main:app --host 0.0.0.0 --port $API_PORT" "$API_PORT" || true
API_PID=$(cat "$LOG_DIR/backend.pid" 2>/dev/null || echo "")

# ── 7. Frontend ────────────────────────────────────────────────────────────
WEB_PID=""
if [ "$BACKEND_ONLY" -ne 1 ]; then
  if [ ! -d "$PROJECT_ROOT/web/node_modules" ]; then
    log "首次啟動：npm install (web)"
    (cd "$PROJECT_ROOT/web" && npm install >>"$LOG_DIR/npm-install.log" 2>&1)
  fi
  start_bg frontend "cd '$PROJECT_ROOT/web' && npm run dev -- --port $WEB_PORT" "$WEB_PORT" || true
  WEB_PID=$(cat "$LOG_DIR/frontend.pid" 2>/dev/null || echo "")
fi

# ── 8. Print URLs ──────────────────────────────────────────────────────────
echo
ok "════════════════════════════════════════════════════════════════"
ok "  ✓ 開發環境就緒"
ok "════════════════════════════════════════════════════════════════"
echo "  Frontend (admin):  http://localhost:$WEB_PORT"
echo "  Backend API:       http://localhost:$API_PORT"
echo "  API docs:          http://localhost:$API_PORT/docs"
echo "  PostgreSQL:        localhost:$DB_PORT  (lock / 0000 / lock_AI_data)"
echo
echo "  登入 admin 帳號:    test@lock-ai.com / changeme123"
echo
echo "  常用後台頁面:"
echo "    /admin/dispatch-queue           派工佇列"
echo "    /work-orders                    工單列表"
echo "    /admin/customers                客戶主檔"
echo "    /admin/warranty-claims          保固索賠"
echo "    /admin/disputes                 爭議仲裁"
echo "    /accounting                     月結算"
echo "    /admin/inventory                庫存"
echo "    /admin/reports/kpi              KPI 儀表板"
echo
echo "  收尾:    Ctrl+C  (停 backend/frontend；DB 容器保留)"
echo "  砍 DB:   docker rm -f $DB_CONTAINER"
echo "  Logs:    tail -f $LOG_DIR/backend.log  /  $LOG_DIR/frontend.log"
ok "════════════════════════════════════════════════════════════════"

# ── 9. Trap + wait ─────────────────────────────────────────────────────────
cleanup() {
  echo
  log "shutting down..."
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null && log "backend 已停 ($API_PID)" || true
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null && log "frontend 已停 ($WEB_PID)" || true
  log "DB 容器保留中，停止用：docker stop $DB_CONTAINER"
  exit 0
}
trap cleanup INT TERM

# 等使用者 Ctrl+C
log "（按 Ctrl+C 停止 backend/frontend）"
while true; do sleep 60; done
