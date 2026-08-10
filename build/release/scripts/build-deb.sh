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
cp -a "${PIXIU_ROOT}/backend/scripts" "${BK}/"
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
    PIXIU_DEBIAN_DEPENDS="python3 (>= 3.10), python3-venv, dbus, \
libqt5widgets5, libqt5network5, libqt5websockets5, \
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
install -m 0644 "${DEB_SRC}/pixiu.env" "${STAGE}/etc/pixiu/pixiu.env"
install -m 0644 "${DEB_SRC}/pixiu-backend.service" \
    "${STAGE}/lib/systemd/system/pixiu-backend.service"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu" "${STAGE}/usr/bin/pixiu"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu-backend" "${STAGE}/usr/bin/pixiu-backend"

# ── 5/5 dpkg 打包 ──────────────────────────────────────────────
log "[5/5] dpkg-deb"
DEB="${OUT}/pixiu_${PIXIU_VERSION}-${PIXIU_REVISION}_${PIXIU_ARCH}.deb"
dpkg-deb --build --root-owner-group "${STAGE}" "${DEB}" >/dev/null
sha256sum "${DEB}" > "${DEB}.sha256"
log "done: ${DEB}"
log "checksum: $(awk '{print $1}' "${DEB}.sha256")"
