#!/usr/bin/env bash
# ADR-037 pilot：以 API 同一映像建立/更新 Cloud Run Job。
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${REGION:?REGION is required}"
: "${IMAGE_OVERRIDE:?IMAGE_OVERRIDE must be an immutable @sha256 digest}"
if [[ "${IMAGE_OVERRIDE}" != *@sha256:* ]]; then
  echo "IMAGE_OVERRIDE must use immutable digest" >&2
  exit 2
fi

JOB_NAME="${JOB_NAME:-smart-lock-webhook-cleanup}"
JOB_ID="${JOB_ID:-webhook-idempotency-cleanup}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-lock-ai-worker@${PROJECT_ID}.iam.gserviceaccount.com}"
CLOUDSQL_INSTANCE="${CLOUDSQL_INSTANCE:-${PROJECT_ID}:${REGION}:lock-ai}"

common=(
  "--image=${IMAGE_OVERRIDE}"
  "--region=${REGION}"
  "--service-account=${SERVICE_ACCOUNT}"
  "--tasks=1"
  "--max-retries=3"
  "--task-timeout=5m"
  "--command=python"
  "--args=-m,worker_main,run,${JOB_ID}"
  # --max-retries=3 代表首次 + 3 次重試，registry 以 4 判定 terminal attempt。
  "--set-env-vars=DB_URI_STRICT=1,API_SURFACE=dispatch,WORKER_MAX_ATTEMPTS=4"
  "--set-secrets=POSTGRES_URI=POSTGRES_URI:latest"
  "--set-cloudsql-instances=${CLOUDSQL_INSTANCE}"
)

if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" >/dev/null 2>&1; then
  gcloud run jobs update "${JOB_NAME}" "${common[@]}"
else
  gcloud run jobs create "${JOB_NAME}" "${common[@]}"
fi

if [[ "${EXECUTE_JOB:-0}" == "1" ]]; then
  gcloud run jobs execute "${JOB_NAME}" --region="${REGION}" --wait
fi
