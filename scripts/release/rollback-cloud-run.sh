#!/usr/bin/env bash
# 切回指定 Cloud Run revision；不執行 DB down migration。
set -euo pipefail

if [[ "$#" -ne 2 ]]; then
  echo "usage: $0 <service> <previous-revision>" >&2
  exit 2
fi

service="$1"
revision="$2"
: "${REGION:?REGION is required}"

if [[ -z "${service}" || -z "${revision}" || "${service}" == */* || "${revision}" == */* ]]; then
  echo "invalid service/revision" >&2
  exit 2
fi

gcloud run revisions describe "${revision}" \
  --region="${REGION}" \
  --format='value(metadata.name)' >/dev/null
gcloud run services update-traffic "${service}" \
  --region="${REGION}" \
  --to-revisions="${revision}=100"
echo "traffic restored: ${service} -> ${revision}=100"
