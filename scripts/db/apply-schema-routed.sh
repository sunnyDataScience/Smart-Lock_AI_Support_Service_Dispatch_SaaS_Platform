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
#   ./scripts/db/apply-schema-routed.sh             # 套用（跳過該庫已登記的版本）
#   ./scripts/db/apply-schema-routed.sh --force-all # 不跳過，全部重跑（舊行為）
#
# 已登記於該庫 public.schema_migrations 的版本預設**不重跑**（2026-07-28 起）。
# 原本每次全跑，前提是每支 migration 都冪等——該前提被 016 推翻（守衛帶
# NOT LIKE '%sop%'，套用後就匹配不到，無守衛的 ADD CONSTRAINT 必炸），對已有
# 資料的庫執行會在第 16 支中斷。冪等性仍是第二道防線但不再是唯一防線。
# 記帳缺失的庫（無 schema_migrations 表或無該列）行為不變：照樣跑，靠冪等承接。
#
# record 走 ON CONFLICT DO NOTHING（保留既有 applied_at）。
# 安全：prod 執行前先 gcloud sql backups create --instance=lock-ai。
# ============================================================
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

DRY_RUN=0
FORCE_ALL=0
for a in "$@"; do
    [[ "$a" == "--dry-run" ]] && DRY_RUN=1
    [[ "$a" == "--force-all" ]] && FORCE_ALL=1
done

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
# 先建檔：全數跳過時沒有任何 psql 輸出重導進來，後面掃 ERROR 的 grep 會噴
# "No such file or directory" 而看起來像失敗。
: > "${LOG_FILE}"

apply_file() {  # $1=uri $2=file
    psql "$1" -v ON_ERROR_STOP=1 -f "$2" >> "${LOG_FILE}" 2>&1
}
# 已登記於該庫 schema_migrations 的版本 → 跳過（--force-all 可關閉）。
#
# 為什麼需要這道閘：本腳本原本每次都重跑「全部」migration，前提是每支都冪等。
# 該前提 2026-07-28 被推翻 —— 016 的 ADD CONSTRAINT 守衛帶 NOT LIKE '%sop%'，
# 套用過就再也匹配不到，重跑必炸（016 已於同一輪補 DROP IF EXISTS）。但靠「每支
# 都冪等」當唯一防線太脆：任何人新增一支忘了守衛，就會讓既有環境的 migration
# 全線中斷。已套用的不重跑才是 runner 該有的行為，冪等性退為第二道防線。
#
# 注意：只跳過「有登記」的。schema_migrations 缺表或缺列的庫（例如本次的技師庫、
# 平台庫）行為與過去完全相同——照樣全跑，靠冪等性承接。
already_applied() {  # $1=uri $2=ver
    [[ "${FORCE_ALL}" -eq 1 ]] && return 1
    local n
    n="$(psql "$1" -tA -c \
        "SELECT count(*) FROM public.schema_migrations WHERE version = '$2'" 2>/dev/null || echo 0)"
    [[ "${n:-0}" != "0" ]]
}
record() {  # $1=uri $2=ver $3=base
    psql "$1" -v ON_ERROR_STOP=1 -c \
        "CREATE TABLE IF NOT EXISTS public.schema_migrations(version TEXT PRIMARY KEY, filename TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now(), note TEXT);
         INSERT INTO public.schema_migrations(version,filename,note) VALUES ('$2','$3','applied') ON CONFLICT (version) DO NOTHING;" \
        >> "${LOG_FILE}" 2>&1
}

echo "== 分流套用 migrations（dry-run=${DRY_RUN}, force-all=${FORCE_ALL}）=="
# 用 |target| 形式的字串當集合，而非 associative array —— macOS 內建 bash 是 3.2，
# 沒有 declare -A，原寫法在本機一律報 "declare: -A: invalid option"（不致命但每次都噴錯）。
SKIPPED_TARGETS=""
APPLIED_COUNT=0
SKIPPED_COUNT=0
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
            case "${SKIPPED_TARGETS}" in *"|$t|"*) ;; *) SKIPPED_TARGETS="${SKIPPED_TARGETS}|$t|";; esac
            continue
        fi
        if already_applied "$u" "$ver"; then
            echo "      [已套用] target=$t ver=$ver → 跳過"
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
            continue
        fi
        if [[ "${DRY_RUN}" -eq 0 ]]; then
            if ! apply_file "$u" "$f"; then
                echo "FAIL: target=${t} migration=${base} 套用失敗；未登記 schema_migrations"
                echo "log: ${LOG_FILE}"
                exit 1
            fi
            if ! record "$u" "$ver" "$base"; then
                echo "FAIL: target=${t} migration=${base} 套用成功但記帳失敗"
                echo "log: ${LOG_FILE}"
                exit 1
            fi
            APPLIED_COUNT=$((APPLIED_COUNT + 1))
        fi
    done
done

if [[ "${DRY_RUN}" -eq 0 ]]; then
    echo ""
    echo "== 本次動作 =="
    echo "  實際套用 ${APPLIED_COUNT} 次 / 因已登記跳過 ${SKIPPED_COUNT} 次"
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
for t in brand tech platform; do
    case "${SKIPPED_TARGETS}" in
        *"|$t|"*) echo "WARN: target=$t 有 migration 但 URI 未設，未套用該庫";;
    esac
done

if [[ "${DRY_RUN}" -eq 0 ]]; then
    echo ""
    echo "== 自我驗證：多庫 migration drift-check（依 migrate-targets 對三庫比對）=="
    # POSTGRES_URI/TECH_POSTGRES_URI/PLATFORM_POSTGRES_URI 已在 env → 直接對照各庫
    if ! python3 "${PROJECT_ROOT}/scripts/ci/migration-drift-check.py"; then
        echo "FAIL: drift-check 報漂移；本次 migration 發布證據不得標記成功"
        exit 1
    fi
fi
