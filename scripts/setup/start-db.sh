#!/usr/bin/env bash
# start-db.sh — 啟動 Postgres + 灌 schema + 灌 seeds
# Idempotent：第一次跑會 run；後續跑只會 start + skip 已建表
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
cd "$REPO_ROOT"

log_title "Stage 1/4 — 資料庫"

# 1. Container：不存在就 run，存在但停了就 start，已在跑就略過
if ! docker ps -a --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
  log_step "建立並啟動 ${DB_CONTAINER} container"
  docker run -d \
    --name "$DB_CONTAINER" \
    -e POSTGRES_USER=lock \
    -e POSTGRES_PASSWORD=0000 \
    -e POSTGRES_DB=lock_AI_data \
    -p ${DB_HOST_PORT}:5432 \
    -v lock_AI_data:/var/lib/postgresql/data \
    pgvector/pgvector:pg17 >/dev/null
  log_ok "Container 已建立"
elif ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
  log_step "啟動既有 ${DB_CONTAINER} container"
  docker start "$DB_CONTAINER" >/dev/null
  log_ok "Container 已啟動"
else
  log_ok "${DB_CONTAINER} 已在運行"
fi

# 2. 等 Postgres 接受連線
log_step "等待 Postgres 接受連線"
i=0
until docker exec "$DB_CONTAINER" pg_isready -U lock -d lock_AI_data >/dev/null 2>&1; do
  sleep 1
  ((i++))
  if (( i >= 30 )); then
    log_err "Postgres 啟動超時（30s）"
    exit 1
  fi
done
log_ok "Postgres ready"

# 3. 檢查 schema 是否已建（看 users 表）
HAS_USERS=$(docker exec "$DB_CONTAINER" psql -U lock -d lock_AI_data -tAc \
  "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='users');" 2>/dev/null || echo "f")

if [[ "$HAS_USERS" == "t" ]]; then
  log_ok "Schema 已存在，略過建表"
else
  log_step "灌 Schema（4 個 .sql 檔依序執行）"
  for sql in SQL/Schema.sql SQL/Schema_harness_migration.sql SQL/Schema_v2_extensions.sql SQL/Schema_api_phase1.sql; do
    if [[ ! -f "$sql" ]]; then
      log_warn "找不到 $sql，略過"
      continue
    fi
    log_info "  ↳ $sql"
    docker cp "$sql" "$DB_CONTAINER:/tmp/schema.sql"
    docker exec "$DB_CONTAINER" psql -U lock -d lock_AI_data -q -f /tmp/schema.sql >/dev/null 2>&1 || {
      log_warn "  $sql 部分語句失敗（多為 IF NOT EXISTS / NOTICE，可忽略）"
    }
  done
  log_ok "Schema 建立完成"
fi

# 4. 檢查 seed 是否已灌（看 admin 帳號）
HAS_ADMIN=$(docker exec "$DB_CONTAINER" psql -U lock -d lock_AI_data -tAc \
  "SELECT COUNT(*) FROM users WHERE email='admin@example.com';" 2>/dev/null || echo "0")

if [[ "$HAS_ADMIN" -gt 0 ]]; then
  log_ok "Seed 已灌（admin@example.com 存在）"
else
  log_step "灌 Seeds（依字母順序，_admin_user.sql 因 _ 前綴最先跑）"
  if ls SQL/seeds/*.sql >/dev/null 2>&1; then
    for f in $(ls SQL/seeds/*.sql | sort); do
      log_info "  ↳ $(basename "$f")"
      docker cp "$f" "$DB_CONTAINER:/tmp/seed.sql"
      docker exec "$DB_CONTAINER" psql -U lock -d lock_AI_data -q -f /tmp/seed.sql >/dev/null 2>&1 || {
        log_warn "  $(basename "$f") 部分失敗（重複 INSERT 會跳過，通常不影響）"
      }
    done
    log_ok "Seeds 灌完"
  else
    log_warn "找不到 SQL/seeds/，前端列表頁會空白"
  fi
fi

# 5. 摘要
echo ""
log_ok "DB 就緒：postgresql://lock:0000@localhost:${DB_HOST_PORT}/lock_AI_data"
log_info "進去看資料：docker exec -it $DB_CONTAINER psql -U lock -d lock_AI_data"
