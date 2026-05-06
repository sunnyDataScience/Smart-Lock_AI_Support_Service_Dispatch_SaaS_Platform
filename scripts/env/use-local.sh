#!/usr/bin/env bash
# scripts/env/use-local.sh — 切換到本機 docker DB 環境
#
# 把 .env.local 複製到 .env，agent 啟動時會讀本機的 PostgreSQL 容器。
#
# Usage:
#   ./scripts/env/use-local.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_ENV="$PROJECT_ROOT/.env.local"
TARGET_ENV="$PROJECT_ROOT/.env"

if [[ ! -f "$LOCAL_ENV" ]]; then
  echo "[use-local] FAIL: $LOCAL_ENV 不存在"
  echo "  請先確認 .env.local 已建立（內容應為連接本機 docker DB 的設定）"
  exit 1
fi

# 備份目前 .env（如果跟 .env.local 不同）
if [[ -f "$TARGET_ENV" ]] && ! cmp -s "$LOCAL_ENV" "$TARGET_ENV"; then
  cp "$TARGET_ENV" "$TARGET_ENV.bak.$(date +%Y%m%d-%H%M%S)"
  echo "[use-local] 已備份原 .env 為 .env.bak.*"
fi

cp "$LOCAL_ENV" "$TARGET_ENV"
echo "[use-local] OK: 已切換到本機 docker DB 環境"
echo ""
echo "下一步："
echo "  ./scripts/dev/dev-up.sh             # 啟動 DB + ngrok + uvicorn"
echo "  或：cd agent && uvicorn app:app --reload --port 8000"
