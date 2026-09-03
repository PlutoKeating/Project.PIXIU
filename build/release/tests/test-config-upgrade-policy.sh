#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD="${ROOT}/build/release/scripts/build-deb.sh"
POSTINST="${ROOT}/build/release/debian/postinst"

test ! -e "${ROOT}/build/release/debian/conffiles"
grep -q 'usr/share/pixiu/pixiu.env.default' "${BUILD}"
if grep -q 'STAGE}/etc/pixiu/pixiu.env' "${BUILD}"; then
    echo "runtime config must not be shipped as a dpkg conffile" >&2
    exit 1
fi
grep -q 'CONF_TEMPLATE="/usr/share/pixiu/pixiu.env.default"' "${POSTINST}"
grep -q 'if \[ ! -e "${CONF}" \]' "${POSTINST}"

echo "config upgrade policy tests: OK"
