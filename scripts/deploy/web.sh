#!/usr/bin/env bash
# ============================================================
# scripts/deploy/web.sh — Build, push, and deploy web/ to Cloud Run
#
# Usage:
#   ./scripts/deploy/web.sh              # 完整部署（build + push + deploy）
#   ./scripts/deploy/web.sh --build-only # 只 build image
#   ./scripts/deploy/web.sh --deploy-only # 用既有 image 重新部署
#
# Prereq（首次部署）：
#   - gcloud auth login + gcloud auth application-default login
#   - 已建立 Artifact Registry repo "lock-ai-repo"
#   - service account "lock-ai@PROJECT.iam.gserviceaccount.com" 存在
#
# 與 agent.sh / api.sh 共用同一個 lock-ai-repo 與 service account
# ============================================================
set -euo pipefail

# ── 品牌參數化(AI-3 / 20260702 會議 §三「一品牌一 GCP 專案」)──
# BRAND=<name> 時載入 scripts/deploy/brands/<name>.env 覆蓋下方預設;
# 未設 BRAND = 現行預設(locksmart 參考值),行為與參數化前完全相同。
# 用法:BRAND=brandx ./scripts/deploy/api.sh
_DEPLOY_SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -n "${BRAND:-}" ]]; then
    _BRAND_ENV="${_DEPLOY_SCRIPT_DIR}/brands/${BRAND}.env"
    if [[ ! -f "${_BRAND_ENV}" ]]; then
        echo "FAIL: 找不到品牌設定 ${_BRAND_ENV}(參考 brands/locksmart.env 建立)"
        exit 1
    fi
    # shellcheck disable=SC1090
    source "${_BRAND_ENV}"
    echo "已載入品牌設定:${BRAND} (${_BRAND_ENV})"
fi

# ── GCP 設定 ──
PROJECT_ID="${PROJECT_ID:-cedar-scope-489604-g3}"
REGION="${REGION:-asia-east1}"
SERVICE_NAME="${SERVICE_NAME:-smart-lock-web}"
API_SERVICE_NAME="${API_SERVICE_NAME:-}"   # 解析 api URL 烤入前端；預設依 WEB_APP 對映（見下）
REPO="${REPO:-lock-ai-repo}"

# Image tag: git short SHA + timestamp（支援 rollback）
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%Y%m%d-%H%M)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"
IMAGE_BASE="asia-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"
IMAGE="${IMAGE_BASE}:${IMAGE_TAG}"

# ── Cloud Run 設定 ──
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-lock-ai@${PROJECT_ID}.iam.gserviceaccount.com}"
PORT=8080
MEMORY="512Mi"     # Next.js standalone 不需要太多記憶體
CPU=1
MIN_INSTANCES=0
MAX_INSTANCES=3
TIMEOUT=60         # web 是 SSR，不需要 long-running request

# ── 環境變數（NEXT_PUBLIC_ 開頭的會編進 image，必須在 build time 注入）──
# 先讀本機 web/<app>/.env.production（如有），fallback 到預設值
# 檔案層拆分（2026-07-09）：WEB_APP 選站台目錄（預設 brand-portal = Cloud Run smart-lock-web 現況）
WEB_APP="${WEB_APP:-brand-portal}"
# API base 依站台對映（0723 UAT：tech-portal / platform-console 依 R6 runbook 部署時
# 未帶 API_SERVICE_NAME → bundle 烤成品牌 smart-lock-api → 技師站/平台 console 瀏覽器
# 登入被 CORS preflight 全擋。NEXT_PUBLIC_* 為 build-time 烤入，錯了只能重建。）
if [[ -z "${API_SERVICE_NAME}" ]]; then
    case "${WEB_APP}" in
        tech-portal)      API_SERVICE_NAME="lock-tech-api" ;;
        platform-console) API_SERVICE_NAME="lock-platform-api" ;;
        *)                API_SERVICE_NAME="smart-lock-api" ;;
    esac
fi
WEB_DIR="web/${WEB_APP}"
WEB_ENV_FILE="${WEB_DIR}/.env.production"
if [[ -f "${WEB_ENV_FILE}" ]]; then
    echo "  使用 ${WEB_ENV_FILE} 中的 NEXT_PUBLIC_* 設定"
fi
# Runtime 環境變數（不需要 build-time）
ENV_VARS="NODE_ENV=production"

# ── 切到 PROJECT_ROOT（docker build context）──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# ── 解析參數 ──
BUILD=true
DEPLOY=true
if [[ "${1:-}" == "--build-only" ]]; then
    DEPLOY=false
elif [[ "${1:-}" == "--deploy-only" ]]; then
    BUILD=false
fi

# ── Pre-flight ──
preflight_checks() {
    echo "=========================================="
    echo " Pre-flight 檢查"
    echo "=========================================="

    local failed=0

    if ! gcloud auth print-access-token &>/dev/null; then
        echo "  FAIL: gcloud 未登入，請執行: gcloud auth login"
        failed=1
    else
        echo "  OK: gcloud 已登入"
    fi

    local current_project
    current_project=$(gcloud config get-value project 2>/dev/null)
    if [[ "${current_project}" != "${PROJECT_ID}" ]]; then
        echo "  FAIL: 目前專案是 ${current_project}，預期 ${PROJECT_ID}"
        echo "        執行: gcloud config set project ${PROJECT_ID}"
        failed=1
    else
        echo "  OK: 專案 ${PROJECT_ID}"
    fi

    if ! docker info &>/dev/null; then
        echo "  FAIL: Docker daemon 未啟動"
        failed=1
    else
        echo "  OK: Docker daemon 運行中"
    fi

    # 檢查 web/ 必要檔
    if [[ ! -f "${WEB_DIR}/package.json" ]] || [[ ! -f "${WEB_DIR}/Dockerfile" ]]; then
        echo "  FAIL: ${WEB_DIR}/package.json 或 ${WEB_DIR}/Dockerfile 缺失"
        failed=1
    else
        echo "  OK: ${WEB_DIR}/package.json + ${WEB_DIR}/Dockerfile 存在"
    fi

    # 確認 next.config 設定 standalone output
    if ! grep -q 'output.*standalone' ${WEB_DIR}/next.config.* 2>/dev/null; then
        echo "  WARN: ${WEB_DIR}/next.config 沒設 output:standalone，image 會很大"
    else
        echo "  OK: next.config 啟用 standalone build"
    fi

    if [[ $failed -eq 1 ]]; then
        echo ""
        echo "Pre-flight 失敗，停止部署"
        exit 1
    fi
    echo ""
}

# ── Build & Push ──
build_and_push() {
    echo "=========================================="
    echo " Building image: ${IMAGE}"
    echo "=========================================="

    # NEXT_PUBLIC_* 在 build time 烤入 bundle：解析 api 的 Cloud Run URL，
    # 前端瀏覽器端 API base = https；即時推送 WebSocket = wss（同網域）。
    local api_url realtime_url
    api_url=$(gcloud run services describe "${API_SERVICE_NAME}" \
        --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)
    if [[ -z "${api_url}" ]]; then
        echo "  WARN: 找不到 ${API_SERVICE_NAME} URL —— web 會 fallback 到 localhost、即時推送停用。"
        echo "        請先部署 api 再部 web。"
        realtime_url=""
    else
        realtime_url="${api_url/https:\/\//wss://}"
        echo "  NEXT_PUBLIC_API_BASE_URL=${api_url}"
        echo "  NEXT_PUBLIC_REALTIME_BASE_URL=${realtime_url}"
    fi

    # 站台別 build args(0719 雲端 UAT C-1:本機 compose 有帶、雲端全缺 →
    # APP_MODE=all 跨站導向失效、「我是鎖匠師傅」死連結)。dispatch↔tech 互為
    # peer,URL 從對方 web 服務解析;解析不到留空(appMode 退站內路由)。
    local app_mode="" peer_url=""
    local peer_service="${PEER_WEB_SERVICE_NAME:-}"
    case "${WEB_APP}" in
        brand-portal)     app_mode="dispatch"; peer_service="${peer_service:-lock-tech-web}" ;;
        tech-portal)      app_mode="tech";     peer_service="${peer_service:-smart-lock-web}" ;;
        platform-console) app_mode="platform" ;;
        landing)          app_mode="landing" ;;  # 上雲時另補 NEXT_PUBLIC_*_PORTAL_URL CTA 目標
    esac
    if [[ -n "${peer_service}" ]]; then
        peer_url=$(gcloud run services describe "${peer_service}" \
            --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)
        if [[ -z "${peer_url}" ]]; then
            echo "  WARN: 找不到 peer 服務 ${peer_service} —— 跨站連結退回站內路由。"
        fi
    fi
    echo "  NEXT_PUBLIC_APP_MODE=${app_mode}"
    echo "  NEXT_PUBLIC_PEER_PORTAL_URL=${peer_url}"

    docker build --platform linux/amd64 -f ${WEB_DIR}/Dockerfile \
        --build-arg NEXT_PUBLIC_API_BASE_URL="${api_url}" \
        --build-arg NEXT_PUBLIC_REALTIME_BASE_URL="${realtime_url}" \
        --build-arg NEXT_PUBLIC_APP_MODE="${app_mode}" \
        --build-arg NEXT_PUBLIC_PEER_PORTAL_URL="${peer_url}" \
        -t "${IMAGE}" .

    echo ""
    echo "=========================================="
    echo " Pushing image to Artifact Registry"
    echo "=========================================="
    # 設定 docker push 的 credential helper
    gcloud auth configure-docker asia-east1-docker.pkg.dev --quiet
    docker push "${IMAGE}"
}

# ── Deploy to Cloud Run ──
deploy_to_cloud_run() {
    echo ""
    echo "=========================================="
    echo " Deploying to Cloud Run"
    echo "=========================================="

    gcloud run deploy "${SERVICE_NAME}" \
        --image="${IMAGE}" \
        --region="${REGION}" \
        --platform=managed \
        --service-account="${SERVICE_ACCOUNT}" \
        --port="${PORT}" \
        --memory="${MEMORY}" \
        --cpu="${CPU}" \
        --min-instances="${MIN_INSTANCES}" \
        --max-instances="${MAX_INSTANCES}" \
        --timeout="${TIMEOUT}" \
        --set-env-vars="${ENV_VARS}" \
        --allow-unauthenticated \
        --quiet

    echo ""
    echo "=========================================="
    echo " 部署完成"
    echo "=========================================="
    local service_url
    service_url=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" \
        --format='value(status.url)')
    echo "  Service URL: ${service_url}"
    echo "  Image tag  : ${IMAGE_TAG}"
}

# ── Health Check ──
health_check() {
    echo ""
    echo "=========================================="
    echo " Health Check"
    echo "=========================================="
    local service_url
    service_url=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" \
        --format='value(status.url)' 2>/dev/null)

    if [[ -z "${service_url}" ]]; then
        echo "  WARN: 取不到 service URL，跳過 health check"
        return
    fi

    # Next.js 沒有預設 /health，但 / 會回 200（dashboard 首頁）
    for i in $(seq 1 30); do
        local code
        code=$(curl -s -o /dev/null -w "%{http_code}" "${service_url}/" || echo "000")
        if [[ "${code}" == "200" ]]; then
            echo "  OK: ${service_url}/ → HTTP 200"
            return
        fi
        echo "  retry $i/30 (got ${code})"
        sleep 2
    done
    echo "  WARN: health check 30 次重試後仍未 200"
    echo "  手動檢查: gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --limit=50"
}

# ── 主流程 ──
preflight_checks

if [[ "${BUILD}" == "true" ]]; then
    build_and_push
fi

if [[ "${DEPLOY}" == "true" ]]; then
    deploy_to_cloud_run
    health_check
fi

echo ""
echo "Done. To rollback: gcloud run services update-traffic ${SERVICE_NAME} \\"
echo "  --region=${REGION} --to-revisions=<PREVIOUS_REVISION>=100"
