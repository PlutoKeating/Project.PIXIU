#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
runtime_source="${repo_root}/third_party/kylin-agent-runtime"
output_root="${repo_root}/build/release/out/agent-runtime"
wheelhouse="${output_root}/wheelhouse"
lockfile="${output_root}/runtime-cp312.lock"
generated_lock="${output_root}/runtime-cp312.generated.lock"
dependency_lock="${output_root}/runtime-cp312.dependencies.lock"
committed_lock="${script_dir}/runtime-cp312.lock"
build_tools_lock="${script_dir}/build-tools-cp312.lock"
action="${1:-prepare}"

expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["components"]["agent_runtime"]["source_commit"])' "${repo_root}/build/release/agent-supply-chain-policy.json")"
if [[ "$(git -C "${runtime_source}" rev-parse HEAD)" != "${expected_commit}" ]] ||
   [[ -n "$(git -C "${runtime_source}" status --porcelain)" ]]; then
    echo "Agent Runtime submodule must be clean and pinned to ${expected_commit}" >&2
    exit 2
fi

case "${action}" in
prepare)
    [[ "$(dpkg --print-architecture)" = "amd64" ]] || {
        echo "The committed Runtime lock is only valid for amd64" >&2
        exit 2
    }
    [[ "$(python3 -c 'import sys; print(sys.implementation.cache_tag)')" = "cpython-312" ]] || {
        echo "The committed Runtime lock requires CPython 3.12" >&2
        exit 2
    }
    [[ -s "${committed_lock}" && -s "${build_tools_lock}" ]] || {
        echo "Committed Runtime and build-tool locks are required" >&2
        exit 2
    }
    rm -rf "${repo_root}/build/release/out/agent-runtime"
    mkdir -p "${wheelhouse}" "${output_root}/source"
    git -C "${runtime_source}" archive --format=tar HEAD | tar -xf - -C "${output_root}/source"
    for runtime_patch in "${script_dir}"/patches/*.patch; do
        [[ -f "${runtime_patch}" ]] || {
            echo "At least one Runtime distribution patch is required" >&2
            exit 2
        }
        patch -d "${output_root}/source" -p1 --forward --batch < "${runtime_patch}"
    done
    # The pinned upstream setuptools configuration packages plugin Python
    # modules but omits their manifests.  Without plugin.yaml the Runtime
    # scanner cannot discover bundled backends (including keyless DDGS).
    # Keep this distribution-only correction outside the read-only submodule.
    install -m 0644 "${script_dir}/runtime-wheel-MANIFEST.in" \
        "${output_root}/source/MANIFEST.in"
    python3 - "${output_root}/source" <<'PY'
from pathlib import Path
import re
import shutil
import sys

root = Path(sys.argv[1])
for relative in (
    "optional-skills/research/scrapling",
    "skills/github/github-auth",
    "skills/github/github-code-review",
    "skills/github/github-issues",
    "skills/github/github-pr-workflow",
    "skills/github/github-repo-management",
):
    candidate = root / relative
    if not candidate.is_dir():
        raise SystemExit(f"expected optional Runtime skill is missing: {relative}")
    shutil.rmtree(candidate)
pattern = re.compile(rb"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@")
findings = [
    path.relative_to(root).as_posix()
    for path in root.rglob("*")
    if path.is_file()
    and path.relative_to(root).parts[0] not in {"tests", "website", "skills-old"}
    and pattern.search(path.read_bytes())
]
if findings != ["agent/redact.py"]:
    raise SystemExit(f"unexpected authenticated URL locations after pruning: {findings}")
PY
    build_venv="${output_root}/build-venv"
    python3 -m venv "${build_venv}"
    "${build_venv}/bin/pip" install --require-hashes -r "${build_tools_lock}"
    SOURCE_DATE_EPOCH="$(git -C "${runtime_source}" show -s --format=%ct HEAD)" \
        "${build_venv}/bin/pip" wheel --no-deps --no-build-isolation \
        --wheel-dir "${wheelhouse}" "${output_root}/source"
    grep -v '^kylin-agent-runtime==' "${committed_lock}" > "${dependency_lock}"
    "${build_venv}/bin/pip" download --only-binary=:all: \
        --dest "${wheelhouse}" --find-links "${wheelhouse}" \
        --require-hashes -r "${dependency_lock}"
    python3 "${script_dir}/make-wheel-lock.py" "${wheelhouse}" "${generated_lock}"
    cmp "${committed_lock}" "${generated_lock}" || {
        echo "Built Runtime wheelhouse differs from the committed lock" >&2
        exit 2
    }
    cp "${committed_lock}" "${lockfile}"
    rm -f "${generated_lock}" "${dependency_lock}"
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
import ddgs
import kylin_agent_runtime_cli
from agent.web_search_registry import get_active_search_provider
from gateway.platforms.api_server import APIServerAdapter
from kylin_agent_runtime_cli.plugins import discover_plugins, get_bundled_plugins_dir

manifest = get_bundled_plugins_dir() / "web" / "ddgs" / "plugin.yaml"
if not manifest.is_file():
    raise SystemExit(f"bundled DDGS manifest is missing from Runtime wheel: {manifest}")
discover_plugins()
provider = get_active_search_provider()
if provider is None or provider.name != "ddgs" or not provider.is_available():
    raise SystemExit("bundled DDGS web-search provider is not active")
print(f"kylin-agent-runtime-cli={kylin_agent_runtime_cli.__version__}")
print(f"aiohttp={aiohttp.__version__}")
print(f"ddgs={ddgs.__version__}")
print(f"web-search-provider={provider.name}")
print(f"gateway-adapter={APIServerAdapter.__name__}")
PY
    "${verify_root}/venv/bin/kylin-agent-runtime" --version
    ;;
*)
    echo "Usage: $0 prepare|verify-offline" >&2
    exit 2
    ;;
esac
