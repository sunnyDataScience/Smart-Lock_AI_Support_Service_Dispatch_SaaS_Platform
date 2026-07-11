#!/usr/bin/env bash
# uat-clean-data.sh — UAT 測試前清空交易類測試資料
#
# 預設模式（快速清理，約 3 秒）：
#   清空所有交易類資料（工單、問題卡、對話、報價、發票、折讓、爭議…），
#   保留系統運作必要的主檔：帳號/RBAC、師傅、價目表、服務目錄、庫存主檔、知識庫。
#
# --full 模式（完整重建，約 2 分鐘）：
#   停 api/agent → DROP 三個 schema → db-init 重建（schema+migrations+seeds）
#   → 補跑 family_reviews seed（已知 seed 順序 bug）→ 重啟 api/agent
#   → 再跑一次快速清理把 seed demo 交易資料清掉。
#   注意：--full 會把「快速清理後仍保留」的資料也重置回 seed 狀態
#   （例如你自己註冊的帳號會消失，回到 seed 的預設帳號）。
#
# 用法：
#   ./scripts/dev/uat-clean-data.sh            # 快速清理（會先確認）
#   ./scripts/dev/uat-clean-data.sh --yes      # 快速清理（跳過確認）
#   ./scripts/dev/uat-clean-data.sh --full     # 完整重建 + 清理
#
# 連線參數可用環境變數覆蓋：PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE

set -euo pipefail

cd "$(dirname "$0")/../.."

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-5433}"
export PGUSER="${PGUSER:-lock}"
export PGPASSWORD="${PGPASSWORD:-0000}"
export PGDATABASE="${PGDATABASE:-lock_AI_data}"
COMPOSE_FILE="web/brand-portal/docker-compose.yml"

FULL=0
YES=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    --yes)  YES=1 ;;
    *) echo "未知參數：$arg"; exit 1 ;;
  esac
done

confirm() {
  if [ "$YES" = "1" ]; then return 0; fi
  read -r -p "$1 [y/N] " ans
  [ "$ans" = "y" ] || [ "$ans" = "Y" ] || { echo "已取消"; exit 1; }
}

clean_transactional() {
  echo "==> 清空交易類測試資料（保留帳號/師傅/價目表/知識庫等主檔）"
  psql -v ON_ERROR_STOP=1 -q <<'SQL'
TRUNCATE TABLE
  public.conversations,
  public.messages,
  public.problem_cards,
  public.work_orders,
  public.dispatch_logs,
  public.disputes,
  public.family_reviews,
  public.invoices,
  public.reconciliations,
  public.refund_requests,
  public.sentiment_alerts,
  public.settlements,
  public.sop_drafts,
  public.vouchers,
  public.warranty_claims,
  public.inventory_transactions,
  public.notifications,
  saas.intake_case
RESTART IDENTITY CASCADE;
SQL
}

verify() {
  echo "==> 驗證結果"
  psql -t -A -c "
SELECT '交易資料  quote='||(SELECT count(*) FROM quote)
     ||' / work_orders='||(SELECT count(*) FROM work_orders)
     ||' / problem_cards='||(SELECT count(*) FROM problem_cards)
     ||' / conversations='||(SELECT count(*) FROM conversations);
SELECT '保留主檔  users='||(SELECT count(*) FROM users)
     ||' / technicians='||(SELECT count(*) FROM technicians)
     ||' / service_catalog='||(SELECT count(*) FROM service_catalog)
     ||' / manuals='||(SELECT count(*) FROM manuals);"
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    http://localhost:8001/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@lock-ai.com","password":"changeme123"}' || echo "000")
  echo "登入檢查  HTTP ${code} (200=正常)"
}

if [ "$FULL" = "1" ]; then
  confirm "⚠️  完整重建會 DROP 整個資料庫重來（含你自己註冊的帳號），確定？"
  echo "==> 停止 api/agent 容器"
  docker compose -f "$COMPOSE_FILE" stop api agent

  echo "==> DROP 三個 schema"
  psql -v ON_ERROR_STOP=1 -q <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
 WHERE datname = current_database() AND pid <> pg_backend_pid();
DROP SCHEMA IF EXISTS public CASCADE;
DROP SCHEMA IF EXISTS saas CASCADE;
DROP SCHEMA IF EXISTS agent CASCADE;
CREATE SCHEMA public;
SQL

  echo "==> db-init 重建（schema + migrations + seeds）"
  docker compose -f "$COMPOSE_FILE" --profile init up db-init --abort-on-container-exit

  echo "==> 補跑 family_reviews seed（已知 seed 順序 bug workaround）"
  psql -v ON_ERROR_STOP=1 -q -f SQL/seeds/family_reviews.sql

  echo "==> 重啟 api/agent"
  docker compose -f "$COMPOSE_FILE" up -d api agent
  sleep 8

  clean_transactional
  verify
else
  confirm "將清空所有交易類測試資料（工單/問題卡/對話/報價/帳務…），確定？"
  clean_transactional
  verify
fi

echo "✅ 完成，可以開始 UAT"
