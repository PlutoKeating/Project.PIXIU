#!/usr/bin/env bash
set -euo pipefail

# PIXIU 前端自动化回归（Phase 8 本地基线）。
#
# 覆盖：
#   - PIXIU_HAVE_KYSDK=OFF / ON 两路径 configure + build
#   - ctest 全量（offscreen）
#   - KYSDK 路径 offscreen 冒烟（应用成功启动并挂载主题/窗口/快捷键）
#   - desktop-file-validate
#   - .deb 打包 + dpkg-deb 内容校验
#
# 用法：
#   scripts/regression.sh
#   OFF_BUILD=/tmp/pixiu-off ON_BUILD=/tmp/pixiu-on scripts/regression.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OFF_BUILD="${OFF_BUILD:-${ROOT}/build/regression-off}"
ON_BUILD="${ON_BUILD:-${ROOT}/build/regression-on}"
DIST_DIR="${ROOT}/build/dist"

run_off() {
    echo "==> [OFF] configure + build"
    cmake -S "${ROOT}" -B "${OFF_BUILD}" \
        -DPIXIU_HAVE_KYSDK=OFF -DCMAKE_BUILD_TYPE=Debug >/dev/null
    cmake --build "${OFF_BUILD}" -j"$(nproc)" >/dev/null
    echo "==> [OFF] ctest"
    (cd "${OFF_BUILD}" && ctest --output-on-failure)
}

run_on() {
    echo "==> [ON] configure + build"
    cmake -S "${ROOT}" -B "${ON_BUILD}" \
        -DPIXIU_HAVE_KYSDK=ON -DCMAKE_BUILD_TYPE=Debug >/dev/null
    cmake --build "${ON_BUILD}" -j"$(nproc)" >/dev/null
    echo "==> [ON] ctest"
    (cd "${ON_BUILD}" && ctest --output-on-failure)

    echo "==> [ON] offscreen smoke"
    local smoke_log
    smoke_log="$(mktemp /tmp/pixiu-smoke.XXXXXX)"
    local rc=0
    QT_QPA_PLATFORM=offscreen timeout 4 "${ON_BUILD}/pixiu-frontend" \
        >"${smoke_log}" 2>&1 || rc=$?
    if [[ ${rc} -ne 0 && ${rc} -ne 124 ]]; then
        echo "smoke failed (rc=${rc})" >&2
        cat "${smoke_log}" >&2
        exit 1
    fi
    if ! rg -q "PIXIU application started" "${smoke_log}"; then
        echo "smoke failed: app did not reach started state" >&2
        cat "${smoke_log}" >&2
        exit 1
    fi
    rg "pixiu\.(theme|ukui-window|shortcut):" "${smoke_log}" | head -5
}

validate_desktop() {
    echo "==> desktop-file-validate"
    desktop-file-validate "${ROOT}/resources/com.kylin.pixiu.desktop"
}

run_deb() {
    echo "==> .deb 打包"
    PIXIU_HAVE_KYSDK=ON "${ROOT}/scripts/build-deb.sh"
    echo "==> dpkg-deb 内容校验"
    local deb
    deb="$(ls "${DIST_DIR}"/pixiu-frontend_*.deb | head -1)"
    dpkg-deb -I "${deb}" | sed -n '1,20p'
    dpkg-deb -c "${deb}" | rg "usr/bin/pixiu-frontend|applications/com.kylin.pixiu.desktop"
}

run_off
run_on
validate_desktop
run_deb

echo "==> regression passed"
