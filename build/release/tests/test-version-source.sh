#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../scripts/functions.sh
source "${ROOT}/build/release/scripts/functions.sh"

test -f "${ROOT}/VERSION"
EXPECTED="$(tr -d '\r\n' < "${ROOT}/VERSION")"
printf '%s\n' "${EXPECTED}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'

unset PIXIU_VERSION PIXIU_REVISION PIXIU_ARCH
resolve_version
test "${PIXIU_VERSION}" = "${EXPECTED}"

if (PIXIU_VERSION=9.9.9 resolve_version) >/dev/null 2>&1; then
    echo "explicit version drift must be rejected" >&2
    exit 1
fi

grep -q 'PIXIU_ROOT}/VERSION' "${ROOT}/build/release/scripts/functions.sh"
grep -q 'CMAKE_CURRENT_SOURCE_DIR}/../VERSION' "${ROOT}/frontend/CMakeLists.txt"
grep -qx 'version: @VERSION@' \
    "${ROOT}/integrations/kylin_agent/pixiu/plugin.yaml.in"
test ! -e "${ROOT}/integrations/kylin_agent/pixiu/plugin.yaml"

if grep -nF "${EXPECTED}" \
        "${ROOT}/frontend/CMakeLists.txt" \
        "${ROOT}/frontend/debian/control" \
        "${ROOT}/frontend/scripts/build-deb.sh" \
        "${ROOT}/integrations/kylin_agent/pixiu/plugin.yaml.in" \
        "${ROOT}/build/release/scripts/functions.sh" \
        "${ROOT}/build/release/scripts/build-deb.sh" \
        "${ROOT}/build/release/scripts/generate-release-manifest.py" \
        "${ROOT}/.github/workflows/release.yml"; then
    echo "build metadata must not duplicate the current product version" >&2
    exit 1
fi

printf 'single version source tests: OK\n'
