#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TEMPLATE="${ROOT}/build/release/debian/preinst.in"
TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP}"' EXIT

test -f "${TEMPLATE}"
grep -q '@STRICT_NATIVE@' "${TEMPLATE}"
grep -q '@ARCH@' "${TEMPLATE}"
grep -q 'kylin-agent-runtime' "${TEMPLATE}"
grep -q 'libkylin-coreai-embedding' "${TEMPLATE}"
grep -q 'libkysdk-vector-engine-client' "${TEMPLATE}"
grep -q 'preinst.in' "${ROOT}/build/release/scripts/build-deb.sh"

sed -e 's/@STRICT_NATIVE@/0/g' -e 's/@ARCH@/amd64/g' \
    "${TEMPLATE}" > "${TMP}/generic-preinst"
sh "${TMP}/generic-preinst" >/dev/null

mkdir -p "${TMP}/root/etc" "${TMP}/bin"
printf '%s\n' 'ID=kylin' 'NAME="Kylin OS"' 'VERSION_ID=11.2' \
    > "${TMP}/root/etc/os-release"
for command in kylin-agent kylin-agent-runtime; do
    printf '%s\n' '#!/bin/sh' 'exit 0' > "${TMP}/bin/${command}"
    chmod 0755 "${TMP}/bin/${command}"
done
printf '%s\n' '#!/bin/sh' 'echo "KylinAgent v0.9.8"' \
    > "${TMP}/bin/kylin-agent-runtime"
chmod 0755 "${TMP}/bin/kylin-agent-runtime"
printf '%s\n' '#!/bin/sh' 'printf amd64' > "${TMP}/bin/dpkg"
printf '%s\n' '#!/bin/sh' \
    'if [ -n "${MISSING_SDK:-}" ]; then case "$*" in *"${MISSING_SDK}"*) exit 1;; esac; fi' \
    'printf installed' > "${TMP}/bin/dpkg-query"
chmod 0755 "${TMP}/bin/dpkg" "${TMP}/bin/dpkg-query"
sed -e 's/@STRICT_NATIVE@/1/g' -e 's/@ARCH@/amd64/g' \
    "${TEMPLATE}" > "${TMP}/strict-preinst"

PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
PIXIU_PREFLIGHT_PATH="${TMP}/bin" \
PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
PIXIU_PREFLIGHT_DPKG_QUERY="${TMP}/bin/dpkg-query" \
    sh "${TMP}/strict-preinst" >/dev/null

printf '%s\n' 'ID=kylin' 'NAME="Kylin OS"' 'VERSION_ID=10.0' \
    > "${TMP}/root/etc/os-release"
if PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
        PIXIU_PREFLIGHT_PATH="${TMP}/bin" \
        PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
        PIXIU_PREFLIGHT_DPKG_QUERY="${TMP}/bin/dpkg-query" \
        sh "${TMP}/strict-preinst" >/dev/null 2>&1; then
    echo "strict preflight must reject non-V11 Kylin systems" >&2
    exit 1
fi
printf '%s\n' 'ID=kylin' 'NAME="Kylin OS"' 'VERSION_ID=11.2' \
    > "${TMP}/root/etc/os-release"

rm "${TMP}/bin/kylin-agent-runtime"
if PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
        PIXIU_PREFLIGHT_PATH="${TMP}/bin" \
        PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
        PIXIU_PREFLIGHT_DPKG_QUERY="${TMP}/bin/dpkg-query" \
        sh "${TMP}/strict-preinst" >/dev/null 2>&1; then
    echo "strict preflight must reject a missing Agent runtime" >&2
    exit 1
fi

cp "${TMP}/bin/kylin-agent" "${TMP}/bin/kylin-agent-runtime"
printf '%s\n' '#!/bin/sh' 'echo "KylinAgent v0.9.8"' \
    > "${TMP}/bin/kylin-agent-runtime"
chmod 0755 "${TMP}/bin/kylin-agent-runtime"
if MISSING_SDK=libkylin-coreai-embedding \
        PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
        PIXIU_PREFLIGHT_PATH="${TMP}/bin" \
        PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
        PIXIU_PREFLIGHT_DPKG_QUERY="${TMP}/bin/dpkg-query" \
        sh "${TMP}/strict-preinst" >/dev/null 2>&1; then
    echo "strict preflight must reject a missing Kylin SDK package" >&2
    exit 1
fi

printf '%s\n' '#!/bin/sh' 'echo "KylinAgent v0.10.0"' \
    > "${TMP}/bin/kylin-agent-runtime"
chmod 0755 "${TMP}/bin/kylin-agent-runtime"
if PIXIU_PREFLIGHT_ROOT="${TMP}/root" \
        PIXIU_PREFLIGHT_PATH="${TMP}/bin" \
        PIXIU_PREFLIGHT_DPKG="${TMP}/bin/dpkg" \
        PIXIU_PREFLIGHT_DPKG_QUERY="${TMP}/bin/dpkg-query" \
        sh "${TMP}/strict-preinst" >/dev/null 2>&1; then
    echo "strict preflight must reject an unsupported Agent runtime" >&2
    exit 1
fi

printf 'install preflight tests: OK\n'
