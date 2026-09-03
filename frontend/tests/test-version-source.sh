#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$1"
BUILD_DIR="$2"
ROOT="$(cd "${SOURCE_DIR}/.." && pwd)"
EXPECTED="$(tr -d '\r\n' < "${ROOT}/VERSION")"

grep -q 'CMAKE_CURRENT_SOURCE_DIR}/../VERSION' "${SOURCE_DIR}/CMakeLists.txt"
if grep -qE 'project\(pixiu-frontend VERSION [0-9]+\.[0-9]+\.[0-9]+' \
        "${SOURCE_DIR}/CMakeLists.txt"; then
    echo "frontend CMake must not duplicate the product version" >&2
    exit 1
fi

ACTUAL="$(sed -n 's/^CMAKE_PROJECT_VERSION:STATIC=//p' \
    "${BUILD_DIR}/CMakeCache.txt")"
test "${ACTUAL}" = "${EXPECTED}"

grep -q '^Version: @VERSION@-@REVISION@$' "${SOURCE_DIR}/debian/control"
grep -q 'ROOT}/../VERSION' "${SOURCE_DIR}/scripts/build-deb.sh"
if rg -n '0\.1\.7' "${SOURCE_DIR}/CMakeLists.txt" \
        "${SOURCE_DIR}/debian/control" "${SOURCE_DIR}/scripts/build-deb.sh"; then
    echo "frontend build metadata must not duplicate the product version" >&2
    exit 1
fi

printf 'frontend version source test: OK\n'
