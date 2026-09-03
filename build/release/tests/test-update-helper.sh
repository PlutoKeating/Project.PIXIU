#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HELPER="${ROOT}/frontend/scripts/install-update"

grep -q 'dpkg-deb --field .* Package' "${HELPER}"
grep -q 'dpkg-deb --field .* Version' "${HELPER}"
grep -q 'dpkg-deb --field .* Architecture' "${HELPER}"
grep -q 'PRODUCT_VERSION=${PACKAGE_VERSION%-\*}' "${HELPER}"
grep -q 'openssl pkeyutl -verify -pubin -rawin' "${HELPER}"
grep -q '/usr/share/pixiu/keys/pixiu-release-ed25519.pub' "${HELPER}"
grep -q 'backend.foundation.api.install_health' "${HELPER}"
grep -q 'exit 4' "${HELPER}"
test -f "${ROOT}/build/release/keys/pixiu-release-ed25519.pub"
grep -q 'PIXIU_RELEASE_SIGNING_KEY' "${ROOT}/.github/workflows/release.yml"
grep -q '\*.sha256.sig' "${ROOT}/.github/workflows/release.yml"
grep -q 'signed checksum missing' "${ROOT}/build/release/scripts/publish.sh"

if "${HELPER}" /not/a/package invalid AAA= 2>/dev/null; then
    echo "invalid digest must be rejected" >&2
    exit 1
fi

echo "update helper tests: OK"
