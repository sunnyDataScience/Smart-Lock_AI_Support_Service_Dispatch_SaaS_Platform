#!/usr/bin/env bash
# ============================================================
# deploy.sh — Build, push, and deploy to Cloud Run
#
# Usage:
#   ./scripts/deploy.sh              # 完整部署（build + push + deploy）
#   ./scripts/deploy.sh --build-only # 只建立 image 不部署
#   ./scripts/deploy.sh --deploy-only # 只部署（用已存在的 image）
#   ./scripts/deploy.sh --update-db-uri # 從 DB_PASSWORD 重建 POSTGRES_URI secret
# ============================================================
set -euo pipefail

# ── GCP 設定 ──
PROJECT_ID="cedar-scope-489604-g3"
REGION="asia-east1"
SERVICE_NAME="smart-lock-agent"
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
MIN_INSTANCES=1
MAX_INSTANCES=3
TIMEOUT=180

# ── Cloud SQL 連線元件（用於自動拼接 POSTGRES_URI）──
DB_USER="lock-ai"
DB_NAME="lock-ai-db"
DB_SOCKET="/cloudsql/${CLOUDSQL_INSTANCE}"

# ── 環境變數 ──
ENV_VARS="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=us-central1"

# ── Secrets（Secret Manager → 環境變數）──
SECRETS="LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest"
SECRETS="${SECRETS},LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest"
SECRETS="${SECRETS},POSTGRES_URI=POSTGRES_URI:latest"
SECRETS="${SECRETS},OPIK_API_KEY=OPIK_API_KEY:latest"
SECRETS="${SECRETS},OPIK_WORKSPACE=OPIK_WORKSPACE:latest"

# ── 切到 agent 目錄（Dockerfile 所在位置）──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."

# ── 解析參數 ──
BUILD=true
DEPLOY=true
UPDATE_DB_URI=false
if [[ "${1:-}" == "--build-only" ]]; then
    DEPLOY=false
elif [[ "${1:-}" == "--deploy-only" ]]; then
    BUILD=false
elif [[ "${1:-}" == "--update-db-uri" ]]; then
    BUILD=false
    DEPLOY=false
    UPDATE_DB_URI=true
fi

# ── 工具函式 ──

update_postgres_uri() {
    # 從 DB_PASSWORD secret 讀取原始密碼，自動 URL encode，拼接完整 POSTGRES_URI
    echo "=========================================="
    echo " 從 DB_PASSWORD 重建 POSTGRES_URI"
    echo "=========================================="

    # 讀取 DB_PASSWORD（透過 stdin 傳遞，避免 shell 特殊字元問題）
    local raw_pw
    raw_pw=$(gcloud secrets versions access latest --secret=DB_PASSWORD 2>/dev/null) || {
        echo "ERROR: 無法讀取 DB_PASSWORD secret。請先建立："
        echo "  echo -n 'your-password' | gcloud secrets create DB_PASSWORD --data-file=-"
        exit 1
    }

    # URL encode + 拼接 + 驗證（全部在 Python 中完成，密碼透過 stdin 傳入，零 shell 展開）
    local full_uri
    full_uri=$(echo -n "${raw_pw}" | python3 -c "
import sys, urllib.parse
raw_pw = sys.stdin.read()
encoded_pw = urllib.parse.quote(raw_pw, safe='')
uri = f'postgresql://${DB_USER}:{encoded_pw}@/${DB_NAME}?host=${DB_SOCKET}'

# 驗證
from urllib.parse import urlparse
r = urlparse(uri)
assert r.scheme == 'postgresql', f'scheme 錯誤: {r.scheme}'
assert r.username == '${DB_USER}', f'username 錯誤: {r.username}'
assert r.path == '/${DB_NAME}', f'dbname 錯誤: {r.path}'

# 驗證 decode 後密碼一致（round-trip check）
decoded_pw = urllib.parse.unquote(r.password)
assert decoded_pw == raw_pw, 'URL encode round-trip 失敗'

print(uri, end='')
") || {
        echo "ERROR: POSTGRES_URI 拼接/驗證失敗"
        exit 1
    }

    echo "URI 格式驗證通過（含 round-trip check）"

    # 寫入 Secret Manager（新增版本）
    echo -n "${full_uri}" | gcloud secrets versions add POSTGRES_URI --data-file=- 2>/dev/null || {
        # Secret 不存在，建立新的
        echo -n "${full_uri}" | gcloud secrets create POSTGRES_URI --data-file=-
        # 授予 SA 存取權
        gcloud secrets add-iam-policy-binding POSTGRES_URI \
            --member="serviceAccount:${SERVICE_ACCOUNT}" \
            --role="roles/secretmanager.secretAccessor" --quiet
    }

    local pw_len=${#raw_pw}
    echo "POSTGRES_URI secret 已更新"
    echo "  user: ${DB_USER}"
    echo "  db:   ${DB_NAME}"
    echo "  host: ${DB_SOCKET}"
    echo "  pw:   ${raw_pw:0:2}***${raw_pw: -1} (${pw_len} chars)"
}

preflight_checks() {
    echo "=========================================="
    echo " Pre-flight 檢查"
    echo "=========================================="

    local failed=0

    # 檢查 gcloud 登入
    if ! gcloud auth print-access-token &>/dev/null; then
        echo "  FAIL: gcloud 未登入，請執行: gcloud auth login"
        failed=1
    else
        echo "  OK: gcloud 已登入"
    fi

    # 檢查專案設定
    local current_project
    current_project=$(gcloud config get-value project 2>/dev/null)
    if [[ "${current_project}" != "${PROJECT_ID}" ]]; then
        echo "  FAIL: 目前專案是 ${current_project}，預期 ${PROJECT_ID}"
        echo "        執行: gcloud config set project ${PROJECT_ID}"
        failed=1
    else
        echo "  OK: 專案 ${PROJECT_ID}"
    fi

    # 檢查 Docker 認證
    if ! docker info &>/dev/null; then
        echo "  FAIL: Docker daemon 未啟動"
        failed=1
    else
        echo "  OK: Docker daemon 運行中"
    fi

    # 檢查必要 secrets 存在
    local required_secrets=("LINE_CHANNEL_SECRET" "LINE_CHANNEL_ACCESS_TOKEN" "POSTGRES_URI" "OPIK_API_KEY" "OPIK_WORKSPACE")
    for secret in "${required_secrets[@]}"; do
        if gcloud secrets describe "${secret}" &>/dev/null; then
            echo "  OK: Secret ${secret}"
        else
            echo "  FAIL: Secret ${secret} 不存在"
            failed=1
        fi
    done

    # 驗證 POSTGRES_URI 格式（讀回 secret，透過 stdin 傳入 Python 避免 shell 展開問題）
    local pg_uri
    pg_uri=$(gcloud secrets versions access latest --secret=POSTGRES_URI 2>/dev/null) || true
    if [[ -n "${pg_uri}" ]]; then
        echo -n "${pg_uri}" | python3 -c "
import sys
from urllib.parse import urlparse
uri = sys.stdin.read()
r = urlparse(uri)
if r.scheme != 'postgresql':
    print('  FAIL: POSTGRES_URI scheme 不是 postgresql')
    sys.exit(1)
if not r.username:
    print('  FAIL: POSTGRES_URI 缺少 username')
    sys.exit(1)
if 'cloudsql' not in (r.query or ''):
    print('  WARN: POSTGRES_URI 未使用 Unix socket（缺少 ?host=/cloudsql/...）')
print('  OK: POSTGRES_URI 格式正確')
" || failed=1
    fi

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
        local response
        response=$(curl -s -w "\n%{http_code}" "${url}/health" 2>/dev/null) || true
        local http_code
        http_code=$(echo "${response}" | tail -1)
        local body
        body=$(echo "${response}" | head -1)

        if [[ "${http_code}" == "200" ]]; then
            echo "Health check PASSED (HTTP ${http_code})"
            echo "  ${body}"
            return 0
        elif [[ "${http_code}" == "503" ]]; then
            echo "Health check: 服務降級 (HTTP 503) — DB 連線異常"
            echo "  ${body}"
            echo "  請檢查 POSTGRES_URI 是否正確: ./scripts/deploy.sh --update-db-uri"
            return 1
        fi

        echo "  Attempt ${i}/${max_attempts}: HTTP ${http_code} — 等待 ${wait_secs}s..."
        sleep $wait_secs
    done

    echo "Health check FAILED — 服務未在時間內就緒"
    return 1
}

# ── 主流程 ──

# --update-db-uri 模式
if $UPDATE_DB_URI; then
    update_postgres_uri
    exit 0
fi

# Pre-flight 檢查（僅在部署時）
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

    # 同時標記為 latest（方便 deploy-only 使用）
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
    # 使用最新 tagged image（build 剛推的，或 deploy-only 用 latest）
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
        --min-instances="${MIN_INSTANCES}" \
        --max-instances="${MAX_INSTANCES}" \
        --timeout="${TIMEOUT}" \
        --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
        --set-env-vars="${ENV_VARS}" \
        --set-secrets="${SECRETS}"

    # 動態取得服務 URL（不硬編碼）
    SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
        --region="${REGION}" \
        --format='value(status.url)')

    echo ""
    echo "=========================================="
    echo " Deployment complete!"
    echo " URL: ${SERVICE_URL}"
    echo " Image: ${local_image}"
    echo "=========================================="

    # Health check with retry
    health_check_with_retry "${SERVICE_URL}"
fi
