#!/usr/bin/env bash
#
# check-operationid-orphans.sh
# --------------------------------
# 檢查 SSOT 契約與文件之間的 operationId 一致性：
#   1) OpenAPI operationId 必須被至少一個 flow 文件或 page spec 引用
#   2) flow 文件與 page spec 中引用的 operationId 必須在 OpenAPI 中存在
#   3) AsyncAPI operationId 同樣檢查
#   4) [PAGE META] openapi_ops 宣告必須在 OpenAPI 中存在（always strict）
#   5) [PAGE META] asyncapi_ops 宣告必須在 AsyncAPI 中存在（always strict）
#   6) spec body 中 /api/v1/ path 必須在 OpenAPI paths 中存在（advisory / strict）
#
# 輸出：孤兒 / 斷鏈清單，exit code 1 表示有問題
#
# Usage:
#   ./scripts/check-operationid-orphans.sh
#   ./scripts/check-operationid-orphans.sh --quiet   # 僅顯示結果摘要
#   ./scripts/check-operationid-orphans.sh --strict  # body path 也視為 error

set -uo pipefail
# 不用 -e：本腳本大量使用 comm/grep 正常情況下會 exit 非 0

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OPENAPI="docs/02-design/specs/openapi.yaml"
ASYNCAPI="docs/02-design/specs/asyncapi.yaml"
FLOWS_DIR="docs/02-design"
PAGES_DIR="web_design_spec_prompt_pipeline/pages"
MAPPING="$PAGES_DIR/MAPPING.md"

QUIET=0
STRICT=0
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=1 ;;
    --strict) STRICT=1 ;;  # 使 dangling 觸發 exit 1（Week 5+ 啟用）
  esac
done

errors=0

log() {
  [[ $QUIET -eq 0 ]] && echo "$@"
}

extract_operation_ids() {
  # 從 yaml 擷取所有 operationId 值
  grep -E "^\s+operationId:\s+" "$1" | sed -E 's/.*operationId:\s+([a-zA-Z0-9_]+).*/\1/' | sort -u
}

# ----------------------------------------------------------------------
# 1. 收集 OpenAPI operationId
# ----------------------------------------------------------------------
if [[ ! -f "$OPENAPI" ]]; then
  echo "ERROR: $OPENAPI not found"
  exit 1
fi

openapi_ops=$(extract_operation_ids "$OPENAPI")
openapi_count=$(echo "$openapi_ops" | wc -l | tr -d ' ')

log "=== OpenAPI operationIds: $openapi_count ==="
[[ $QUIET -eq 0 ]] && echo "$openapi_ops" | sed 's/^/  /'

# ----------------------------------------------------------------------
# 2. 收集所有文件中引用的 operationId
# ----------------------------------------------------------------------
# 合併 flow 文件 + page spec + MAPPING
referenced_ops=$(
  grep -rhoE "\`?openapi#operationId=[a-zA-Z0-9_]+\`?|\`([a-zA-Z0-9_]+)\`" \
    "$FLOWS_DIR" "$PAGES_DIR" 2>/dev/null \
    | sed -E 's/.*operationId=//; s/[\`,]//g' \
    | sort -u
)

# 另一種格式：直接列 operationId 名（如 `listWorkOrders` 在 markdown 中）
# 我們只接受有 operationId= 明確引用的，其他為 false positive
explicit_refs=$(
  grep -rhoE "operationId=[a-zA-Z0-9_]+" \
    "$FLOWS_DIR" "$PAGES_DIR" 2>/dev/null \
    | sed -E 's/operationId=//' \
    | sort -u
)

# 流程文件 metadata 區塊的裸 operationId（格式 `listConversations` 在 Endpoints: 行）
bare_refs_in_metadata=$(
  grep -rhE "^>\s*\*\*Endpoints" \
    "$FLOWS_DIR" 2>/dev/null \
    | grep -oE "\`[a-zA-Z][a-zA-Z0-9_]*\`" \
    | tr -d '`' \
    | sort -u
)

# 過濾明顯佔位符（README 的 xxx/yyy 等教學範例）
all_refs=$(printf "%s\n%s\n%s\n" "$explicit_refs" "$bare_refs_in_metadata" \
  | grep -Ev "^(xxx|yyy|foo|bar|YOUR_|example|TODO)$" \
  | sort -u \
  | grep -v '^$' || true)
ref_count=$(echo "$all_refs" | wc -l | tr -d ' ')

log ""
log "=== Referenced operationIds in docs: $ref_count ==="
[[ $QUIET -eq 0 ]] && echo "$all_refs" | sed 's/^/  /'

# ----------------------------------------------------------------------
# 3. 檢查孤兒：OpenAPI 定義但無文件引用
# ----------------------------------------------------------------------
log ""
log "=== Check 1: Orphan operationIds（已定義但文件無引用）==="
orphans=$(comm -23 <(echo "$openapi_ops") <(echo "$all_refs") || true)
if [[ -n "$orphans" ]]; then
  orphan_count=$(echo "$orphans" | wc -l | tr -d ' ')
  log "⚠️  發現 $orphan_count 個孤兒 operationId（OpenAPI 有定義，文件未引用）："
  [[ $QUIET -eq 0 ]] && echo "$orphans" | sed 's/^/    /'
  # 骨架階段孤兒是 warning 不是 error
  log "   （骨架階段視為 warning — Week 4 後所有新端點應有對應 flow/page 引用）"
else
  log "✅ 無孤兒 operationId"
fi

# ----------------------------------------------------------------------
# 4. 檢查斷鏈：文件引用但 OpenAPI 未定義
# ----------------------------------------------------------------------
log ""
log "=== Check 2: Dangling references（文件引用但 OpenAPI 未定義）==="
dangling=$(comm -13 <(echo "$openapi_ops") <(echo "$all_refs") || true)
if [[ -n "$dangling" ]]; then
  dangling_count=$(echo "$dangling" | wc -l | tr -d ' ')
  if [[ $STRICT -eq 1 ]]; then
    log "❌ 發現 $dangling_count 個斷鏈 operationId（文件引用但 OpenAPI 未定義）："
    [[ $QUIET -eq 0 ]] && echo "$dangling" | sed 's/^/    /'
    errors=$((errors + dangling_count))
  else
    log "⚠️  發現 $dangling_count 個 pending operationId（文件引用但 OpenAPI 未定義）："
    [[ $QUIET -eq 0 ]] && echo "$dangling" | sed 's/^/    /'
    log "   （非 strict 模式視為 TODO。啟用 --strict 轉為 error）"
  fi
else
  log "✅ 無斷鏈 operationId"
fi

# ----------------------------------------------------------------------
# 5. AsyncAPI operationIds（WS/事件）
# ----------------------------------------------------------------------
if [[ -f "$ASYNCAPI" ]]; then
  async_ops=$(extract_operation_ids "$ASYNCAPI")
  async_count=$(echo "$async_ops" | wc -l | tr -d ' ')
  log ""
  log "=== AsyncAPI operationIds: $async_count ==="

  # MAPPING.md §7.1 應該列出所有 async operationId
  async_referenced=$(grep -oE "\`[a-zA-Z][a-zA-Z0-9_]*\`" "$MAPPING" 2>/dev/null \
    | tr -d '`' | sort -u || true)
  async_orphans=$(comm -23 <(echo "$async_ops") <(echo "$async_referenced") || true)
  if [[ -n "$async_orphans" ]]; then
    log "⚠️  AsyncAPI 孤兒（未被 MAPPING.md §7.1 索引）："
    [[ $QUIET -eq 0 ]] && echo "$async_orphans" | sed 's/^/    /'
  else
    log "✅ AsyncAPI operationId 全部被索引"
  fi
fi

# ----------------------------------------------------------------------
# 6. Check 3: [PAGE META] openapi_ops 宣告驗證（always strict）
# ----------------------------------------------------------------------
log ""
log "=== Check 3: [PAGE META] openapi_ops 宣告驗證 ==="
meta_openapi_errors=0

for spec_file in "$PAGES_DIR"/*.md; do
  [[ "$(basename "$spec_file")" == "MAPPING.md" ]] && continue
  [[ "$(basename "$spec_file")" == "page_template.md" ]] && continue

  # 擷取 openapi_ops 行
  ops_line=$(grep -E '^\- \*\*openapi_ops\*\*:' "$spec_file" 2>/dev/null || true)
  [[ -z "$ops_line" ]] && continue

  # 取值：去掉前綴、分割逗號
  ops_value=$(echo "$ops_line" | sed -E 's/^- \*\*openapi_ops\*\*:\s*//')
  [[ "$ops_value" == "none" ]] && continue

  IFS=',' read -ra ops_arr <<< "$ops_value"
  for op in "${ops_arr[@]}"; do
    op=$(echo "$op" | tr -d ' ')
    [[ -z "$op" ]] && continue
    if ! echo "$openapi_ops" | grep -qx "$op"; then
      log "❌ $(basename "$spec_file"): openapi_ops 宣告 '$op' 不存在於 openapi.yaml"
      meta_openapi_errors=$((meta_openapi_errors + 1))
    fi
  done
done

if [[ $meta_openapi_errors -gt 0 ]]; then
  errors=$((errors + meta_openapi_errors))
  log "   共 $meta_openapi_errors 個 [PAGE META] openapi_ops 錯誤"
else
  log "✅ 所有 [PAGE META] openapi_ops 宣告合法"
fi

# ----------------------------------------------------------------------
# 7. Check 4: [PAGE META] asyncapi_ops 宣告驗證（always strict）
# ----------------------------------------------------------------------
if [[ -f "$ASYNCAPI" ]]; then
  log ""
  log "=== Check 4: [PAGE META] asyncapi_ops 宣告驗證 ==="
  meta_async_errors=0

  for spec_file in "$PAGES_DIR"/*.md; do
    [[ "$(basename "$spec_file")" == "MAPPING.md" ]] && continue
    [[ "$(basename "$spec_file")" == "page_template.md" ]] && continue

    ops_line=$(grep -E '^\- \*\*asyncapi_ops\*\*:' "$spec_file" 2>/dev/null || true)
    [[ -z "$ops_line" ]] && continue

    ops_value=$(echo "$ops_line" | sed -E 's/^- \*\*asyncapi_ops\*\*:\s*//')
    [[ "$ops_value" == "none" ]] && continue

    IFS=',' read -ra ops_arr <<< "$ops_value"
    for op in "${ops_arr[@]}"; do
      op=$(echo "$op" | tr -d ' ')
      [[ -z "$op" ]] && continue
      if ! echo "$async_ops" | grep -qx "$op"; then
        log "❌ $(basename "$spec_file"): asyncapi_ops 宣告 '$op' 不存在於 asyncapi.yaml"
        meta_async_errors=$((meta_async_errors + 1))
      fi
    done
  done

  if [[ $meta_async_errors -gt 0 ]]; then
    errors=$((errors + meta_async_errors))
    log "   共 $meta_async_errors 個 [PAGE META] asyncapi_ops 錯誤"
  else
    log "✅ 所有 [PAGE META] asyncapi_ops 宣告合法"
  fi
fi

# ----------------------------------------------------------------------
# 8. Check 5: spec body /api/v1/ path 驗證（advisory / --strict）
# ----------------------------------------------------------------------
log ""
log "=== Check 5: spec body /api/v1/ path 驗證 ==="

# 收集 openapi.yaml 中定義的所有 path（正規化：去掉參數名）
openapi_paths=$(grep -E '^\s+/api/' "$OPENAPI" 2>/dev/null \
  | sed -E 's/^\s+//; s/:\s*$//' \
  | sed -E 's/\{[^}]+\}/{_}/g' \
  | sort -u || true)

body_path_warnings=0
for spec_file in "$PAGES_DIR"/*.md; do
  [[ "$(basename "$spec_file")" == "MAPPING.md" ]] && continue
  [[ "$(basename "$spec_file")" == "page_template.md" ]] && continue

  # 擷取 body 中的 /api/v1/ path（從 backtick 或裸文）
  body_paths=$(grep -oE '/api/v[0-9]+/[a-zA-Z0-9/_{}.-]+' "$spec_file" 2>/dev/null \
    | sed -E 's/\{[^}]+\}/{_}/g' \
    | sort -u || true)
  [[ -z "$body_paths" ]] && continue

  while IFS= read -r bpath; do
    if ! echo "$openapi_paths" | grep -qx "$bpath"; then
      if [[ $STRICT -eq 1 ]]; then
        log "❌ $(basename "$spec_file"): path '$bpath' 不存在於 openapi.yaml"
        body_path_warnings=$((body_path_warnings + 1))
      else
        log "⚠️  $(basename "$spec_file"): path '$bpath' 不存在於 openapi.yaml（planned?）"
        body_path_warnings=$((body_path_warnings + 1))
      fi
    fi
  done <<< "$body_paths"
done

if [[ $body_path_warnings -gt 0 ]]; then
  if [[ $STRICT -eq 1 ]]; then
    errors=$((errors + body_path_warnings))
    log "   共 $body_path_warnings 個 body path 錯誤（strict 模式）"
  else
    log "   共 $body_path_warnings 個 body path 警告（啟用 --strict 轉為 error）"
  fi
else
  log "✅ 所有 spec body /api/ path 已定義於 openapi.yaml"
fi

# ----------------------------------------------------------------------
# 總結
# ----------------------------------------------------------------------
log ""
log "=== Summary ==="
log "  OpenAPI operationIds:  $openapi_count"
log "  Referenced in docs:    $ref_count"
log "  Orphans (warning):     $(echo "$orphans" | grep -c . || echo 0)"
log "  Dangling (warning):    $(echo "$dangling" | grep -c . || echo 0)"
log "  META ops errors:       $((meta_openapi_errors + ${meta_async_errors:-0}))"
log "  Body path issues:      $body_path_warnings"

if [[ $errors -gt 0 ]]; then
  [[ $QUIET -eq 1 ]] && echo "FAIL: $errors error(s)"
  exit 1
fi

[[ $QUIET -eq 1 ]] && echo "OK"
exit 0
