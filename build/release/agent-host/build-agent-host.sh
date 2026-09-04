#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
source_dir="${repo_root}/third_party/kylin-agent"
output_dir="${repo_root}/build/release/out/agent-host"
expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["components"]["kylin_agent"]["source_commit"])' "${repo_root}/build/release/agent-supply-chain-policy.json")"

actual_commit="$(git -C "${source_dir}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${expected_commit}" ]]; then
    echo "Agent host commit mismatch: expected ${expected_commit}, got ${actual_commit}" >&2
    exit 2
fi
if [[ -n "$(git -C "${source_dir}" status --porcelain)" ]]; then
    echo "Agent host submodule must be clean" >&2
    exit 2
fi

if [[ "${output_dir}" != "${repo_root}/build/release/out/agent-host" ]]; then
    echo "Refusing unexpected Agent host output path" >&2
    exit 2
fi
rm -rf "${repo_root}/build/release/out/agent-host"
mkdir -p "${output_dir}/source" "${output_dir}/build" "${output_dir}/install"
git -C "${source_dir}" archive --format=tar HEAD | tar -xf - -C "${output_dir}/source"
patch -d "${output_dir}/source" -p1 --forward --batch \
    < "${script_dir}/patches/0001-build-coherent-offline-host.patch"
install -D -m 0644 "${script_dir}/compat/pixiu_host_compat.cpp" \
    "${output_dir}/source/src/services/pixiu_host_compat.cpp"

cmake -S "${output_dir}/source" -B "${output_dir}/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "${output_dir}/build" --parallel
DESTDIR="${output_dir}/install" cmake --install "${output_dir}/build"
QT_QPA_PLATFORM=offscreen "${output_dir}/install/usr/bin/kylin-agent" --version
