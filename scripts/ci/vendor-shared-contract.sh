#!/usr/bin/env bash
# 產生 ADR-039 immutable vendored package，並刷新四個獨立 consumer lockfile。
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
package_dir="${root}/web/shared-contract"
tarball="${package_dir}/smartlock-shared-contract-0.1.0.tgz"

cd "${package_dir}"
npm ci --ignore-scripts
npm run check:boundary
npm test
npm run build
npm pack --ignore-scripts
test -s "${tarball}"

for portal in brand-portal tech-portal platform-console landing; do
  cd "${root}/web/${portal}"
  npm install \
    "@smartlock/shared-contract@file:../shared-contract/smartlock-shared-contract-0.1.0.tgz" \
    --save-exact --package-lock-only --ignore-scripts --force
done

node "${root}/scripts/ci/check-shared-contract-consumers.mjs"
echo "shared-contract 0.1.0 vendored and four lockfiles refreshed"
