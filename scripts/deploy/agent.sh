#!/usr/bin/env bash
# ============================================================
# scripts/deploy/agent.sh — Build, push, and deploy agent/ to Cloud Run
#
# Usage:
#   ./scripts/deploy/agent.sh              # 完整部署（build + push + deploy）
#   ./scripts/deploy/agent.sh --build-only # 只建立 image 不部署
#   ./scripts/deploy/agent.sh --deploy-only # 只部署（用已存在的 image）
#   ./scripts/deploy/agent.sh --update-db-uri # 從 DB_PASSWORD 重建 POSTGRES_URI secret
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
SERVICE_NAME="${SERVICE_NAME:-smart-lock-agent}"
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
MEMORY="2Gi"
CPU=2
MIN_INSTANCES=1
MAX_INSTANCES=3
TIMEOUT=300

# ── Cloud SQL 連線元件（用於自動拼接 POSTGRES_URI）──
DB_USER="${DB_USER:-lock-ai}"
DB_NAME="${DB_NAME:-lock-ai-db}"
DB_SOCKET="/cloudsql/${CLOUDSQL_INSTANCE}"

# ── 環境變數 ──
# AGENT_TENANT_ID：agent 送 API 的 tenant 別名（"locksmart"）→ 真實租戶 UUID。
#   api 端 _resolve_tenant_id 解析；兩邊需一致。prod 不同需覆蓋此值。
AGENT_TENANT_ID="${AGENT_TENANT_ID:-00000000-0000-0000-0000-000000000001}"
# API_SERVICE_NAME：用來在 deploy 時自動解析 api 的 Cloud Run URL（→ LOCK_API_BASE_URL）。
API_SERVICE_NAME="${API_SERVICE_NAME:-smart-lock-api}"
ENV_VARS="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=asia-northeast1"
ENV_VARS="${ENV_VARS},AGENT_TENANT_ID=${AGENT_TENANT_ID}"
# RAG_TENANT_ID（#16⑤ RAG 生產啟用）：設了才透傳——app_config.load_mcp_servers 以此
# 決定是否掛 locksmith-rag MCP；未設=跳過（agent 行為不變）。2026-07-19 上雲補：
# 原腳本不認此變數，外部傳了也被丟掉 → RAG MCP 永遠不啟用。
if [[ -n "${RAG_TENANT_ID:-}" ]]; then
    ENV_VARS="${ENV_VARS},RAG_TENANT_ID=${RAG_TENANT_ID}"
fi
# LOCK_API_BASE_URL（橋接/查接管狀態目標）在 deploy 時動態解析 api 的 Cloud Run URL 後追加。

# ── Secrets（Secret Manager → 環境變數）──
SECRETS="LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest"
SECRETS="${SECRETS},LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest"
SECRETS="${SECRETS},POSTGRES_URI=POSTGRES_URI:latest"
SECRETS="${SECRETS},OPIK_API_KEY=OPIK_API_KEY:latest"
SECRETS="${SECRETS},OPIK_WORKSPACE=OPIK_WORKSPACE:latest"
# INTERNAL_API_TOKEN：agent 旁路寫 api + 查接管狀態的內部認證（與 api 同值）
SECRETS="${SECRETS},INTERNAL_API_TOKEN=INTERNAL_API_TOKEN:latest"

# ── 切到 PROJECT_ROOT（uv workspace 根，docker build context）──
# 新 Dockerfile 是 multi-stage uv build，需要 PROJECT_ROOT 才能拿到
# uv.lock 與三個 sub-module 的 pyproject.toml
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

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

    # 檢查必要 secrets 存在
    local required_secrets=("LINE_CHANNEL_SECRET" "LINE_CHANNEL_ACCESS_TOKEN" "POSTGRES_URI" "OPIK_API_KEY" "OPIK_WORKSPACE" "INTERNAL_API_TOKEN")
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
    docker build --platform linux/amd64 -f agent/Dockerfile -t "${IMAGE}" .

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

    # 動態解析 api 的 Cloud Run URL → LOCK_API_BASE_URL（橋接/查接管狀態目標）
    api_url=$(gcloud run services describe "${API_SERVICE_NAME}" \
        --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)
    if [[ -z "${api_url}" ]]; then
        echo "  WARN: 找不到 ${API_SERVICE_NAME} 的 Cloud Run URL —— LOCK_API_BASE_URL 未設，"
        echo "        agent 的對話橋接 / AI 暫停會靜默略過。請先部署 api 再部 agent。"
    else
        ENV_VARS="${ENV_VARS},LOCK_API_BASE_URL=${api_url}"
        echo "  LOCK_API_BASE_URL=${api_url}"
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
