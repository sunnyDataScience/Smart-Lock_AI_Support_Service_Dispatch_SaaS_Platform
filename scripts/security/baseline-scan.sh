#!/usr/bin/env bash
# baseline-scan.sh — 上線前資安基線掃描(AI-5/6,20260702 會議 §四三件套的 AI 半)
#
# 三件套對應:
#   壓測      → 既有 loadtest/(Locust 100 VU + SLA gate,CR-0019),不在本腳本
#   弱點掃描  → 本腳本:依賴弱掃(pip-audit / npm audit)+ 容器映像掃(trivy,選配)
#   資安掃描  → 本腳本:secrets 掃(gitleaks,選配)+ Web 基線(OWASP ZAP baseline,選配)
#
# 設計:工具存在才跑、缺工具列「跳過 + 安裝指令」,永不因缺工具而 exit 1;
# 掃描發現高風險才 exit 1(CI gate 可用)。報告輸出 scripts/security/reports/
# (gitignore)。公司資安人員指定工具後(會議 AI-5,人工項),再對齊替換。
#
# 用法:
#   ./scripts/security/baseline-scan.sh              # 全部(可用的)掃描
#   ./scripts/security/baseline-scan.sh --deps-only  # 只掃依賴(pip/npm,最快)
#   ZAP_TARGET=https://<web-url> ./scripts/security/baseline-scan.sh  # 加 ZAP 基線
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPORT_DIR="${SCRIPT_DIR}/reports"
mkdir -p "${REPORT_DIR}"
TS=$(date +%Y%m%d-%H%M)

c_grn=$'\033[32m'; c_red=$'\033[31m'; c_yel=$'\033[33m'; c_rst=$'\033[0m'
ok()   { printf '%s[scan]%s %s\n' "$c_grn" "$c_rst" "$*"; }
warn() { printf '%s[scan]%s %s\n' "$c_yel" "$c_rst" "$*"; }
bad()  { printf '%s[scan]%s %s\n' "$c_red" "$c_rst" "$*"; }

FAILED=0
DEPS_ONLY=false
[[ "${1:-}" == "--deps-only" ]] && DEPS_ONLY=true

# ── 1. Python 依賴弱掃(pip-audit,經 uvx 免安裝)────────────────────────
echo "── [1/5] Python 依賴弱掃(pip-audit)──"
if command -v uvx &>/dev/null || command -v uv &>/dev/null; then
    RUNNER="uvx"; command -v uvx &>/dev/null || RUNNER="uv tool run"
    # 對 uv.lock 匯出的 requirements 掃(workspace 全依賴)
    if (cd "${PROJECT_ROOT}" && uv export --frozen --no-emit-project --no-emit-workspace --no-hashes -o "${REPORT_DIR}/requirements-${TS}.txt" &>/dev/null); then
        if ${RUNNER} pip-audit -r "${REPORT_DIR}/requirements-${TS}.txt" --disable-pip --no-deps \
             -f json -o "${REPORT_DIR}/pip-audit-${TS}.json" 2>"${REPORT_DIR}/pip-audit-${TS}.err"; then
            ok "pip-audit:無已知漏洞(報告 ${REPORT_DIR}/pip-audit-${TS}.json)"
        else
            VULN_N=$(python3 -c "import json;print(len(json.load(open('${REPORT_DIR}/pip-audit-${TS}.json')).get('dependencies',[])))" 2>/dev/null || echo "?")
            bad "pip-audit:發現漏洞(詳 ${REPORT_DIR}/pip-audit-${TS}.json)"
            FAILED=1
        fi
    else
        warn "uv export 失敗 → 跳過 pip-audit"
    fi
else
    warn "跳過(缺 uv;安裝:brew install uv)"
fi

# ── 2. Node 依賴弱掃(npm audit)─────────────────────────────────────────
echo "── [2/5] Node 依賴弱掃(npm audit)──"
if command -v npm &>/dev/null && [[ -f "${PROJECT_ROOT}/web/package-lock.json" ]]; then
    if (cd "${PROJECT_ROOT}/web" && npm audit --omit=dev --audit-level=high --json > "${REPORT_DIR}/npm-audit-${TS}.json" 2>/dev/null); then
        ok "npm audit:無 high/critical(報告 ${REPORT_DIR}/npm-audit-${TS}.json)"
    else
        bad "npm audit:有 high/critical 漏洞(詳 ${REPORT_DIR}/npm-audit-${TS}.json;修復:cd web && npm audit fix)"
        FAILED=1
    fi
else
    warn "跳過(缺 npm 或 web/package-lock.json)"
fi

if $DEPS_ONLY; then
    echo "── --deps-only:跳過 secrets/映像/ZAP ──"
    exit $FAILED
fi

# ── 3. Secrets 掃描(gitleaks,選配)──────────────────────────────────────
echo "── [3/5] Secrets 掃描(gitleaks)──"
if command -v gitleaks &>/dev/null; then
    if gitleaks detect --source "${PROJECT_ROOT}" --report-path "${REPORT_DIR}/gitleaks-${TS}.json" --no-banner 2>/dev/null; then
        ok "gitleaks:無外洩 secrets"
    else
        bad "gitleaks:疑似 secrets 外洩(詳 ${REPORT_DIR}/gitleaks-${TS}.json)"
        FAILED=1
    fi
else
    warn "跳過(缺 gitleaks;安裝:brew install gitleaks)"
fi

# ── 4. 容器映像弱掃(trivy,選配)────────────────────────────────────────
echo "── [4/5] 容器映像弱掃(trivy)──"
if command -v trivy &>/dev/null; then
    for img in lock-dispatch-locksmart-api:latest lock-dispatch-locksmart-web:latest; do
        if docker image inspect "$img" &>/dev/null; then
            if trivy image --severity HIGH,CRITICAL --exit-code 1 -q \
                 -o "${REPORT_DIR}/trivy-${img%%:*}-${TS}.txt" "$img" 2>/dev/null; then
                ok "trivy ${img}:無 HIGH/CRITICAL"
            else
                bad "trivy ${img}:有 HIGH/CRITICAL(詳 reports/)"
                FAILED=1
            fi
        else
            warn "跳過 ${img}(映像不存在,先 docker compose build)"
        fi
    done
else
    warn "跳過(缺 trivy;安裝:brew install trivy)"
fi

# ── 5. Web 基線掃描(OWASP ZAP baseline,選配;需 ZAP_TARGET)──────────────
echo "── [5/5] OWASP ZAP baseline──"
if [[ -n "${ZAP_TARGET:-}" ]]; then
    if command -v docker &>/dev/null; then
        # zap-baseline:被動掃描(不攻擊),適合對 staging/prod 跑;警告不視為 fail
        docker run --rm -v "${REPORT_DIR}:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable \
            zap-baseline.py -t "${ZAP_TARGET}" -r "zap-baseline-${TS}.html" -I \
            && ok "ZAP baseline 完成(報告 reports/zap-baseline-${TS}.html)" \
            || warn "ZAP baseline 有警告(報告 reports/zap-baseline-${TS}.html,人工檢視)"
    else
        warn "跳過(缺 docker)"
    fi
else
    warn "跳過(未設 ZAP_TARGET;用法:ZAP_TARGET=https://<web-url> $0)"
fi

echo "=========================================="
if [[ $FAILED -eq 0 ]]; then
    ok "基線掃描完成:無阻擋級發現(報告在 ${REPORT_DIR}/)"
else
    bad "基線掃描完成:有阻擋級發現,上線前需處理(報告在 ${REPORT_DIR}/)"
fi
exit $FAILED
