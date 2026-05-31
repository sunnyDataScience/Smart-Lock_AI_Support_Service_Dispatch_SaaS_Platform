#!/usr/bin/env bash
#
# scripts/ci/mock-server.sh — 快速啟動 Prism mock server（OpenAPI）
#
# 預設用 npx（需 Node 18+），無 Node 時自動 fallback 到 Docker。
#
# Usage:
#   ./scripts/ci/mock-server.sh           # 啟動在 4010
#   ./scripts/ci/mock-server.sh 4011      # 自訂 port
#   ./scripts/ci/mock-server.sh 4010 --errors  # 產生錯誤範例回應
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${1:-4010}"
shift || true
EXTRA_ARGS="$*"

SPEC="$REPO_ROOT/docs/architecture/api/openapi.yaml"

if [[ ! -f "$SPEC" ]]; then
  echo "ERROR: OpenAPI spec not found at $SPEC"
  exit 1
fi

echo "== Prism Mock Server =="
echo "Spec:  $SPEC"
echo "Port:  $PORT"
echo "Args:  $EXTRA_ARGS"
echo ""

if command -v npx >/dev/null 2>&1; then
  echo "[npx] starting prism..."
  exec npx --yes @stoplight/prism-cli@latest mock "$SPEC" -h 0.0.0.0 -p "$PORT" $EXTRA_ARGS
elif command -v docker >/dev/null 2>&1; then
  echo "[docker] starting prism..."
  exec docker run --rm -i \
    -v "$REPO_ROOT/docs/architecture/api:/specs:ro" \
    -p "${PORT}:${PORT}" \
    stoplight/prism:5 \
    mock -h 0.0.0.0 -p "$PORT" $EXTRA_ARGS /specs/openapi.yaml
else
  echo "ERROR: 需要 npx（Node 18+）或 docker"
  exit 1
fi
