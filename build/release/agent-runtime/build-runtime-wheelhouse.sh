#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
runtime_source="${repo_root}/third_party/kylin-agent-runtime"
output_root="${repo_root}/build/release/out/agent-runtime"
wheelhouse="${output_root}/wheelhouse"
lockfile="${output_root}/runtime-cp312.lock"
action="${1:-prepare}"

expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["components"]["agent_runtime"]["source_commit"])' "${repo_root}/build/release/agent-supply-chain-policy.json")"
if [[ "$(git -C "${runtime_source}" rev-parse HEAD)" != "${expected_commit}" ]] ||
   [[ -n "$(git -C "${runtime_source}" status --porcelain)" ]]; then
    echo "Agent Runtime submodule must be clean and pinned to ${expected_commit}" >&2
    exit 2
fi

case "${action}" in
prepare)
    rm -rf "${repo_root}/build/release/out/agent-runtime"
    mkdir -p "${wheelhouse}"
    build_venv="${output_root}/build-venv"
    python3 -m venv "${build_venv}"
    "${build_venv}/bin/pip" install --upgrade pip setuptools wheel
    "${build_venv}/bin/pip" wheel --wheel-dir "${wheelhouse}" \
        "${runtime_source}" "aiohttp==3.13.3"
    python3 "${script_dir}/make-wheel-lock.py" "${wheelhouse}" "${lockfile}"
    ;;
verify-offline)
    [[ -d "${wheelhouse}" && -s "${lockfile}" ]] || {
        echo "Prepare the Runtime wheelhouse before offline verification" >&2
        exit 2
    }
    verify_root="$(mktemp -d)"
    trap 'rm -rf "${verify_root}"' EXIT
    python3 -m venv "${verify_root}/venv"
    "${verify_root}/venv/bin/pip" install --no-index --find-links "${wheelhouse}" \
        --require-hashes -r "${lockfile}"
    "${verify_root}/venv/bin/python" - <<'PY'
import aiohttp
import kylin_agent_runtime_cli
from gateway.platforms.api_server import APIServerAdapter
print(f"kylin-agent-runtime-cli={kylin_agent_runtime_cli.__version__}")
print(f"aiohttp={aiohttp.__version__}")
print(f"gateway-adapter={APIServerAdapter.__name__}")
PY
    "${verify_root}/venv/bin/kylin-agent-runtime" --version
    ;;
*)
    echo "Usage: $0 prepare|verify-offline" >&2
    exit 2
    ;;
esac
