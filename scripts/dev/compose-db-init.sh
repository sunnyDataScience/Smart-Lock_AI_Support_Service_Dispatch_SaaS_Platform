#!/usr/bin/env bash
# compose-db-init.sh — 派工方 stack 全新品牌空庫一次性初始化(CR-0112)
#
# 由 web/brand-portal/docker-compose.yml 的 db-init service(profile: init)在容器內執行,
# psql 連線參數走 PG* 環境變數(PGHOST=db)。套用順序同 scripts/dev/quickstart.sh:
#   SQL/Schema.sql → SQL/Schema_*.sql(字母序)→ SQL/migrations/*.sql(編號序)
#   → SQL/seeds(SEED_ORDER,FK 相依順序)
# 之後把 migrations 寫入 schema_migrations 追蹤表(同 redeploy-local.sh)。
#
# 冪等防護:偵測 users 表已有資料 → 視為已初始化,直接跳過(FORCE_INIT=1 可強套)。
set -euo pipefail

SQL_DIR="/init/SQL"

log() { echo "[db-init] $*"; }

# ── 已初始化偵測 ─────────────────────────────────────────────────────────
if [ "${FORCE_INIT:-0}" != "1" ]; then
  has_users=$(psql -tAc "SELECT to_regclass('public.users') IS NOT NULL" 2>/dev/null || echo f)
  if [ "$has_users" = "t" ]; then
    n=$(psql -tAc "SELECT count(*) FROM public.users" 2>/dev/null || echo 0)
    if [ "${n:-0}" -gt 0 ]; then
      log "偵測到 users 表已有 ${n} 筆資料 → 視為已初始化,跳過(FORCE_INIT=1 可強套)"
      exit 0
    fi
  fi
fi

apply() {
  local f="$1"
  log "套用 $(basename "$f")"
  # ON_ERROR_STOP=0:Schema/seeds 大量 idempotent 語句(IF NOT EXISTS / ON CONFLICT),
  # 容忍既存物件警告(同 quickstart.sh db_apply_file)
  psql -v ON_ERROR_STOP=0 -q -f "$f" || true
}

# ── 1. 基底 schema ──────────────────────────────────────────────────────
[ -f "$SQL_DIR/Schema.sql" ] && apply "$SQL_DIR/Schema.sql"
for f in "$SQL_DIR"/Schema_*.sql; do
  [ -e "$f" ] && apply "$f"
done

# ── 2. migrations(編號序)──────────────────────────────────────────────
for f in $(ls "$SQL_DIR"/migrations/*.sql 2>/dev/null | sort); do
  apply "$f"
done

# ── 3. migrations 追蹤(046 已建表;同 redeploy-local.sh 寫法)────────────
for f in $(ls "$SQL_DIR"/migrations/*.sql 2>/dev/null | sort); do
  base=$(basename "$f")
  ver="${base%%-*}"
  psql -q -c "INSERT INTO schema_migrations (version, filename)
              VALUES ('${ver}', '${base}') ON CONFLICT (version) DO NOTHING" || true
done

# ── 4. seeds(FK 相依順序,同 quickstart.sh SEED_ORDER)────────────────────
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
  [ -f "$SQL_DIR/seeds/$s" ] && apply "$SQL_DIR/seeds/$s"
done

log "初始化完成(真實感 demo 資料另跑:uv run python scripts/seed/realistic_demo_seed.py | psql ...)"
