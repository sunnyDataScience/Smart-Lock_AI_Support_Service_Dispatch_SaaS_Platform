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
# CORS 對應的 web 服務依 api 服務名對映（0723 UAT：lock-tech-api / lock-platform-api
# 依 R6 runbook 重佈時未帶 WEB_SERVICE_NAME → 吃到 smart-lock-web 預設 → CORS 烤成
# 品牌網址，技師站/平台 console 瀏覽器登入被 preflight 全擋。顯式 export 仍可覆寫。）
case "${SERVICE_NAME}" in
    lock-tech-api)     _DEFAULT_WEB="lock-tech-web" ;;
    lock-platform-api) _DEFAULT_WEB="lock-platform-web" ;;
    *)                 _DEFAULT_WEB="smart-lock-web" ;;
esac
WEB_SERVICE_NAME="${WEB_SERVICE_NAME:-${_DEFAULT_WEB}}"   # 解析 web URL → CORS_ORIGINS
REPO="${REPO:-lock-ai-repo}"

# Image tag: git short SHA + timestamp（支援 rollback）
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date +%Y%m%d-%H%M)
IMAGE_TAG="${GIT_SHA}-${TIMESTAMP}"
IMAGE_BASE="asia-east1-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"
# CI promotion 可注入 immutable digest（IMAGE_OVERRIDE=...@sha256:...）；未注入時保留
# 本機 SHA+timestamp 行為。deploy-only 若有 override 絕不可退 latest。
IMAGE="${IMAGE_OVERRIDE:-${IMAGE_BASE}:${IMAGE_TAG}}"

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
BACKGROUND_RUNTIME_MODE="${BACKGROUND_RUNTIME_MODE:-api}"
case "${BACKGROUND_RUNTIME_MODE}" in
    api|hybrid|external) ;;
    *) echo "BACKGROUND_RUNTIME_MODE must be api, hybrid, or external" >&2; exit 2 ;;
esac
EXTERNALIZED_JOB_IDS="${EXTERNALIZED_JOB_IDS:-webhook-idempotency-cleanup}"
ENV_VARS="VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=asia-northeast1"
ENV_VARS="${ENV_VARS},AGENT_TENANT_ID=${AGENT_TENANT_ID}"
# CR-0153(ADR-020):prod 三庫守衛——漏設對應面 URI 直接拒啟,不靜默 fallback
ENV_VARS="${ENV_VARS},DB_URI_STRICT=1"
ENV_VARS="${ENV_VARS},API_SURFACE=${API_SURFACE}"
ENV_VARS="${ENV_VARS},BACKGROUND_RUNTIME_MODE=${BACKGROUND_RUNTIME_MODE}"
ENV_VARS="${ENV_VARS},EXTERNALIZED_JOB_IDS=${EXTERNALIZED_JOB_IDS}"
# Cloud Run 與 same-origin Next proxy 都是 HTTPS；即使使用 host-only cookie（沒有
# AUTH_COOKIE_DOMAIN），production access/refresh cookie 也必須帶 Secure。
ENV_VARS="${ENV_VARS},AUTH_COOKIE_SECURE=1"
if [[ -n "${AUTH_COOKIE_DOMAIN:-}" ]]; then
    ENV_VARS="${ENV_VARS},AUTH_COOKIE_DOMAIN=${AUTH_COOKIE_DOMAIN}"
fi
# CR-0182（UAT-0723-F2）：跨面 token 守衛——本服務只接受對應面向的 token（技師 token
# 過去可讀 brand 客戶 PII/金流）。刻意獨立於 API_SURFACE：後者是部署塑形（all 同時=本機
# 單體/pytest 模式），復用會自我失效。未設=不強制（本機/測試沿用）。tech/platform 面對稱
# 設定（業主 0726 D3a），順帶擋反向越權。可用 ALLOWED_TOKEN_PORTALS 覆寫。
case "${API_SURFACE}" in
    tech)      _DEFAULT_PORTALS="tech" ;;
    platform)  _DEFAULT_PORTALS="platform" ;;
    *)         _DEFAULT_PORTALS="brand" ;;   # all / dispatch（雲端品牌服務）→ 僅收 brand
esac
ALLOWED_TOKEN_PORTALS="${ALLOWED_TOKEN_PORTALS:-${_DEFAULT_PORTALS}}"
ENV_VARS="${ENV_VARS},ALLOWED_TOKEN_PORTALS=${ALLOWED_TOKEN_PORTALS}"
# CR-0180：客戶面向連結的 base URL（免責簽署連結/quote/track Flex 連結共用 SSOT，
# line_flex/builders.py 與 consent_service 讀）。預設=雲端 brand-portal 公開網址；
# 未設會 fallback 到 example.com 死連結（0719 部署參數 parity 雷同源，故烤入）。
WEB_BASE_URL="${WEB_BASE_URL:-https://smart-lock-web-sjmxp23sqq-de.a.run.app}"
ENV_VARS="${ENV_VARS},WEB_BASE_URL=${WEB_BASE_URL}"
# 忘記密碼信裡的重設頁連結 base。**依 surface 分流**：技師的重設頁在師傅站、
# 其餘在品牌站。未設時 password_reset_service._reset_link 會退各自的正式站
# （2026-07-30 前是退 localhost:3001 → 寄出去的信裡是打不開的連結）。
case "${API_SURFACE}" in
    tech) _DEFAULT_RESET_URL="https://lock-tech-web-sjmxp23sqq-de.a.run.app" ;;
    *)    _DEFAULT_RESET_URL="${WEB_BASE_URL}" ;;
esac
PASSWORD_RESET_WEB_URL="${PASSWORD_RESET_WEB_URL:-${_DEFAULT_RESET_URL}}"
ENV_VARS="${ENV_VARS},PASSWORD_RESET_WEB_URL=${PASSWORD_RESET_WEB_URL}"
echo "  PASSWORD_RESET_WEB_URL=${PASSWORD_RESET_WEB_URL}（忘記密碼信連結）"

# ── Secrets（Secret Manager → 環境變數）──
SECRETS="POSTGRES_URI=POSTGRES_URI:latest"
SECRETS="${SECRETS},API_JWT_SECRET_KEY=API_JWT_SECRET_KEY:latest"
# INTERNAL_API_TOKEN：agent gateway 旁路寫入 + 查接管狀態的內部認證（與 agent 同值）
SECRETS="${SECRETS},INTERNAL_API_TOKEN=INTERNAL_API_TOKEN:latest"
# LINE_CHANNEL_ACCESS_TOKEN：客服接管後 push 訊息回 LINE（CR-0024 / line_push_service）
SECRETS="${SECRETS},LINE_CHANNEL_ACCESS_TOKEN=LINE_CHANNEL_ACCESS_TOKEN:latest"
# LINE_CHANNEL_SECRET：客戶側 OA webhook 驗簽（0720 checklist §1-3：缺=fail-closed 全 401）。
# secret 本已存在（agent.sh 同名掛載），此處只是補掛 api 面。
SECRETS="${SECRETS},LINE_CHANNEL_SECRET=LINE_CHANNEL_SECRET:latest"
# CR-0176 GDPR crypto-shred 三把（0722 OPS 批次日烤入）：未掛=走具名 dev fallback
# （不安全；GDPR_DEK_KEK 換值會使既有 wrapped DEK 解不開→get_or_create fail-loud）。
# 注意：KYC_ENCRYPTION_KEY 刻意**不掛**——prod 既有 KYC 密文以 dev fallback 加密，
# 換鑰須先跑再加密輪（見 docs/ops/ops-batch-day-20260722.md §後續）。
SECRETS="${SECRETS},GDPR_DEK_KEK=GDPR_DEK_KEK:latest"
SECRETS="${SECRETS},USER_PII_BIDX_KEY=USER_PII_BIDX_KEY:latest"
SECRETS="${SECRETS},MEDIA_ENC_KEY=MEDIA_ENC_KEY:latest"
# PUBLIC_TOKEN_HMAC_SECRET（2026-08-02 資安掃描）：消費者公開連結的簽章金鑰。
# 保護 13 個 /api/v1/public + /consumer 端點，其中含**金額決策**
# （POST /consumer/quotes/{token} 代客戶接受報價、
#   POST /consumer/scope-changes/{token} 代客戶核可加價）。
# 未掛 → public_token.py 改用 process 啟動時隨機金鑰並記 CRITICAL：
# 服務仍可服務其他流量，但既有公開連結每次重啟就失效。
# （在此之前是靜默 fallback 到原始碼裡的固定字串，等於人人可簽。）
SECRETS="${SECRETS},PUBLIC_TOKEN_HMAC_SECRET=PUBLIC_TOKEN_HMAC_SECRET:latest"
# ADR-036：新 S2S credential 的 keyed hash pepper；只掛 reference、不讀值。
SECRETS="${SECRETS},SERVICE_CREDENTIAL_PEPPER=SERVICE_CREDENTIAL_PEPPER:latest"
# 品牌 API → technician OHS 的個別 principal credential；bootstrap 後以旗標啟用。
if [[ "${USE_SERVICE_CREDENTIALS:-0}" == "1" ]]; then
    SECRETS="${SECRETS},TECH_API_SERVICE_CREDENTIAL=TECH_API_SERVICE_CREDENTIAL:latest"
fi
# ── SMTP：忘記密碼信的送達通道（CR-0025 / email_provider.py）──
# 2026-07-30 實證：prod 三個 API 服務**都沒有任何 SMTP_* 設定**，部署腳本也沒掛，
# 所以 `send_email` 一直走 fail-safe 回 False——token 有建、信永遠寄不出去
# （prod log：「SMTP 未配置（缺 SMTP_HOST）— 略過寄信」）。這不是壞掉，是從未佈建。
#
# **條件掛載**：secret 不存在時 `gcloud run deploy` 會整個失敗，所以先探測再掛
# ——讓「還沒建憑證」與「已建憑證」兩種狀態都能部署，建完直接重佈即生效。
# 建立方式（業主取得供應商憑證後）：
#   printf '%s' "smtp.sendgrid.net" | gcloud secrets create SMTP_HOST --data-file=-
#   printf '%s' "apikey"            | gcloud secrets create SMTP_USER --data-file=-
#   printf '%s' "<API_KEY>"         | gcloud secrets create SMTP_PASSWORD --data-file=-
#   printf '%s' "no-reply@<domain>" | gcloud secrets create SMTP_FROM --data-file=-
_smtp_mounted=0
for _s in SMTP_HOST SMTP_USER SMTP_PASSWORD SMTP_FROM; do
    if gcloud secrets describe "${_s}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        SECRETS="${SECRETS},${_s}=${_s}:latest"
        _smtp_mounted=$((_smtp_mounted + 1))
    fi
done
if [[ "${_smtp_mounted}" -eq 0 ]]; then
    echo "  WARN: 無任何 SMTP_* secret —— 忘記密碼信不會送達（功能其餘正常，token 照建）"
elif [[ "${_smtp_mounted}" -lt 4 ]]; then
    echo "  WARN: SMTP secret 只建了 ${_smtp_mounted}/4 —— 缺 SMTP_HOST 即整個停用"
else
    echo "  SMTP: 4/4 secret 已掛（忘記密碼信會實際送達）"
fi
# ── R6 多面上雲：依 API_SURFACE 掛對應面的 DB URI secret（db.py:assert_uri_strict 要求）──
#   tech 面需 TECH_POSTGRES_URI；platform 面需 PLATFORM_POSTGRES_URI（皆指向共用 lock-ai
#   實例的 lock_tech / lock_platform database）。品牌面（all/dispatch）走真雙庫（技師身分
#   寫權威庫，tech_mirror）時設 MOUNT_TECH_URI=1 一併掛入。
#   platform 面也需 TECH_POSTGRES_URI（0724 split-brain 實案：平台 console 是技師
#   生命週期操作面，漏掛時 onboard-approve 寫進投影庫、權威庫仍 pending →
#   平台頁顯示啟用中但技師登入 ACCOUNT_PENDING_APPROVAL；db.py 守衛已同步收緊）。
if [[ "${API_SURFACE}" == "tech" || "${API_SURFACE}" == "platform" || "${MOUNT_TECH_URI:-}" == "1" ]]; then
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
    # CR-0173 技師 line_user_id 欄位級加密兩把金鑰（0720 checklist §1-1：不烤入
    # 會在重佈時洗掉手動掛載→解密/去重全走 dev fallback 假金鑰）
    SECRETS="${SECRETS},LINE_UID_ENC_KEY=LINE_UID_ENC_KEY:latest"
    SECRETS="${SECRETS},LINE_UID_BIDX_KEY=LINE_UID_BIDX_KEY:latest"
    # 0720 checklist §1-2：technician_line_service.tech_portal_base() 未設退
    # localhost:3001 → 推播深連結壞。動態解析師傅站 URL 烤入。
    TECH_WEB_SERVICE_NAME="${TECH_WEB_SERVICE_NAME:-lock-tech-web}"
    _tech_web_url=$(gcloud run services describe "${TECH_WEB_SERVICE_NAME}" \
        --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)
    if [[ -n "${_tech_web_url}" ]]; then
        ENV_VARS="${ENV_VARS},TECH_PORTAL_URL=${_tech_web_url}"
        echo "  TECH_PORTAL_URL=${_tech_web_url}（技師推播深連結）"
    else
        echo "  WARN: 找不到 ${TECH_WEB_SERVICE_NAME} URL —— 推播深連結將退 localhost"
    fi
fi
# CR-0169 技師推播的品牌面半邊（0719 雲端 UAT C-4）：品牌 api 的
# _notify_tech_line 需要 TECH_API_BASE_URL 指向 tech-api，未設=靜默跳過
# （fail-soft 無 log）→ 派單/池單技師推播在雲上完全不發。品牌面（all/
# dispatch）自動解析 lock-tech-api URL 烤入；解析不到 WARN（推播退 no-op）。
if [[ "${API_SURFACE}" == "all" || "${API_SURFACE}" == "dispatch" ]]; then
    TECH_API_SERVICE_NAME="${TECH_API_SERVICE_NAME:-lock-tech-api}"
    _tech_api_url=$(gcloud run services describe "${TECH_API_SERVICE_NAME}" \
        --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)
    if [[ -n "${_tech_api_url}" ]]; then
        ENV_VARS="${ENV_VARS},TECH_API_BASE_URL=${_tech_api_url}"
        echo "  TECH_API_BASE_URL=${_tech_api_url}（技師 LINE 推播 internal 鏈）"
    else
        echo "  WARN: 找不到 ${TECH_API_SERVICE_NAME} URL —— 技師 LINE 推播將靜默停用"
    fi
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

    local required_secrets=("POSTGRES_URI" "API_JWT_SECRET_KEY" "INTERNAL_API_TOKEN" "LINE_CHANNEL_ACCESS_TOKEN" "LINE_CHANNEL_SECRET" "GDPR_DEK_KEK" "USER_PII_BIDX_KEY" "MEDIA_ENC_KEY" "SERVICE_CREDENTIAL_PEPPER")
    if [[ "${USE_SERVICE_CREDENTIALS:-0}" == "1" ]]; then
        required_secrets+=("TECH_API_SERVICE_CREDENTIAL")
    fi
    # R6：依 API_SURFACE 追加對應面 DB URI secret 的存在性檢查（與上方 SECRETS 掛載一致）
    if [[ "${API_SURFACE}" == "tech" || "${API_SURFACE}" == "platform" || "${MOUNT_TECH_URI:-}" == "1" ]]; then
        required_secrets+=("TECH_POSTGRES_URI")
    fi
    if [[ "${API_SURFACE}" == "tech" ]]; then
        # 0720 checklist §1-4：PLATFORM_LINE_* 補進 pre-flight（原漏檢）＋CR-0173 兩把金鑰
        required_secrets+=("PLATFORM_LINE_CHANNEL_SECRET" "PLATFORM_LINE_CHANNEL_ACCESS_TOKEN" "LINE_UID_ENC_KEY" "LINE_UID_BIDX_KEY")
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
        local_image="${IMAGE_OVERRIDE:-${IMAGE_BASE}:latest}"
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
