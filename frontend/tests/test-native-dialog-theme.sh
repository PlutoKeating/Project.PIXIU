#!/usr/bin/env bash
# SDK rendering gate; this is deliberately not a portable Qt substitute.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT
qt_flags=( $(pkg-config --cflags --libs kysdk-qtwidgets Qt5Widgets) )
mkdir "${fixture}/source" "${fixture}/config"
bash "${repo_root}/build/release/agent-host/prepare-agent-host.sh" "${fixture}/source"
moc "${fixture}/source/include/utils/thememanager.h" -o "${fixture}/theme-moc.cpp"
c++ -std=c++17 -fPIC -DPIXIU_HAVE_KYSDK=1 -I"${fixture}/source/include" \
    "${repo_root}/frontend/tests/test-native-dialog-theme.cpp" \
    "${fixture}/source/src/utils/thememanager.cpp" \
    "${fixture}/source/src/utils/kylinfiledialog.cpp" "${fixture}/theme-moc.cpp" \
    "${qt_flags[@]}" -o "${fixture}/native-dialog-theme-test"
XDG_CONFIG_HOME="${fixture}/config" timeout 30s "${fixture}/native-dialog-theme-test"
echo "native SDK file picker close contrast and cancellation: PASS"
