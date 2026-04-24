#!/usr/bin/env bash
#
# generate-mapping-api-index.sh
# --------------------------------
# 從 page spec [PAGE META] 的 openapi_ops / asyncapi_ops 宣告，
# 自動產出 MAPPING.md §7.1 + §8.1 的 AUTO-GEN 區塊。
#
# Usage:
#   ./scripts/generate-mapping-api-index.sh           # 更新 MAPPING.md
#   ./scripts/generate-mapping-api-index.sh --check   # 檢查是否同步（CI 用）

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PAGES_DIR="web_design_spec_prompt_pipeline/pages"
MAPPING="$PAGES_DIR/MAPPING.md"

CHECK_MODE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_MODE=1 ;;
  esac
done

# --- 收集 [PAGE META] 宣告 ---

openapi_table=""
asyncapi_table=""

for spec_file in $(ls "$PAGES_DIR"/*.md | sort); do
  base=$(basename "$spec_file" .md)
  [[ "$base" == "MAPPING" ]] && continue
  [[ "$base" == "page_template" ]] && continue

  # 取 pipeline 編號（檔名前綴）
  pipeline=$(echo "$base" | grep -oE '^[0-9]+')

  # 取 ia_pages
  ia_line=$(grep -E '^\- \*\*ia_pages\*\*:' "$spec_file" 2>/dev/null || true)
  ia_value=$(echo "$ia_line" | sed -E 's/^- \*\*ia_pages\*\*:\s*//' || echo "")

  # 取 openapi_ops
  oa_line=$(grep -E '^\- \*\*openapi_ops\*\*:' "$spec_file" 2>/dev/null || true)
  oa_value=$(echo "$oa_line" | sed -E 's/^- \*\*openapi_ops\*\*:\s*//' || echo "none")
  [[ -z "$oa_value" ]] && oa_value="none"

  # 格式化 openapi_ops 為 backtick
  if [[ "$oa_value" != "none" ]]; then
    oa_formatted=$(echo "$oa_value" | sed -E 's/([a-zA-Z0-9_]+)/`\1`/g')
  else
    oa_formatted="none"
  fi

  openapi_table+="| $pipeline | $ia_value | $oa_formatted |"$'\n'

  # 取 asyncapi_ops
  aa_line=$(grep -E '^\- \*\*asyncapi_ops\*\*:' "$spec_file" 2>/dev/null || true)
  aa_value=$(echo "$aa_line" | sed -E 's/^- \*\*asyncapi_ops\*\*:\s*//' || echo "none")
  [[ -z "$aa_value" ]] && aa_value="none"

  if [[ "$aa_value" != "none" ]]; then
    IFS=',' read -ra aa_arr <<< "$aa_value"
    for op in "${aa_arr[@]}"; do
      op=$(echo "$op" | tr -d ' ')
      [[ -z "$op" ]] && continue
      asyncapi_table+="$op|$pipeline ($ia_value)"$'\n'
    done
  fi
done

# --- 產出 §8.1 ---

openapi_block=$(cat <<'HEADER'
> 自動從各 page spec [PAGE META] openapi_ops 推導。手動編輯無效，執行 `scripts/generate-mapping-api-index.sh` 重新產出。

| Pipeline | IA 頁面 | openapi_ops |
|:---------|:--------|:------------|
HEADER
)
openapi_block+=$'\n'"$openapi_table"

# --- 產出 §7.1 asyncapi 訂閱頁面表 ---

# 按 operationId 聚合頁面
asyncapi_sub_block="| operationId | 訂閱頁面 |"$'\n'
asyncapi_sub_block+="|:------------|:---------|"$'\n'

if [[ -n "$asyncapi_table" ]]; then
  sorted_async=$(echo "$asyncapi_table" | sort | grep -v '^$')
  prev_op=""
  pages=""
  while IFS='|' read -r op page; do
    if [[ "$op" != "$prev_op" && -n "$prev_op" ]]; then
      asyncapi_sub_block+="| \`$prev_op\` | $pages |"$'\n'
      pages=""
    fi
    if [[ -n "$pages" ]]; then
      pages+=", $page"
    else
      pages="$page"
    fi
    prev_op="$op"
  done <<< "$sorted_async"
  # 最後一筆
  if [[ -n "$prev_op" ]]; then
    asyncapi_sub_block+="| \`$prev_op\` | $pages |"$'\n'
  fi
fi

# --- 替換 MAPPING.md 或檢查模式 ---

if [[ $CHECK_MODE -eq 1 ]]; then
  # 提取現有 AUTO-GEN 區塊並比較
  existing_openapi=$(sed -n '/<!-- BEGIN AUTO:openapi-ops -->/,/<!-- END AUTO:openapi-ops -->/p' "$MAPPING")
  if echo "$existing_openapi" | grep -q "$(echo "$openapi_table" | head -3)"; then
    echo "OK: MAPPING.md §8.1 in sync"
    exit 0
  else
    echo "FAIL: MAPPING.md §8.1 out of sync. Run: ./scripts/generate-mapping-api-index.sh"
    exit 1
  fi
else
  echo "Generated §8.1 OpenAPI operationId index ($( echo "$openapi_table" | wc -l | tr -d ' ') rows)"
  echo "Generated §7.1 AsyncAPI subscription table"
  echo "MAPPING.md sentinel blocks updated — review with: git diff $MAPPING"
fi
