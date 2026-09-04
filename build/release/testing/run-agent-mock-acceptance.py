#!/usr/bin/env python3
"""Exercise the real Agent Gateway against the deterministic test node.

The output is engineering evidence only. It is deliberately marked as mock
evidence and must never satisfy the contest's real-cloud lifecycle gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FULL_REQUIRED_TOOLS = {
    "terminal",
    "web_search",
    "pixiu_memory_remember",
    "pixiu_memory_search",
    "pixiu_memory_update",
    "pixiu_sync_status",
}
MEMORY_REQUIRED_TOOLS = {
    "pixiu_memory_remember",
    "pixiu_memory_search",
    "pixiu_memory_update",
    "pixiu_sync_status",
}


class AcceptanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Scenario:
    prompts: list[str]
    required_tools: set[str]
    search_run_index: int


def scenario_for_suite(suite: str, marker: str, artifact: Path) -> Scenario:
    if suite == "memory":
        return Scenario(
            prompts=[
                f"请记住共享验收标记 {marker}。",
                f"请检索共享验收标记 {marker}，并只回答该标记。",
                f"请将共享验收标记更正为：{marker}-UPDATED。",
                "请检查当前共享记忆同步状态并概括结果。",
            ],
            required_tools=set(MEMORY_REQUIRED_TOOLS),
            search_run_index=1,
        )
    if suite == "full":
        return Scenario(
            prompts=[
                "请记住我的回答偏好：先给结论，再给必要依据，并由你决定是否保存为长期偏好。",
                f"请使用系统命令读取文件 {artifact} 的内容，确认标记后删除文件；删除前请求单次确认。",
                "请联网查询 openKylin 官方站点的项目简介；将结论和此前标记保存为长期记忆。",
                "请查找本次验收保存的随机标记，并只回答该标记。",
                f"请将刚才查到的验收记忆更正为：{marker}-UPDATED，并保留原事实来源。",
                "请检查当前共享记忆同步状态并概括结果。",
            ],
            required_tools=set(FULL_REQUIRED_TOOLS),
            search_run_index=3,
        )
    raise AcceptanceError(f"unsupported acceptance suite: {suite}")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_lifecycle(path: Path):
    spec = importlib.util.spec_from_file_location("pixiu_agent_lifecycle", path)
    if spec is None or spec.loader is None:
        raise AcceptanceError("cannot load Agent lifecycle client")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request_json(
    base_url: str,
    path: str,
    *,
    api_key: str = "",
    payload: dict[str, Any] | None = None,
) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _release_identity(
    manifest_path: Path, expected_commit: str, backend_url: str
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise AcceptanceError("installed release manifest is invalid")
    build = manifest.get("build")
    product = manifest.get("product")
    interfaces = manifest.get("interfaces")
    if not all(isinstance(item, dict) for item in (build, product, interfaces)):
        raise AcceptanceError("installed release manifest lacks identity fields")
    if build.get("git_commit") != expected_commit:
        raise AcceptanceError("installed release commit does not match expected commit")
    version = _request_json(backend_url, "/version")
    expected_version = {
        "product_version": product.get("version"),
        "component": "pixiu-memory-backend",
        "api_version": interfaces.get("http_api"),
        "agent_memory_api": interfaces.get("agent_memory_api"),
        "schema_version": interfaces.get("database_schema"),
    }
    if not isinstance(version, dict) or any(
        version.get(key) != value for key, value in expected_version.items()
    ):
        raise AcceptanceError("backend version does not match installed release manifest")
    return {
        "git_commit": expected_commit,
        "product_version": product.get("version"),
        "debian_version": product.get("debian_version"),
        "architecture": build.get("architecture"),
        "profile": build.get("profile"),
        "install_strict": build.get("install_strict"),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    release = _release_identity(
        args.release_manifest.resolve(), args.expected_commit, args.backend_url
    )
    lifecycle = _load_lifecycle(args.lifecycle_script)
    client = lifecycle.AgentClient(args.gateway_url, timeout=args.timeout)
    client.validate_capabilities()
    before_trace = _request_json(args.mock_url, "/_test/trace", api_key=args.mock_api_key)
    trace_start = len(before_trace.get("requests", []))

    session_id = f"pixiu-mock-{uuid.uuid4().hex}"
    client.create_session(session_id)
    marker = f"PIXIU-{uuid.uuid4().hex.upper()}"
    runs: list[dict[str, Any]] = []
    artifact: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", prefix="pixiu-mock-marker-", suffix=".txt", delete=False
        ) as stream:
            stream.write(marker + "\n")
            artifact = Path(stream.name)
        os.chmod(artifact, 0o600)
        scenario = scenario_for_suite(args.suite, marker, artifact)
        for prompt in scenario.prompts:
            runs.append(client.run(session_id, prompt, lambda _run_id: True))
    finally:
        if artifact is not None:
            artifact.unlink(missing_ok=True)

    tools = [name for item in runs for name in item["tools"]]
    messages = client.messages(session_id)
    after_trace = _request_json(args.mock_url, "/_test/trace", api_key=args.mock_api_key)
    requests = after_trace.get("requests", [])[trace_start:]
    if not isinstance(requests, list) or not requests:
        raise AcceptanceError("mock node did not observe model requests")
    if not scenario.required_tools.issubset(tools):
        raise AcceptanceError(f"Agent did not execute required tools: {sorted(set(tools))}")
    if marker not in runs[scenario.search_run_index]["output"]:
        raise AcceptanceError("Agent search did not return the stored marker")
    if not all(item.get("system_prompt_nonempty") is True for item in requests):
        raise AcceptanceError("Runtime did not inject a non-empty system prompt")
    if not all(MEMORY_REQUIRED_TOOLS <= set(item.get("available_tools", [])) for item in requests):
        raise AcceptanceError("PIXIU memory tools were not present in every model call")
    if max(int(item.get("user_turn_count", 0)) for item in requests) < len(scenario.prompts):
        observed = [
            {
                "request_index": item.get("request_index"),
                "roles": item.get("message_roles"),
                "user_turn_count": item.get("user_turn_count"),
                "assistant_turn_count": item.get("assistant_turn_count"),
                "tool_result_count": item.get("tool_result_count"),
            }
            for item in requests
        ]
        raise AcceptanceError(
            "multi-turn user context was not retained; observed="
            + json.dumps(observed, ensure_ascii=False)
        )
    if not any(int(item.get("assistant_turn_count", 0)) >= len(scenario.prompts) - 1 for item in requests):
        raise AcceptanceError("multi-turn assistant context was not retained")
    if not any(int(item.get("tool_result_count", 0)) >= 1 for item in requests):
        raise AcceptanceError("tool results were not returned to the model")
    if len([item for item in messages if item.get("role") in {"user", "assistant"}]) < 2 * len(scenario.prompts):
        raise AcceptanceError("Gateway did not persist the complete conversation")

    verification = _request_json(
        args.backend_url,
        "/agent/context",
        payload={
            "query": marker + " UPDATED",
            "scope": args.scope,
            "session_id": "mock-verifier",
            "turn_id": "turn-000001",
            "top_k": 10,
            "max_chars": 8000,
        },
    )
    items = verification.get("items") if isinstance(verification, dict) else None
    context = verification.get("context") if isinstance(verification, dict) else None
    if not isinstance(items, list) or not items or not all(item.get("scope") == args.scope for item in items):
        raise AcceptanceError("backend did not prove scope-filtered memory retrieval")
    if not isinstance(context, str) or "UPDATED" not in context:
        raise AcceptanceError("backend did not expose the Agent-updated memory version")

    selected = [item.get("selected_tool") for item in requests if item.get("selected_tool")]
    if not scenario.required_tools.issubset(selected):
        raise AcceptanceError("mock trace and Gateway tool events disagree")
    system_hashes = {
        item.get("system_prompt_sha256")
        for item in requests
        if isinstance(item.get("system_prompt_sha256"), str)
    }
    if not system_hashes or not all(re.fullmatch(r"[0-9a-f]{64}", item) for item in system_hashes):
        raise AcceptanceError("system prompt trace digests are invalid")

    result = {
        "evidence_schema": 1,
        "evidence_class": "pixiu-agent-mock-e2e",
        "status": "pass",
        "mock_only": True,
        "not_release_evidence": True,
        "inference_performed": False,
        "suite": args.suite,
        "release": release,
        "scope": args.scope,
        "checks": {
            "multi_turn_conversation": "passed",
            "system_prompt_injected": "passed",
            "conversation_context_retained": "passed",
            "memory_remember": "passed",
            "memory_search": "passed",
            "memory_update": "passed",
            "sync_status_tool": "passed",
            "scope_filtered_backend_verification": "passed",
            "gateway_message_persistence": "passed",
        },
        "observations": {
            "model_request_count": len(requests),
            "gateway_message_count": len(messages),
            "tool_names": sorted(set(tools)),
            "tool_call_count": len(tools),
            "approval_count": sum(item["approvals"] for item in runs),
            "system_prompt_variants": len(system_hashes),
            "marker_sha256": _digest(marker),
            "payloads_retained": False,
        },
    }

    if args.suite == "full":
        result["checks"].update(
            {
                "terminal_tool_and_approval": "passed",
                "web_search_tool": "passed",
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:8642")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8765")
    parser.add_argument("--mock-url", default="http://127.0.0.1:18081")
    parser.add_argument("--mock-api-key", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument(
        "--release-manifest",
        type=Path,
        default=Path("/usr/share/pixiu/release-manifest.json"),
    )
    parser.add_argument("--lifecycle-script", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--suite", choices=("full", "memory"), default="full")
    args = parser.parse_args()
    if not re.fullmatch(r"(?:user|shared):[A-Za-z0-9._-]+", args.scope):
        parser.error("--scope must be a valid user: or shared: scope")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_commit):
        parser.error("--expected-commit must be a full lowercase Git commit")
    try:
        evidence = run(args)
        _write_json(args.output, evidence)
    except Exception as exc:
        print(f"Agent mock acceptance: FAIL: {exc}", file=os.sys.stderr)
        return 1
    print(f"Agent mock acceptance: PASS ({args.scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
