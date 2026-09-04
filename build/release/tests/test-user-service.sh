#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
UNIT="${ROOT}/build/release/debian/pixiu-backend.service"
LAUNCHER="${ROOT}/build/release/debian/usr/bin/pixiu"
BACKEND="${ROOT}/build/release/debian/usr/bin/pixiu-backend"
SETUP="${ROOT}/build/release/debian/usr/bin/pixiu-user-setup"
BUILD="${ROOT}/build/release/scripts/build-deb.sh"
INTEGRATE="${ROOT}/build/release/debian/usr/bin/pixiu-agent-integrate"

test -f "${SETUP}"
sh -n "${SETUP}"
sh -n "${LAUNCHER}"
sh -n "${BACKEND}"

grep -q '^WantedBy=default.target$' "${UNIT}"
grep -q '^EnvironmentFile=-%E/pixiu/pixiu.env$' "${UNIT}"
if grep -Eq '^(User|Group)=' "${UNIT}"; then
    echo "user unit must inherit the desktop user's UID" >&2
    exit 1
fi
grep -q 'pixiu-user-setup' "${LAUNCHER}"
grep -q 'systemctl --user' "${SETUP}"
grep -q 'pixiu-user-setup' "${INTEGRATE}"
grep -q 'property MainPID' "${SETUP}"
grep -q '/proc/${SERVICE_PID}/status' "${SETUP}"
grep -q 'pixiu-memory-backend' "${SETUP}"
grep -q 'product_version' "${SETUP}"
grep -q 'pkexec /usr/lib/pixiu/migrate-system-data' "${SETUP}"
grep -q 'migrate-system-data.py' "${BUILD}"
grep -q 'XDG_DATA_HOME' "${BACKEND}"
grep -q 'XDG_CONFIG_HOME' "${BACKEND}"
grep -q 'lib/systemd/user' "${BUILD}"
grep -q 'chmod 0644 .*pixiu-backend.service' "${BUILD}"
if grep -q 'lib/systemd/system' "${BUILD}"; then
    echo "release package must not install the backend as a system service" >&2
    exit 1
fi
if grep -Eq 'useradd|chown -Rh .*pixiu|enable pixiu-backend.service' \
        "${ROOT}/build/release/debian/postinst"; then
    echo "postinst must not create or launch a machine-wide backend identity" >&2
    exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP}"' EXIT
HOME="${TMP}/home" \
XDG_DATA_HOME="${TMP}/data" \
XDG_CONFIG_HOME="${TMP}/config" \
XDG_STATE_HOME="${TMP}/state" \
PIXIU_DEFAULT_CONFIG="${ROOT}/build/release/debian/pixiu.env" \
    sh "${SETUP}" --prepare-only
test -f "${TMP}/config/pixiu/pixiu.env"
test "$(stat -c %a "${TMP}/config/pixiu/pixiu.env")" = 600
test "$(stat -c %a "${TMP}/data/pixiu")" = 700
test "$(stat -c %a "${TMP}/state/pixiu")" = 700
if grep -q 'change-me-before-production' "${TMP}/config/pixiu/pixiu.env"; then
    echo "first user setup must replace the packaged passphrase placeholder" >&2
    exit 1
fi

printf '1\n' >"${TMP}/strict"
HOME="${TMP}/home" \
XDG_DATA_HOME="${TMP}/strict-data" \
XDG_CONFIG_HOME="${TMP}/strict-config" \
XDG_STATE_HOME="${TMP}/strict-state" \
PIXIU_DEFAULT_CONFIG="${ROOT}/build/release/debian/pixiu.env" \
PIXIU_STRICT_FILE="${TMP}/strict" \
    sh "${SETUP}" --prepare-only
grep -qx 'PIXIU_EMBEDDING=kylin' "${TMP}/strict-config/pixiu/pixiu.env"
grep -qx 'PIXIU_VECTOR_STORE=kylin' "${TMP}/strict-config/pixiu/pixiu.env"

echo "user service packaging tests: OK"
