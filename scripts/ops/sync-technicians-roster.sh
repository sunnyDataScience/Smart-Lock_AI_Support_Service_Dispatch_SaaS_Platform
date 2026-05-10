#!/usr/bin/env bash
#
# scripts/ops/sync-technicians-roster.sh — Pull real technicians roster from
# GCP Secret Manager into local .ops/ folder (gitignored) for ops use.
#
# CR-0006 governance: real PII (names / phones / addresses) MUST NOT be in git.
# This script provides the official path to retrieve real roster when needed.
#
# Pattern follows scripts/env/use-gcp.sh (POSTGRES_URI fetch from Secret Manager).
#
# Usage:
#   ./scripts/ops/sync-technicians-roster.sh           # pull latest, write .ops/technicians-roster.csv
#   ./scripts/ops/sync-technicians-roster.sh --check   # just verify secret exists, no fetch
#   ./scripts/ops/sync-technicians-roster.sh --upload <file>  # update secret from local file
#
# Prerequisites:
#   1. gcloud auth login
#   2. gcloud config set project cedar-scope-489604-g3
#   3. IAM roles/secretmanager.secretAccessor on TECHNICIANS_ROSTER secret
#
# First-time secret bootstrap (run once, manually):
#   gcloud secrets create TECHNICIANS_ROSTER --replication-policy=automatic
#   echo -n "<csv-content>" | gcloud secrets versions add TECHNICIANS_ROSTER --data-file=-

set -euo pipefail

GCP_PROJECT="${GCP_PROJECT:-cedar-scope-489604-g3}"
SECRET_NAME="TECHNICIANS_ROSTER"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPS_DIR="$REPO_ROOT/.ops"
OUT_FILE="$OPS_DIR/technicians-roster.csv"

MODE="fetch"
UPLOAD_FILE=""
for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --upload) MODE="upload" ;;
    -h|--help)
      sed -n '2,30p' "$0" | grep -E '^# ' | sed 's/^# //'
      exit 0
      ;;
    *) UPLOAD_FILE="$arg" ;;
  esac
done

log()  { printf '\033[36m[ops/roster]\033[0m %s\n' "$*"; }
err()  { printf '\033[31m[ops/roster]\033[0m %s\n' "$*" >&2; }

if ! command -v gcloud >/dev/null 2>&1; then
  err "gcloud CLI required. Install from https://cloud.google.com/sdk/docs/install"
  exit 1
fi

mkdir -p "$OPS_DIR"

# Ensure .ops/ is gitignored
if [[ ! -f "$REPO_ROOT/.gitignore" ]] || ! grep -q "^\.ops/" "$REPO_ROOT/.gitignore"; then
  log "Adding .ops/ to .gitignore (PII protection)"
  echo "" >> "$REPO_ROOT/.gitignore"
  echo "# CR-0006 PII protection — real technicians roster never in git" >> "$REPO_ROOT/.gitignore"
  echo ".ops/" >> "$REPO_ROOT/.gitignore"
fi

case "$MODE" in
  check)
    log "Checking secret $SECRET_NAME in project $GCP_PROJECT..."
    if gcloud secrets describe "$SECRET_NAME" --project="$GCP_PROJECT" >/dev/null 2>&1; then
      log "✅ Secret exists"
      gcloud secrets versions list "$SECRET_NAME" --project="$GCP_PROJECT" --limit=3
    else
      err "Secret $SECRET_NAME not found in $GCP_PROJECT"
      err "Bootstrap with:"
      err "  gcloud secrets create $SECRET_NAME --replication-policy=automatic --project=$GCP_PROJECT"
      exit 1
    fi
    ;;
  fetch)
    log "Fetching $SECRET_NAME (latest) from $GCP_PROJECT..."
    if gcloud secrets versions access latest \
        --secret="$SECRET_NAME" \
        --project="$GCP_PROJECT" \
        > "$OUT_FILE" 2>/dev/null; then
      chmod 600 "$OUT_FILE"
      lines=$(wc -l < "$OUT_FILE")
      log "✅ Wrote $OUT_FILE ($lines lines, mode 600)"
      log "DO NOT commit this file. Auto-gitignored via .ops/"
    else
      err "Fetch failed. Check IAM (roles/secretmanager.secretAccessor) and gcloud auth."
      exit 1
    fi
    ;;
  upload)
    if [[ -z "$UPLOAD_FILE" || ! -f "$UPLOAD_FILE" ]]; then
      err "Usage: $0 --upload <local-csv-file>"
      exit 1
    fi
    log "Uploading $UPLOAD_FILE → $SECRET_NAME (new version)..."
    if gcloud secrets describe "$SECRET_NAME" --project="$GCP_PROJECT" >/dev/null 2>&1; then
      gcloud secrets versions add "$SECRET_NAME" \
        --data-file="$UPLOAD_FILE" \
        --project="$GCP_PROJECT"
      log "✅ New version added. Older versions auto-retained for rollback."
    else
      log "Secret not found, creating..."
      gcloud secrets create "$SECRET_NAME" \
        --replication-policy=automatic \
        --project="$GCP_PROJECT"
      gcloud secrets versions add "$SECRET_NAME" \
        --data-file="$UPLOAD_FILE" \
        --project="$GCP_PROJECT"
      log "✅ Secret created with first version"
    fi
    ;;
esac
