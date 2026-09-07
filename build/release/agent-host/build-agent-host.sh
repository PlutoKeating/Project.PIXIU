#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
output_dir="${repo_root}/build/release/out/agent-host"

# The only removed tree is this fixed, generated build output.
if [[ -L "${output_dir}" ]]; then
    echo "Refusing symlink Agent output directory" >&2
    exit 2
fi
rm -rf "${repo_root}/build/release/out/agent-host"
mkdir -p "${output_dir}/source" "${output_dir}/build" "${output_dir}/install"
bash "${script_dir}/prepare-agent-host.sh" "${output_dir}/source"

cmake -S "${output_dir}/source" -B "${output_dir}/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "${output_dir}/build" --parallel "${CMAKE_BUILD_PARALLEL_LEVEL:-2}"
DESTDIR="${output_dir}/install" cmake --install "${output_dir}/build"
host_binary="${output_dir}/install/usr/bin/kylin-agent"
file "${host_binary}"
if ldd "${host_binary}" | grep -q 'not found'; then
    echo "Agent host has unresolved dynamic dependencies" >&2
    exit 3
fi
# The pinned upstream host has no CLI version action.  Its documented --hide
# activation path initializes the QApplication/single-instance boundary and
# exits without opening a window, making it a deterministic headless smoke test.
QT_QPA_PLATFORM=offscreen "${host_binary}" --hide
