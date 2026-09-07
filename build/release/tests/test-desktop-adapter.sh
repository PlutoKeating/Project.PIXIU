#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT
qt_flags=( $(pkg-config --cflags --libs Qt5Widgets) )
c++ -std=c++17 -fPIC \
    -I"${repo_root}/build/release/agent-host/compat" \
    "${repo_root}/build/release/tests/test-desktop-adapter.cpp" \
    "${qt_flags[@]}" -o "${fixture}/desktop-adapter-test"
QT_QPA_PLATFORM=offscreen "${fixture}/desktop-adapter-test"
echo "portable desktop adapter interactions: OK"
