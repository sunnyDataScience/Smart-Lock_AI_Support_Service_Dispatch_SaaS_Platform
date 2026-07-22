#!/usr/bin/env bash
# ============================================================
# OPS 批次日 20260722 — Step 3：CD WIF（Workload Identity Federation）啟用
#
# 對應 .github/workflows/cloud-run-deploy.yml 檔頭前置（WBS 1.6.1 CD 殘項）：
#   deployer SA（roles/run.admin + artifactregistry.writer + 對 runtime SA 的
#   serviceAccountUser）＋ github-pool/github-provider（attribute-condition 綁
#   本 repo）＋ gh secret set 兩條。冪等：已存在資源跳過。
#
# 前置：gcloud 已登入有 IAM admin 權限；gh CLI 已 auth（gh auth status）。
# 用法：./scripts/ops/opsday-20260722-3-wif.sh
# ============================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-cedar-scope-489604-g3}"
REPO_GH="Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform"
DEPLOYER_SA="deployer@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA="lock-ai@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "${PROJECT_ID}" --quiet
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')
echo "== project=${PROJECT_ID}（number=${PROJECT_NUMBER}）repo=${REPO_GH} =="

echo "== 1) deployer SA =="
if gcloud iam service-accounts describe "${DEPLOYER_SA}" &>/dev/null; then
    echo "  SKIP: ${DEPLOYER_SA} 已存在"
else
    gcloud iam service-accounts create deployer --display-name="GitHub Actions CD deployer"
fi

echo "== 2) roles（run.admin / artifactregistry.writer / serviceAccountUser→runtime SA）=="
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_SA}" --role="roles/run.admin" --quiet >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${DEPLOYER_SA}" --role="roles/artifactregistry.writer" --quiet >/dev/null
gcloud iam service-accounts add-iam-policy-binding "${RUNTIME_SA}" \
    --member="serviceAccount:${DEPLOYER_SA}" --role="roles/iam.serviceAccountUser" --quiet >/dev/null
echo "  三個 role 綁定 ✓"

echo "== 3) WIF pool + OIDC provider（attribute-condition 鎖定本 repo）=="
if ! gcloud iam workload-identity-pools describe github-pool --location=global &>/dev/null; then
    gcloud iam workload-identity-pools create github-pool \
        --location=global --display-name="GitHub Actions"
else
    echo "  SKIP: github-pool 已存在"
fi
if ! gcloud iam workload-identity-pools providers describe github-provider \
        --location=global --workload-identity-pool=github-pool &>/dev/null; then
    gcloud iam workload-identity-pools providers create-oidc github-provider \
        --location=global --workload-identity-pool=github-pool \
        --display-name="GitHub OIDC" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
        --attribute-condition="assertion.repository=='${REPO_GH}'"
else
    echo "  SKIP: github-provider 已存在"
fi

echo "== 4) 允許本 repo 的 GitHub OIDC 身分 impersonate deployer SA =="
gcloud iam service-accounts add-iam-policy-binding "${DEPLOYER_SA}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${REPO_GH}" \
    --quiet >/dev/null
echo "  workloadIdentityUser 綁定 ✓"

echo "== 5) GitHub repo secrets（cloud-run-deploy.yml:50-51 對應名）=="
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "${REPO_GH}" \
    --body "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
gh secret set GCP_SERVICE_ACCOUNT --repo "${REPO_GH}" --body "${DEPLOYER_SA}"

echo ""
echo "✅ Step 3 完成。煙囪測試：GitHub → Actions → cloud-run-deploy → Run workflow"
echo "   （service=api；provider 路徑用 project number=${PROJECT_NUMBER}，非 id）"
