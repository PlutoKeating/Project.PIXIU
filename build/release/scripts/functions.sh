#!/usr/bin/env bash
# PIXIU release pipeline — 公共函数
set -euo pipefail

PIXIU_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PIXIU_RELEASE_DIR="${PIXIU_ROOT}/build/release"
export PIXIU_ROOT PIXIU_RELEASE_DIR

log()  { printf '[pixiu-build] %s\n' "$*"; }
warn() { printf '[pixiu-build][warn] %s\n' "$*" >&2; }
die()  { printf '[pixiu-build][error] %s\n' "$*" >&2; exit 1; }

resolve_version() {
    PIXIU_VERSION="${PIXIU_VERSION:-0.1.3}"
    PIXIU_REVISION="${PIXIU_REVISION:-1}"
    PIXIU_ARCH="${PIXIU_ARCH:-$(dpkg --print-architecture 2>/dev/null || echo amd64)}"
    export PIXIU_VERSION PIXIU_REVISION PIXIU_ARCH
}

out_dir()            { printf '%s/out' "${PIXIU_RELEASE_DIR}"; }
stage_dir()          { printf '%s/out/stage' "${PIXIU_RELEASE_DIR}"; }
dist_dir()           { printf '%s/dist' "${PIXIU_RELEASE_DIR}"; }
frontend_build_dir() { printf '%s/build/frontend' "${PIXIU_ROOT}"; }
