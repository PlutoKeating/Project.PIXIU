#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PRODUCT_VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
SCRIPT="${ROOT}/build/release/debian/usr/bin/pixiu-agent-integrate"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

FAKE_BIN="${TMP}/kylin-agent-runtime"
printf '%s\n' '#!/bin/sh' \
    'if [ "${1:-}" = "--version" ]; then printf "%s\n" "KylinAgent v0.9.8"; exit 0; fi' \
    'printf "%s\n" "$*" > "${HERMES_HOME}/runtime-call"' > "${FAKE_BIN}"
chmod 0755 "${FAKE_BIN}"
FAKE_HOST="${TMP}/kylin-agent"
printf '%s\n' '#!/bin/sh' 'exit 0' > "${FAKE_HOST}"
chmod 0755 "${FAKE_HOST}"
STRICT_FILE="${TMP}/install-strict"
printf '1\n' > "${STRICT_FILE}"

HOME="${TMP}/home" \
PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" \
PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
    "${SCRIPT}" --quiet

DEST="${TMP}/home/.kylin-agent-runtime/plugins/pixiu"
test -f "${DEST}/.pixiu-managed"
test -f "${DEST}/provider.py"
test ! -f "${DEST}/plugin.yaml.in"
grep -qx "version: ${PRODUCT_VERSION}" "${DEST}/plugin.yaml"
grep -qx 'config set memory.provider pixiu' \
    "${TMP}/home/.kylin-agent-runtime/runtime-call"
grep -qx 'PIXIU_AGENT_ENDPOINT=http://127.0.0.1:8765' \
    "${TMP}/home/.kylin-agent-runtime/.env"
grep -qx 'PIXIU_AGENT_STRICT=1' "${TMP}/home/.kylin-agent-runtime/.env"

# Managed upgrades are idempotent and preserve explicit user configuration.
sed -i 's/^PIXIU_AGENT_SCOPE=.*/PIXIU_AGENT_SCOPE=user:tester/' \
    "${TMP}/home/.kylin-agent-runtime/.env"
sed -i 's/^PIXIU_AGENT_STRICT=.*/PIXIU_AGENT_STRICT=0/' \
    "${TMP}/home/.kylin-agent-runtime/.env"
HOME="${TMP}/home" \
PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" \
PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
    "${SCRIPT}" --quiet
grep -qx 'PIXIU_AGENT_SCOPE=user:tester' "${TMP}/home/.kylin-agent-runtime/.env"
grep -qx 'PIXIU_AGENT_STRICT=1' "${TMP}/home/.kylin-agent-runtime/.env"
test "$(grep -c '^PIXIU_AGENT_ENDPOINT=' "${TMP}/home/.kylin-agent-runtime/.env")" -eq 1

# An unmanaged collision is never overwritten.
mkdir -p "${TMP}/other/plugins/pixiu"
printf 'user owned\n' > "${TMP}/other/plugins/pixiu/custom.txt"
if HOME="${TMP}/other-home" HERMES_HOME="${TMP}/other" \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
   "${SCRIPT}" --quiet 2>/dev/null; then
    echo "unmanaged plugin collision must fail" >&2
    exit 1
fi
grep -qx 'user owned' "${TMP}/other/plugins/pixiu/custom.txt"

if HOME="${TMP}/home" HERMES_HOME=relative/path \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
   "${SCRIPT}" --quiet 2>/dev/null; then
    echo "relative Agent profile must fail" >&2
    exit 1
fi

# Agent/runtime validation happens before mutating the user's profile.
for scenario in missing-host runtime-nonzero runtime-unsupported runtime-ambiguous; do
    rm -rf "${TMP}/failure-home"
    runtime="${FAKE_BIN}"
    host="${FAKE_HOST}"
    case "${scenario}" in
        missing-host) host="${TMP}/missing-host" ;;
        runtime-nonzero)
            runtime="${TMP}/runtime-nonzero"
            printf '%s\n' '#!/bin/sh' 'echo "KylinAgent v0.9.8"' 'exit 7' > "${runtime}"
            chmod 0755 "${runtime}"
            ;;
        runtime-unsupported)
            runtime="${TMP}/runtime-unsupported"
            printf '%s\n' '#!/bin/sh' 'echo "KylinAgent v0.10.0"' > "${runtime}"
            chmod 0755 "${runtime}"
            ;;
        runtime-ambiguous)
            runtime="${TMP}/runtime-ambiguous"
            printf '%s\n' '#!/bin/sh' 'echo "0.9.8 compatible with 0.9.7"' > "${runtime}"
            chmod 0755 "${runtime}"
            ;;
    esac
    if HOME="${TMP}/failure-home" \
       PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
       PIXIU_AGENT_RUNTIME_BIN="${runtime}" PIXIU_AGENT_HOST_BIN="${host}" \
       PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
       "${SCRIPT}" --quiet >/dev/null 2>&1; then
        echo "Agent integration must reject ${scenario}" >&2
        exit 1
    fi
    test ! -e "${TMP}/failure-home/.kylin-agent-runtime/plugins/pixiu"
done

grep -q 'integrations/kylin_agent' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'pixiu-agent-integrate' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'pixiu-agent-integrate --quiet' \
    "${ROOT}/build/release/debian/usr/bin/pixiu"
grep -q 'exec /usr/bin/kylin-agent' \
    "${ROOT}/build/release/debian/usr/bin/pixiu"
grep -q 'PATH=/usr/bin:/bin:/usr/sbin:/sbin' \
    "${ROOT}/build/release/debian/usr/bin/pixiu"
grep -q 'KYLIN_AGENT_FORCE_RUNTIME_RESTART=1' \
    "${ROOT}/build/release/debian/usr/bin/pixiu"
grep -q 'RUNTIME=/usr/bin/kylin-agent-runtime' \
    "${ROOT}/build/release/debian/usr/bin/pixiu-agent-integrate"
grep -q 'agent-supply-chain.py\|audit-agent-supply-chain.py' \
    "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'runtime-cp312.lock' "${ROOT}/build/release/debian/postinst"
grep -q -- '--require-hashes' "${ROOT}/build/release/debian/postinst"
grep -q 'plugin.yaml.in' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'PIXIU_PRODUCT_VERSION=@PRODUCT_VERSION@' \
    "${ROOT}/build/release/debian/pixiu-backend.service"
grep -q 'usr/share/pixiu/VERSION' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'usr/share/pixiu/install-strict' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 's/@PRODUCT_VERSION@/' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'backend=runtime-injected' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'backend.foundation.api.install_health' \
    "${ROOT}/frontend/scripts/install-update"

echo "agent integration packaging tests: OK"
