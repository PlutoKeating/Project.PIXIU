#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT
mkdir "${fixture}/source" "${fixture}/config"
bash "${repo_root}/build/release/agent-host/prepare-agent-host.sh" "${fixture}/source"
qt_flags=( $(pkg-config --cflags --libs Qt5Widgets) )
moc "${fixture}/source/include/utils/thememanager.h" -o "${fixture}/theme-moc.cpp"
c++ -std=c++17 -fPIC -I"${fixture}/source/include" \
    "${repo_root}/build/release/tests/test-agent-host-theme.cpp" \
    "${fixture}/source/src/utils/thememanager.cpp" "${fixture}/theme-moc.cpp" \
    "${qt_flags[@]}" -o "${fixture}/theme-test"
for list_name in memorySources auditRecords; do
    XDG_CONFIG_HOME="${fixture}/config" QT_QPA_PLATFORM=offscreen "${fixture}/theme-test" "${list_name}"
done
