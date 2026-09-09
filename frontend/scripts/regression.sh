#!/usr/bin/env bash
set -euo pipefail

# One product host; run each platform independently (OFF by default).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD_ROOT="${PIXIU_REGRESSION_BUILD_DIR:-${ROOT}/frontend/build/regression}"
KYSDK_MODE="${PIXIU_KYSDK:-OFF}"
case "${KYSDK_MODE}" in ON|OFF) ;; *) echo "PIXIU_KYSDK must be ON or OFF" >&2; exit 2 ;; esac
mkdir -p "${BUILD_ROOT}"

cmake -S "${ROOT}/frontend" -B "${BUILD_ROOT}/contracts" -G Ninja -DBUILD_TESTING=ON
cmake --build "${BUILD_ROOT}/contracts" --parallel 2
QT_QPA_PLATFORM=offscreen ctest --test-dir "${BUILD_ROOT}/contracts" --output-on-failure
cmake -S "${ROOT}/frontend" -B "${BUILD_ROOT}/management" -G Ninja -DPIXIU_MANAGEMENT_TESTS=ON
cmake --build "${BUILD_ROOT}/management" --parallel 2
QT_QPA_PLATFORM=offscreen ctest --test-dir "${BUILD_ROOT}/management" --output-on-failure

# The export preparer refuses nonempty directories. Never overwrite an old tree.
host_source="$(mktemp -d "${BUILD_ROOT}/host-source.XXXXXX")"
bash "${ROOT}/build/release/agent-host/prepare-agent-host.sh" "${host_source}"
cmake -S "${host_source}" -B "${host_source}/build" -G Ninja \
    -DPIXIU_HAVE_KYSDK="${KYSDK_MODE}" -DCMAKE_BUILD_TYPE=Release
cmake --build "${host_source}/build" --parallel 2
desktop-file-validate "${ROOT}/frontend/resources/com.kylin.pixiu.desktop"
# Actual desktop startup, SDK registration and input require native acceptance.
PIXIU_KYSDK="${KYSDK_MODE}" make -C "${ROOT}/build/release" build-deb
