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
# The public upstream tree contains one credential-bearing clone URL and two
# unused online bootstrap scripts.  They are not admissible in a distributable
# source archive.  Replace exactly that URL with its public upstream and remove
# only the two uncompiled bootstrap files; fail if upstream shape changes.
python3 - "${output_dir}/source" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
gateway = root / "src/services/gatewayservice.cpp"
content = gateway.read_text(encoding="utf-8")
pattern = re.compile(r"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@[^\\\"\s]+")
content, count = pattern.subn("https://gitee.com/openkylin/kylin-cua.git", content)
if count != 1:
    raise SystemExit(f"expected one authenticated upstream URL, found {count}")
gateway.write_text(content, encoding="utf-8")
for relative in ("scripts/agent_runtime_install.sh", "scripts/agent_runtime_install_bak.sh"):
    candidate = root / relative
    if not candidate.is_file():
        raise SystemExit(f"expected upstream bootstrap file is missing: {relative}")
    candidate.unlink()
PY

cmake -S "${output_dir}/source" -B "${output_dir}/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr
cmake --build "${output_dir}/build" --parallel
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
