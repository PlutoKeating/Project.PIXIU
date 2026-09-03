#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck source=/dev/null
. "${ROOT}/build/release/profiles/kylin-v11-native-x86_64.env"

test "${PIXIU_KYSDK}" = "ON"
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

echo "native profile tests: OK"
