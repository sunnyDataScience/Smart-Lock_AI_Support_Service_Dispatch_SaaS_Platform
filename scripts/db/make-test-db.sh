#!/usr/bin/env bash
# ============================================================
# scripts/db/make-test-db.sh — 建立可跑全套 pytest 的拋棄式 scratch DB
#
# 為什麼需要這支：pytest 單庫 fallback 的 POSTGRES_URI **就是本機 UAT 庫 5433**，
# 直接跑全套會把測試資料洩漏進業主手動 UAT 的同一顆庫（歷史事故：假的 intake_case /
# conversations / users 冒進 /admin/cases）。本腳本以「複製 → 補 migration」建立隔離副本，
# 全套跑完 UAT 庫零接觸。
#
# ⚠️ 別想從 SQL/*.sql 從零建：實測 base schema 需要 `SQL/Schema.sql` 先建表
# （`Schema_api_phase1.sql` 只是 ALTER TABLE 補欄位），且缺 pgvector 時
# case_entries / manual_chunks / sop_drafts 建不起來，連鎖失敗；即使補齊仍缺 seed，
# 259 支測試紅。複製既有庫才是可行路徑。
#
# 用法：
#   ./scripts/db/make-test-db.sh                 # 建庫並印出 POSTGRES_URI
#   ./scripts/db/make-test-db.sh --run           # 建庫後直接跑全套 pytest
#   ./scripts/db/make-test-db.sh --drop          # 只清除 scratch 庫
#
# 2026-07-27 實測基準：2091 passed / 13 failed（13 支為 seed 依賴，非程式回歸）。
# ============================================================
set -uo pipefail

CONTAINER="${CONTAINER:-lock-dispatch-locksmart-db-1}"
DB_USER="${DB_USER:-lock}"
SRC_DB="${SRC_DB:-lock_AI_data}"
SCRATCH_DB="${SCRATCH_DB:-lock_scratch_test}"
HOST_PORT="${HOST_PORT:-5433}"
DB_PASS="${DB_PASS:-0000}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
URI="postgresql://${DB_USER}:${DB_PASS}@localhost:${HOST_PORT}/${SCRATCH_DB}"

psql_scratch() { docker exec -i "${CONTAINER}" psql -U "${DB_USER}" -d "${SCRATCH_DB}" "$@"; }

if [[ "${1:-}" == "--drop" ]]; then
    docker exec "${CONTAINER}" psql -U "${DB_USER}" -d postgres -q \
        -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};"
    echo "✅ 已清除 ${SCRATCH_DB}"
    exit 0
fi

docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}" || {
    echo "FAIL: 找不到執行中的容器 ${CONTAINER}（本機 UAT 庫未啟動？）"; exit 1; }

echo "== 1/3 複製 ${SRC_DB} → ${SCRATCH_DB}（來源唯讀，UAT 庫零寫入）=="
docker exec "${CONTAINER}" psql -U "${DB_USER}" -d postgres -q \
    -c "DROP DATABASE IF EXISTS ${SCRATCH_DB};" \
    -c "CREATE DATABASE ${SCRATCH_DB} OWNER ${DB_USER};" 2>&1 | grep -v NOTICE || true
docker exec "${CONTAINER}" sh -c \
    "pg_dump -U ${DB_USER} ${SRC_DB} | psql -q -U ${DB_USER} -d ${SCRATCH_DB}" 2>&1 \
    | grep -E "^ERROR" | head -5 || true

echo "== 2/3 補套全部 migration（本機 UAT 庫常落後數支，例如缺 users.email_bidx）=="
applied=0
for f in "${ROOT}"/SQL/migrations/*.sql; do
    case "$f" in *MIGRATION_REGISTRY*) continue;; esac
    psql_scratch -v ON_ERROR_STOP=0 -q < "$f" >/dev/null 2>&1
    applied=$((applied + 1))
done
echo "   已套 ${applied} 支"

echo "== 3/3 檢查 =="
tables="$(psql_scratch -tA -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('public','saas')")"
bidx="$(psql_scratch -tA -c \
    "SELECT count(*) FROM information_schema.columns WHERE table_name='users' AND column_name='email_bidx'")"
echo "   表數=${tables}  users.email_bidx=${bidx}（應為 1）"
echo ""
echo "POSTGRES_URI=\"${URI}\""

if [[ "${1:-}" == "--run" ]]; then
    echo ""
    echo "== 跑全套 pytest（對 scratch 庫；UAT 庫零接觸）=="
    cd "${ROOT}/api" || exit 1
    POSTGRES_URI="${URI}" env -u TECH_POSTGRES_URI -u PLATFORM_POSTGRES_URI \
        uv run pytest -q
fi
