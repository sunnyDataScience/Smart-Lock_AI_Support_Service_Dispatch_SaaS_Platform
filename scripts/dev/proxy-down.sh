#!/usr/bin/env bash
# scripts/dev/proxy-down.sh — 停止 cloud-sql-proxy
#
# Usage:
#   ./scripts/dev/proxy-down.sh

set -euo pipefail

# CLI 參數處理
for arg in "$@"; do
  case "$arg" in
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "[proxy] 未知參數: $arg"; echo "  用 -h 看說明"; exit 1 ;;
  esac
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$PROJECT_ROOT/.dev-logs/cloud-sql-proxy.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "[proxy] 沒有 pid 檔，可能本來就沒啟動"
  exit 0
fi

PID=$(cat "$PID_FILE")
if ! kill -0 "$PID" 2>/dev/null; then
  echo "[proxy] pid $PID 不在執行中，清掉舊 pid 檔"
  rm -f "$PID_FILE"
  exit 0
fi

kill "$PID"
sleep 1

if kill -0 "$PID" 2>/dev/null; then
  echo "[proxy] 嘗試 SIGTERM 後仍在執行，改用 SIGKILL"
  kill -9 "$PID"
fi

rm -f "$PID_FILE"
echo "[proxy] OK: 已停止 (pid $PID)"
