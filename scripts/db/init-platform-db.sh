#!/usr/bin/env bash
# init-platform-db.sh — 平台庫(lock_platform)初始化(CR-0114)
#
# 功能:
#   1. 套 SQL/platform/Schema_platform.sql(IF NOT EXISTS,可重複執行)
#   2. seed 第一個平台管理員(bcrypt 後入庫;明文絕不入 repo/argv/history)
#
# 用法(先起 platform stack:docker compose -f web/platform-console/docker-compose.yml up -d):
#   ./scripts/db/init-platform-db.sh --email test@lock-ai.com [--name '平台管理員']
#     → 密碼互動輸入(不回顯),或事先 export PLATFORM_ADMIN_PASSWORD
#   PLATFORM_DB_URI=postgresql://lock:0000@localhost:5435/lock_platform ./scripts/db/init-platform-db.sh ...
#
# ⚠️ 刻意不提供 --password 參數:argv 會進 shell history 且在 process table
#   (ps aux / /proc/<pid>/cmdline)對其他本機使用者可見。密碼只走互動 read -rs
#   或環境變數,並以 stdin(非 argv)交給 python 做 bcrypt。
#
# 既有同 email 帳號 → 跳過 seed(不覆寫密碼);要重設密碼加 --reset-password。

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCHEMA="${ROOT}/SQL/platform/Schema_platform.sql"
DB_URI="${PLATFORM_DB_URI:-postgresql://lock:0000@localhost:5435/lock_platform}"

ADMIN_EMAIL=""
ADMIN_PASSWORD="${PLATFORM_ADMIN_PASSWORD:-}"
ADMIN_NAME="平台管理員"
RESET_PASSWORD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)           ADMIN_EMAIL="$2"; shift 2 ;;
    --password)
      echo "已停用 --password(argv 會洩入 shell history 與 process table);" >&2
      echo "請改互動輸入或 export PLATFORM_ADMIN_PASSWORD。" >&2
      exit 1 ;;
    --name)            ADMIN_NAME="$2"; shift 2 ;;
    --reset-password)  RESET_PASSWORD=1; shift ;;
    *) echo "未知參數: $1" >&2; exit 1 ;;
  esac
done

command -v psql >/dev/null || { echo "需要 psql(brew install libpq)" >&2; exit 1; }

echo "[1/2] 套用 schema → ${DB_URI%%\?*}"
psql "${DB_URI}" -v ON_ERROR_STOP=1 -f "${SCHEMA}" >/dev/null
echo "      schema OK"

if [[ -z "${ADMIN_EMAIL}" ]]; then
  echo "[2/2] 未帶 --email → 跳過 seed(僅套 schema)"
  exit 0
fi
if [[ -z "${ADMIN_PASSWORD}" ]]; then
  read -rs -p "平台管理員密碼(輸入不回顯,至少 8 字元): " ADMIN_PASSWORD
  echo
fi
if [[ "${#ADMIN_PASSWORD}" -lt 8 ]]; then
  echo "密碼至少 8 字元" >&2
  exit 1
fi

# bcrypt hash 用與 API 相同的 passlib 設定(uv 環境已含 api deps)。
# 明文走 stdin 交給 python —— 不入 argv(process table 不可見)。
HASH="$(printf '%s' "${ADMIN_PASSWORD}" | (cd "${ROOT}" && uv run python -c "
import sys
from passlib.context import CryptContext
print(CryptContext(schemes=['bcrypt'], deprecated='auto').hash(sys.stdin.read()))
"))"

if [[ "${RESET_PASSWORD}" -eq 1 ]]; then
  echo "[2/2] seed/重設平台管理員 ${ADMIN_EMAIL}(--reset-password)"
  psql "${DB_URI}" -v ON_ERROR_STOP=1 -q \
    -v email="${ADMIN_EMAIL}" -v hash="${HASH}" -v name="${ADMIN_NAME}" <<'SQL'
INSERT INTO users (display_name, email, password_hash, role, is_active)
VALUES (:'name', :'email', :'hash', 'platform_admin', TRUE)
ON CONFLICT (email) DO UPDATE
  SET password_hash = EXCLUDED.password_hash,
      password_changed_at = NOW(),
      failed_login_attempts = 0,
      locked_until = NULL,
      updated_at = NOW();
SQL
else
  echo "[2/2] seed 平台管理員 ${ADMIN_EMAIL}(已存在則跳過)"
  psql "${DB_URI}" -v ON_ERROR_STOP=1 -q \
    -v email="${ADMIN_EMAIL}" -v hash="${HASH}" -v name="${ADMIN_NAME}" <<'SQL'
INSERT INTO users (display_name, email, password_hash, role, is_active)
VALUES (:'name', :'email', :'hash', 'platform_admin', TRUE)
ON CONFLICT (email) DO NOTHING;
SQL
fi

echo "完成。登入:POST /api/v1/platform/auth/login(console http://localhost:3003/platform/login)"
