#!/usr/bin/env bash
# scripts/ci/contract-schemathesis.sh — OpenAPI 合約 fuzz 測試
#
# 對應 docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md §5.2 contract layer (5%)
# 與 §10 #21。用 schemathesis 對既有 91 ops 衍生 N 個 fuzz example，
# 驗證實際 API 回應符合 OpenAPI spec 宣告的 status code / schema / headers。
#
# 用法：
#   ./scripts/ci/contract-schemathesis.sh                      # 預設 :8001
#   API_BASE=http://localhost:8000 ./scripts/ci/contract-schemathesis.sh
#   MAX_EXAMPLES=20 ./scripts/ci/contract-schemathesis.sh      # 加深 fuzz
#
# 設計原則：
#   - 不啟動 api（呼叫者責任）；只檢查連通性
#   - 失敗時印明確修復提示
#   - 支援 --check-only 模式（只跑 spec 結構檢查，不打 api）

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SPEC="$REPO_ROOT/docs/02-design/specs/openapi.yaml"
API_BASE="${API_BASE:-http://localhost:8001}"
MAX_EXAMPLES="${MAX_EXAMPLES:-10}"
CHECK_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --check-only) CHECK_ONLY=1 ;;
    -h|--help)
      sed -n '2,/^set -uo/p' "$0" | grep -E '^# ' | sed 's/^# //'
      exit 0 ;;
    *) echo "[schemathesis] unknown flag: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf '\033[36m[schemathesis]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[schemathesis]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[schemathesis]\033[0m %s\n' "$*" >&2; }

# ── Spec 存在性 ────────────────────────────────────────────────
if [[ ! -f "$SPEC" ]]; then
  err "OpenAPI spec not found at: $SPEC"
  exit 1
fi
log "spec: $SPEC"

# ── schemathesis CLI 存在性 ────────────────────────────────────
if ! uv run schemathesis --version >/dev/null 2>&1; then
  err "schemathesis 不可用。請先跑：uv sync --group test"
  exit 1
fi
log "tool: $(uv run schemathesis --version 2>&1 | head -1)"

# ── --check-only：只驗 spec 結構（不打 api） ───────────────────
if (( CHECK_ONLY == 1 )); then
  log "check-only mode：只跑 OpenAPI 結構檢查（不打 api）"
  if uv run python -c "import yaml; yaml.safe_load(open('$SPEC'))" 2>/dev/null; then
    log "✓ OpenAPI spec YAML 結構合法"
    exit 0
  else
    err "✗ OpenAPI spec YAML 解析失敗"
    exit 1
  fi
fi

# ── api 連通性 ──────────────────────────────────────────────────
log "checking api connectivity at: $API_BASE"
if ! curl -fsS "$API_BASE/health" >/dev/null 2>&1; then
  err "api not responding at $API_BASE/health"
  err "  請先啟動 api：cd api && uv run uvicorn main:app --port 8001"
  err "  或設 API_BASE 指向其他位置：API_BASE=http://localhost:8000 $0"
  exit 1
fi
log "✓ api 健康檢查通過"

# ── 執行 schemathesis ───────────────────────────────────────────
log "running fuzz: max examples=$MAX_EXAMPLES per operation"
log "target: $API_BASE"
echo ""

# --checks all 包含 status_code / content_type / response_schema 等
# --hypothesis-max-examples 限制 fuzz 數量（避免 PR 跑太久）
# --hypothesis-deadline 單 case timeout
uv run schemathesis run "$SPEC" \
  --base-url "$API_BASE" \
  --checks all \
  --hypothesis-max-examples="$MAX_EXAMPLES" \
  --hypothesis-deadline=10000 \
  --workers 2 \
  --show-errors-tracebacks
RC=$?

echo ""
if (( RC == 0 )); then
  log "✓ contract test 全綠（91 ops × $MAX_EXAMPLES examples）"
else
  warn "contract test 失敗（rc=$RC）— 請檢視上方報告，修補 spec 或實作"
fi
exit $RC
