#!/usr/bin/env python3
"""Capture fail-closed, payload-free evidence from the real Agent Gateway."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


EVIDENCE_CLASS = "kylin-v11-agent-lifecycle"
STATE_CLASS = "kylin-v11-agent-lifecycle-capture-state"
COMMIT = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
REQUIRED_CHECKS = {
    "three_turn_session",
    "session_restore",
    "autonomous_memory_read",
    "autonomous_memory_write",
    "shell_tool",
    "web_search_tool",
    "approval",
    "tool_result_persisted",
    "cross_session_recall",
}
FORBIDDEN_PROMPT_TOKENS = {
    "pixiu_memory_search",
    "pixiu_memory_remember",
    "pixiu_memory_update",
    "pixiu_memory_forget",
    "pixiu_sync_status",
    "web_search",
    "terminal",
}
ARTIFACT_PLACEHOLDER = "{{ARTIFACT_PATH}}"


class EvidenceError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError("input is not readable JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError("input JSON must be an object")
    return value


def _write_json(path: Path, value: dict[str, Any], *, overwrite: bool = False) -> None:
    path = path.resolve()
    if path.exists() and not overwrite:
        raise EvidenceError("output already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError("input file is not readable") from exc
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_loopback_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise EvidenceError("Agent Gateway must be an HTTP loopback URL")
    return value.rstrip("/")


def validate_scenario(value: dict[str, Any]) -> dict[str, Any]:
    turns = value.get("turns")
    prompts = list(turns) if isinstance(turns, list) else []
    prompts.extend([value.get("restore_prompt"), value.get("cross_session_prompt")])
    if (
        value.get("schema_version") != 1
        or not isinstance(turns, list)
        or len(turns) != 3
        or not all(isinstance(item, str) and 10 <= len(item.strip()) <= 2000 for item in prompts)
        or sum(ARTIFACT_PLACEHOLDER in item for item in turns) != 1
        or ARTIFACT_PLACEHOLDER in value["restore_prompt"]
        or ARTIFACT_PLACEHOLDER in value["cross_session_prompt"]
    ):
        raise EvidenceError("scenario does not satisfy the controlled lifecycle schema")
    lowered = "\n".join(prompts).lower()
    if any(token in lowered for token in FORBIDDEN_PROMPT_TOKENS):
        raise EvidenceError("scenario names an implementation tool and cannot prove autonomous selection")
    return value


def host_process_identity() -> str:
    try:
        result = subprocess.run(
            ["pgrep", "-x", "kylin-agent"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceError("the Kylin Agent desktop host is not running") from exc
    pids = [line.strip() for line in result.stdout.splitlines() if line.strip().isdigit()]
    if len(pids) != 1:
        raise EvidenceError("exactly one Kylin Agent desktop host process is required")
    return _digest(f"kylin-agent-process:{pids[0]}")


def validate_native_evidence(value: dict[str, Any]) -> dict[str, str]:
    release = value.get("release")
    candidate = value.get("candidate_package")
    checks = value.get("checks")
    capabilities = value.get("capabilities")
    agent_host = value.get("agent_host")
    agent_runtime = value.get("agent_runtime")
    if not all(
        isinstance(item, dict)
        for item in (release, candidate, checks, capabilities, agent_host, agent_runtime)
    ):
        raise EvidenceError("native evidence is incomplete")
    platform = capabilities.get("platform")
    embedding = capabilities.get("embedding")
    vector_store = capabilities.get("vector_store")
    commit = release.get("git_commit")
    package_sha = candidate.get("sha256")
    required = {"contest_ready", "memory_write", "vector_search", "vector_delete", "deleted_memory_hidden"}
    if not (
        value.get("evidence_class") == "kylin-v11-native-sdk-product-lifecycle"
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and isinstance(commit, str) and COMMIT.fullmatch(commit)
        and isinstance(package_sha, str) and SHA256.fullmatch(package_sha)
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and capabilities.get("contest_ready") is True
        and isinstance(platform, dict)
        and platform.get("family") == "kylin"
        and platform.get("version_major") == "11"
        and platform.get("v11") is True
        and all(
            isinstance(runtime, dict)
            and runtime.get("configured") == "kylin"
            and runtime.get("runtime") == "kylin"
            and runtime.get("compliant") is True
            for runtime in (embedding, vector_store)
        )
        and agent_host.get("available") is True
        and isinstance(agent_runtime.get("version"), str)
        and re.fullmatch(r"0\.9\.[0-9]+", agent_runtime["version"])
        and isinstance(checks, dict)
        and all(checks.get(name) == "passed" for name in required)
    ):
        raise EvidenceError("native evidence is not a passing strict Kylin V11 lifecycle")
    return {"git_commit": commit, "candidate_package_sha256": package_sha}


class AgentClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: int = 600) -> None:
        self.base_url = validate_loopback_url(base_url)
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None):
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            return urllib.request.urlopen(request, timeout=self.timeout)
        except (OSError, urllib.error.HTTPError) as exc:
            raise EvidenceError("Agent Gateway request failed") from exc

    def json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        with self._request(method, path, payload) as response:
            try:
                return json.load(response)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise EvidenceError("Agent Gateway returned invalid JSON") from exc

    def runtime_identity(self) -> str:
        value = self.json("GET", "/health/detailed")
        if not isinstance(value, dict) or value.get("status") != "ok" or not isinstance(value.get("pid"), int):
            raise EvidenceError("Agent Gateway detailed health lacks a process identity")
        return _digest(f"agent-runtime-process:{value['pid']}")

    def validate_capabilities(self) -> None:
        value = self.json("GET", "/v1/capabilities")
        features = value.get("features") if isinstance(value, dict) else None
        runtime = value.get("runtime") if isinstance(value, dict) else None
        required = {"run_submission", "run_status", "run_events_sse", "run_approval_response", "tool_progress_events", "approval_events"}
        if not (
            isinstance(features, dict)
            and all(features.get(name) is True for name in required)
            and isinstance(runtime, dict)
            and runtime.get("mode") == "server_agent"
            and runtime.get("tool_execution") == "server"
        ):
            raise EvidenceError("Agent Gateway lacks the required server-side lifecycle contract")

    def create_session(self, session_id: str) -> None:
        value = self.json("POST", "/api/sessions", {"id": session_id, "source": "desktop", "title": "PIXIU acceptance"})
        if not isinstance(value, dict) or value.get("id") != session_id:
            raise EvidenceError("Agent session creation failed")

    def messages(self, session_id: str) -> list[dict[str, Any]]:
        value = self.json("GET", f"/api/sessions/{urllib.parse.quote(session_id, safe='')}/messages")
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise EvidenceError("Agent session messages are invalid")
        return value

    def run(self, session_id: str, prompt: str, approve: Callable[[str], bool]) -> dict[str, Any]:
        started = self.json("POST", "/v1/runs", {"input": prompt, "session_id": session_id})
        run_id = started.get("run_id") if isinstance(started, dict) else None
        if not isinstance(run_id, str) or not re.fullmatch(r"run_[0-9a-f]{32}", run_id):
            raise EvidenceError("Agent Gateway did not return a valid run id")
        tools_started: list[str] = []
        tools_completed: list[str] = []
        approvals = 0
        output = ""
        with self._request("GET", f"/v1/runs/{run_id}/events") as response:
            for raw in response:
                line = raw.decode("utf-8", errors="strict").strip()
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError as exc:
                    raise EvidenceError("Agent SSE stream contains invalid JSON") from exc
                if not isinstance(event, dict):
                    raise EvidenceError("Agent SSE event is not an object")
                kind = event.get("event")
                if kind == "tool.started" and isinstance(event.get("tool"), str):
                    tools_started.append(event["tool"])
                elif kind == "tool.completed" and isinstance(event.get("tool"), str):
                    if bool(event.get("error")):
                        raise EvidenceError("Agent tool execution failed")
                    tools_completed.append(event["tool"])
                elif kind == "approval.request":
                    if not approve(run_id):
                        raise EvidenceError("operator did not explicitly approve the Agent action")
                    result = self.json("POST", f"/v1/runs/{run_id}/approval", {"choice": "once"})
                    if not isinstance(result, dict) or result.get("choice") != "once" or result.get("resolved", 0) < 1:
                        raise EvidenceError("Agent approval was not resolved")
                    approvals += 1
                elif kind == "run.completed":
                    output = str(event.get("output") or "")
                elif kind in {"run.failed", "run.cancelled"}:
                    raise EvidenceError("Agent run did not complete")
        status = self.json("GET", f"/v1/runs/{run_id}")
        if not isinstance(status, dict) or status.get("status") != "completed":
            raise EvidenceError("Agent run has no completed terminal status")
        if sorted(tools_started) != sorted(tools_completed):
            raise EvidenceError("Agent tool start/completion events are inconsistent")
        return {"run_id_digest": _digest(run_id), "tools": tools_completed, "approvals": approvals, "output": output}


def _message_fingerprints(messages: list[dict[str, Any]]) -> list[str]:
    result = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            result.append(_digest(f"{role}\0{content}"))
    return result


def _interactive_approval(run_id: str) -> bool:
    expected = f"APPROVE {run_id}"
    print("Agent 请求执行受控操作。请在独立界面核对动作；同意仅本次执行时输入：")
    return getpass.getpass(f"{expected}\n> ") == expected


def capture_before(
    client: AgentClient,
    native: dict[str, Any],
    scenario: dict[str, Any],
    approve,
    *,
    host_identity: str | None = None,
) -> dict[str, Any]:
    client.validate_capabilities()
    session_id = f"pixiu-acceptance-{uuid.uuid4()}"
    client.create_session(session_id)
    marker = f"PIXIU-{uuid.uuid4().hex.upper()}"
    artifact_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", prefix="pixiu-agent-evidence-", suffix=".txt", delete=False
        ) as stream:
            stream.write(marker + "\n")
            artifact_path = Path(stream.name)
        os.chmod(artifact_path, 0o600)
        turns = [prompt.replace(ARTIFACT_PLACEHOLDER, str(artifact_path)) for prompt in scenario["turns"]]
        runs = [client.run(session_id, prompt, approve) for prompt in turns]
    finally:
        if artifact_path is not None:
            artifact_path.unlink(missing_ok=True)
    messages = client.messages(session_id)
    tools = [tool for run in runs for tool in run["tools"]]
    positions = {name: [i for i, tool in enumerate(tools) if tool == name] for name in set(tools)}
    prior_value_tools = positions.get("terminal", []) + positions.get("web_search", [])
    remember_positions = positions.get("pixiu_memory_remember", [])
    if not (
        all(name in tools for name in ("terminal", "web_search", "pixiu_memory_remember"))
        and sum(run["approvals"] for run in runs) >= 1
        and prior_value_tools and remember_positions
        and max(prior_value_tools) < max(remember_positions)
        and len(_message_fingerprints(messages)) >= 6
    ):
        observed_tools = ",".join(tools) if tools else "none"
        raise EvidenceError(
            "first phase did not exercise the required autonomous Agent lifecycle "
            f"(tools={observed_tools}; approvals={sum(run['approvals'] for run in runs)}; "
            f"messages={len(_message_fingerprints(messages))})"
        )
    return {
        "state_schema": 1,
        "state_class": STATE_CLASS,
        "captured_at": _utc_now(),
        "release": native,
        "session_id": session_id,
        "session_id_digest": _digest(session_id),
        "runtime_identity": client.runtime_identity(),
        "host_identity": host_identity or host_process_identity(),
        "memory_marker": marker,
        "message_fingerprints": _message_fingerprints(messages),
        "run_id_digests": [run["run_id_digest"] for run in runs],
        "tool_sequence": tools,
        "approval_count": sum(run["approvals"] for run in runs),
    }


def capture_after(
    client: AgentClient,
    state: dict[str, Any],
    scenario: dict[str, Any],
    approve,
    *,
    host_identity: str | None = None,
) -> dict[str, Any]:
    if state.get("state_class") != STATE_CLASS or state.get("state_schema") != 1:
        raise EvidenceError("capture state is invalid")
    client.validate_capabilities()
    new_identity = client.runtime_identity()
    if new_identity == state.get("runtime_identity"):
        raise EvidenceError("Agent Runtime was not restarted between capture phases")
    new_host_identity = host_identity or host_process_identity()
    if new_host_identity == state.get("host_identity"):
        raise EvidenceError("Kylin Agent desktop host was not restarted between capture phases")
    session_id = state.get("session_id")
    if not isinstance(session_id, str):
        raise EvidenceError("capture state lacks the session id")
    restored = _message_fingerprints(client.messages(session_id))
    before = state.get("message_fingerprints")
    if not isinstance(before, list) or restored[: len(before)] != before:
        raise EvidenceError("pre-restart Agent session was not restored intact")
    restore_run = client.run(session_id, scenario["restore_prompt"], approve)
    cross_session_id = f"pixiu-recall-{uuid.uuid4()}"
    client.create_session(cross_session_id)
    recall_run = client.run(cross_session_id, scenario["cross_session_prompt"], approve)
    marker = state.get("memory_marker")
    if not (
        isinstance(marker, str)
        and "pixiu_memory_search" in recall_run["tools"]
        and marker in recall_run["output"]
        and len(_message_fingerprints(client.messages(session_id))) >= len(before) + 2
    ):
        raise EvidenceError("post-restart cross-session memory recall was not proven")
    checks = {name: "passed" for name in sorted(REQUIRED_CHECKS)}
    return {
        "evidence_schema": 1,
        "evidence_class": EVIDENCE_CLASS,
        "real_device_evidence": True,
        "status": "pass",
        "captured_at": _utc_now(),
        "release": state["release"],
        "checks": checks,
        "sessions": {
            "primary_digest": state["session_id_digest"],
            "cross_session_digest": _digest(cross_session_id),
            "distinct_sessions": True,
            "pre_restart_message_count": len(before),
            "post_restart_message_count": len(_message_fingerprints(client.messages(session_id))),
        },
        "runtime": {
            "pre_restart_identity_digest": state["runtime_identity"],
            "post_restart_identity_digest": new_identity,
            "process_changed": True,
            "pre_restart_host_identity_digest": state["host_identity"],
            "post_restart_host_identity_digest": new_host_identity,
            "host_process_changed": True,
        },
        "runs": {
            "three_turn_count": len(state["run_id_digests"]),
            "restore_run_digest": restore_run["run_id_digest"],
            "recall_run_digest": recall_run["run_id_digest"],
        },
        "observations": {
            "tool_names": sorted(set(state["tool_sequence"] + restore_run["tools"] + recall_run["tools"])),
            "approval_count": state["approval_count"] + restore_run["approvals"] + recall_run["approvals"],
            "memory_marker_sha256": _digest(marker),
            "payloads_retained": False,
        },
    }


def validate_final(value: dict[str, Any]) -> None:
    release = value.get("release")
    checks = value.get("checks")
    sessions = value.get("sessions")
    runtime = value.get("runtime")
    observations = value.get("observations")
    runs = value.get("runs")
    if not all(isinstance(item, dict) for item in (release, checks, sessions, runtime, observations, runs)):
        raise EvidenceError("Agent lifecycle evidence is incomplete")
    digest_fields = (
        sessions.get("primary_digest"),
        sessions.get("cross_session_digest"),
        runtime.get("pre_restart_identity_digest"),
        runtime.get("post_restart_identity_digest"),
        runtime.get("pre_restart_host_identity_digest"),
        runtime.get("post_restart_host_identity_digest"),
        runs.get("restore_run_digest"),
        runs.get("recall_run_digest"),
        observations.get("memory_marker_sha256"),
    )
    if not (
        value.get("evidence_schema") == 1
        and value.get("evidence_class") == EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and isinstance(release.get("git_commit"), str) and COMMIT.fullmatch(release["git_commit"])
        and isinstance(release.get("candidate_package_sha256"), str) and SHA256.fullmatch(release["candidate_package_sha256"])
        and isinstance(release.get("native_evidence_sha256"), str) and SHA256.fullmatch(release["native_evidence_sha256"])
        and set(checks) == REQUIRED_CHECKS
        and all(checks[name] == "passed" for name in REQUIRED_CHECKS)
        and all(isinstance(item, str) and SHA256.fullmatch(item) for item in digest_fields)
        and sessions.get("distinct_sessions") is True
        and sessions.get("pre_restart_message_count", 0) >= 6
        and sessions.get("post_restart_message_count", 0) >= sessions.get("pre_restart_message_count", 0) + 2
        and runtime.get("process_changed") is True
        and runtime.get("host_process_changed") is True
        and runtime.get("pre_restart_identity_digest") != runtime.get("post_restart_identity_digest")
        and runtime.get("pre_restart_host_identity_digest") != runtime.get("post_restart_host_identity_digest")
        and runs.get("three_turn_count") == 3
        and observations.get("payloads_retained") is False
        and isinstance(observations.get("tool_names"), list)
        and {"terminal", "web_search", "pixiu_memory_remember", "pixiu_memory_search"}.issubset(observations["tool_names"])
        and observations.get("approval_count", 0) >= 1
    ):
        raise EvidenceError("Agent lifecycle evidence does not pass the final contract")


def _client(args: argparse.Namespace) -> AgentClient:
    api_key = os.environ.get(args.api_key_env, "")
    return AgentClient(args.agent_url, api_key=api_key, timeout=args.timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("before-restart", "after-restart", "validate"))
    parser.add_argument("--agent-url", default="http://127.0.0.1:8642")
    parser.add_argument("--api-key-env", default="KYLIN_AGENT_API_KEY")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--native-evidence", type=Path)
    parser.add_argument("--scenario", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        if args.phase == "validate":
            if args.output is None:
                raise EvidenceError("--output is required")
            validate_final(_read_json(args.output))
            print("Agent lifecycle evidence: PASS")
            return 0
        if args.scenario is None or args.state is None:
            raise EvidenceError("--scenario and --state are required")
        scenario = validate_scenario(_read_json(args.scenario))
        client = _client(args)
        if args.phase == "before-restart":
            if args.native_evidence is None:
                raise EvidenceError("--native-evidence is required before restart")
            native = validate_native_evidence(_read_json(args.native_evidence))
            native["native_evidence_sha256"] = _file_sha256(args.native_evidence)
            state = capture_before(client, native, scenario, _interactive_approval)
            _write_json(args.state, state, overwrite=args.overwrite)
            print("First phase captured. Restart the Agent host and Runtime, then run after-restart.")
        else:
            if args.output is None:
                raise EvidenceError("--output is required after restart")
            evidence = capture_after(client, _read_json(args.state), scenario, _interactive_approval)
            validate_final(evidence)
            _write_json(args.output, evidence, overwrite=args.overwrite)
            print("Agent lifecycle evidence: PASS")
        return 0
    except EvidenceError as exc:
        print(f"Agent lifecycle evidence: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
