#!/usr/bin/env bash
# 從 openapi.yaml 生成 Pydantic v2 models。
#
# 用法：cd api && ./scripts/generate_models.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPEC="$ROOT/../docs/02-design/specs/openapi.yaml"
OUT="$ROOT/models/generated.py"

if [[ ! -f "$SPEC" ]]; then
  echo "Spec not found: $SPEC" >&2
  exit 1
fi

datamodel-codegen \
  --input "$SPEC" \
  --input-file-type openapi \
  --output "$OUT" \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.11 \
  --use-standard-collections \
  --use-union-operator \
  --field-constraints \
  --use-schema-description \
  --use-field-description \
  --collapse-root-models \
  --disable-timestamp

echo "Generated: $OUT ($(wc -l < "$OUT") lines)"
