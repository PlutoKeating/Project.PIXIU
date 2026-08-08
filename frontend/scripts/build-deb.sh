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

mkdir -p "${DIST_DIR}"
echo "==> building ${DIST_DIR}/${deb_name}"
dpkg-deb --build --root-owner-group "${stage}" "${DIST_DIR}/${deb_name}" >/dev/null

echo "==> done: ${DIST_DIR}/${deb_name}"
