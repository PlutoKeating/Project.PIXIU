#!/usr/bin/env bash
# Sign the canonical lowercase digest with the offline Ed25519 release key.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CHECKSUM="${1:-}"
KEY="${PIXIU_SIGNING_KEY_FILE:-}"
[ -f "${CHECKSUM}" ] && [ ! -L "${CHECKSUM}" ] || {
    echo "pixiu-sign: checksum file required" >&2
    exit 2
}
[ -f "${KEY}" ] && [ ! -L "${KEY}" ] || {
    echo "pixiu-sign: PIXIU_SIGNING_KEY_FILE must name a regular file" >&2
    exit 2
}

DIGEST="$(awk 'NR == 1 {print tolower($1)}' "${CHECKSUM}")"
case "${DIGEST}" in
    *[!0-9a-f]*|"") echo "pixiu-sign: invalid SHA-256 manifest" >&2; exit 2 ;;
esac
[ "${#DIGEST}" -eq 64 ] || {
    echo "pixiu-sign: invalid SHA-256 length" >&2
    exit 2
}

SIGNATURE="${CHECKSUM}.sig"
printf '%s\n' "${DIGEST}" | openssl pkeyutl -sign -rawin \
    -inkey "${KEY}" -out "${SIGNATURE}"
printf '%s\n' "${DIGEST}" | openssl pkeyutl -verify -pubin -rawin \
    -inkey "${ROOT}/build/release/keys/pixiu-release-ed25519.pub" \
    -sigfile "${SIGNATURE}" >/dev/null
echo "pixiu-sign: wrote ${SIGNATURE}"
