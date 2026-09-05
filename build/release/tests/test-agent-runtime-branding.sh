#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FIXTURE="$(mktemp -d)"
trap 'rm -rf "${FIXTURE}"' EXIT

mkdir -p "${FIXTURE}/source"
git -C "${ROOT}/third_party/kylin-agent-runtime" archive --format=tar HEAD |
    tar -xf - -C "${FIXTURE}/source"
for runtime_patch in "${ROOT}"/build/release/agent-runtime/patches/*.patch; do
    patch -d "${FIXTURE}/source" -p1 --forward --batch < "${runtime_patch}" >/dev/null
done

grep -q '_pixiu_model_facing_text' "${FIXTURE}/source/agent/system_prompt.py"
grep -q 'visible_skill_lines' "${FIXTURE}/source/agent/system_prompt.py"
grep -q '_pixiu_model_facing_schema' "${FIXTURE}/source/model_tools.py"
grep -q 'pixiu_tools.py' "${FIXTURE}/source/tools/code_execution_tool.py"
grep -q '你的产品身份、助手署名和对外名称统一为 PIXIU' "${ROOT}/integrations/kylin_agent/SOUL.md"
! grep -qi 'hermes' "${ROOT}/integrations/kylin_agent/SOUL.md"

python3 - "${FIXTURE}/source" <<'PY'
from __future__ import annotations

import ast
from pathlib import Path
import sys


def load_helper(path: Path, function_name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Import) and any(alias.name == "re" for alias in node.names):
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_LEGACY_PRODUCT_NAME"
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == function_name:
            selected.append(node)
    namespace: dict[str, object] = {"Any": object}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace[function_name]


root = Path(sys.argv[1])
brand_text = load_helper(root / "agent/system_prompt.py", "_pixiu_model_facing_text")
brand_schema = load_helper(root / "model_tools.py", "_pixiu_model_facing_schema")

prompt = brand_text("Hermes Agent uses HERMES_HOME in the Hermes WebUI")
if "hermes" in prompt.casefold() or prompt.count("PIXIU") < 2:
    raise SystemExit(f"runtime prompt branding failed: {prompt}")

schema = brand_schema({
    "name": "execute_code",
    "description": "Use Hermes Agent with HERMES_HOME and from hermes_tools import terminal",
})
blob = repr(schema).casefold()
if "hermes" in blob or "pixiu_tools" not in blob or schema["name"] != "execute_code":
    raise SystemExit(f"tool schema branding failed: {schema}")

print("agent runtime branding tests: OK")
PY
