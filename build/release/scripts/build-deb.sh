#!/usr/bin/env bash
# PIXIU 全量 .deb 构建流水线：
#   前端（CMake/Qt5，KYSDK 可切 ON/OFF）+ 后端（Python 源码随包安装）
#   + 可选离线 Python wheels + systemd 服务 + 一键启动器
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/functions.sh"

DEB_SRC="${PIXIU_RELEASE_DIR}/debian"
STAGE="$(stage_dir)"
OUT="$(out_dir)"

# 平台画像必须在使用任何默认值之前加载，否则预置默认值会盖掉画像
# （实测教训：默认 310 先于画像 312 赋值，导致 pydantic_core 打进 cp310 wheels）。
# 优先级：显式环境变量 > profile > 内置默认值。
PIXIU_PROFILE="${PIXIU_PROFILE:-kylin-v11-x86_64}"
PROFILE_FILE="${PIXIU_RELEASE_DIR}/profiles/${PIXIU_PROFILE}.env"
if [ -f "${PROFILE_FILE}" ]; then
    while IFS='=' read -r KEY VALUE; do
        case "${KEY}" in
            PIXIU_*|APT_*)
                if [ -z "${!KEY:-}" ]; then
                    # 去掉 profile 值两侧的引号（值可含空格/括号）
                    VALUE="${VALUE%\"}"
                    VALUE="${VALUE#\"}"
                    export "${KEY}=${VALUE}"
                fi
                ;;
        esac
    done < "${PROFILE_FILE}"
    log "profile loaded: ${PIXIU_PROFILE}"
else
    warn "profile not found: ${PROFILE_FILE}（使用默认 env 值）"
fi

# 未由环境变量/profile 提供时才使用内置默认值
PIXIU_KYSDK="${PIXIU_KYSDK:-OFF}"
PIXIU_BUNDLE_WHEELS="${PIXIU_BUNDLE_WHEELS:-1}"
PIXIU_PYTHON="${PIXIU_PYTHON:-python3}"
PIXIU_PYTHON_VERSION="${PIXIU_PYTHON_VERSION:-310}"
PIXIU_SKIP_TESTS="${PIXIU_SKIP_TESTS:-0}"
PIXIU_DEBIAN_DEPENDS="${PIXIU_DEBIAN_DEPENDS:-}"
PIXIU_INCLUDE_TESTS="${PIXIU_INCLUDE_TESTS:-0}"
PIXIU_FRONTEND_BUILD_DIR="${PIXIU_FRONTEND_BUILD_DIR:-$(frontend_build_dir)}"

resolve_version
log "PIXIU ${PIXIU_VERSION}-${PIXIU_REVISION} [${PIXIU_ARCH}] KYSDK=${PIXIU_KYSDK} wheels=${PIXIU_BUNDLE_WHEELS} py=${PIXIU_PYTHON_VERSION}"

# ── 0/5 版本一致性预检（S2.1：四处版本源同步，不一致即中止发布）────────
# 用户宗旨①的可执行化：frontend/CMakeLists.txt（project VERSION 及其派生的
# PIXIU_VERSION 宏）、frontend/src/main.cpp（消费宏、不得硬编码）、
# frontend/src/services/HttpBackendTransport.cpp（User-Agent 消费宏、不得
# 硬编码，S4 曾因硬编码 0.1.0 漏检）、build/release/scripts/functions.sh
# （resolve_version 默认值）四处必须一致。
check_version_consistency() {
    local frontend_cmake="${PIXIU_ROOT}/frontend/CMakeLists.txt"
    local frontend_main="${PIXIU_ROOT}/frontend/src/main.cpp"
    local frontend_http="${PIXIU_ROOT}/frontend/src/services/HttpBackendTransport.cpp"
    local funcs_file="${PIXIU_ROOT}/build/release/scripts/functions.sh"
    local cmake_ver pixiu_ver funcs_ver

    # 1) CMakeLists project VERSION（单一事实源）
    cmake_ver="$(sed -nE 's/.*project\(pixiu-frontend VERSION ([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' \
        "${frontend_cmake}" | head -n1)"
    # 2) PIXIU_VERSION 宏定义：由 ${PROJECT_VERSION} 派生视为与 project VERSION
    #    构造一致；若退化为字面量（回归防线），必须等于 project VERSION。
    if grep -qF 'PIXIU_VERSION_STR' "${frontend_cmake}" \
       && grep -qF 'PROJECT_VERSION' "${frontend_cmake}"; then
        pixiu_ver="${cmake_ver}"
    else
        pixiu_ver="$(grep -F 'PIXIU_VERSION=' "${frontend_cmake}" \
            | sed -nE 's/.*PIXIU_VERSION=[^0-9]*([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' \
            | head -n1 || true)"
    fi
    # 3) functions.sh resolve_version 默认版本
    funcs_ver="$(sed -nE 's/.*PIXIU_VERSION:-([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' \
        "${funcs_file}" | head -n1)"
    # 4) main.cpp 必须消费宏、不得残留硬编码版本
    if ! grep -qF 'QStringLiteral(PIXIU_VERSION)' "${frontend_main}"; then
        die "frontend/src/main.cpp 未使用 PIXIU_VERSION 宏（setApplicationVersion 应改为 QStringLiteral(PIXIU_VERSION)）"
    fi
    if grep -qE 'setApplicationVersion\(QStringLiteral\("[0-9]+\.[0-9]+\.[0-9]+"\)\)' "${frontend_main}"; then
        die "frontend/src/main.cpp 的 setApplicationVersion 存在硬编码版本（应改用 PIXIU_VERSION 宏）"
    fi
    # 5) HttpBackendTransport.cpp（第 4 处版本源，S4 曾漏检）：User-Agent 必须
    #    消费 PIXIU_VERSION 宏、不得残留 "PIXIU-Frontend/<版本>" 硬编码字面量。
    if ! grep -qF 'QStringLiteral(PIXIU_VERSION)' "${frontend_http}"; then
        die "frontend/src/services/HttpBackendTransport.cpp 未使用 PIXIU_VERSION 宏" \
            "（User-Agent 应改为 QStringLiteral(\"PIXIU-Frontend/\") + QStringLiteral(PIXIU_VERSION)）"
    fi
    if grep -qF 'PIXIU-Frontend/0.1.' "${frontend_http}"; then
        die "frontend/src/services/HttpBackendTransport.cpp 存在硬编码 User-Agent 版本" \
            "（应改用 PIXIU_VERSION 宏，杜绝第 4 处版本源漂移）"
    fi

    log "version precheck: CMakeLists=${cmake_ver:-?} PIXIU_VERSION宏=${pixiu_ver:-?} functions.sh=${funcs_ver:-?} HttpTransport=macro-ok"
    if [ -z "${cmake_ver}" ] || [ -z "${pixiu_ver}" ] || [ -z "${funcs_ver}" ] \
       || [ "${cmake_ver}" != "${pixiu_ver}" ] || [ "${pixiu_ver}" != "${funcs_ver}" ]; then
        die "版本不一致（用户宗旨①：四处同步不得遗漏）：" \
            "frontend/CMakeLists.txt=${cmake_ver:-<未提取>}，" \
            "PIXIU_VERSION 宏=${pixiu_ver:-<未提取>}，" \
            "functions.sh=${funcs_ver:-<未提取>}"
    fi
    # 6) 显式 PIXIU_VERSION 覆盖（CI tag/手动输入）若与四处文件版本不一致，
    #    .deb 包版本将与 App 内版本不符——同样中止发布。
    if [ -n "${PIXIU_VERSION:-}" ] && [ "${PIXIU_VERSION}" != "${funcs_ver}" ]; then
        die "环境变量 PIXIU_VERSION=${PIXIU_VERSION} 与四处版本 ${funcs_ver} 不一致：" \
            "deb 包版本将与 App 版本不符，请先同步四处版本再发布"
    fi
    log "version consistency OK: ${funcs_ver}"
}

check_version_consistency

rm -rf "${STAGE}" "${OUT}"
mkdir -p "${STAGE}" "${OUT}"

# ── 1/5 前端：构建 + 安装到 stage ──────────────────────────────
log "[1/5] frontend build (KYSDK=${PIXIU_KYSDK})"
cmake -S "${PIXIU_ROOT}/frontend" -B "${PIXIU_FRONTEND_BUILD_DIR}" \
    -DPIXIU_HAVE_KYSDK="${PIXIU_KYSDK}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_TESTING=ON \
    -G Ninja
cmake --build "${PIXIU_FRONTEND_BUILD_DIR}" -j"$(nproc)"

if [ "${PIXIU_SKIP_TESTS}" != "1" ]; then
    log "[1.5/5] frontend tests (offscreen ctest)"
    (cd "${PIXIU_FRONTEND_BUILD_DIR}" && QT_QPA_PLATFORM=offscreen ctest --output-on-failure)
fi

cmake --install "${PIXIU_FRONTEND_BUILD_DIR}" --prefix "${STAGE}/usr"

# ── 2/5 后端：源码随包安装 ──────────────────────────────────────
log "[2/5] backend source staging"
BK="${STAGE}/usr/lib/pixiu/backend"
mkdir -p "${BK}"
cp -a "${PIXIU_ROOT}/backend/engine" "${BK}/"
cp -a "${PIXIU_ROOT}/backend/foundation" "${BK}/"
if [ -d "${PIXIU_ROOT}/backend/scripts" ]; then
    cp -a "${PIXIU_ROOT}/backend/scripts" "${BK}/"
fi
cp "${PIXIU_ROOT}/backend/requirements.txt" "${BK}/requirements.txt"
if [ -f "${PIXIU_ROOT}/backend/foundation/requirements-sync.txt" ]; then
    cp "${PIXIU_ROOT}/backend/foundation/requirements-sync.txt" \
        "${BK}/foundation/requirements-sync.txt"
fi
if [ "${PIXIU_INCLUDE_TESTS}" != "1" ]; then
    rm -rf "${BK}/engine/tests" "${BK}/foundation/tests"
fi
find "${BK}" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "${BK}" -name '*.pyc' -delete

# ── 3/5 可选离线 wheels（目标 Python 版本；含 sync 额外依赖）─────
log "[3/5] python wheels (target py${PIXIU_PYTHON_VERSION})"
WHEELS="${STAGE}/usr/lib/pixiu/wheels"
if [ "${PIXIU_BUNDLE_WHEELS}" = "1" ]; then
    if ! "${PIXIU_PYTHON}" -m pip --version >/dev/null 2>&1; then
        warn "pip unavailable; wheels skipped (postinst 将在线安装)"
    else
        mkdir -p "${WHEELS}"
        WHEELS_OK=1
        for REQ in \
                "${PIXIU_ROOT}/backend/requirements.txt" \
                "${PIXIU_ROOT}/backend/foundation/requirements-sync.txt"; do
            [ -f "${REQ}" ] || continue
            if ! "${PIXIU_PYTHON}" -m pip download \
                    --only-binary=:all: \
                    --python-version "${PIXIU_PYTHON_VERSION}" \
                    -d "${WHEELS}" \
                    -r "${REQ}"; then
                WHEELS_OK=0
                break
            fi
        done
        if [ "${WHEELS_OK}" != "1" ]; then
            warn "wheel download failed（网络/ABI）；postinst 将在线安装"
            rm -rf "${WHEELS}"
        fi
    fi
fi
if [ -d "${WHEELS}" ] && [ -z "$(ls -A "${WHEELS}" 2>/dev/null)" ]; then
    rm -rf "${WHEELS}"
fi

# ── 4/5 deb 元数据与运行文件 ────────────────────────────────────
log "[4/5] deb metadata staging"
mkdir -p "${STAGE}/DEBIAN" \
         "${STAGE}/etc/pixiu" \
         "${STAGE}/lib/systemd/system" \
         "${STAGE}/usr/bin"

if [ -z "${PIXIU_DEBIAN_DEPENDS}" ]; then
    PIXIU_DEBIAN_DEPENDS="python3 (>= 3.10), curl, dbus, pkexec, \
libqt5widgets5, libqt5network5, libqt5websockets5, libqt5svg5, \
libkysdk-shortcut, libkysdk-notification, libkysdk-qtwidgets, libgsettings-qt1"
fi
sed -e "s/@VERSION@/${PIXIU_VERSION}-${PIXIU_REVISION}/" \
    -e "s/@ARCH@/${PIXIU_ARCH}/" \
    -e "s/@DEPENDS@/${PIXIU_DEBIAN_DEPENDS}/" \
    "${DEB_SRC}/control.in" > "${STAGE}/DEBIAN/control"
if [ -n "${PIXIU_DEBIAN_SUGGESTS:-}" ]; then
    sed -i "s|@SUGGESTS@|Suggests: ${PIXIU_DEBIAN_SUGGESTS}|" "${STAGE}/DEBIAN/control"
else
    sed -i "/@SUGGESTS@/d" "${STAGE}/DEBIAN/control"
fi
install -m 0755 "${DEB_SRC}/postinst" "${STAGE}/DEBIAN/postinst"
install -m 0755 "${DEB_SRC}/prerm"    "${STAGE}/DEBIAN/prerm"
install -m 0755 "${DEB_SRC}/postrm"   "${STAGE}/DEBIAN/postrm"
install -m 0644 "${DEB_SRC}/conffiles" "${STAGE}/DEBIAN/conffiles"
install -m 0640 "${DEB_SRC}/pixiu.env" "${STAGE}/etc/pixiu/pixiu.env"
install -m 0644 "${DEB_SRC}/pixiu-backend.service" \
    "${STAGE}/lib/systemd/system/pixiu-backend.service"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu" "${STAGE}/usr/bin/pixiu"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu-backend" "${STAGE}/usr/bin/pixiu-backend"
install -m 0755 "${PIXIU_ROOT}/frontend/scripts/install-update" \
    "${STAGE}/usr/lib/pixiu/install-update"

# ── 5/5 dpkg 打包 ──────────────────────────────────────────────
log "[5/5] dpkg-deb"
DEB="${OUT}/pixiu_${PIXIU_VERSION}-${PIXIU_REVISION}_${PIXIU_ARCH}.deb"
dpkg-deb --build --root-owner-group "${STAGE}" "${DEB}" >/dev/null
sha256sum "${DEB}" > "${DEB}.sha256"
log "done: ${DEB}"
log "checksum: $(awk '{print $1}' "${DEB}.sha256")"
