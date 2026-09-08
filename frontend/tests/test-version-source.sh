#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$1"
BUILD_DIR="$2"
ROOT="$(cd "${SOURCE_DIR}/.." && pwd)"
EXPECTED="$(tr -d '\r\n' < "${ROOT}/VERSION")"

grep -q 'CMAKE_CURRENT_SOURCE_DIR}/../VERSION' "${SOURCE_DIR}/CMakeLists.txt"
test ! -e "${SOURCE_DIR}/src/main.cpp"
for retired_source in app/PixiuApp app/SingleInstanceGuard app/TrayIcon app/UserIdentity widgets/EvidenceDetailDialog widgets/SettingsDialog widgets/FloatingBall widgets/ChatWindow widgets/InputBar widgets/MessageList widgets/ThinkingSkeleton widgets/EvidenceCard; do
    test ! -e "${SOURCE_DIR}/src/${retired_source}.cpp"
    test ! -e "${SOURCE_DIR}/src/${retired_source}.h"
done
test ! -e "${SOURCE_DIR}/src/app/UiIcons.h"
test ! -e "${SOURCE_DIR}/src/models/ChatMessage.h"
if rg -n 't_app_navigation|t_window_restore|src/app/PixiuApp|t_settings_dialog|widgets/SettingsDialog|t_floating_ball|widgets/FloatingBall|t_chat_window|widgets/ChatWindow|t_user_identity|src/app/UserIdentity|t_input_bar|widgets/InputBar|app/UiIcons' "${SOURCE_DIR}/CMakeLists.txt"; then
    echo "retired application lifecycle must not return through regression targets" >&2
    exit 1
fi
if cmake --build "${BUILD_DIR}" --target pixiu-frontend >/dev/null 2>&1; then
    echo "retired standalone application target must not be buildable" >&2
    exit 1
fi
if grep -qE 'project\(pixiu-frontend VERSION [0-9]+\.[0-9]+\.[0-9]+' \
        "${SOURCE_DIR}/CMakeLists.txt"; then
    echo "frontend CMake must not duplicate the product version" >&2
    exit 1
fi

ACTUAL="$(sed -n 's/^CMAKE_PROJECT_VERSION:STATIC=//p' \
    "${BUILD_DIR}/CMakeCache.txt")"
test "${ACTUAL}" = "${EXPECTED}"

grep -q '^Version: @VERSION@$' "${ROOT}/build/release/debian/control.in"
test ! -e "${SOURCE_DIR}/debian/control"
test ! -e "${SOURCE_DIR}/scripts/build-deb.sh"
if rg -n '0\.1\.7' "${SOURCE_DIR}/CMakeLists.txt" \
        "${ROOT}/build/release/debian/control.in"; then
    echo "frontend build metadata must not duplicate the product version" >&2
    exit 1
fi

printf 'frontend version source test: OK\n'
