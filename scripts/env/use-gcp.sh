#!/usr/bin/env bash
# scripts/env/use-gcp.sh — 切換到 GCP Cloud SQL 環境
#
# 把 .env.gcp 複製到 .env，agent 啟動時會透過 cloud-sql-proxy 連 GCP DB。
#
# Usage:
#   ./scripts/env/use-gcp.sh             # 直接切換（.env.gcp 須已存在）
#   ./scripts/env/use-gcp.sh --fetch     # 從 GCP Secret Manager 取 POSTGRES_URI
#                                    #   重建 .env.gcp 後再切換
#
# 前置條件（必須）：
#   1. gcloud auth login 已完成
#   2. gcloud config set project cedar-scope-489604-g3
#   3. cloud-sql-proxy 已啟動（用 ./scripts/dev/proxy-up.sh）

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GCP_ENV="$PROJECT_ROOT/.env.gcp"
GCP_TEMPLATE="$PROJECT_ROOT/.env.gcp.example"
TARGET_ENV="$PROJECT_ROOT/.env"
GCP_PROJECT="cedar-scope-489604-g3"

FETCH=0
for arg in "$@"; do
  case "$arg" in
    --fetch) FETCH=1 ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "未知參數: $arg"; exit 1 ;;
  esac
done

# === --fetch：從 Secret Manager 重建 .env.gcp ===
if [[ "$FETCH" -eq 1 ]]; then
  command -v gcloud >/dev/null || { echo "[use-gcp] FAIL: 找不到 gcloud"; exit 1; }

  if ! gcloud auth list --filter='status:ACTIVE' --format='value(account)' 2>/dev/null | grep -q '@'; then
    echo "[use-gcp] FAIL: gcloud 未登入。請先執行："
    echo "  ! gcloud auth login"
    exit 1
  fi

  echo "[use-gcp] 從 Secret Manager 取 POSTGRES_URI ..."
  POSTGRES_URI_FROM_GCP=$(gcloud secrets versions access latest \
    --secret=POSTGRES_URI \
    --project="$GCP_PROJECT" 2>&1) || {
    echo "[use-gcp] FAIL: 無法存取 POSTGRES_URI secret"
    echo "  輸出：$POSTGRES_URI_FROM_GCP"
    exit 1
  }

  # Secret Manager 中的 POSTGRES_URI 是給 Cloud Run 用的（Unix socket /cloudsql/...）
  # 本機透過 cloud-sql-proxy 連，要把 host 改為 127.0.0.1:5432
  # 從原 URI 抽出 user / password / dbname
  CRED_DBNAME=$(echo "$POSTGRES_URI_FROM_GCP" | sed -E 's|^postgresql://([^@]+)@.*/([^?]+).*$|\1@127.0.0.1:5432/\2|')
  PROXY_URI="postgresql://${CRED_DBNAME}"
  PROXY_PG_VECTOR="postgresql+psycopg://${CRED_DBNAME}"

  echo "[use-gcp] 寫入 .env.gcp（透過 proxy 走 127.0.0.1:5432） ..."
  if [[ -f "$GCP_ENV" ]]; then
    cp "$GCP_ENV" "$GCP_ENV.bak.$(date +%Y%m%d-%H%M%S)"
  fi

  if [[ ! -f "$GCP_TEMPLATE" ]]; then
    echo "[use-gcp] FAIL: 找不到範本 .env.gcp.example"
    exit 1
  fi

  cp "$GCP_TEMPLATE" "$GCP_ENV"
  # 用 | 當分隔符避免 / 衝突
  sed -i -E "s|^POSTGRES_URI=.*$|POSTGRES_URI=\"${PROXY_URI}\"|" "$GCP_ENV"
  sed -i -E "s|^PG_VECTOR_URI=.*$|PG_VECTOR_URI=\"${PROXY_PG_VECTOR}\"|" "$GCP_ENV"
  chmod 600 "$GCP_ENV"
  echo "[use-gcp] OK: .env.gcp 已從 Secret Manager 重建（chmod 600）"
fi

# === 套用切換 ===
if [[ ! -f "$GCP_ENV" ]]; then
  echo "[use-gcp] FAIL: $GCP_ENV 不存在"
  echo "  請執行：./scripts/env/use-gcp.sh --fetch"
  echo "  或手動複製範本：cp .env.gcp.example .env.gcp 後填密碼"
  exit 1
fi

# 備份目前 .env
if [[ -f "$TARGET_ENV" ]] && ! cmp -s "$GCP_ENV" "$TARGET_ENV"; then
  cp "$TARGET_ENV" "$TARGET_ENV.bak.$(date +%Y%m%d-%H%M%S)"
  echo "[use-gcp] 已備份原 .env 為 .env.bak.*"
fi

cp "$GCP_ENV" "$TARGET_ENV"
echo "[use-gcp] OK: 已切換到 GCP Cloud SQL 環境"
echo ""
echo "下一步："
echo "  1. 確認 cloud-sql-proxy 已啟動："
echo "     ./scripts/dev/proxy-up.sh"
echo "  2. 啟動 agent（不需 dev-up.sh，因為 DB 是遠端）："
echo "     cd agent && uv run uvicorn app:app --reload --port 8000"
