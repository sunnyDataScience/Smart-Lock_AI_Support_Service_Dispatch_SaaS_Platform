#!/usr/bin/env bash
# ============================================================
# scripts/db/apply-schema-routed.sh  (LOCK-62 item 2)
#   依「落庫目標」把 migration 分流到 品牌/技師/平台 三庫，並**逐庫記帳**
#   到各庫 public.schema_migrations。取代 apply-schema-prod.sh 的單庫限制
#   —— 那是 0724/0725 兩顆「該落技師庫卻只套品牌庫」地雷的根源。
#
# 落庫目標宣告（migration 檔頭，機讀）：
#   -- migrate-targets: brand            → 只套品牌庫（預設；未標注 = brand，向下相容）
#   -- migrate-targets: tech             → 只套技師庫
#   -- migrate-targets: brand,tech,platform  → 三庫都套（如動 users 這種各庫皆有的表）
#   目標名：brand=POSTGRES_URI / tech=TECH_POSTGRES_URI / platform=PLATFORM_POSTGRES_URI
#
# 用法（prod 經 cloud-sql-proxy，三庫同實例不同 database）：
#   export POSTGRES_URI=...            # 品牌庫（必填）
#   export TECH_POSTGRES_URI=...       # 技師庫（選填；未設則 target=tech 的 migration 跳過+WARN）
#   export PLATFORM_POSTGRES_URI=...   # 平台庫（選填）
#   ./scripts/db/apply-schema-routed.sh --dry-run   # 只印分流計畫不套用
#   ./scripts/db/apply-schema-routed.sh             # 套用
#
# 全 idempotent；record 走 ON CONFLICT DO NOTHING（保留既有 applied_at）。
# 安全：prod 執行前先 gcloud sql backups create --instance=lock-ai。
# ============================================================
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

DRY_RUN=0
for a in "$@"; do [[ "$a" == "--dry-run" ]] && DRY_RUN=1; done

[[ -z "${POSTGRES_URI:-}" ]] && { echo "FAIL: 需 export POSTGRES_URI（品牌庫，必填）"; exit 1; }

# 目標名 → URI（未設者留空 = 跳過該目標）
uri_for() {
    case "$1" in
        brand)    echo "${POSTGRES_URI:-}" ;;
        tech)     echo "${TECH_POSTGRES_URI:-}" ;;
        platform) echo "${PLATFORM_POSTGRES_URI:-}" ;;
        *)        echo "" ;;
    esac
}

# 讀 migration 檔頭 migrate-targets（無 → brand）。回逗號分隔小寫。
targets_of() {
    local f="$1" line
    line="$(grep -iE '^--[[:space:]]*migrate-targets:' "$f" | head -1 || true)"
    if [[ -z "$line" ]]; then echo "brand"; return; fi
    # 取 colon 後的 target 清單，只保留 [字母,] 到第一個非法字元為止（濾掉行內 (LOCK-62…) 註解）
    echo "$line" | sed -E 's/^.*migrate-targets:[[:space:]]*//I; s/[^a-zA-Z,].*$//' | tr 'A-Z' 'a-z'
}

LOG_DIR="${PROJECT_ROOT}/.dev-logs"; mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/apply-routed-$(date +%Y%m%d-%H%M%S).log"

apply_file() {  # $1=uri $2=file
    psql "$1" -v ON_ERROR_STOP=0 -f "$2" >> "${LOG_FILE}" 2>&1
}
record() {  # $1=uri $2=ver $3=base
    psql "$1" -v ON_ERROR_STOP=0 -c \
        "CREATE TABLE IF NOT EXISTS public.schema_migrations(version TEXT PRIMARY KEY, filename TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now(), note TEXT);
         INSERT INTO public.schema_migrations(version,filename,note) VALUES ('$2','$3','applied') ON CONFLICT (version) DO NOTHING;" \
        >> "${LOG_FILE}" 2>&1
}

echo "== 分流套用 migrations（dry-run=${DRY_RUN}）=="
declare -A SKIPPED
for f in SQL/migrations/*.sql; do
    case "$f" in *MIGRATION_REGISTRY*) continue;; esac
    base="$(basename "$f")"; ver="${base%%-*}"
    tgts="$(targets_of "$f")"
    printf "  %-46s → %s\n" "$base" "$tgts"
    IFS=',' read -ra TS <<< "$tgts"
    for t in "${TS[@]}"; do
        [[ -z "$t" ]] && continue
        u="$(uri_for "$t")"
        if [[ -z "$u" ]]; then
            echo "      [skip] target=$t 之 URI 未設 → 跳過（記入 WARN）"
            SKIPPED["$t"]=1; continue
        fi
        if [[ "${DRY_RUN}" -eq 0 ]]; then
            apply_file "$u" "$f"
            record "$u" "$ver" "$base"
        fi
    done
done

if [[ "${DRY_RUN}" -eq 0 ]]; then
    echo ""
    echo "== 各庫已追蹤 migration 數 =="
    for t in brand tech platform; do
        u="$(uri_for "$t")"; [[ -z "$u" ]] && { echo "  $t: (URI 未設)"; continue; }
        n="$(psql "$u" -tA -c "SELECT count(*) FROM public.schema_migrations" 2>/dev/null || echo '?')"
        echo "  $t: ${n} 筆"
    done
    echo ""
    echo "== 掃 log ERROR（忽略 already exists）=="
    grep -iE "^ERROR|ERROR:" "${LOG_FILE}" | grep -viE "already exists|does not exist, skipping" | head -40 || true
    echo "log: ${LOG_FILE}"
fi
for t in "${!SKIPPED[@]}"; do echo "WARN: target=$t 有 migration 但 URI 未設，未套用該庫"; done

if [[ "${DRY_RUN}" -eq 0 ]]; then
    echo ""
    echo "== 自我驗證：多庫 migration drift-check（依 migrate-targets 對三庫比對）=="
    # POSTGRES_URI/TECH_POSTGRES_URI/PLATFORM_POSTGRES_URI 已在 env → 直接對照各庫
    python3 "${PROJECT_ROOT}/scripts/ci/migration-drift-check.py" || \
        echo "  ⚠️ drift-check 報漂移（見上）——套用後仍有落差，人工確認"
fi
