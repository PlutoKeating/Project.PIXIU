#!/usr/bin/env python3
"""Deterministic OpenAI-compatible node for PIXIU end-to-end tests.

This process performs no inference. It selects responses from observable
conversation state so the real Agent Runtime, tool dispatcher, persistence,
and PIXIU provider can be exercised without sending test data to a vendor.
Raw prompts, tool results, and credentials remain in memory and are never
returned by the trace endpoint or written by this process.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import signal
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


MODEL_ID = "pixiu-e2e-mock"
GATEWAY_MODEL_ID = "hermes-agent"
DESKTOP_MODEL_ID = "deepseek-chat"
MARKER = re.compile(r"PIXIU-[A-F0-9]{16,64}")
SAFE_ARTIFACT = re.compile(r"/(?:tmp|run/user/[0-9]+)/[A-Za-z0-9._/-]+")
PIXIU_PROMPT_TOOLS = {
    "pixiu_memory_search",
    "pixiu_memory_remember",
    "pixiu_memory_update",
    "pixiu_memory_forget",
}
PIXIU_TOOL_REQUIRED_PROPERTIES = {
    "pixiu_memory_search": {"query", "top_k"},
    "pixiu_memory_remember": {"content", "tool_name"},
    "pixiu_memory_update": {"knowledge_id", "expected_version", "content", "title"},
    "pixiu_memory_forget": {"command", "confirmation_token"},
    "pixiu_sync_status": set(),
}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    return ""


def _tool_names(payload: dict[str, Any]) -> set[str]:
    result = set()
    for item in payload.get("tools") or []:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if item.get("type") == "function" else item
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            result.add(function["name"])
    return result


def _tool_schema_contract(payload: dict[str, Any]) -> bool:
    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools:
        return False
    for item in tools:
        if not isinstance(item, dict):
            return False
        function = item.get("function") if item.get("type") == "function" else item
        if not isinstance(function, dict) or not isinstance(function.get("name"), str):
            return False
        parameters = function.get("parameters")
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            return False
        if "properties" in parameters and not isinstance(parameters["properties"], dict):
            return False
    return True


def _pixiu_tool_schema_contract(payload: dict[str, Any]) -> bool:
    schemas: dict[str, dict[str, Any]] = {}
    for item in payload.get("tools") or []:
        if not isinstance(item, dict):
            continue
        function = item.get("function") if item.get("type") == "function" else item
        if isinstance(function, dict) and isinstance(function.get("name"), str):
            schemas[function["name"]] = function
    if not PIXIU_TOOL_REQUIRED_PROPERTIES.keys() <= schemas.keys():
        return False
    for name, required_properties in PIXIU_TOOL_REQUIRED_PROPERTIES.items():
        parameters = schemas[name].get("parameters")
        properties = parameters.get("properties") if isinstance(parameters, dict) else None
        if not isinstance(properties, dict) or not required_properties <= properties.keys():
            return False
    return True


def _latest_user(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return _text(message.get("content"))
    return ""


def _last_tool_name(messages: list[dict[str, Any]]) -> str:
    if not messages or messages[-1].get("role") != "tool":
        return ""
    name = messages[-1].get("name") or messages[-1].get("tool_name")
    if isinstance(name, str) and name:
        return name
    call_id = messages[-1].get("tool_call_id")
    for message in reversed(messages[:-1]):
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict) and call.get("id") == call_id:
                function = call.get("function") or {}
                return str(function.get("name") or "")
    return ""


def _find_marker(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        match = MARKER.search(_text(message.get("content")))
        if match:
            return match.group(0)
    return ""


def _find_knowledge(messages: list[dict[str, Any]]) -> tuple[str, int]:
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        content = _text(message.get("content"))
        id_match = re.search(r"knw_[A-Za-z0-9_-]{8,128}", content)
        version_match = re.search(r'(?i)["\']?version["\']?\s*[:=]\s*(\d+)', content)
        if id_match:
            return id_match.group(0), int(version_match.group(1)) if version_match else 1
    return "", 1


def _tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "call_" + uuid.uuid4().hex,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def _choose(payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | str]:
    messages = [item for item in payload.get("messages") or [] if isinstance(item, dict)]
    available = _tool_names(payload)
    user = _latest_user(messages)
    tool = _last_tool_name(messages)
    marker = _find_marker(messages)

    if tool == "terminal":
        return None, f"已读取并清理临时验收文件；随机标记为 {marker or '未识别'}。"
    if tool == "web_search":
        content = (
            "openKylin 是面向开源桌面操作系统生态的项目；"
            f"本次验收随机标记为 {marker or '未识别'}。"
        )
        return "pixiu_memory_remember", {"content": content, "tool_name": "web_search"}
    if tool == "pixiu_memory_remember":
        return None, "已将经工具验证的信息保存为长期记忆。"
    if tool == "pixiu_memory_update":
        return None, "已完成记忆版本更新。"
    if tool == "pixiu_sync_status":
        return None, "已核对共享记忆同步状态。"
    if tool == "pixiu_memory_search":
        if any(word in user for word in ("更正", "更新", "改为")):
            knowledge_id, version = _find_knowledge(messages)
            return "pixiu_memory_update", {
                "knowledge_id": knowledge_id or "knw_mock_missing",
                "expected_version": version,
                "content": user,
                "title": "用户确认的记忆更正",
            }
        return None, marker or "未找到验收随机标记"

    if "系统命令读取文件" in user:
        paths = SAFE_ARTIFACT.findall(user)
        if not paths:
            return None, "未找到受控临时文件路径。"
        path = paths[-1].rstrip("。；，,;")
        command = f"cat -- {shlex.quote(path)} && rm -- {shlex.quote(path)}"
        return "terminal", {"command": command, "timeout": 30}
    if "联网查询" in user or "在线查询" in user:
        return "web_search", {"query": "site:openkylin.top openKylin 项目简介", "limit": 3}
    if "同步状态" in user:
        return "pixiu_sync_status", {}
    if any(word in user for word in ("更正", "更新", "改为")):
        return "pixiu_memory_search", {"query": marker or user, "top_k": 5}
    if any(word in user for word in ("全新会话", "找回", "查找", "检索")):
        return "pixiu_memory_search", {"query": marker or user, "top_k": 5}
    if "记住" in user or "保存" in user:
        return "pixiu_memory_remember", {"content": user}
    if "恢复" in user or "概括" in user:
        return None, "此前完成了偏好保存、受控系统命令以及联网检索与长期记忆沉淀。"
    return None, "已理解本轮内容，并保留当前会话上下文。"


class State:
    def __init__(self, api_key: str, trace_file: Path | None = None) -> None:
        self.api_key = api_key
        self.trace_file = trace_file
        self.requests: list[dict[str, Any]] = []

    def record(self, payload: dict[str, Any], selected_tool: str | None) -> None:
        messages = [item for item in payload.get("messages") or [] if isinstance(item, dict)]
        systems = [_text(item.get("content")) for item in messages if item.get("role") == "system"]
        combined_system = "\n".join(systems)
        tools = payload.get("tools") or []
        self.requests.append(
            {
                "request_index": len(self.requests) + 1,
                "model": str(payload.get("model") or ""),
                "message_count": len(messages),
                "message_roles": [str(item.get("role") or "") for item in messages],
                "system_message_count": len(systems),
                "system_prompt_sha256": _digest(combined_system),
                "system_prompt_nonempty": any(item.strip() for item in systems),
                "pixiu_prompt_contract": all(
                    name in combined_system for name in PIXIU_PROMPT_TOOLS
                ),
                "user_turn_count": sum(item.get("role") == "user" for item in messages),
                "user_message_sha256": [
                    _digest(_text(item.get("content")))
                    for item in messages
                    if item.get("role") == "user"
                ],
                "assistant_turn_count": sum(item.get("role") == "assistant" for item in messages),
                "assistant_nonempty_count": sum(
                    item.get("role") == "assistant" and bool(_text(item.get("content")).strip())
                    for item in messages
                ),
                "tool_result_count": sum(item.get("role") == "tool" for item in messages),
                "available_tools": sorted(_tool_names(payload)),
                "tool_schema_valid": _tool_schema_contract(payload),
                "pixiu_tool_schema_contract": _pixiu_tool_schema_contract(payload),
                "tool_schema_sha256": _digest(
                    json.dumps(tools, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                ),
                "selected_tool": selected_tool,
            }
        )
        if self.trace_file is not None:
            value = {
                "schema_version": 1,
                "mode": "deterministic-no-inference",
                "raw_payloads_retained": False,
                "requests": self.requests,
            }
            self.trace_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.trace_file.with_name(self.trace_file.name + ".tmp")
            temporary.write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.trace_file)


class Handler(BaseHTTPRequestHandler):
    server_version = "PIXIUMock/1"

    @property
    def state(self) -> State:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _authorized(self) -> bool:
        expected = "Bearer " + self.state.api_key
        return self.headers.get("Authorization", "") == expected

    def _json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": {"message": "unauthorized"}})
            return
        if self.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "mode": "deterministic-no-inference"})
        elif self.path == "/v1/models":
            self._json(
                HTTPStatus.OK,
                {
                    "object": "list",
                    "data": [{"id": MODEL_ID, "object": "model", "owned_by": "pixiu-test"}],
                },
            )
        elif self.path == "/_test/trace":
            self._json(
                HTTPStatus.OK,
                {
                    "schema_version": 1,
                    "mode": "deterministic-no-inference",
                    "raw_payloads_retained": False,
                    "requests": self.state.requests,
                },
            )
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": {"message": "unauthorized"}})
            return
        if self.path != "/v1/chat/completions":
            self._json(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": {"message": "invalid JSON"}})
            return
        requested_model = payload.get("model") if isinstance(payload, dict) else None
        if requested_model not in {MODEL_ID, GATEWAY_MODEL_ID, DESKTOP_MODEL_ID}:
            self._json(HTTPStatus.BAD_REQUEST, {"error": {"message": "unsupported model"}})
            return

        selected_tool, value = _choose(payload)
        available = _tool_names(payload)
        if selected_tool and selected_tool not in available:
            selected_tool = None
            value = "所需工具未由 Agent Runtime 提供。"
        self.state.record(payload, selected_tool)
        tool_calls = [_tool_call(selected_tool, value)] if selected_tool else None
        content = None if selected_tool else str(value)
        finish_reason = "tool_calls" if selected_tool else "stop"
        completion_id = "chatcmpl-" + uuid.uuid4().hex
        created = int(time.time())

        if not payload.get("stream"):
            self._json(
                HTTPStatus.OK,
                {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content,
                                "tool_calls": tool_calls,
                            },
                            "finish_reason": finish_reason,
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                },
            )
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        delta: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            delta["tool_calls"] = [{"index": 0, **tool_calls[0]}]
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": requested_model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        usage = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": requested_model,
            "choices": [],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        for item in (chunk, usage):
            self.wfile.write(b"data: " + json.dumps(item, ensure_ascii=False).encode("utf-8") + b"\n\n")
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18081)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--trace-file", type=Path)
    args = parser.parse_args()
    if not args.api_key.strip():
        parser.error("--api-key must be non-empty")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.state = State(args.api_key, args.trace_file)  # type: ignore[attr-defined]
    if args.ready_file:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text(
            json.dumps({"base_url": f"http://{args.host}:{server.server_port}"}) + "\n",
            encoding="utf-8",
        )
    def stop_from_signal(*_args: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_from_signal)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
