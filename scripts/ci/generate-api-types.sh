#!/usr/bin/env bash
#
# scripts/ci/generate-api-types.sh — 從 OpenAPI spec 生成 TypeScript 型別
#
# 輸出位置：
#   - 若存在 web/lib/types/，直接寫入 api.generated.ts
#   - 否則寫入 docs/02-design/specs/generated/api.generated.ts（暫存）
#
# 依賴：npx（Node 18+）+ openapi-typescript 套件
#
# Usage:
#   ./scripts/ci/generate-api-types.sh           # 正常生成
#   ./scripts/ci/generate-api-types.sh --check   # 僅檢查是否需重新生成（CI 用，不改檔）
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# CR-0009 dual-write: docs_v2/ is the new SSOT; docs/ remains as legacy mirror
# during 90-day cutover. Both paths must stay in sync until CR-0008 removes docs/.
SPEC_NEW="docs_v2/2-contracts/api/openapi.yaml"
SPEC_LEGACY="docs/02-design/specs/openapi.yaml"
if [[ -f "$SPEC_NEW" && -f "$SPEC_LEGACY" ]]; then
  if ! diff -q "$SPEC_NEW" "$SPEC_LEGACY" >/dev/null 2>&1; then
    echo "ERROR (CR-0009): SPEC drift between"
    echo "  new:    $SPEC_NEW"
    echo "  legacy: $SPEC_LEGACY"
    echo "Both must stay in sync during the 90-day cutover (until CR-0008)."
    diff "$SPEC_NEW" "$SPEC_LEGACY" | head -20
    exit 1
  fi
  SPEC="$SPEC_NEW"
elif [[ -f "$SPEC_NEW" ]]; then
  SPEC="$SPEC_NEW"
else
  SPEC="$SPEC_LEGACY"
fi
CHECK_ONLY=0
for arg in "$@"; do
  [[ "$arg" == "--check" ]] && CHECK_ONLY=1
done

# 決定輸出位置
if [[ -d "web/lib" ]]; then
  OUT_DIR="web/lib/types"
elif [[ -d "web" ]]; then
  OUT_DIR="web/types"
else
  OUT_DIR="docs/02-design/specs/generated"
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
