#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

(
    unset APT_BUILD_DEPS
    # shellcheck source=/dev/null
    . "${ROOT}/build/release/profiles/kylin-v11-x86_64.env"
    test "${PIXIU_KYSDK}" = "OFF"
    test "${PIXIU_INSTALL_STRICT}" = "0"
    case "${APT_BUILD_DEPS}" in
        *cmake*ninja-build*g++*qtbase5-dev*libqt5websockets5-dev*) ;;
        *) echo "portable Kylin build dependencies missing" >&2; exit 1 ;;
    esac
)

# shellcheck source=/dev/null
. "${ROOT}/build/release/profiles/kylin-v11-native-x86_64.env"

test "${PIXIU_KYSDK}" = "ON"
test "${PIXIU_INSTALL_STRICT}" = "1"
case "${PIXIU_DEBIAN_DEPENDS}" in
    *libkylin-coreai-embedding*libkysdk-vector-engine-client*) ;;
    *) echo "native runtime dependencies missing" >&2; exit 1 ;;
esac
case "${APT_BUILD_DEPS}" in
    *libkylin-coreai-embedding-dev*libkysdk-vector-engine-client-dev*) ;;
    *) echo "native build dependencies missing" >&2; exit 1 ;;
esac
grep -q 'PIXIU_VECTOR_STORE: portable' "${ROOT}/.github/workflows/ci.yml"
grep -q 'profile: generic-ubuntu' "${ROOT}/.github/workflows/release.yml"
grep -q 'runs-on: \[self-hosted, linux, x64, kylin-v11\]' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'PIXIU_VECTOR_STORE=kylin' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'pixiu-agent-integrate --quiet' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'HERMES_HOME:.*runner.temp.*pixiu-agent-profile' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'native-sdk-smoke.py' "${ROOT}/.github/workflows/kylin-native.yml"

if PIXIU_PROFILE=kylin-v11-native-x86_64 PIXIU_KYSDK=ON \
        PIXIU_INSTALL_STRICT=0 PIXIU_SKIP_TESTS=1 \
        "${ROOT}/build/release/scripts/build-deb.sh" >/dev/null 2>&1; then
    echo "native KYSDK builds must not disable strict install checks" >&2
    exit 1
fi
if PIXIU_PROFILE=generic-ubuntu PIXIU_KYSDK=OFF PIXIU_INSTALL_STRICT=1 \
        PIXIU_SKIP_TESTS=1 \
        "${ROOT}/build/release/scripts/build-deb.sh" >/dev/null 2>&1; then
    echo "strict install checks must not be paired with KYSDK=OFF" >&2
    exit 1
fi

echo "native profile tests: OK"
