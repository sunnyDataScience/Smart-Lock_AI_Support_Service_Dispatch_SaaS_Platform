#!/usr/bin/env bash
# ============================================================================
# provision-brand-tenant.sh — 品牌庫租戶初始化（CR-0186 / WBS 3.3.1）
# ============================================================================
#
# 為什麼需要這支（0727 偵察揪出的開站致命斷點）：
#   `saas.tenant` 全庫只有一列 seed —— migration 004 的 demo UUID
#   `00000000-…-0001`，其註解自己寫「Production tenants are created via
#   onboarding」，**但那段 onboarding code 不存在**。同時全庫有 **24 個 FK
#   指向 saas.tenant**（config_version / reconciliation / settlement / dispute /
#   inventory / price_rule …）。
#
#   而 `scripts/deploy/provision_brand.py` 會把**平台庫**的租戶 UUID 寫進
#   `brands/<slug>.env` 的 `AGENT_TENANT_ID`。兩者一對照就是：新品牌的
#   AGENT_TENANT_ID 指向一個**在它自己品牌庫裡並不存在**的租戶 →
#   任何 per-tenant 寫入都會 FK violation，第二個品牌從第一天就是壞的。
#
#   本腳本補上缺的那一步：在**品牌庫**建立該租戶列 + 建品牌 Admin 帳號。
#
# 用法：
#   ./scripts/db/provision-brand-tenant.sh --tenant-id <uuid> --name '品牌名' \
#       [--email admin@brand.com] [--admin-name '管理員'] [--reset-password] [--dry-run]
#
#   POSTGRES_URI=postgresql://... ./scripts/db/provision-brand-tenant.sh ...
#   （預設連本機 compose 品牌庫 5433/lock_AI_data）
#
# ⚠️ 與 init-platform-db.sh 同樣**刻意不提供 --password**：argv 會進 shell
#    history 且在 process table（ps aux）對其他本機使用者可見。密碼只走互動
#    read -rs 或環境變數 BRAND_ADMIN_PASSWORD，並以 stdin（非 argv）做 bcrypt。
#
# 全 idempotent：租戶走 ON CONFLICT (id) DO NOTHING；admin 因**品牌庫 users 沒有
# email 唯一約束**（只有 id PK 與 line_user_id unique，與平台庫不同）不能用
# ON CONFLICT (email)，改以「同 tenant + 同 email」為邏輯鍵的 NOT EXISTS /
# UPDATE-or-INSERT。預設不覆寫既有密碼，要重設加 --reset-password。
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_URI="${POSTGRES_URI:-postgresql://lock:0000@localhost:5433/lock_AI_data}"

TENANT_ID=""
TENANT_NAME=""
ADMIN_EMAIL=""
ADMIN_NAME="品牌管理員"
ADMIN_PASSWORD="${BRAND_ADMIN_PASSWORD:-}"
RESET_PASSWORD=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tenant-id)      TENANT_ID="$2"; shift 2 ;;
    --name)           TENANT_NAME="$2"; shift 2 ;;
    --email)          ADMIN_EMAIL="$2"; shift 2 ;;
    --admin-name)     ADMIN_NAME="$2"; shift 2 ;;
    --reset-password) RESET_PASSWORD=1; shift ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --password)
      echo "已停用 --password（argv 會洩入 shell history 與 process table）；" >&2
      echo "請改互動輸入或 export BRAND_ADMIN_PASSWORD。" >&2
      exit 1 ;;
    *) echo "未知參數: $1" >&2; exit 1 ;;
  esac
done

[[ -z "${TENANT_ID}" ]] && { echo "FAIL: 需 --tenant-id <uuid>（與 brands/<slug>.env 的 AGENT_TENANT_ID 一致）" >&2; exit 1; }
[[ -z "${TENANT_NAME}" ]] && { echo "FAIL: 需 --name '品牌名'" >&2; exit 1; }
command -v psql >/dev/null || { echo "需要 psql（brew install libpq）" >&2; exit 1; }

# UUID 格式先擋（避免把非法值寫進 env 後才在 runtime 才炸）
if ! printf '%s' "${TENANT_ID}" | grep -qiE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
  echo "FAIL: --tenant-id 不是合法 UUID：${TENANT_ID}" >&2
  exit 1
fi

echo "========================================"
echo " 品牌庫租戶初始化"
echo "========================================"
echo "  DB        : ${DB_URI%%\?*}"
echo "  tenant_id : ${TENANT_ID}"
echo "  name      : ${TENANT_NAME}"
echo "  admin     : ${ADMIN_EMAIL:-（未指定 --email，僅建租戶列）}"
[[ "${DRY_RUN}" -eq 1 ]] && echo "  模式      : DRY-RUN（不寫入）"

# ── 前置：schema 必須已套（saas.tenant 由 migration 004 建立）──────────────
HAS_TENANT_TABLE="$(psql "${DB_URI}" -tA -c "SELECT to_regclass('saas.tenant') IS NOT NULL" 2>/dev/null || echo f)"
if [[ "${HAS_TENANT_TABLE}" != "t" ]]; then
  echo "FAIL: saas.tenant 不存在 —— 請先套 schema 與 migrations" >&2
  echo "      本機：BRAND=<slug> docker compose -f web/brand-portal/docker-compose.yml --profile init run --rm db-init" >&2
  echo "      雲端：./scripts/db/apply-schema-routed.sh" >&2
  exit 1
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo ""
  echo "[dry-run] 將執行："
  echo "  INSERT INTO saas.tenant (id, name) VALUES ('${TENANT_ID}', '${TENANT_NAME}') ON CONFLICT (id) DO NOTHING;"
  [[ -n "${ADMIN_EMAIL}" ]] && echo "  UPDATE-or-INSERT users（tenant+email 為邏輯鍵）：'${ADMIN_EMAIL}' role=admin tenant=${TENANT_ID}"
  exit 0
fi

# ── 1. 租戶列（24 個 FK 的 target）───────────────────────────────────────
echo ""
echo "[1/2] 建立 saas.tenant 列"
psql "${DB_URI}" -v ON_ERROR_STOP=1 -q \
  -v tid="${TENANT_ID}" -v tname="${TENANT_NAME}" <<'SQL'
INSERT INTO saas.tenant (id, name)
VALUES (:'tid'::uuid, :'tname')
ON CONFLICT (id) DO NOTHING;
SQL
EXISTS="$(psql "${DB_URI}" -tA -c "SELECT name FROM saas.tenant WHERE id = '${TENANT_ID}'::uuid")"
echo "      OK：saas.tenant['${TENANT_ID}'] = '${EXISTS}'"

# ── 2. 品牌 Admin 帳號 ───────────────────────────────────────────────────
if [[ -z "${ADMIN_EMAIL}" ]]; then
  echo "[2/2] 未帶 --email → 跳過 admin（僅建租戶列）"
  echo ""
  echo "⚠️ 尚未建立品牌 Admin，該品牌後台無人可登入。稍後補："
  echo "   $0 --tenant-id ${TENANT_ID} --name '${TENANT_NAME}' --email admin@brand.com"
  exit 0
fi

if [[ -z "${ADMIN_PASSWORD}" ]]; then
  read -rs -p "品牌管理員密碼（輸入不回顯，至少 8 字元）: " ADMIN_PASSWORD
  echo
fi
if [[ "${#ADMIN_PASSWORD}" -lt 8 ]]; then
  echo "密碼至少 8 字元" >&2
  exit 1
fi

# bcrypt 用與 API 相同的 passlib 設定；明文走 stdin 不入 argv
HASH="$(printf '%s' "${ADMIN_PASSWORD}" | (cd "${ROOT}" && uv run python -c "
import sys
from passlib.context import CryptContext
print(CryptContext(schemes=['bcrypt'], deprecated='auto').hash(sys.stdin.read()))
"))"

if [[ "${RESET_PASSWORD}" -eq 1 ]]; then
  echo "[2/2] seed/重設品牌 Admin ${ADMIN_EMAIL}（--reset-password）"
  psql "${DB_URI}" -v ON_ERROR_STOP=1 -q \
    -v email="${ADMIN_EMAIL}" -v hash="${HASH}" -v name="${ADMIN_NAME}" -v tid="${TENANT_ID}" <<'SQL'
-- 品牌庫 users **沒有 email 唯一約束**（只有 id PK 與 line_user_id unique），
-- 故不能用 ON CONFLICT (email) —— 會 "no unique or exclusion constraint matching"。
-- 改以「同 tenant + 同 email」為邏輯鍵做 UPDATE-or-INSERT（明確、可讀、冪等）。
-- 註：email 可重複正是既有「同帳號雙 row」陷阱的根源；此處刻意以 tenant 收斂範圍。
WITH upd AS (
  UPDATE users
     SET password_hash = :'hash',
         display_name = :'name',
         role = 'admin',
         is_active = TRUE,
         password_changed_at = NOW(),
         failed_login_attempts = 0,
         locked_until = NULL,
         updated_at = NOW()
   WHERE email = :'email' AND tenant_id = :'tid'::uuid
  RETURNING id
)
INSERT INTO users (tenant_id, display_name, email, password_hash, role, is_active)
SELECT :'tid'::uuid, :'name', :'email', :'hash', 'admin', TRUE
WHERE NOT EXISTS (SELECT 1 FROM upd);
SQL
else
  echo "[2/2] seed 品牌 Admin ${ADMIN_EMAIL}（已存在則跳過，不覆寫密碼）"
  psql "${DB_URI}" -v ON_ERROR_STOP=1 -q \
    -v email="${ADMIN_EMAIL}" -v hash="${HASH}" -v name="${ADMIN_NAME}" -v tid="${TENANT_ID}" <<'SQL'
-- 同上：品牌庫 users 無 email 唯一約束 → 用 NOT EXISTS 守冪等（不覆寫既有密碼）。
INSERT INTO users (tenant_id, display_name, email, password_hash, role, is_active)
SELECT :'tid'::uuid, :'name', :'email', :'hash', 'admin', TRUE
WHERE NOT EXISTS (
  SELECT 1 FROM users WHERE email = :'email' AND tenant_id = :'tid'::uuid
);
SQL
fi

ROLE_OK="$(psql "${DB_URI}" -tA -c \
  "SELECT role || '/' || COALESCE(tenant_id::text,'NULL') FROM users WHERE email = '${ADMIN_EMAIL}'")"
echo "      OK：users['${ADMIN_EMAIL}'] role/tenant = ${ROLE_OK}"

echo ""
echo "========================================"
echo " 完成 —— 後續步驟（provision_brand.py checklist）"
echo "========================================"
cat <<'TIP'
  ✅ 本腳本已完成：品牌庫 saas.tenant 列 + 品牌 Admin 帳號
  ⬜ 仍須手動：GCP 專案 / Secret Manager / Casdoor org / LINE channel 綁定
     （見 scripts/deploy/README.md 與 scripts/deploy/provision_brand.py 的 checklist）

  驗證登入：品牌後台以上述 email 登入，應看得到該租戶（非 demo-tenant）的資料。
TIP
