#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TEMPLATE="${ROOT}/build/release/debian/preinst.in"
TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP}"' EXIT

test -f "${TEMPLATE}"
grep -q '@STRICT_NATIVE@' "${TEMPLATE}"
grep -q '@ARCH@' "${TEMPLATE}"
grep -q 'preinst.in' "${ROOT}/build/release/scripts/build-deb.sh"

sed -e 's/@STRICT_NATIVE@/0/g' -e 's/@ARCH@/amd64/g' \
    "${TEMPLATE}" > "${TMP}/generic-preinst"
sh "${TMP}/generic-preinst" >/dev/null

mkdir -p "${TMP}/root/etc" "${TMP}/bin"
printf '%s\n' 'ID=kylin' 'NAME="Kylin OS"' 'VERSION_ID=11.2' \
    > "${TMP}/root/etc/os-release"
printf '%s\n' '#!/bin/sh' 'printf amd64' > "${TMP}/bin/dpkg"
chmod 0755 "${TMP}/bin/dpkg"
sed -e 's/@STRICT_NATIVE@/1/g' -e 's/@ARCH@/amd64/g' \
    "${TEMPLATE}" > "${TMP}/strict-preinst"

PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
    sh "${TMP}/strict-preinst" >/dev/null

printf '%s\n' 'ID=kylin' 'NAME="Kylin OS"' 'VERSION_ID=10.0' \
    > "${TMP}/root/etc/os-release"
if PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
        PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
        sh "${TMP}/strict-preinst" >/dev/null 2>&1; then
    echo "strict preflight must reject non-V11 Kylin systems" >&2
    exit 1
fi
printf '%s\n' 'ID=kylin' 'NAME="Kylin OS"' 'VERSION_ID=11.2' \
    > "${TMP}/root/etc/os-release"

printf '%s\n' '#!/bin/sh' 'printf arm64' > "${TMP}/bin/dpkg"
chmod 0755 "${TMP}/bin/dpkg"
if PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
        PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
        sh "${TMP}/strict-preinst" >/dev/null 2>&1; then
    echo "strict preflight must reject an incompatible architecture" >&2
    exit 1
fi

printf 'install preflight tests: OK\n'
