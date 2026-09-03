#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CHECKER="${ROOT}/build/release/scripts/verify-governance.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

make_fixture() {
    local fixture="$1"
    mkdir -p "${fixture}/docs"
    printf 'official text\n' > "${fixture}/docs/OriginProblemDescription.md"
    printf 'official deck\n' > "${fixture}/docs/完整赛题要求.pptx"
    (
        cd "${fixture}"
        sha256sum docs/OriginProblemDescription.md docs/完整赛题要求.pptx \
            > docs/OFFICIAL_SOURCES.sha256
        git init -q
        git config user.email 'test@pixiu.invalid'
        git config user.name 'PIXIU Test'
        git add docs
        git commit -qm fixture
    )
}

test_clean_repository_passes() {
    local fixture="${TMP}/clean"
    make_fixture "${fixture}"
    "${CHECKER}" --root "${fixture}" >/dev/null
}

test_changed_official_source_fails() {
    local fixture="${TMP}/tampered"
    make_fixture "${fixture}"
    printf 'changed\n' >> "${fixture}/docs/OriginProblemDescription.md"
    if "${CHECKER}" --root "${fixture}" >/dev/null 2>&1; then
        printf 'expected a changed official source to fail\n' >&2
        return 1
    fi
}

test_dirty_repository_fails() {
    local fixture="${TMP}/dirty"
    make_fixture "${fixture}"
    printf 'temporary\n' > "${fixture}/unexpected.txt"
    if "${CHECKER}" --root "${fixture}" >/dev/null 2>&1; then
        printf 'expected an untracked file to fail\n' >&2
        return 1
    fi
}

test_clean_repository_passes
test_changed_official_source_fails
test_dirty_repository_fails
printf 'governance tests: OK\n'
