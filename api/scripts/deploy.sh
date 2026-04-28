#!/usr/bin/env bash
# ============================================================
# api/scripts/deploy.sh — Build, push, and deploy api/ to Cloud Run
#
# Usage:
#   ./api/scripts/deploy.sh              # 完整部署（build + push + deploy）
#   ./api/scripts/deploy.sh --build-only # 只建立 image 不部署
#   ./api/scripts/deploy.sh --deploy-only # 只部署（用已存在的 image）
#
# Prereq:
#   gcloud secrets create API_JWT_SECRET_KEY --data-file=- <<< "$(openssl rand -hex 32)"
# ============================================================
set -euo pipefail

# ── GCP 設定 ──
PROJECT_ID="cedar-scope-489604-g3"
REGION="asia-east1"
SERVICE_NAME="smart-lock-api"
REPO="lock-ai-repo"

# Image tag: git short SHA + timestamp（支援 rollback）
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%Y%m%d-%H%M)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"
IMAGE_BASE="asia-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"
IMAGE="${IMAGE_BASE}:${IMAGE_TAG}"

# ── Cloud Run 設定 ──
SERVICE_ACCOUNT="lock-ai@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUDSQL_INSTANCE="${PROJECT_ID}:${REGION}:lock-ai"
PORT=8080
MEMORY="1Gi"
CPU=1
MIN_INSTANCES=0
MAX_INSTANCES=3
TIMEOUT=300

# ── 環境變數 ──
ENV_VARS="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=asia-northeast1"

# ── Secrets（Secret Manager → 環境變數）──
SECRETS="POSTGRES_URI=POSTGRES_URI:latest"
SECRETS="${SECRETS},JWT_SECRET_KEY=API_JWT_SECRET_KEY:latest"

# ── 切到 api 目錄（Dockerfile 所在位置）──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."

# ── 解析參數 ──
BUILD=true
DEPLOY=true
if [[ "${1:-}" == "--build-only" ]]; then
    DEPLOY=false
elif [[ "${1:-}" == "--deploy-only" ]]; then
    BUILD=false
fi

# ── 工具函式 ──

preflight_checks() {
    echo "=========================================="
    echo " Pre-flight 檢查 (smart-lock-api)"
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

    local required_secrets=("POSTGRES_URI" "API_JWT_SECRET_KEY")
    for secret in "${required_secrets[@]}"; do
        if gcloud secrets describe "${secret}" &>/dev/null; then
            echo "  OK: Secret ${secret}"
        else
            echo "  FAIL: Secret ${secret} 不存在"
            if [[ "${secret}" == "API_JWT_SECRET_KEY" ]]; then
                echo "        執行: openssl rand -hex 32 | gcloud secrets create API_JWT_SECRET_KEY --data-file=-"
                echo "        並授權: gcloud secrets add-iam-policy-binding API_JWT_SECRET_KEY \\"
                echo "                  --member=serviceAccount:${SERVICE_ACCOUNT} \\"
                echo "                  --role=roles/secretmanager.secretAccessor"
            fi
            failed=1
        fi
    done

    echo ""
    if [[ $failed -ne 0 ]]; then
        echo "Pre-flight 檢查失敗，中止部署。"
        exit 1
    fi
    echo "Pre-flight 檢查全部通過。"
}

health_check_with_retry() {
    local url="$1"
    local max_attempts=6
    local wait_secs=10

    echo ""
    echo "Running health check (最多等待 ${max_attempts}x${wait_secs}s)..."

    for i in $(seq 1 $max_attempts); do
        local response http_code body
        response=$(curl -s -w "\n%{http_code}" "${url}/health" 2>/dev/null) || true
        http_code=$(echo "${response}" | tail -1)
        body=$(echo "${response}" | head -1)

        if [[ "${http_code}" == "200" ]]; then
            echo "Health check PASSED (HTTP ${http_code})"
            echo "  ${body}"
            return 0
        elif [[ "${http_code}" == "503" ]]; then
            echo "Health check: 服務降級 (HTTP 503) — DB 連線異常"
            echo "  ${body}"
            return 1
        fi

        echo "  Attempt ${i}/${max_attempts}: HTTP ${http_code} — 等待 ${wait_secs}s..."
        sleep $wait_secs
    done

    echo "Health check FAILED"
    return 1
}

# ── 主流程 ──

if $DEPLOY; then
    preflight_checks
fi

# ── Step 1: Build & Push ──
if $BUILD; then
    echo ""
    echo "=========================================="
    echo " Building image: ${IMAGE}"
    echo "=========================================="
    docker build --platform linux/amd64 -t "${IMAGE}" .
    docker tag "${IMAGE}" "${IMAGE_BASE}:latest"

    echo ""
    echo "=========================================="
    echo " Pushing image to Artifact Registry"
    echo "=========================================="
    docker push "${IMAGE}"
    docker push "${IMAGE_BASE}:latest"

    echo ""
    echo "Image pushed: ${IMAGE}"
fi

# ── Step 2: Deploy to Cloud Run ──
if $DEPLOY; then
    local_image="${IMAGE}"
    if ! $BUILD; then
        local_image="${IMAGE_BASE}:latest"
    fi

    echo ""
    echo "=========================================="
    echo " Deploying to Cloud Run: ${SERVICE_NAME}"
    echo " Image: ${local_image}"
    echo "=========================================="

    gcloud run deploy "${SERVICE_NAME}" \
        --image="${local_image}" \
        --region="${REGION}" \
        --platform=managed \
        --allow-unauthenticated \
        --service-account="${SERVICE_ACCOUNT}" \
        --port="${PORT}" \
        --memory="${MEMORY}" \
        --cpu="${CPU}" \
        --cpu-boost \
        --execution-environment=gen2 \
        --min-instances="${MIN_INSTANCES}" \
        --max-instances="${MAX_INSTANCES}" \
        --timeout="${TIMEOUT}" \
        --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
        --set-env-vars="${ENV_VARS}" \
        --set-secrets="${SECRETS}"

    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" \
        --format='value(status.url)')

    echo ""
    echo "=========================================="
    echo " Deployment complete!"
    echo " URL: ${SERVICE_URL}"
    echo " Image: ${local_image}"
    echo "=========================================="

    health_check_with_retry "${SERVICE_URL}"
fi
