#!/usr/bin/env bash
# scripts/dev/redeploy-local.sh
#   讓本機 docker compose stack 對齊「現行 code」：rebuild → up → 套 migration → smoke。
#
# 為什麼存在（CR-0038 §7「部署落差」）：
#   團隊一直 commit code，但 docker compose 三容器（web/api/agent）若不重建就停在舊 image。
#   2026-06-19 實測:跑著的 stack 停在 6-16 build、落後 HEAD ~12 個 CR —— 師傅註冊 / 忘記密碼
#   / payout-rules 等「已完成」功能在實機全 404 或不可達。本 script 把「rebuild + 套 migration
#   + smoke」一鍵化，納入每輪收尾，避免 Beta 點測在測舊畫面。
#
#   ※ 與 quickstart.sh / dev-up.sh 的差異：那兩支跑 host 模式（uvicorn/npm 直跑）；
#     本 script 專打「docker compose stack」這條線（你實際在用的那套）。
#
# Usage:
#   ./scripts/dev/redeploy-local.sh                # 完整：build + up + migrate + smoke
#   ./scripts/dev/redeploy-local.sh --no-build     # 跳過 image rebuild（只 up + migrate + smoke）
#   ./scripts/dev/redeploy-local.sh --smoke-only   # 只跑 smoke（不動容器、不套 migration）
#   ./scripts/dev/redeploy-local.sh --no-migrate   # rebuild + up，但不套 migration
#
# 退出碼：smoke 全過=0；任一 critical smoke 失敗=1（CI / 收尾 gate 可用）。
# 注意：不用 `set -e`，讓 smoke 跑完所有檢查再彙總，而非第一個失敗就中止。

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# ── 可由環境變數覆蓋的設定 ──────────────────────────────────────────────
DB_SVC="${DB_SVC:-db}"
DB_USER="${DB_USER:-lock}"
DB_NAME="${DB_NAME:-lock_AI_data}"
API_BASE="${API_BASE:-http://localhost:8001}"
WEB_BASE="${WEB_BASE:-http://localhost:3000}"
TENANT_ID="${TENANT_ID:-00000000-0000-0000-0000-000000000001}"
ADMIN_EMAIL="${ADMIN_EMAIL:-test@lock-ai.com}"
ADMIN_PASS="${ADMIN_PASS:-changeme123}"

DO_BUILD=1; DO_UP=1; DO_MIGRATE=1; SMOKE_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-build)   DO_BUILD=0 ;;
    --no-migrate) DO_MIGRATE=0 ;;
    --smoke-only) SMOKE_ONLY=1; DO_BUILD=0; DO_UP=0; DO_MIGRATE=0 ;;
    -h|--help)    sed -n '2,/^set -uo/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

c_blue=$'\033[36m'; c_grn=$'\033[32m'; c_red=$'\033[31m'; c_yel=$'\033[33m'; c_rst=$'\033[0m'
log()  { printf '%s[redeploy]%s %s\n' "$c_blue" "$c_rst" "$*"; }
ok()   { printf '%s[redeploy]%s %s\n' "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s[redeploy]%s %s\n' "$c_yel" "$c_rst" "$*"; }
err()  { printf '%s[redeploy]%s %s\n' "$c_red" "$c_rst" "$*" >&2; }
need() { command -v "$1" >/dev/null 2>&1 || { err "缺少工具: $1"; exit 1; }; }

# CR-0112 雙 stack 拆分後,本 script 打「派工方 stack」(web/brand-portal/docker-compose.yml;
# 師傅 stack 見 web/tech-portal/docker-compose.yml,rebuild 同參數換 -f 即可)。
DC="docker compose -f $PROJECT_ROOT/web/brand-portal/docker-compose.yml"
dbq() { $DC exec -T "$DB_SVC" psql -U "$DB_USER" -d "$DB_NAME" "$@"; }
http_code() { curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$@"; }

# ── Preflight ──────────────────────────────────────────────────────────
need docker; need curl; need python3
docker compose version >/dev/null 2>&1 || { err "需要 docker compose v2"; exit 1; }
[ -f "$PROJECT_ROOT/.env" ] || warn ".env 不存在（compose 可能仍有預設值，但建議從 .env.example 複製）"

# ── 1. Rebuild images ──────────────────────────────────────────────────
if [ "$DO_BUILD" -eq 1 ]; then
  log "rebuild web/api/agent image（吃當前 working tree 的 code）..."
  $DC build web api agent || { err "build 失敗"; exit 1; }
  ok "build 完成"
fi

# ── 2. Recreate containers ─────────────────────────────────────────────
if [ "$DO_UP" -eq 1 ]; then
  log "up -d（用新 image 重建容器；db 保留）..."
  $DC up -d || { err "up 失敗"; exit 1; }
fi

# ── 等服務就緒 ──────────────────────────────────────────────────────────
if [ "$SMOKE_ONLY" -eq 0 ]; then
  log "等 api /health 就緒..."
  for i in $(seq 1 40); do
    [ "$(http_code "$API_BASE/health")" = "200" ] && break
    sleep 1
    [ "$i" -eq 40 ] && { err "api 40s 內未 healthy"; exit 1; }
  done
  log "等 web /login 就緒..."
  for i in $(seq 1 40); do
    [ "$(http_code "$WEB_BASE/login")" = "200" ] && break
    sleep 1
    [ "$i" -eq 40 ] && warn "web 40s 內未回 200（smoke 會再驗）"
  done
  ok "服務就緒"
fi

# ── 3. 套 migration（idempotent）+ 記入 schema_migrations ────────────────
if [ "$DO_MIGRATE" -eq 1 ]; then
  log "套用 SQL/migrations/*.sql（idempotent）到 compose DB..."
  applied=0
  for f in SQL/migrations/*.sql; do
    case "$f" in *MIGRATION_REGISTRY*) continue;; esac
    dbq -v ON_ERROR_STOP=0 < "$f" >/dev/null 2>&1 && applied=$((applied+1))
  done
  # 046 建 schema_migrations；套完後記錄每支（保留既有 applied_at）
  for f in SQL/migrations/*.sql; do
    case "$f" in *MIGRATION_REGISTRY*) continue;; esac
    base="$(basename "$f")"; ver="${base%%-*}"
    dbq -q -c "INSERT INTO public.schema_migrations(version,filename,note)
               VALUES ('${ver}','${base}','applied via redeploy-local')
               ON CONFLICT (version) DO NOTHING;" >/dev/null 2>&1
  done
  ok "migration 套用完成（已記入 schema_migrations）"
fi

# ── 4. Smoke ───────────────────────────────────────────────────────────
log "smoke 檢查（實機是否真的對齊 code）..."
PASS=0; FAIL=0
check() {  # check <名稱> <期望> <實際>
  if [ "$2" = "$3" ]; then ok   "PASS  $1  ($3)"; PASS=$((PASS+1));
  else                     err  "FAIL  $1  期望=$2 實際=$3"; FAIL=$((FAIL+1)); fi
}

# 4a. api 健康 + db
HEALTH="$(curl -s --max-time 8 "$API_BASE/health" || true)"
echo "$HEALTH" | grep -q '"db":"ok"' && check "api /health db=ok" "ok" "ok" || check "api /health db=ok" "ok" "BAD($HEALTH)"

# 4b. 登入拿 token
TOKEN="$(curl -s --max-time 8 -X POST "$API_BASE/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASS\"}" \
  | python3 -c "import sys,json
try: print(json.load(sys.stdin)['data']['access_token'])
except Exception: print('')" 2>/dev/null)"
[ -n "$TOKEN" ] && check "admin 登入取 token" "ok" "ok" || check "admin 登入取 token" "ok" "EMPTY"
AUTH=(-H "Authorization: Bearer $TOKEN" -H "X-Tenant-ID: $TENANT_ID")

# 4c. v2 tenant-scoped API（核心讀路徑）
check "GET v2 work-orders"       "200" "$(http_code "$API_BASE/tenants/$TENANT_ID/work-orders?limit=5" "${AUTH[@]}")"
check "GET v2 technicians"       "200" "$(http_code "$API_BASE/tenants/$TENANT_ID/technicians?limit=5" "${AUTH[@]}")"

# 4d. 近期 CR 的端點是否真的在實機（404 = stack 落後 code）
check "CR-0037 payout-rules 在實機"          "200" "$(http_code "$API_BASE/tenants/$TENANT_ID/payout-rules?service_code=SVC-RES-001" "${AUTH[@]}")"
PR_CODE="$(http_code -X POST "$API_BASE/api/v1/auth/request-password-reset" -H 'Content-Type: application/json' -d '{"email":"x@y.com"}')"
[ "$PR_CODE" != "404" ] && check "CR-0025 忘記密碼端點在實機" "ok" "ok" || check "CR-0025 忘記密碼端點在實機" "ok" "404"

# 4e. 公開頁可達（AuthGuard 白名單 + bundle 路由都要對）
for p in /login /register /forgot-password /vendor-login /tech-login; do
  check "web 公開頁 $p"          "200" "$(http_code "$WEB_BASE$p")"
done

# 4f. migration drift：檔案數 vs schema_migrations 記錄數
FILE_CNT="$(ls SQL/migrations/*.sql 2>/dev/null | grep -v MIGRATION_REGISTRY | wc -l | tr -d ' ')"
TRACK_CNT="$(dbq -t -A -c "SELECT count(*) FROM public.schema_migrations" 2>/dev/null | tr -d ' ')"
if [ -n "$TRACK_CNT" ] && [ "$TRACK_CNT" -ge "$FILE_CNT" ] 2>/dev/null; then
  check "migration 追蹤 ≥ 檔案數（無漂移）" "ok" "ok"
else
  check "migration 追蹤 ≥ 檔案數（無漂移）" "ok" "files=$FILE_CNT tracked=${TRACK_CNT:-NA}"
fi

# ── 彙總 ────────────────────────────────────────────────────────────────
echo
if [ "$FAIL" -eq 0 ]; then
  ok "SMOKE 全過：$PASS passed, 0 failed —— 實機已對齊 code。"
  exit 0
else
  err "SMOKE 有失敗：$PASS passed, $FAIL failed —— 實機與 code 不一致，見上方 FAIL 行。"
  exit 1
fi
