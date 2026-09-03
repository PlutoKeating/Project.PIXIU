#!/usr/bin/env bash
# Verify immutable contest sources and repository cleanliness before delivery work.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MANIFEST="docs/OFFICIAL_SOURCES.sha256"
ALLOW_DIRTY=0

usage() {
    printf 'usage: %s [--root PATH] [--manifest PATH] [--allow-dirty]\n' "$0"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --root)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            ROOT="$2"
            shift 2
            ;;
        --manifest)
            [ "$#" -ge 2 ] || { usage >&2; exit 2; }
            MANIFEST="$2"
            shift 2
            ;;
        --allow-dirty)
            ALLOW_DIRTY=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'governance: unknown argument: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ ! -d "${ROOT}/.git" ]; then
    printf 'governance: not a Git worktree: %s\n' "${ROOT}" >&2
    exit 1
fi

if [[ "${MANIFEST}" = /* ]]; then
    MANIFEST_PATH="${MANIFEST}"
else
    MANIFEST_PATH="${ROOT}/${MANIFEST}"
fi
if [ ! -f "${MANIFEST_PATH}" ]; then
    printf 'governance: official source manifest missing: %s\n' "${MANIFEST_PATH}" >&2
    exit 1
fi

(
    cd "${ROOT}"
    sha256sum --check "${MANIFEST_PATH}"
)

if [ "${ALLOW_DIRTY}" != "1" ]; then
    STATUS="$(git -C "${ROOT}" status --short --untracked-files=all)"
    if [ -n "${STATUS}" ]; then
        printf 'governance: worktree is not clean:\n%s\n' "${STATUS}" >&2
        exit 1
    fi
fi

printf 'governance: official sources verified; worktree %s\n' \
    "$([ "${ALLOW_DIRTY}" = "1" ] && printf 'check skipped' || printf 'clean')"
