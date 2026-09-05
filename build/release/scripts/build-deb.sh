#!/usr/bin/env bash
# PIXIU 全量 .deb 构建流水线：
#   前端（CMake/Qt5）+ 后端（Python 源码；KYSDK=ON 时强制构建原生扩展）
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
PIXIU_INSTALL_STRICT="${PIXIU_INSTALL_STRICT:-0}"
PIXIU_FRONTEND_BUILD_DIR="${PIXIU_FRONTEND_BUILD_DIR:-$(frontend_build_dir)}"

case "${PIXIU_INSTALL_STRICT}" in
    0|1) ;;
    *) die "PIXIU_INSTALL_STRICT must be 0 or 1" ;;
esac
if [ "${PIXIU_KYSDK}" = "ON" ] && [ "${PIXIU_INSTALL_STRICT}" != "1" ]; then
    die "KYSDK=ON packages must use strict install and activation checks"
fi
if [ "${PIXIU_INSTALL_STRICT}" = "1" ] && [ "${PIXIU_KYSDK}" != "ON" ]; then
    die "strict install checks require KYSDK=ON"
fi
if [ "${PIXIU_PROFILE}" = "kylin-v11-native-x86_64" ] \
   && { [ "${PIXIU_KYSDK}" != "ON" ] || [ "${PIXIU_INSTALL_STRICT}" != "1" ]; }; then
    die "native Kylin V11 profile requires KYSDK=ON and PIXIU_INSTALL_STRICT=1"
fi

resolve_version
log "PIXIU ${PIXIU_VERSION}-${PIXIU_REVISION} [${PIXIU_ARCH}] KYSDK=${PIXIU_KYSDK} wheels=${PIXIU_BUNDLE_WHEELS} py=${PIXIU_PYTHON_VERSION}"

# ── 0/5 版本一致性预检（含 Module E manifest，不一致即中止发布）────────
# 用户宗旨①的可执行化：frontend/CMakeLists.txt（project VERSION 及其派生的
# PIXIU_VERSION 宏）、frontend/src/main.cpp（消费宏、不得硬编码）、
# frontend/src/services/HttpBackendTransport.cpp（User-Agent 消费宏、不得
# 硬编码，S4 曾因硬编码 0.1.0 漏检）及 Module E plugin.yaml 必须与根
# VERSION 单一事实源一致。
check_version_consistency() {
    local frontend_cmake="${PIXIU_ROOT}/frontend/CMakeLists.txt"
    local frontend_main="${PIXIU_ROOT}/frontend/src/main.cpp"
    local frontend_http="${PIXIU_ROOT}/frontend/src/services/HttpBackendTransport.cpp"
    local version_file="${PIXIU_ROOT}/VERSION"
    local backend_version="${PIXIU_ROOT}/backend/foundation/api/version.py"
    local backend_service="${PIXIU_ROOT}/build/release/debian/pixiu-backend.service"
    local source_ver cmake_ver pixiu_ver provider_ver

    source_ver="$(tr -d '\r\n' < "${version_file}")"

    # 1) CMake project VERSION 必须直接从根 VERSION 派生。
    if grep -qF 'CMAKE_CURRENT_SOURCE_DIR}/../VERSION' "${frontend_cmake}" \
       && grep -qF 'project(pixiu-frontend VERSION "${PIXIU_PRODUCT_VERSION}"' \
            "${frontend_cmake}"; then
        cmake_ver="${source_ver}"
    else
        cmake_ver=""
    fi
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
    # 3) Module E manifest 必须是由根 VERSION 渲染的模板。
    if grep -qx 'version: @VERSION@' \
            "${PIXIU_ROOT}/integrations/kylin_agent/pixiu/plugin.yaml.in"; then
        provider_ver="${source_ver}"
    else
        provider_ver=""
    fi
    # 4) main.cpp 必须消费宏、不得残留硬编码版本
    if ! grep -qF 'QStringLiteral(PIXIU_VERSION)' "${frontend_main}"; then
        die "frontend/src/main.cpp 未使用 PIXIU_VERSION 宏（setApplicationVersion 应改为 QStringLiteral(PIXIU_VERSION)）"
    fi
    if grep -qE 'setApplicationVersion\(QStringLiteral\("[0-9]+\.[0-9]+\.[0-9]+"\)\)' "${frontend_main}"; then
        die "frontend/src/main.cpp 的 setApplicationVersion 存在硬编码版本（应改用 PIXIU_VERSION 宏）"
    fi
    # 5) HttpBackendTransport.cpp：User-Agent 必须
    #    消费 PIXIU_VERSION 宏、不得残留 "PIXIU-Frontend/<版本>" 硬编码字面量。
    if ! grep -qF 'QStringLiteral(PIXIU_VERSION)' "${frontend_http}"; then
        die "frontend/src/services/HttpBackendTransport.cpp 未使用 PIXIU_VERSION 宏" \
            "（User-Agent 应改为 QStringLiteral(\"PIXIU-Frontend/\") + QStringLiteral(PIXIU_VERSION)）"
    fi
    if grep -qF 'PIXIU-Frontend/0.1.' "${frontend_http}"; then
        die "frontend/src/services/HttpBackendTransport.cpp 存在硬编码 User-Agent 版本" \
            "（应改用 PIXIU_VERSION 宏，杜绝派生版本漂移）"
    fi
    if ! grep -qF 'PIXIU_PRODUCT_VERSION' "${backend_version}" \
       || ! grep -qF 'PIXIU_PRODUCT_VERSION=@PRODUCT_VERSION@' "${backend_service}"; then
        die "后端产品版本未由发布包注入（version API 与 systemd 模板必须同时接线）"
    fi

    log "version precheck: VERSION=${source_ver:-?} CMakeLists=${cmake_ver:-?} PIXIU_VERSION宏=${pixiu_ver:-?} provider=${provider_ver:-?} HttpTransport=macro-ok backend=runtime-injected"
    if [ -z "${source_ver}" ] || [ -z "${cmake_ver}" ] || [ -z "${pixiu_ver}" ] \
       || [ -z "${provider_ver}" ] || [ "${cmake_ver}" != "${pixiu_ver}" ] \
       || [ "${source_ver}" != "${pixiu_ver}" ] \
       || [ "${source_ver}" != "${provider_ver}" ]; then
        die "版本不一致（发布版本与 Module E 均不得遗漏）：" \
            "VERSION=${source_ver:-<未提取>}，" \
            "frontend/CMakeLists.txt=${cmake_ver:-<未提取>}，" \
            "PIXIU_VERSION 宏=${pixiu_ver:-<未提取>}，" \
            "provider=${provider_ver:-<未提取>}"
    fi
    # 6) 显式 PIXIU_VERSION 覆盖（CI tag/手动输入）若与文件版本不一致，
    #    .deb 包版本将与 App 内版本不符——同样中止发布。
    if [ -n "${PIXIU_VERSION:-}" ] && [ "${PIXIU_VERSION}" != "${source_ver}" ]; then
        die "环境变量 PIXIU_VERSION=${PIXIU_VERSION} 与源码版本 ${source_ver} 不一致：" \
            "deb 包版本将与 App 版本不符，请先更新 VERSION 及其派生清单"
    fi
    log "version consistency OK: ${source_ver}"
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

# Module E is an independent user-installed MemoryProvider. The package keeps
# the canonical read-only payload under /usr/lib; the per-user launcher installs
# it into the active Agent profile without modifying either upstream submodule.
INTEGRATION_ROOT="${STAGE}/usr/lib/pixiu/integrations/kylin_agent"
mkdir -p "${INTEGRATION_ROOT}"
cp -a "${PIXIU_ROOT}/integrations/kylin_agent/pixiu" "${INTEGRATION_ROOT}/"
install -m 0644 "${PIXIU_ROOT}/integrations/kylin_agent/SOUL.md" \
    "${INTEGRATION_ROOT}/SOUL.md"
sed "s/@VERSION@/${PIXIU_VERSION}/g" \
    "${INTEGRATION_ROOT}/pixiu/plugin.yaml.in" \
    > "${INTEGRATION_ROOT}/pixiu/plugin.yaml"
rm -f "${INTEGRATION_ROOT}/pixiu/plugin.yaml.in"
find "${INTEGRATION_ROOT}" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "${INTEGRATION_ROOT}" -name '*.pyc' -delete
find "${INTEGRATION_ROOT}" -type d -exec chmod 0755 {} +
find "${INTEGRATION_ROOT}" -type f -exec chmod 0644 {} +

# A strict release is a single complete OS Agent package. Its host/runtime
# inputs must already have passed the artifact-backed supply-chain audit.
if [ "${PIXIU_INSTALL_STRICT}" = "1" ]; then
    install -m 0755 "${PIXIU_ROOT}/integrations/kylin_agent/kylin_genai_bridge.py" \
        "${INTEGRATION_ROOT}/kylin_genai_bridge.py"
    AGENT_EVIDENCE="${PIXIU_RELEASE_DIR}/evidence/agent-supply-chain"
    AGENT_DOC="${STAGE}/usr/share/doc/pixiu/agent"
    AGENT_RUNTIME="${STAGE}/usr/lib/pixiu/agent-runtime"
    "${PIXIU_PYTHON}" "${PIXIU_RELEASE_DIR}/scripts/audit-agent-supply-chain.py" \
        --root "${PIXIU_ROOT}" --evidence-dir "${AGENT_EVIDENCE}" \
        --output "${STAGE}/usr/share/pixiu/agent-supply-chain-audit.json" \
        --expected-arch "${PIXIU_ARCH}" \
        --require-ready
    install -m 0755 "${AGENT_EVIDENCE}/host/kylin-agent" \
        "${STAGE}/usr/bin/kylin-agent"
    install -d -m 0755 "${AGENT_RUNTIME}/wheelhouse" "${AGENT_DOC}"
    cp -a "${AGENT_EVIDENCE}/wheelhouse/." "${AGENT_RUNTIME}/wheelhouse/"
    install -m 0644 "${AGENT_EVIDENCE}/runtime/runtime-cp312.lock" \
        "${AGENT_RUNTIME}/runtime-cp312.lock"
    for item in agent-host-build.json runtime-wheelhouse.json \
            agent-components.spdx.json NOTICE.agent.txt; do
        install -m 0644 "${AGENT_EVIDENCE}/${item}" "${AGENT_DOC}/${item}"
    done
    cp -a "${AGENT_EVIDENCE}/host/"*.tar.* "${AGENT_DOC}/"
    install -m 0644 "${PIXIU_ROOT}/third_party/kylin-agent/LICENSE" \
        "${AGENT_DOC}/LICENSE.kylin-agent"
    install -m 0644 "${PIXIU_ROOT}/third_party/kylin-agent-runtime/LICENSE" \
        "${AGENT_DOC}/LICENSE.kylin-agent-runtime"
    install -d -m 0755 "${AGENT_DOC}/message-renderer"
    install -m 0644 "${PIXIU_ROOT}/integrations/kylin_agent/message_renderer/licenses/"* \
        "${AGENT_DOC}/message-renderer/"
fi

if [ "${PIXIU_KYSDK}" = "ON" ]; then
    log "[2.5/5] backend Kylin SDK native bindings"
    NATIVE_BUILD_DIR="${OUT}/kylin-native"
    PYBIND11_CMAKE_DIR="$("${PIXIU_PYTHON}" -m pybind11 --cmakedir)" || \
        die "pybind11 Python package is required for PIXIU_KYSDK=ON"
    cmake -S "${PIXIU_ROOT}/backend/engine/kylin/cpp" \
        -B "${NATIVE_BUILD_DIR}" \
        -Dpybind11_DIR="${PYBIND11_CMAKE_DIR}" \
        -DCMAKE_BUILD_TYPE=Release \
        -G Ninja
    cmake --build "${NATIVE_BUILD_DIR}" -j"$(nproc)"
    EMBEDDING_MODULE="$(find "${NATIVE_BUILD_DIR}" -maxdepth 1 -type f \
        -name '_kylin_text_embedding*.so' -print -quit)"
    VECTOR_MODULE="$(find "${NATIVE_BUILD_DIR}" -maxdepth 1 -type f \
        -name '_kylin_vector_client*.so' -print -quit)"
    [ -n "${EMBEDDING_MODULE}" ] || die "embedding native module was not built"
    [ -n "${VECTOR_MODULE}" ] || die "vector native module was not built"
    install -m 0755 "${EMBEDDING_MODULE}" "${BK}/engine/kylin/"
    install -m 0755 "${VECTOR_MODULE}" "${BK}/engine/kylin/"
fi

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
         "${STAGE}/usr/lib/systemd/user" \
         "${STAGE}/usr/bin" \
         "${STAGE}/usr/share/pixiu"
install -d -m 0755 "${STAGE}/usr/share/pixiu/keys"
install -m 0644 "${PIXIU_RELEASE_DIR}/keys/pixiu-release-ed25519.pub" \
    "${STAGE}/usr/share/pixiu/keys/pixiu-release-ed25519.pub"
PIXIU_VERSION="${PIXIU_VERSION}" \
PIXIU_REVISION="${PIXIU_REVISION}" \
PIXIU_ARCH="${PIXIU_ARCH}" \
PIXIU_PROFILE="${PIXIU_PROFILE}" \
PIXIU_KYSDK="${PIXIU_KYSDK}" \
PIXIU_INSTALL_STRICT="${PIXIU_INSTALL_STRICT}" \
PIXIU_PYTHON_VERSION="${PIXIU_PYTHON_VERSION}" \
    "${PIXIU_PYTHON}" \
    "${PIXIU_RELEASE_DIR}/scripts/generate-release-manifest.py" \
    --root "${PIXIU_ROOT}" \
    --output "${STAGE}/usr/share/pixiu/release-manifest.json"

if [ -z "${PIXIU_DEBIAN_DEPENDS}" ]; then
    PIXIU_DEBIAN_DEPENDS="python3 (>= 3.10), curl, dbus, openssl, dpkg-repack, pkexec, \
libqt5widgets5, libqt5network5, libqt5webenginewidgets5, libqt5websockets5, libqt5svg5, libqt5multimedia5, \
fonts-noto-color-emoji, libkysdk-shortcut, libkysdk-notification, libkysdk-qtwidgets, libgsettings-qt1"
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
sed -e "s/@STRICT_NATIVE@/${PIXIU_INSTALL_STRICT}/g" \
    -e "s/@ARCH@/${PIXIU_ARCH}/g" \
    "${DEB_SRC}/preinst.in" > "${STAGE}/DEBIAN/preinst"
chmod 0755 "${STAGE}/DEBIAN/preinst"
install -m 0755 "${DEB_SRC}/prerm"    "${STAGE}/DEBIAN/prerm"
install -m 0755 "${DEB_SRC}/postrm"   "${STAGE}/DEBIAN/postrm"
install -m 0644 "${DEB_SRC}/pixiu.env" \
    "${STAGE}/usr/share/pixiu/pixiu.env.default"
sed "s/@PRODUCT_VERSION@/${PIXIU_VERSION}/g" \
    "${DEB_SRC}/pixiu-backend.service" \
    > "${STAGE}/usr/lib/systemd/user/pixiu-backend.service"
chmod 0644 "${STAGE}/usr/lib/systemd/user/pixiu-backend.service"
printf '%s\n' "${PIXIU_VERSION}" > "${STAGE}/usr/share/pixiu/VERSION"
printf '%s\n' "${PIXIU_INSTALL_STRICT}" \
    > "${STAGE}/usr/share/pixiu/install-strict"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu" "${STAGE}/usr/bin/pixiu"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu-backend" "${STAGE}/usr/bin/pixiu-backend"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu-user-setup" "${STAGE}/usr/bin/pixiu-user-setup"
install -m 0755 "${DEB_SRC}/usr/bin/pixiu-agent-integrate" \
    "${STAGE}/usr/bin/pixiu-agent-integrate"
if [ "${PIXIU_INSTALL_STRICT}" = "1" ]; then
    install -m 0755 "${DEB_SRC}/usr/bin/kylin-agent-runtime" \
        "${STAGE}/usr/bin/kylin-agent-runtime"
    install -D -m 0644 \
        "${DEB_SRC}/usr/lib/systemd/user/kylin-agent-runtime-gateway.service" \
        "${STAGE}/usr/lib/systemd/user/kylin-agent-runtime-gateway.service"
    install -D -m 0644 \
        "${DEB_SRC}/usr/lib/systemd/user/pixiu-kylin-genai-bridge.service" \
        "${STAGE}/usr/lib/systemd/user/pixiu-kylin-genai-bridge.service"
    DESKTOP_FILE="${STAGE}/usr/share/applications/com.kylin.pixiu.desktop"
    [ -f "${DESKTOP_FILE}" ] || die "PIXIU desktop entry is missing from frontend install"
    sed -i 's/^Exec=.*/Exec=pixiu/' "${DESKTOP_FILE}"
fi
install -m 0755 "${PIXIU_RELEASE_DIR}/scripts/migrate-system-data.py" \
    "${STAGE}/usr/lib/pixiu/migrate-system-data"
install -m 0755 "${PIXIU_ROOT}/frontend/scripts/install-update" \
    "${STAGE}/usr/lib/pixiu/install-update"
install -m 0755 "${PIXIU_ROOT}/frontend/scripts/restart-client" \
    "${STAGE}/usr/lib/pixiu/restart-client"

# ── 5/5 dpkg 打包 ──────────────────────────────────────────────
log "[5/5] dpkg-deb"
DEB="${OUT}/pixiu_${PIXIU_VERSION}-${PIXIU_REVISION}_${PIXIU_ARCH}.deb"
dpkg-deb --build --root-owner-group "${STAGE}" "${DEB}" >/dev/null
DEB_NAME="$(basename "${DEB}")"
(
    cd "${OUT}"
    sha256sum "${DEB_NAME}" > "${DEB_NAME}.sha256"
)
log "done: ${DEB}"
log "checksum: $(awk '{print $1}' "${DEB}.sha256")"
