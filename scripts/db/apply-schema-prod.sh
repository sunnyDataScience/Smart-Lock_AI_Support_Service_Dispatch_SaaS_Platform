#!/usr/bin/env bash
# ============================================================
# scripts/db/apply-schema-prod.sh
#   把完整 schema（Schema.sql + Schema_*.sql + migrations/*.sql）依正規順序
#   套用到**單一目標 DB**。全部 idempotent（ADD COLUMN IF NOT EXISTS 等），已存在的略過。
#   **不灌 demo seed**（prod 只補 schema，不動業務資料）。
#
#   ⚠️ 多庫（品牌/技師/平台）分流請改用 apply-schema-routed.sh（LOCK-62 item 2）——
#      本單庫腳本把所有 migration 套同一庫，是 0724/0725「該落技師庫卻只套品牌庫」地雷
#      的根源。routed 版讀 migration 檔頭 `-- migrate-targets:` 分流並逐庫記帳。
#
#   順序對齊 scripts/dev/quickstart.sh：
#     1) SQL/Schema.sql
#     2) SQL/Schema_*.sql（字母序；Schema.sql 不含底線故不重複）
#     2b) SQL/platform/Schema_platform.sql（單庫 fallback：PLATFORM_POSTGRES_URI
#         未設時平台表住主庫，platform console 端點才有表可查。內含創始品牌
#         locksmart 的租戶名冊冪等補登 —— 屬名冊基準資料而非 demo seed）
#     3) SQL/migrations/*.sql（編號序）
#
# 用法（prod 經 cloud-sql-proxy）：
#   ./scripts/dev/proxy-up.sh                       # proxy → 127.0.0.1:5432
#   export POSTGRES_URI="postgresql://lock-ai:<DB_PASSWORD>@127.0.0.1:5432/lock-ai-db"
#   ./scripts/db/apply-schema-prod.sh               # 套用
#   ./scripts/dev/proxy-down.sh
#
# 安全：執行前請先建 Cloud SQL 備份（gcloud sql backups create --instance=lock-ai）。
# ============================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ -z "${POSTGRES_URI:-}" ]]; then
    echo "FAIL: 請先 export POSTGRES_URI（指向目標 DB，prod 經 proxy 為 127.0.0.1:5432）"
    exit 1
fi

LOG_DIR="${PROJECT_ROOT}/.dev-logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/apply-schema-prod-$(date +%Y%m%d-%H%M%S).log"
echo "套用 log → ${LOG_FILE}"

# ON_ERROR_STOP=0：idempotent 重跑時容忍 benign 警告（already exists）；
# 真正錯誤會留在 log，結尾用 grep 攔出來人工確認。
apply() {
    local f="$1"
    [[ -f "$f" ]] || return 0
    echo "  → ${f}"
    echo "===== ${f} =====" >> "${LOG_FILE}"
    psql "${POSTGRES_URI}" -v ON_ERROR_STOP=0 -f "$f" >> "${LOG_FILE}" 2>&1
}

echo "== 1) Schema.sql =="
apply "SQL/Schema.sql"

echo "== 2) Schema_*.sql =="
for f in SQL/Schema_*.sql; do apply "$f"; done

echo "== 2b) platform/Schema_platform.sql（單庫 fallback：平台表住主庫）=="
apply "SQL/platform/Schema_platform.sql"

echo "== 3) migrations/*.sql =="
for f in SQL/migrations/*.sql; do
    case "$f" in *MIGRATION_REGISTRY*) continue;; esac
    apply "$f"
done

# CR-0038 階段0：記錄已套用 migration 到 public.schema_migrations（由 046 建表）。
# 必須在 migration 迴圈「之後」做，因 046 在迴圈中才建出 schema_migrations 表。
# ON CONFLICT DO NOTHING：保留既有 applied_at（如 035/045 首套的真實時間），重跑不覆寫。
echo "== 4) 記錄已套用 migration → schema_migrations（CR-0038 漂移追蹤）=="
for f in SQL/migrations/*.sql; do
    case "$f" in *MIGRATION_REGISTRY*) continue;; esac
    base="$(basename "$f")"
    ver="${base%%-*}"
    psql "${POSTGRES_URI}" -v ON_ERROR_STOP=0 -c \
        "INSERT INTO public.schema_migrations(version, filename, note) VALUES ('${ver}', '${base}', 'applied') ON CONFLICT (version) DO NOTHING;" \
        >> "${LOG_FILE}" 2>&1
done
psql "${POSTGRES_URI}" -t -A -c "SELECT '已追蹤 migration 數：'||count(*) FROM public.schema_migrations;" 2>/dev/null || true

echo ""
echo "== 完成。掃描 log 中的 ERROR（忽略 'already exists' 類 NOTICE）=="
grep -iE "^ERROR|ERROR:" "${LOG_FILE}" | grep -viE "already exists|does not exist, skipping" | head -40 || true
echo "（若上面無輸出 = 無未預期錯誤）完整 log：${LOG_FILE}"
