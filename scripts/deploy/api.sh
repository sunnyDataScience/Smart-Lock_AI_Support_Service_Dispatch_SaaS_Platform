#!/usr/bin/env bash
# ============================================================
# scripts/deploy/api.sh — Build, push, and deploy api/ to Cloud Run
#
# Usage:
#   ./scripts/deploy/api.sh              # 完整部署（build + push + deploy）
#   ./scripts/deploy/api.sh --build-only # 只建立 image 不部署
#   ./scripts/deploy/api.sh --deploy-only # 只部署（用已存在的 image）
#
# Prereq:
#   gcloud secrets create API_JWT_SECRET_KEY --data-file=- <<< "$(openssl rand -hex 32)"
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
SERVICE_NAME="${SERVICE_NAME:-smart-lock-api}"
WEB_SERVICE_NAME="${WEB_SERVICE_NAME:-smart-lock-web}"   # 解析 web URL → CORS_ORIGINS
REPO="${REPO:-lock-ai-repo}"

# Image tag: git short SHA + timestamp（支援 rollback）
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%Y%m%d-%H%M)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"
IMAGE_BASE="asia-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"
IMAGE="${IMAGE_BASE}:${IMAGE_TAG}"

# ── Cloud Run 設定 ──
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-lock-ai@${PROJECT_ID}.iam.gserviceaccount.com}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-${PROJECT_ID}:${REGION}:lock-ai}"
PORT=8080
MEMORY="1Gi"
CPU=1
# min=1/max=1 硬約束（23_Deployment §3／24_Runbook RB-02/03，2026-07-10 架構稽核修正）：
# WS hub 與 11 個 cron 為進程內狀態——min=0 會 scale-to-zero 令 cron 停擺；
# REDIS_URL 部署面未掛前擴到第 2 實例＝跨實例訊息遺失＋cron 重跑（含 GDPR 硬刪）。
# 掛上 Redis 驗證後才可用 env 調升。
MIN_INSTANCES="${MIN_INSTANCES:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"
TIMEOUT=300

# ── 環境變數 ──
# AGENT_TENANT_ID：把 agent 送來的別名 tenant（如 "locksmart"）對應到真實租戶 UUID
#   （internal_ingest._resolve_tenant_id 用）。預設 seed 租戶，prod 不同需覆蓋此值。
AGENT_TENANT_ID="${AGENT_TENANT_ID:-00000000-0000-0000-0000-000000000001}"
# API_SURFACE（CR-0112 師傅/派工雙 stack + CR-0114 platform）：all（品牌單庫預設）/
#   tech / platform / dispatch。R6 多面上雲：tech-api 設 API_SURFACE=tech、
#   platform-api 設 API_SURFACE=platform（api/main.py:149 讀此值做路由過濾 + worker 停用）。
API_SURFACE="${API_SURFACE:-all}"
ENV_VARS="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=asia-northeast1"
ENV_VARS="${ENV_VARS},AGENT_TENANT_ID=${AGENT_TENANT_ID}"
# CR-0153(ADR-020):prod 三庫守衛——漏設對應面 URI 直接拒啟,不靜默 fallback
ENV_VARS="${ENV_VARS},DB_URI_STRICT=1"
ENV_VARS="${ENV_VARS},API_SURFACE=${API_SURFACE}"

# ── Secrets（Secret Manager → 環境變數）──
SECRETS="POSTGRES_URI=POSTGRES_URI:latest"
SECRETS="${SECRETS},API_JWT_SECRET_KEY=API_JWT_SECRET_KEY:latest"
# INTERNAL_API_TOKEN：agent gateway 旁路寫入 + 查接管狀態的內部認證（與 agent 同值）
SECRETS="${SECRETS},INTERNAL_API_TOKEN=INTERNAL_API_TOKEN:latest"
# LINE_CHANNEL_ACCESS_TOKEN：客服接管後 push 訊息回 LINE（CR-0024 / line_push_service）
SECRETS="${SECRETS},LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest"
# ── R6 多面上雲：依 API_SURFACE 掛對應面的 DB URI secret（db.py:assert_uri_strict 要求）──
#   tech 面需 TECH_POSTGRES_URI；platform 面需 PLATFORM_POSTGRES_URI（皆指向共用 lock-ai
#   實例的 lock_tech / lock_platform database）。品牌面（all/dispatch）走真雙庫（技師身分
#   寫權威庫，tech_mirror）時設 MOUNT_TECH_URI=1 一併掛入。
if [[ "${API_SURFACE}" == "tech" || "${MOUNT_TECH_URI:-}" == "1" ]]; then
    SECRETS="${SECRETS},TECH_POSTGRES_URI=TECH_POSTGRES_URI:latest"
fi
if [[ "${API_SURFACE}" == "platform" ]]; then
    SECRETS="${SECRETS},PLATFORM_POSTGRES_URI=PLATFORM_POSTGRES_URI:latest"
fi
# CR-0169 技師 LINE 推播：平台官方號憑證只掛 tech 面（綁定 webhook 驗簽＋推播）。
# 2026-07-19 上雲時建立（gcloud secrets create）。不寫進這裡的話，下次 api.sh
# 重佈 tech 面會把手動掛的 secrets 洗掉 → 推播靜默 no-op、綁定卡退回「開通中」。
if [[ "${API_SURFACE}" == "tech" ]]; then
    SECRETS="${SECRETS},PLATFORM_LINE_CHANNEL_SECRET=PLATFORM_LINE_CHANNEL_SECRET:latest"
    SECRETS="${SECRETS},PLATFORM_LINE_CHANNEL_ACCESS_TOKEN=PLATFORM_LINE_CHANNEL_ACCESS_TOKEN:latest"
fi

# ── 切到 PROJECT_ROOT（uv workspace 根，docker build context）──
# 新 Dockerfile 是 multi-stage uv build，需要 PROJECT_ROOT 才能拿到
# uv.lock 與三個 sub-module 的 pyproject.toml
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

    # 檢查 uv 與 lockfile 一致性（避免 lock 漂移導致 prod 與本地不同步）
    if ! command -v uv &>/dev/null; then
        echo "  FAIL: 找不到 uv（pip install --user uv 或 pipx install uv）"
        failed=1
    elif ! (cd "${PROJECT_ROOT}" && uv lock --check &>/dev/null); then
        echo "  FAIL: uv.lock 與 pyproject.toml 不同步"
        echo "        修復：cd ${PROJECT_ROOT} && uv lock，把 uv.lock 一起 commit"
        failed=1
    else
        echo "  OK: uv.lock 與 pyproject.toml 同步"
    fi

    local required_secrets=("POSTGRES_URI" "API_JWT_SECRET_KEY" "INTERNAL_API_TOKEN" "LINE_CHANNEL_ACCESS_TOKEN")
    # R6：依 API_SURFACE 追加對應面 DB URI secret 的存在性檢查（與上方 SECRETS 掛載一致）
    if [[ "${API_SURFACE}" == "tech" || "${MOUNT_TECH_URI:-}" == "1" ]]; then
        required_secrets+=("TECH_POSTGRES_URI")
    fi
    if [[ "${API_SURFACE}" == "platform" ]]; then
        required_secrets+=("PLATFORM_POSTGRES_URI")
    fi
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
    docker build --platform linux/amd64 -f api/Dockerfile -t "${IMAGE}" .
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

    # 動態解析 web 的 Cloud Run URL → CORS_ORIGINS（瀏覽器跨網域呼叫 api 必需）。
    # web 尚未部署時（首次）falls back 到 config/localhost；web 部好後重跑 api 即補上。
    deploy_env_vars="${ENV_VARS}"
    web_url=$(gcloud run services describe "${WEB_SERVICE_NAME}" \
        --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)
    if [[ -n "${web_url}" ]]; then
        # Cloud Run 每個服務有兩個等價網址：status.url（-<hash>-<gw>.a.run.app）
        # 與 projectnumber 形式（<svc>-<projnum>.<region>.run.app）。瀏覽器從哪個進來
        # 就帶哪個 Origin，故 CORS 兩個都要放行（只放一個會讓另一個網址登入 Failed to fetch）。
        # 多個 origin 以「空白」分隔（不可用逗號 —— gcloud --set-env-vars 以逗號拆 env）。
        proj_num=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)' 2>/dev/null || true)
        cors="${web_url}"
        if [[ -n "${proj_num}" ]]; then
            cors="${cors} https://${WEB_SERVICE_NAME}-${proj_num}.${REGION}.run.app"
        fi
        deploy_env_vars="${deploy_env_vars},CORS_ORIGINS=${cors}"
        echo "  CORS_ORIGINS=${cors}"
    else
        echo "  WARN: 找不到 ${WEB_SERVICE_NAME} URL —— CORS 用預設（localhost）。web 部署後重跑 api 補上。"
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
        --set-env-vars="${deploy_env_vars}" \
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
