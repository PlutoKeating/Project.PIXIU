#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# Every complete distribution uses the committed cp312 Runtime closure, not
# only the generic CI profile. Apt must reject incompatible system interpreters.
if PIXIU_PROFILE=generic-ubuntu PIXIU_BUNDLE_WHEELS=0 \
        "${ROOT}/build/release/scripts/build-deb.sh" >/dev/null 2>&1; then
    echo "complete packages must not omit backend dependencies" >&2
    exit 1
fi
for PROFILE in generic-ubuntu kylin-v11-x86_64 kylin-v11-native-x86_64; do
    (
        . "${ROOT}/build/release/profiles/${PROFILE}.env"
        test "${PIXIU_PYTHON_VERSION}" = 312
        for DEPENDENCY in 'python3 (>= 3.12)' 'python3 (<< 3.13)' \
                python3-venv libqt5sql5-sqlite; do
            printf '%s\n' "${PIXIU_DEBIAN_DEPENDS}" | grep -qF "${DEPENDENCY}"
        done
    )
done
if PIXIU_PROFILE=missing-unreviewed-profile \
        "${ROOT}/build/release/scripts/build-deb.sh" >/dev/null 2>&1; then
    echo "unknown distribution profiles must fail before building" >&2
    exit 1
fi

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
for package in libgsettings-qt-dev libkysdk-shortcut-dev \
        libkysdk-notification-dev libkysdk-qtwidgets-dev; do
    case " ${APT_BUILD_DEPS} " in
        *" ${package} "*) ;;
        *) echo "native desktop SDK build dependency missing: ${package}" >&2; exit 1 ;;
    esac
done
grep -q 'PIXIU_VECTOR_STORE: portable' "${ROOT}/.github/workflows/ci.yml"
grep -q 'PIXIU_PROFILE: generic-ubuntu' "${ROOT}/.github/workflows/ci.yml"
grep -q 'uses: ./.github/workflows/ci.yml' "${ROOT}/.github/workflows/release.yml"
grep -q 'uses: ./.github/workflows/kylin-native.yml' "${ROOT}/.github/workflows/release.yml"
grep -q 'runs-on: \[self-hosted, linux, x64, kylin-v11\]' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'PIXIU_PROFILE: kylin-v11-native-x86_64' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'pixiu-agent-integrate --quiet' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'systemctl --user restart pixiu-backend.service' \
    "${ROOT}/.github/workflows/kylin-native.yml"
grep -q 'prepare-agent-supply-chain.sh' "${ROOT}/.github/workflows/kylin-native.yml"
PREPARE="${ROOT}/build/release/scripts/prepare-agent-supply-chain.sh"
test "$(PIXIU_KYSDK=ON bash "$PREPARE" --describe)" = kylin-v11
test "$(PIXIU_KYSDK=OFF bash "$PREPARE" --describe)" = generic-debian
if PIXIU_KYSDK=invalid bash "$PREPARE" --describe >/dev/null 2>&1; then
    echo "invalid supply-chain SDK selection must fail" >&2
    exit 1
fi
grep -qF 'PIXIU_KYSDK="${PIXIU_KYSDK:-ON}"' "$PREPARE"
grep -qF -- '--expected-os "$target_os"' "$PREPARE"
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
