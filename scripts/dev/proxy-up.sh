#!/usr/bin/env bash
# scripts/dev/proxy-up.sh — 啟動 cloud-sql-proxy，讓本機可連 GCP Cloud SQL
#
# 把 GCP 實例 cedar-scope-489604-g3:asia-east1:lock-ai 對映到 127.0.0.1:5432
# 預設背景執行，PID 寫到 .dev-logs/cloud-sql-proxy.pid。
#
# Usage:
#   ./scripts/dev/proxy-up.sh             # 背景啟動
#   ./scripts/dev/proxy-up.sh --foreground # 前景執行（看 log）

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.dev-logs"
PID_FILE="$LOG_DIR/cloud-sql-proxy.pid"
LOG_FILE="$LOG_DIR/cloud-sql-proxy.log"

INSTANCE="cedar-scope-489604-g3:asia-east1:lock-ai"
PORT=5432

FOREGROUND=0
for arg in "$@"; do
  case "$arg" in
    --foreground|-f) FOREGROUND=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "未知參數: $arg"; exit 1 ;;
  esac
done

mkdir -p "$LOG_DIR"

# 找 binary
PROXY_BIN=""
if command -v cloud-sql-proxy >/dev/null; then
  PROXY_BIN="$(command -v cloud-sql-proxy)"
elif [[ -x "$HOME/bin/cloud-sql-proxy" ]]; then
  PROXY_BIN="$HOME/bin/cloud-sql-proxy"
else
  echo "[proxy] FAIL: 找不到 cloud-sql-proxy"
  echo "  安裝："
  echo "    curl -o ~/bin/cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.13.0/cloud-sql-proxy.linux.amd64"
  echo "    chmod +x ~/bin/cloud-sql-proxy"
  exit 1
fi

# 檢查 ADC 認證
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "[proxy] FAIL: ADC 未設定。請先執行："
  echo "  ! gcloud auth application-default login"
  exit 1
fi

# 已啟動則跳過
if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "[proxy] 已在執行（pid $(cat "$PID_FILE"))"
  echo "  log: $LOG_FILE"
  exit 0
fi

# 檢查 5432 是否被佔用（例如本機 docker DB 已 bind 5432）
if lsof -iTCP:$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
  echo "[proxy] FAIL: port $PORT 已被佔用。請先停掉佔用該 port 的程序："
  echo "  lsof -iTCP:$PORT -sTCP:LISTEN"
  exit 1
fi

if [[ "$FOREGROUND" -eq 1 ]]; then
  echo "[proxy] 前景啟動 → $INSTANCE 對映到 127.0.0.1:$PORT"
  exec "$PROXY_BIN" "$INSTANCE" --port "$PORT"
fi

echo "[proxy] 背景啟動 → $INSTANCE 對映到 127.0.0.1:$PORT ..."
nohup "$PROXY_BIN" "$INSTANCE" --port "$PORT" >"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# 等待 ready
for i in $(seq 1 15); do
  if grep -q 'ready for new connections' "$LOG_FILE" 2>/dev/null; then
    echo "[proxy] OK: ready for new connections (pid $(cat "$PID_FILE"))"
    echo "  log: $LOG_FILE"
    echo ""
    echo "下一步："
    echo "  ./scripts/env/use-gcp.sh           # 切換 .env 到 GCP 設定"
    echo "  cd agent && uv run uvicorn app:app --reload --port 8000"
    exit 0
  fi
  sleep 1
done

echo "[proxy] WARN: 15 秒內未看到 ready 訊號，請檢查 log："
echo "  tail -50 $LOG_FILE"
exit 1
