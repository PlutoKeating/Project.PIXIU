#!/usr/bin/env bash
set -euo pipefail

test_binary="$1"
test_case="$2"
isolation_root=$(mktemp -d "${TMPDIR:-/tmp}/pixiu-test-isolation.XXXXXX")
sentinel="${isolation_root}/pixiu-update-other-process.deb"
cleanup() {
    # Only our own sentinel is removed; never recursively clean a shared temp root.
    rm -f -- "$sentinel"
    rmdir -- "$isolation_root"
}
trap cleanup EXIT
printf '%s' 'owned by another process' > "$sentinel"

TMPDIR="$isolation_root" QT_QPA_PLATFORM=offscreen "$test_binary" "$test_case"
if [[ ! -f "$sentinel" ]] || [[ "$(< "$sentinel")" != 'owned by another process' ]]; then
    echo 'upgrade test modified another process temporary package' >&2
    exit 1
fi
echo 'upgrade test temporary package isolation: OK'
