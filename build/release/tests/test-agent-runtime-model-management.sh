#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source_dir="${repo_root}/third_party/kylin-agent-runtime"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT

mkdir -p "${fixture}/source"
git -C "${source_dir}" archive --format=tar HEAD | tar -xf - -C "${fixture}/source"
patch -d "${fixture}/source" -p1 --forward --batch \
    < "${repo_root}/build/release/agent-runtime/patches/0001-secure-model-management.patch"

api="${fixture}/source/gateway/platforms/api_server.py"
grep -q 'credential_configured' "${api}"
grep -q '_redact_model_entry' "${api}"
grep -q '_handle_probe_config_model' "${api}"
grep -q '/api/config/models/probe' "${api}"
grep -q 'preferredDefaultModel' "${api}"
test "$(grep -c 'os.chmod(temporary, 0o600)' "${api}")" -eq 2
grep -q 'class NoRedirect(urllib.request.HTTPRedirectHandler)' "${api}"
grep -q 'credential = credential or str(redacted.pop("api_key", "")' "${api}"
grep -q 'cfg\["model"\]\["api_key"\] = first.get("apiKey") or ""' "${api}"
grep -q 'return web.json_response(self._redact_model_entry(entry), status=201)' "${api}"
grep -q 'return web.json_response(self._redact_model_entry(entry))' "${api}"
! grep -q 'return web.json_response(cleaned)' "${api}"
! grep -q 'return web.json_response(entry, status=201)' "${api}"

python3 -m py_compile "${api}"
echo "agent runtime model management tests: OK"
