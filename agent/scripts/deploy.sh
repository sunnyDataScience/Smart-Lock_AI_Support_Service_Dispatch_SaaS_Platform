#!/usr/bin/env bash
# ============================================================
# deploy.sh — Build, push, and deploy to Cloud Run
#
# Usage:
#   ./scripts/deploy.sh              # 完整部署（build + push + deploy）
#   ./scripts/deploy.sh --build-only # 只建立 image 不部署
#   ./scripts/deploy.sh --deploy-only # 只部署（用已存在的 image）
# ============================================================
set -euo pipefail

# ── GCP 設定 ──
PROJECT_ID="cedar-scope-489604-g3"
REGION="asia-east1"
SERVICE_NAME="smart-lock-agent"
REPO="lock-ai-repo"
IMAGE="asia-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}:latest"

# ── Cloud Run 設定 ──
SERVICE_ACCOUNT="lock-ai@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUDSQL_INSTANCE="${PROJECT_ID}:${REGION}:lock-ai"
PORT=8080
MEMORY="1Gi"
CPU=1
MIN_INSTANCES=1
MAX_INSTANCES=3
TIMEOUT=180

# ── 環境變數 ──
ENV_VARS="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=us-central1"

# ── Secrets（Secret Manager → 環境變數）──
SECRETS="LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest"
SECRETS="${SECRETS},LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest"
SECRETS="${SECRETS},OPIK_API_KEY=OPIK_API_KEY:latest"
SECRETS="${SECRETS},OPIK_WORKSPACE=OPIK_WORKSPACE:latest"

# ── POSTGRES_URI（含 Cloud SQL Unix socket）──
# DB_PASSWORD 從 Secret Manager 取得，部署時組合成完整 URI
POSTGRES_URI="postgresql://lock-ai:\${DB_PASSWORD}@/lock-ai-db?host=/cloudsql/${CLOUDSQL_INSTANCE}"

# ── 切到 agent 目錄（Dockerfile 所在位置）──
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

# ── Step 1: Build & Push ──
if $BUILD; then
    echo "=========================================="
    echo " Building image: ${IMAGE}"
    echo "=========================================="
    docker build --platform linux/amd64 -t "${IMAGE}" .

    echo ""
    echo "=========================================="
    echo " Pushing image to Artifact Registry"
    echo "=========================================="
    docker push "${IMAGE}"

    echo ""
    echo "Image pushed successfully."
fi

# ── Step 2: Deploy to Cloud Run ──
if $DEPLOY; then
    echo ""
    echo "=========================================="
    echo " Deploying to Cloud Run: ${SERVICE_NAME}"
    echo "=========================================="

    # 先取得 DB_PASSWORD
    DB_PASSWORD=$(gcloud secrets versions access latest --secret=DB_PASSWORD --project="${PROJECT_ID}")
    FULL_POSTGRES_URI="postgresql://lock-ai:${DB_PASSWORD}@/lock-ai-db?host=/cloudsql/${CLOUDSQL_INSTANCE}"

    gcloud run deploy "${SERVICE_NAME}" \
        --image="${IMAGE}" \
        --region="${REGION}" \
        --platform=managed \
        --allow-unauthenticated \
        --service-account="${SERVICE_ACCOUNT}" \
        --port="${PORT}" \
        --memory="${MEMORY}" \
        --cpu="${CPU}" \
        --min-instances="${MIN_INSTANCES}" \
        --max-instances="${MAX_INSTANCES}" \
        --timeout="${TIMEOUT}" \
        --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
        --set-env-vars="${ENV_VARS},POSTGRES_URI=${FULL_POSTGRES_URI}" \
        --set-secrets="${SECRETS}"

    echo ""
    echo "=========================================="
    echo " Deployment complete!"
    echo " URL: https://${SERVICE_NAME}-1083648618124.${REGION}.run.app"
    echo "=========================================="

    # ── Health check ──
    echo ""
    echo "Running health check..."
    sleep 5
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://${SERVICE_NAME}-1083648618124.${REGION}.run.app/health" || true)
    if [[ "${HTTP_CODE}" == "200" ]]; then
        echo "Health check passed (HTTP ${HTTP_CODE})"
    else
        echo "Health check returned HTTP ${HTTP_CODE} — may need a moment to start up"
    fi
fi
