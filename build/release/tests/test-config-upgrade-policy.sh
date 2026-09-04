#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BUILD="${ROOT}/build/release/scripts/build-deb.sh"
POSTINST="${ROOT}/build/release/debian/postinst"
USER_SETUP="${ROOT}/build/release/debian/usr/bin/pixiu-user-setup"

test ! -e "${ROOT}/build/release/debian/conffiles"
grep -q 'usr/share/pixiu/pixiu.env.default' "${BUILD}"
if grep -q 'STAGE}/etc/pixiu/pixiu.env' "${BUILD}"; then
    echo "runtime config must not be shipped as a dpkg conffile" >&2
    exit 1
fi
if grep -q '/etc/pixiu/pixiu.env' "${POSTINST}"; then
    echo "postinst must not create per-user runtime configuration" >&2
    exit 1
fi
grep -q 'DEFAULT_CONFIG=${PIXIU_DEFAULT_CONFIG:-/usr/share/pixiu/pixiu.env.default}' "${USER_SETUP}"
grep -q 'XDG_CONFIG_HOME' "${USER_SETUP}"

echo "config upgrade policy tests: OK"
