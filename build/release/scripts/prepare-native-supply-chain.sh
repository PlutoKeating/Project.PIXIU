#!/usr/bin/env bash
# Rebuild the pinned Agent distribution and record real network-isolated evidence.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$root"
evidence="$root/build/release/evidence/agent-supply-chain"
test ! -e "$evidence" || {
    echo "Use a fresh checkout: supply-chain evidence already exists" >&2
    exit 2
}
mkdir -p "$evidence/logs"
builder="$(id -un)"
sudo -n unshare --net runuser -u "$builder" -- \
    env TMPDIR="${TMPDIR:-/tmp}" CMAKE_BUILD_PARALLEL_LEVEL=2 \
    bash build/release/agent-host/build-agent-host.sh \
    2>&1 | tee "$evidence/logs/host-build.log"
tar -czf "$evidence/host-corresponding-source.tar.gz" \
    -C build/release/out/agent-host source \
    -C "$root" build/release/agent-host integrations/kylin_agent/message_renderer
record=(python3 build/release/scripts/record-agent-supply-chain.py
    --root . --evidence-dir "$evidence")
"${record[@]}" host-build --target-arch amd64 \
    --artifact build/release/out/agent-host/install/usr/bin/kylin-agent \
    --source-archive "$evidence/host-corresponding-source.tar.gz" \
    --build-log "$evidence/logs/host-build.log" --network-isolated
bash build/release/agent-runtime/build-runtime-wheelhouse.sh prepare
sudo -n unshare --net runuser -u "$builder" -- \
    env TMPDIR="${TMPDIR:-/tmp}" \
    bash build/release/agent-runtime/build-runtime-wheelhouse.sh verify-offline \
    2>&1 | tee "$evidence/logs/runtime-offline-install.log"
"${record[@]}" runtime-wheelhouse --target-arch amd64 --python-abi cp312 \
    --wheelhouse build/release/out/agent-runtime/wheelhouse \
    --lockfile build/release/out/agent-runtime/runtime-cp312.lock \
    --offline-install-log "$evidence/logs/runtime-offline-install.log" --network-isolated
"${record[@]}" legal
python3 build/release/scripts/audit-agent-supply-chain.py \
    --root . --evidence-dir "$evidence" --require-ready --expected-arch amd64
