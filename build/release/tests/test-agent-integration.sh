#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="${ROOT}/build/release/debian/usr/bin/pixiu-agent-integrate"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

FAKE_BIN="${TMP}/kylin-agent-runtime"
cat > "${FAKE_BIN}" <<'SH'
#!/bin/sh
printf '%s\n' "$*" > "${HERMES_HOME}/runtime-call"
SH
chmod 0755 "${FAKE_BIN}"

HOME="${TMP}/home" \
PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" \
    "${SCRIPT}" --quiet

DEST="${TMP}/home/.kylin-agent-runtime/plugins/pixiu"
test -f "${DEST}/.pixiu-managed"
test -f "${DEST}/provider.py"
test ! -f "${DEST}/plugin.yaml.in"
grep -qx 'version: 0.1.7' "${DEST}/plugin.yaml"
grep -qx 'config set memory.provider pixiu' \
    "${TMP}/home/.kylin-agent-runtime/runtime-call"
grep -qx 'PIXIU_AGENT_ENDPOINT=http://127.0.0.1:8765' \
    "${TMP}/home/.kylin-agent-runtime/.env"

# Managed upgrades are idempotent and preserve explicit user configuration.
sed -i 's/^PIXIU_AGENT_SCOPE=.*/PIXIU_AGENT_SCOPE=user:tester/' \
    "${TMP}/home/.kylin-agent-runtime/.env"
HOME="${TMP}/home" \
PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" \
    "${SCRIPT}" --quiet
grep -qx 'PIXIU_AGENT_SCOPE=user:tester' "${TMP}/home/.kylin-agent-runtime/.env"
test "$(grep -c '^PIXIU_AGENT_ENDPOINT=' "${TMP}/home/.kylin-agent-runtime/.env")" -eq 1

# An unmanaged collision is never overwritten.
mkdir -p "${TMP}/other/plugins/pixiu"
printf 'user owned\n' > "${TMP}/other/plugins/pixiu/custom.txt"
if HOME="${TMP}/other-home" HERMES_HOME="${TMP}/other" \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" "${SCRIPT}" --quiet 2>/dev/null; then
    echo "unmanaged plugin collision must fail" >&2
    exit 1
fi
grep -qx 'user owned' "${TMP}/other/plugins/pixiu/custom.txt"

if HOME="${TMP}/home" HERMES_HOME=relative/path \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" "${SCRIPT}" --quiet 2>/dev/null; then
    echo "relative Agent profile must fail" >&2
    exit 1
fi

grep -q 'integrations/kylin_agent' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'pixiu-agent-integrate' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'pixiu-agent-integrate --quiet' \
    "${ROOT}/build/release/debian/usr/bin/pixiu"
grep -q 'plugin.yaml.in' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'PIXIU_PRODUCT_VERSION=@PRODUCT_VERSION@' \
    "${ROOT}/build/release/debian/pixiu-backend.service"
grep -q 'usr/share/pixiu/VERSION' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 's/@PRODUCT_VERSION@/' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'backend=runtime-injected' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'backend.foundation.api.install_health' \
    "${ROOT}/frontend/scripts/install-update"

echo "agent integration packaging tests: OK"
