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
grep -q 'CMAKE_CURRENT_SOURCE_DIR}/../../VERSION' "${ROOT}/frontend/cmake/Management.cmake"
grep -qx 'version: @VERSION@' \
    "${ROOT}/backend/agent/pixiu/plugin.yaml.in"
test ! -e "${ROOT}/backend/agent/pixiu/plugin.yaml"
for removed in frontend/debian/control frontend/debian/rules frontend/debian/postinst frontend/scripts/build-deb.sh; do
    test ! -e "${ROOT}/${removed}"
done
grep -qx 'Package: pixiu' "${ROOT}/build/release/debian/control.in"

if grep -nF "${EXPECTED}" \
        "${ROOT}/frontend/cmake/Management.cmake" \
        "${ROOT}/build/release/debian/control.in" \
        "${ROOT}/backend/agent/pixiu/plugin.yaml.in" \
        "${ROOT}/build/release/scripts/functions.sh" \
        "${ROOT}/build/release/scripts/build-deb.sh" \
        "${ROOT}/build/release/scripts/generate-release-manifest.py" \
        "${ROOT}/.github/workflows/release.yml"; then
    echo "build metadata must not duplicate the current product version" >&2
    exit 1
fi

# Exercise the actual packaging precheck against isolated source fixtures. The
# legacy frontend CMake/main are deliberately absent: they are not shipped.
fixture="$(mktemp -d)"
trap 'rm -rf -- "${fixture}"' EXIT
(
    cd "${ROOT}"
    cp --parents VERSION frontend/cmake/Management.cmake \
        frontend/src/services/HttpBackendTransport.cpp \
        frontend/host/patches/0011-product-application-version.patch \
        build/release/agent-host/prepare-agent-host.sh \
        backend/foundation/api/version.py build/release/debian/pixiu-backend.service \
        backend/agent/pixiu/plugin.yaml.in "${fixture}"
)
source <(sed -n '/^check_version_consistency() {/,/^}/p' \
    "${ROOT}/build/release/scripts/build-deb.sh")
PIXIU_ROOT="${fixture}" check_version_consistency
sed -i 's/PIXIU_VERSION="${PIXIU_MANAGEMENT_VERSION}"/PIXIU_VERSION="9.9.9"/' \
    "${fixture}/frontend/cmake/Management.cmake"
if (PIXIU_ROOT="${fixture}" check_version_consistency) >/dev/null 2>&1; then
    echo "management version drift must be rejected" >&2
    exit 1
fi
cp "${ROOT}/frontend/cmake/Management.cmake" "${fixture}/frontend/cmake/Management.cmake"
sed -i 's/QStringLiteral(PIXIU_PRODUCT_VERSION)/QStringLiteral("9.9.9")/' \
    "${fixture}/frontend/host/patches/0011-product-application-version.patch"
if (PIXIU_ROOT="${fixture}" check_version_consistency) >/dev/null 2>&1; then
    echo "host version drift must be rejected" >&2
    exit 1
fi
printf 'single version source tests: OK\n'
