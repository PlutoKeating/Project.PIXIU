#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source_dir="${repo_root}/third_party/kylin-agent"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT

expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["components"]["kylin_agent"]["source_commit"])' "${repo_root}/build/release/agent-supply-chain-policy.json")"
test "$(git -C "${source_dir}" rev-parse HEAD)" = "${expected_commit}"

mkdir -p "${fixture}/source"
git -C "${source_dir}" archive --format=tar HEAD | tar -xf - -C "${fixture}/source"
patch -d "${fixture}/source" -p1 --forward --batch \
    < "${repo_root}/build/release/agent-host/patches/0001-build-coherent-offline-host.patch"
install -D -m 0644 "${repo_root}/build/release/agent-host/compat/pixiu_host_compat.cpp" \
    "${fixture}/source/src/services/pixiu_host_compat.cpp"

grep -q 'src/services/pixiu_host_compat.cpp' "${fixture}/source/CMakeLists.txt"
grep -q 'GatewayService gatewayService' "${fixture}/source/src/main.cpp"
! grep -q 'src/ui/modelsettingswidget.cpp' "${fixture}/source/CMakeLists.txt"
grep -q '/v1/chat/completions' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'chatCompletionFinished' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q -- '--hide' "${repo_root}/build/release/agent-host/build-agent-host.sh"
! grep -q -- 'kylin-agent.*--version' "${repo_root}/build/release/agent-host/build-agent-host.sh"

echo "agent host adaptation tests: OK"
