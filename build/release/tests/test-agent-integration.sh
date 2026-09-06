#!/usr/bin/env bash
set -euo pipefail

# The fixtures intentionally vary HOME. Runner-wide XDG/Agent paths must not
# redirect their units, backups or profiles outside the temporary fixture.
unset XDG_CONFIG_HOME XDG_STATE_HOME HERMES_HOME

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PRODUCT_VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
export PIXIU_PRODUCT_VERSION_FILE="${ROOT}/VERSION"
SCRIPT="${ROOT}/build/release/debian/usr/bin/pixiu-agent-integrate"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

FAKE_BIN="${TMP}/kylin-agent-runtime"
printf '%s\n' '#!/bin/sh' \
    'if [ "${1:-}" = "--version" ]; then printf "%s\n" "KylinAgent v0.9.8"; exit 0; fi' \
    'if [ "${PIXIU_RUNTIME_FAIL_CONFIG:-0}" = "1" ]; then exit 9; fi' \
    'printf "%s\n" "$*" >> "${HERMES_HOME}/runtime-call"' > "${FAKE_BIN}"
chmod 0755 "${FAKE_BIN}"
FAKE_HOST="${TMP}/kylin-agent"
printf '%s\n' '#!/bin/sh' 'exit 0' > "${FAKE_HOST}"
chmod 0755 "${FAKE_HOST}"
FAKE_USER_SETUP="${TMP}/pixiu-user-setup"
printf '%s\n' '#!/bin/sh' 'test "${1:-}" = "--start"' > "${FAKE_USER_SETUP}"
chmod 0755 "${FAKE_USER_SETUP}"
STRICT_FILE="${TMP}/install-strict"
printf '1\n' > "${STRICT_FILE}"
FAKE_SYSTEMCTL="${TMP}/systemctl"
printf '%s\n' '#!/bin/sh' 'printf "%s\n" "$*" >> "${PIXIU_SYSTEMCTL_LOG}"' \
    'if [ "${PIXIU_SYSTEMCTL_FAIL_ENABLE:-0}" = "1" ] && [ "${2:-}" = "enable" ]; then exit 8; fi' \
    'if [ "${PIXIU_SYSTEMCTL_FAIL_RESTART:-0}" = "1" ] && [ "${2:-}" = "restart" ]; then exit 8; fi' \
    > "${FAKE_SYSTEMCTL}"
chmod 0755 "${FAKE_SYSTEMCTL}"
FAKE_UNIT="${TMP}/kylin-agent-runtime-gateway.service"
printf '%s\n' '[Service]' 'ExecStart=/usr/bin/kylin-agent-runtime gateway run --replace' \
    > "${FAKE_UNIT}"
FAKE_BRIDGE="${TMP}/kylin_genai_bridge.py"
printf '%s\n' '# bridge fixture' > "${FAKE_BRIDGE}"
FAKE_BRIDGE_UNIT="${TMP}/pixiu-kylin-genai-bridge.service"
printf '%s\n' '[Service]' 'ExecStart=/usr/bin/true' > "${FAKE_BRIDGE_UNIT}"
mkdir -p "${TMP}/home/.config/systemd/user"
printf '%s\n' '[Service]' \
    'ExecStart=/home/tester/.local/bin/kylin-agent-runtime gateway run --replace' \
    > "${TMP}/home/.config/systemd/user/kylin-agent-runtime-gateway.service"
printf '%s\n' '[Service]' \
    'ExecStart=/home/tester/.local/bin/kylin-agent-runtime gateway run --replace' \
    > "${TMP}/home/.config/systemd/user/hermes-gateway.service"

HOME="${TMP}/home" \
PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" \
PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
PIXIU_SYSTEMCTL_BIN="${FAKE_SYSTEMCTL}" \
PIXIU_SYSTEMCTL_LOG="${TMP}/systemctl-call" \
PIXIU_AGENT_GATEWAY_UNIT="${FAKE_UNIT}" \
PIXIU_KYLIN_BRIDGE_SOURCE="${FAKE_BRIDGE}" \
PIXIU_KYLIN_BRIDGE_UNIT="${FAKE_BRIDGE_UNIT}" \
    "${SCRIPT}" --quiet

DEST="${TMP}/home/.kylin-agent-runtime/plugins/pixiu"
test -f "${DEST}/.pixiu-managed"
test -f "${DEST}/provider.py"
test ! -f "${DEST}/plugin.yaml.in"
grep -qx "version: ${PRODUCT_VERSION}" "${DEST}/plugin.yaml"
grep -qx 'config set memory.provider pixiu' \
    "${TMP}/home/.kylin-agent-runtime/runtime-call"
grep -qx 'config set model.provider custom' "${TMP}/home/.kylin-agent-runtime/runtime-call"
grep -qx 'config set model.default kylin-default' "${TMP}/home/.kylin-agent-runtime/runtime-call"
grep -qx 'config set model.base_url http://127.0.0.1:8767/v1' \
    "${TMP}/home/.kylin-agent-runtime/runtime-call"
grep -qx 'config set model.api_key pixiu-local-bridge' \
    "${TMP}/home/.kylin-agent-runtime/runtime-call"
test -f "${TMP}/home/.kylin-agent-runtime/.pixiu-kylin-model-seeded"
grep -qx -- '--user daemon-reload' "${TMP}/systemctl-call"
grep -qx -- '--user disable --now hermes-gateway.service' \
    "${TMP}/systemctl-call"
grep -qx -- '--user enable --now kylin-agent-runtime-gateway.service' \
    "${TMP}/systemctl-call"
grep -qx -- '--user restart kylin-agent-runtime-gateway.service' \
    "${TMP}/systemctl-call"
grep -qx -- '--user enable --now pixiu-kylin-genai-bridge.service' \
    "${TMP}/systemctl-call"
grep -qx -- '--user restart pixiu-kylin-genai-bridge.service' \
    "${TMP}/systemctl-call"
test ! -e "${TMP}/home/.config/systemd/user/kylin-agent-runtime-gateway.service"
test ! -e "${TMP}/home/.config/systemd/user/hermes-gateway.service"
grep -q '/home/tester/.local/bin/kylin-agent-runtime' \
    "${TMP}"/home/.local/state/pixiu/service-backups/kylin-agent-runtime-gateway.service.pre-pixiu.*
grep -q '/home/tester/.local/bin/kylin-agent-runtime' \
    "${TMP}"/home/.local/state/pixiu/service-backups/hermes-gateway.service.pre-pixiu.*
grep -qx 'PIXIU_AGENT_ENDPOINT=http://127.0.0.1:8765' \
    "${TMP}/home/.kylin-agent-runtime/.env"
grep -qx 'PIXIU_AGENT_STRICT=1' "${TMP}/home/.kylin-agent-runtime/.env"
cmp "${ROOT}/integrations/kylin_agent/SOUL.md" \
    "${TMP}/home/.kylin-agent-runtime/SOUL.md"

# Managed upgrades are idempotent and preserve explicit user configuration.
sed -i 's/^PIXIU_AGENT_SCOPE=.*/PIXIU_AGENT_SCOPE=user:tester/' \
    "${TMP}/home/.kylin-agent-runtime/.env"
sed -i 's/^PIXIU_AGENT_STRICT=.*/PIXIU_AGENT_STRICT=0/' \
    "${TMP}/home/.kylin-agent-runtime/.env"
HOME="${TMP}/home" \
PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" \
PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
PIXIU_SYSTEMCTL_BIN="${FAKE_SYSTEMCTL}" \
PIXIU_SYSTEMCTL_LOG="${TMP}/systemctl-call" \
PIXIU_AGENT_GATEWAY_UNIT="${FAKE_UNIT}" \
PIXIU_KYLIN_BRIDGE_SOURCE="${FAKE_BRIDGE}" \
PIXIU_KYLIN_BRIDGE_UNIT="${FAKE_BRIDGE_UNIT}" \
    "${SCRIPT}" --quiet
grep -qx 'PIXIU_AGENT_SCOPE=user:tester' "${TMP}/home/.kylin-agent-runtime/.env"
grep -qx 'PIXIU_AGENT_STRICT=1' "${TMP}/home/.kylin-agent-runtime/.env"
test "$(grep -c '^PIXIU_AGENT_ENDPOINT=' "${TMP}/home/.kylin-agent-runtime/.env")" -eq 1
test "$(grep -c '^config set model.default kylin-default$' \
    "${TMP}/home/.kylin-agent-runtime/runtime-call")" -eq 1

# An unmanaged collision is never overwritten.
mkdir -p "${TMP}/other/plugins/pixiu"
printf 'user owned\n' > "${TMP}/other/plugins/pixiu/custom.txt"
if HOME="${TMP}/other-home" HERMES_HOME="${TMP}/other" \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
   "${SCRIPT}" --quiet 2>/dev/null; then
    echo "unmanaged plugin collision must fail" >&2
    exit 1
fi
grep -qx 'user owned' "${TMP}/other/plugins/pixiu/custom.txt"

if HOME="${TMP}/home" HERMES_HOME=relative/path \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
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
       PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
       PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
       "${SCRIPT}" --quiet >/dev/null 2>&1; then
        echo "Agent integration must reject ${scenario}" >&2
        exit 1
    fi
    test ! -e "${TMP}/failure-home/.kylin-agent-runtime/plugins/pixiu"
done

# Unsafe user-unit collisions are rejected before the profile is created.
mkdir -p "${TMP}/unsafe-home/.config/systemd/user"
printf '%s\n' '[Service]' 'ExecStart=/usr/bin/user-service --serve' \
    > "${TMP}/unsafe-home/.config/systemd/user/hermes.service"
if HOME="${TMP}/unsafe-home" \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
   PIXIU_SYSTEMCTL_BIN="${FAKE_SYSTEMCTL}" \
   PIXIU_AGENT_GATEWAY_UNIT="${FAKE_UNIT}" \
   "${SCRIPT}" --quiet >/dev/null 2>&1; then
    echo "unmanaged Agent unit must fail preflight" >&2
    exit 1
fi
test ! -e "${TMP}/unsafe-home/.kylin-agent-runtime/plugins/pixiu"

# A Runtime configuration failure restores the provider and profile files.
ROLLBACK_HOME="${TMP}/rollback-home"
ROLLBACK_AGENT="${ROLLBACK_HOME}/.kylin-agent-runtime"
mkdir -p "${ROLLBACK_AGENT}/plugins/pixiu"
printf '%s\n' 'old-provider' > "${ROLLBACK_AGENT}/plugins/pixiu/.pixiu-managed"
printf '%s\n' 'old-provider-data' > "${ROLLBACK_AGENT}/plugins/pixiu/old.txt"
printf '%s\n' 'EXISTING=value' > "${ROLLBACK_AGENT}/.env"
printf '%s\n' 'memory: old' > "${ROLLBACK_AGENT}/config.yaml"
printf '%s\n' 'old identity' > "${ROLLBACK_AGENT}/SOUL.md"
if HOME="${ROLLBACK_HOME}" PIXIU_RUNTIME_FAIL_CONFIG=1 \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${TMP}/non-strict" \
   "${SCRIPT}" --quiet >/dev/null 2>&1; then
    echo "Runtime configuration failure must abort activation" >&2
    exit 1
fi
grep -qx 'old-provider-data' "${ROLLBACK_AGENT}/plugins/pixiu/old.txt"
grep -qx 'EXISTING=value' "${ROLLBACK_AGENT}/.env"
grep -qx 'memory: old' "${ROLLBACK_AGENT}/config.yaml"
grep -qx 'old identity' "${ROLLBACK_AGENT}/SOUL.md"
test ! -e "${ROLLBACK_AGENT}/plugins/pixiu/provider.py"

# A gateway activation failure restores both profile data and migrated units.
SYSTEMD_HOME="${TMP}/systemd-rollback-home"
SYSTEMD_AGENT="${SYSTEMD_HOME}/.kylin-agent-runtime"
SYSTEMD_UNITS="${SYSTEMD_HOME}/.config/systemd/user"
mkdir -p "${SYSTEMD_AGENT}/plugins/pixiu" "${SYSTEMD_UNITS}"
printf '%s\n' 'old-provider' > "${SYSTEMD_AGENT}/plugins/pixiu/.pixiu-managed"
printf '%s\n' 'old-provider-data' > "${SYSTEMD_AGENT}/plugins/pixiu/old.txt"
printf '%s\n' 'EXISTING=value' > "${SYSTEMD_AGENT}/.env"
printf '%s\n' '[Service]' \
    'ExecStart=/home/tester/.local/bin/kylin-agent-runtime gateway run --replace' \
    > "${SYSTEMD_UNITS}/hermes-gateway.service"
if HOME="${SYSTEMD_HOME}" PIXIU_SYSTEMCTL_FAIL_ENABLE=1 \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
   PIXIU_SYSTEMCTL_BIN="${FAKE_SYSTEMCTL}" \
   PIXIU_SYSTEMCTL_LOG="${TMP}/systemctl-rollback-call" \
   PIXIU_AGENT_GATEWAY_UNIT="${FAKE_UNIT}" \
   "${SCRIPT}" --quiet >/dev/null 2>&1; then
    echo "gateway activation failure must abort activation" >&2
    exit 1
fi
grep -qx 'old-provider-data' "${SYSTEMD_AGENT}/plugins/pixiu/old.txt"
grep -qx 'EXISTING=value' "${SYSTEMD_AGENT}/.env"
grep -q 'kylin-agent-runtime gateway run --replace' \
    "${SYSTEMD_UNITS}/hermes-gateway.service"
test ! -e "${SYSTEMD_AGENT}/plugins/pixiu/provider.py"

# A running gateway that cannot restart also rolls profile data back.
RESTART_HOME="${TMP}/restart-rollback-home"
RESTART_AGENT="${RESTART_HOME}/.kylin-agent-runtime"
mkdir -p "${RESTART_AGENT}/plugins/pixiu"
printf '%s\n' 'old-provider' > "${RESTART_AGENT}/plugins/pixiu/.pixiu-managed"
printf '%s\n' 'old-provider-data' > "${RESTART_AGENT}/plugins/pixiu/old.txt"
printf '%s\n' 'memory: old' > "${RESTART_AGENT}/config.yaml"
if HOME="${RESTART_HOME}" PIXIU_SYSTEMCTL_FAIL_RESTART=1 \
   PIXIU_AGENT_PLUGIN_SOURCE="${ROOT}/integrations/kylin_agent/pixiu" \
   PIXIU_AGENT_RUNTIME_BIN="${FAKE_BIN}" PIXIU_AGENT_HOST_BIN="${FAKE_HOST}" \
   PIXIU_USER_SETUP_BIN="${FAKE_USER_SETUP}" \
   PIXIU_AGENT_DEFAULT_STRICT_FILE="${STRICT_FILE}" \
   PIXIU_SYSTEMCTL_BIN="${FAKE_SYSTEMCTL}" \
   PIXIU_SYSTEMCTL_LOG="${TMP}/systemctl-restart-rollback-call" \
   PIXIU_AGENT_GATEWAY_UNIT="${FAKE_UNIT}" \
   "${SCRIPT}" --quiet >/dev/null 2>&1; then
    echo "gateway restart failure must abort activation" >&2
    exit 1
fi
grep -qx 'old-provider-data' "${RESTART_AGENT}/plugins/pixiu/old.txt"
grep -qx 'memory: old' "${RESTART_AGENT}/config.yaml"
test ! -e "${RESTART_AGENT}/plugins/pixiu/provider.py"

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
grep -q 'kylin-agent-runtime-gateway.service' \
    "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'pixiu-kylin-genai-bridge.service' \
    "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'kylin_genai_bridge.py' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'libkysdk-genai-nlp0' \
    "${ROOT}/build/release/profiles/kylin-v11-native-x86_64.env"
grep -q 'agent-supply-chain.py\|audit-agent-supply-chain.py' \
    "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'runtime-cp312.lock' "${ROOT}/build/release/debian/postinst"
grep -q -- '--require-hashes' "${ROOT}/build/release/debian/postinst"
grep -q -- '--force-reinstall --require-hashes' \
    "${ROOT}/build/release/debian/postinst"
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
