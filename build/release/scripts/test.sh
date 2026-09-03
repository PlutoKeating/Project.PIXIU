#!/usr/bin/env bash
# PIXIU 测试入口：前端 ctest（必跑）+ 后端 pytest（可选）。
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/functions.sh"

PIXIU_SKIP_TESTS="${PIXIU_SKIP_TESTS:-0}"
PIXIU_BACKEND_TESTS="${PIXIU_BACKEND_TESTS:-0}"
PIXIU_FRONTEND_BUILD_DIR="${PIXIU_FRONTEND_BUILD_DIR:-$(frontend_build_dir)}"

if [ "${PIXIU_SKIP_TESTS}" = "1" ]; then
    log "tests skipped (PIXIU_SKIP_TESTS=1)"
    exit 0
fi

if [ ! -d "${PIXIU_FRONTEND_BUILD_DIR}" ]; then
    die "frontend build dir not found: ${PIXIU_FRONTEND_BUILD_DIR}（先执行 build-deb.sh 或设 PIXIU_FRONTEND_BUILD_DIR）"
fi
log "frontend ctest (offscreen)"
(cd "${PIXIU_FRONTEND_BUILD_DIR}" && QT_QPA_PLATFORM=offscreen ctest --output-on-failure)

if [ "${PIXIU_BACKEND_TESTS}" = "1" ]; then
    log "backend pytest"
    (cd "${PIXIU_ROOT}" && "${PIXIU_PYTHON:-python3}" -m pytest \
        backend/foundation/tests backend/engine/tests integrations/kylin_agent/tests -q)
else
    warn "backend pytest skipped（PIXIU_BACKEND_TESTS=1 启用，需已安装 backend/requirements.txt）"
fi
bash "${PIXIU_ROOT}/build/release/tests/test-agent-integration.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-update-helper.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-release-key-rotation.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-release-manifest.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-version-source.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-artifact-manifest.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-install-preflight.sh"
bash "${PIXIU_ROOT}/build/release/tests/test-native-profile.sh"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_ROOT}/build/release/tests/test-native-sdk-smoke.py"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_ROOT}/build/release/tests/test-three-device-evidence.py"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_ROOT}/build/release/tests/test-agent-supply-chain.py"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_ROOT}/build/release/tests/test-agent-supply-chain-record.py"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_ROOT}/submission/tests/test_build_submission.py"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_ROOT}/submission/build_submission.py" --check
log "tests OK"
