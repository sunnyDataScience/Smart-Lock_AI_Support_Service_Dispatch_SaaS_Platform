#!/usr/bin/env bash
#
# scripts/ci/generate-api-types.sh — 從 FastAPI runtime export 生成 TypeScript 型別
#
# 型別 SoT（2026-07-09 業主裁決，CR-0126）：**runtime export**（scripts/ops/
# export_openapi.py 自 api.main:app 匯出的實際契約，/api/v1/* 全端點）。
# 設計稿 api/openapi.yaml 仍為設計期契約（spec-lint / mock-smoke / contract-check
# 對象），但**不是**型別來源——兩者路徑前綴與 schema 集合本就不同。
#
# 輸出位置（2026-07-09 web 檔案層拆分）：四站各持一份 api.generated.ts，
# 本腳本一次生成、同步寫入四站（單一 runtime 真相 → 四份副本零漂移）。
#
# 依賴：uv（匯出 runtime spec，需 api 套件 deps）+ npx（Node 18+）
# openapi-typescript 版本釘死：不同版本輸出格式不同，@latest 會讓 --check 假紅。
#
# Usage:
#   ./scripts/ci/generate-api-types.sh           # 正常生成（寫入四站）
#   ./scripts/ci/generate-api-types.sh --check   # 僅檢查四站是否與 runtime 同步（CI 用，不改檔）
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

OPENAPI_TS_VERSION="7.13.0"
CHECK_ONLY=0
for arg in "$@"; do
  [[ "$arg" == "--check" ]] && CHECK_ONLY=1
done

OUT_DIRS=(web/brand-portal/src/types web/tech-portal/src/types web/landing/src/types web/platform-console/src/types)

echo "== FastAPI runtime → OpenAPI → TypeScript =="
echo "Source:  api.main:app（scripts/ops/export_openapi.py）"
echo "Outputs: ${OUT_DIRS[*]}"
echo ""

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 需要 uv（匯出 runtime spec）"
  exit 1
fi
if ! command -v npx >/dev/null 2>&1; then
  echo "ERROR: 需要 npx（Node 18+）"
  exit 1
fi

TMP_SPEC="$(mktemp -t openapi-runtime.json.XXXXXX)"
TMP_FILE="$(mktemp -t api.generated.ts.XXXXXX)"
trap 'rm -f "$TMP_SPEC" "$TMP_FILE"' EXIT

echo "[uv] exporting runtime spec..."
if ! uv run python scripts/ops/export_openapi.py --output "$TMP_SPEC" --compact; then
  echo "ERROR: runtime spec 匯出失敗（api.main:app import 不過？先跑 uv sync）"
  exit 1
fi

echo "[npx] generating types..."
npx --yes "openapi-typescript@${OPENAPI_TS_VERSION}" "$TMP_SPEC" -o "$TMP_FILE" 2>&1 | tail -5

if [[ ! -s "$TMP_FILE" ]]; then
  echo "ERROR: 型別生成失敗（空檔）"
  exit 1
fi

lines=$(wc -l < "$TMP_FILE")
echo "Generated: $lines lines"

STALE=0
for OUT_DIR in "${OUT_DIRS[@]}"; do
  OUT_FILE="$OUT_DIR/api.generated.ts"
  if [[ $CHECK_ONLY -eq 1 ]]; then
    if [[ -f "$OUT_FILE" ]] && diff -q "$TMP_FILE" "$OUT_FILE" > /dev/null 2>&1; then
      echo "✅ $OUT_FILE 已是最新"
    else
      echo "❌ $OUT_FILE 與 runtime 契約不同步"
      STALE=1
    fi
  else
    mkdir -p "$OUT_DIR"
    cp "$TMP_FILE" "$OUT_FILE"
    echo "✅ 寫入 $OUT_FILE"
  fi
done

if [[ $CHECK_ONLY -eq 1 ]]; then
  if [[ $STALE -eq 1 ]]; then
    echo ""
    echo "請執行：./scripts/ci/generate-api-types.sh"
    exit 1
  fi
  exit 0
fi

echo ""
echo "Next steps:"
echo "  1) 各站 tsc 驗證：cd web/<app> && npx tsc --noEmit"
echo "  2) CI 用 --check 模式阻擋未同步的 commit"
