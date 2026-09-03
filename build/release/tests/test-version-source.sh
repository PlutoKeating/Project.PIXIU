#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=../scripts/functions.sh
source "${ROOT}/build/release/scripts/functions.sh"

test -f "${ROOT}/VERSION"
test "$(tr -d '[:space:]' < "${ROOT}/VERSION")" = "0.1.7"

unset PIXIU_VERSION PIXIU_REVISION PIXIU_ARCH
resolve_version
test "${PIXIU_VERSION}" = "0.1.7"

if (PIXIU_VERSION=9.9.9 resolve_version) >/dev/null 2>&1; then
    echo "explicit version drift must be rejected" >&2
    exit 1
fi

grep -q 'PIXIU_ROOT}/VERSION' "${ROOT}/build/release/scripts/functions.sh"
grep -q 'CMAKE_CURRENT_SOURCE_DIR}/../VERSION' "${ROOT}/frontend/CMakeLists.txt"
grep -qx 'version: @VERSION@' \
    "${ROOT}/integrations/kylin_agent/pixiu/plugin.yaml.in"
test ! -e "${ROOT}/integrations/kylin_agent/pixiu/plugin.yaml"
if grep -q 'PIXIU_VERSION:-0\.1\.7' \
        "${ROOT}/build/release/scripts/functions.sh"; then
    echo "functions.sh must not contain a duplicate product version" >&2
    exit 1
fi

printf 'single version source tests: OK\n'
