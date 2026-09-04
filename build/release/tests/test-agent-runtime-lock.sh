#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="${ROOT}/build/release/agent-runtime/build-runtime-wheelhouse.sh"
RUNTIME_LOCK="${ROOT}/build/release/agent-runtime/runtime-cp312.lock"
TOOLS_LOCK="${ROOT}/build/release/agent-runtime/build-tools-cp312.lock"

test -s "${RUNTIME_LOCK}"
test -s "${TOOLS_LOCK}"
grep -q -- '--require-hashes -r "${build_tools_lock}"' "${SCRIPT}"
grep -q -- '--require-hashes -r "${committed_lock}"' "${SCRIPT}"
grep -q 'cmp "${committed_lock}" "${generated_lock}"' "${SCRIPT}"
grep -q 'dpkg --print-architecture' "${SCRIPT}"
grep -q 'cpython-312' "${SCRIPT}"
grep -q '^ddgs==' "${RUNTIME_LOCK}"
grep -q 'import ddgs' "${SCRIPT}"

python3 - "${RUNTIME_LOCK}" "${TOOLS_LOCK}" <<'PY'
from pathlib import Path
import re
import sys

entry = re.compile(r"^[A-Za-z0-9_.-]+==[^ ]+ --hash=sha256:[0-9a-f]{64}$")
for filename in sys.argv[1:]:
    lines = [
        line for line in Path(filename).read_text().splitlines()
        if line and not line.startswith("#")
    ]
    if not lines or any(not entry.fullmatch(line) for line in lines):
        raise SystemExit(f"invalid hash lock: {filename}")
PY

echo "agent runtime committed-lock tests: OK"
