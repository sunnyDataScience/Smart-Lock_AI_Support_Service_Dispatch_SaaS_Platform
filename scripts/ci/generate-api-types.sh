#!/usr/bin/env bash
#
# scripts/ci/generate-api-types.sh — 從 OpenAPI spec 生成 TypeScript 型別
#
# 輸出位置：
#   - 若存在 web/lib/types/，直接寫入 api.generated.ts
# 依賴：npx（Node 18+）+ openapi-typescript 套件
#
# Usage:
#   ./scripts/ci/generate-api-types.sh           # 正常生成
#   ./scripts/ci/generate-api-types.sh --check   # 僅檢查是否需重新生成（CI 用，不改檔）
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

SPEC="docs/2-contracts/api/openapi.yaml"
CHECK_ONLY=0
for arg in "$@"; do
  [[ "$arg" == "--check" ]] && CHECK_ONLY=1
done

# 決定輸出位置
if [[ -d "web/lib" ]]; then
  OUT_DIR="web/lib/types"
else
  OUT_DIR="web/types"
fi
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/api.generated.ts"

echo "== OpenAPI → TypeScript =="
echo "Spec:   $SPEC"
echo "Output: $OUT_FILE"
echo ""

if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: 需要 npx（Node 18+）"
  exit 1
fi

TMP_FILE="$(mktemp -t api.generated.ts.XXXXXX)"
trap 'rm -f "$TMP_FILE"' EXIT

echo "[npx] generating types..."
npx --yes openapi-typescript@latest "$SPEC" -o "$TMP_FILE" 2>&1 | tail -5

if [[ ! -s "$TMP_FILE" ]]; then
  echo "ERROR: 型別生成失敗（空檔）"
  exit 1
fi

lines=$(wc -l < "$TMP_FILE")
echo "Generated: $lines lines"

if [[ $CHECK_ONLY -eq 1 ]]; then
  if [[ -f "$OUT_FILE" ]] && diff -q "$TMP_FILE" "$OUT_FILE" > /dev/null 2>&1; then
    echo "✅ 型別檔已是最新（與 spec 一致）"
    exit 0
  else
    echo "❌ 型別檔與 spec 不同步，請執行：./scripts/ci/generate-api-types.sh"
    exit 1
  fi
fi

mv "$TMP_FILE" "$OUT_FILE"
echo "✅ 寫入 $OUT_FILE"
echo ""
echo "Next steps:"
echo "  1) 在 web/ 專案建立後，將 $OUT_FILE 搬到 web/lib/types/"
echo "  2) package.json 加 \"postinstall\": \"npm run generate-api-types\""
echo "  3) CI 用 --check 模式阻擋未同步的 commit"
