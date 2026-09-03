#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
HELPER="${ROOT}/frontend/scripts/install-update"
RESTART_HELPER="${ROOT}/frontend/scripts/restart-client"

grep -q 'dpkg-deb --field .* Package' "${HELPER}"
grep -q 'dpkg-deb --field .* Version' "${HELPER}"
grep -q 'dpkg-deb --field .* Architecture' "${HELPER}"
grep -q 'PRODUCT_VERSION=${PACKAGE_VERSION%-\*}' "${HELPER}"
grep -q 'openssl pkeyutl -verify -pubin -rawin' "${HELPER}"
grep -q '/usr/share/pixiu/keys/pixiu-release-ed25519.pub' "${HELPER}"
grep -q 'backend.foundation.api.install_health' "${HELPER}"
grep -q 'dpkg-repack' "${HELPER}"
grep -q 'source.backup(target)' "${HELPER}"
grep -q 'PIXIU_UPGRADE_TEST_FAIL_HEALTH' "${HELPER}"
grep -q 'rollback' "${HELPER}"
grep -q 'exit 5' "${HELPER}"
grep -q 'exit 6' "${HELPER}"
test -f "${ROOT}/build/release/keys/pixiu-release-ed25519.pub"
grep -q 'PIXIU_RELEASE_SIGNING_KEY' "${ROOT}/.github/workflows/release.yml"
grep -q '\*.sha256.sig' "${ROOT}/.github/workflows/release.yml"
grep -q 'signed checksum missing' "${ROOT}/build/release/scripts/publish.sh"
test -x "${RESTART_HELPER}"
sh -n "${RESTART_HELPER}"
grep -q '/usr/bin/pixiu' "${RESTART_HELPER}"
grep -q 'restart-client' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q '^deb: build-deb$' "${ROOT}/build/release/Makefile"
if "${RESTART_HELPER}" invalid >/dev/null 2>&1; then
    echo "restart helper must reject a non-numeric PID" >&2
    exit 1
fi
PIXIU_RESTART_EXECUTABLE=/bin/true "${RESTART_HELPER}" 99999999
sleep 0.2 &
old_client_pid=$!
PIXIU_RESTART_EXECUTABLE=/bin/true "${RESTART_HELPER}" "${old_client_pid}"

if "${HELPER}" /not/a/package invalid AAA= 2>/dev/null; then
    echo "invalid digest must be rejected" >&2
    exit 1
fi

echo "update helper tests: OK"
