#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HELPER="${ROOT}/frontend/scripts/install-update"

grep -q 'dpkg-deb --field .* Package' "${HELPER}"
grep -q 'dpkg-deb --field .* Version' "${HELPER}"
grep -q 'dpkg-deb --field .* Architecture' "${HELPER}"
grep -q 'PRODUCT_VERSION=${PACKAGE_VERSION%-\*}' "${HELPER}"
grep -q 'backend.foundation.api.install_health' "${HELPER}"
grep -q 'exit 4' "${HELPER}"

if "${HELPER}" /not/a/package invalid 2>/dev/null; then
    echo "invalid digest must be rejected" >&2
    exit 1
fi

echo "update helper tests: OK"
