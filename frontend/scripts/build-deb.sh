#!/usr/bin/env bash
set -euo pipefail

# PIXIU 前端 .deb 打包脚本（不依赖 debhelper）。
#
# 用法：
#   scripts/build-deb.sh                  # KYSDK=ON Release 打包
#   PIXIU_HAVE_KYSDK=OFF scripts/build-deb.sh
#   BUILD_DIR=/tmp/pixiu-deb scripts/build-deb.sh
#
# 产物：build/dist/pixiu-frontend_<version>_<arch>.deb

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-${ROOT}/build/deb}"
DIST_DIR="${ROOT}/build/dist"
KYSDK="${PIXIU_HAVE_KYSDK:-ON}"

control="${ROOT}/debian/control"
postinst="${ROOT}/debian/postinst"

if [[ ! -f "${control}" ]]; then
    echo "error: ${control} not found" >&2
    exit 1
fi

version="$(sed -n 's/^Version: //p' "${control}")"

# ── 版本一致性预检（镜像 build/release/scripts/build-deb.sh 的
#    check_version_consistency 思路）：debian/control 的 Version 上游部分
#    必须与 frontend/CMakeLists.txt 的 project VERSION（单一事实源）一致，
#    防止 dpkg -l 显示版本与应用内版本漂移（V-3 曾实测 0.1.0-1 vs 0.1.1）。
cmake_ver="$(sed -nE 's/.*project\(pixiu-frontend VERSION ([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' \
    "${ROOT}/CMakeLists.txt" | head -n1)"
upstream_ver="${version%-*}"   # 剥离 Debian 修订号（如 0.1.1-1 → 0.1.1）
if [ -z "${cmake_ver}" ] || [ "${upstream_ver}" != "${cmake_ver}" ]; then
    echo "error: 版本不一致：debian/control Version=${version:-<未提取>} 上游 ${upstream_ver:-<未提取>}，" \
         "frontend/CMakeLists.txt project VERSION=${cmake_ver:-<未提取>}（应同步为同一版本）" >&2
    exit 1
fi

arch="$(dpkg --print-architecture)"
deb_name="pixiu-frontend_${version}_${arch}.deb"

echo "==> configuring (KYSDK=${KYSDK}, Release)"
cmake -S "${ROOT}" -B "${BUILD_DIR}" \
    -DPIXIU_HAVE_KYSDK="${KYSDK}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr

echo "==> building"
cmake --build "${BUILD_DIR}" -j"$(nproc)"

stage="$(mktemp -d /tmp/pixiu-deb.XXXXXX)"
trap 'rm -rf "${stage}"' EXIT

echo "==> staging install tree"
cmake --install "${BUILD_DIR}" --prefix "${stage}/usr" >/dev/null

mkdir -p "${stage}/DEBIAN"
cp "${control}" "${stage}/DEBIAN/control"
install -m 0755 "${postinst}" "${stage}/DEBIAN/postinst"
mkdir -p "${stage}/usr/lib/pixiu"
install -m 0755 "${ROOT}/scripts/install-update" \
    "${stage}/usr/lib/pixiu/install-update"

mkdir -p "${DIST_DIR}"
echo "==> building ${DIST_DIR}/${deb_name}"
dpkg-deb --build --root-owner-group "${stage}" "${DIST_DIR}/${deb_name}" >/dev/null

echo "==> done: ${DIST_DIR}/${deb_name}"
