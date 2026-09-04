"""OpenAI-wire adapter for the Kylin GenAI text SDK.

The KylinAgent Runtime speaks the OpenAI chat-completions protocol.  Kylin OS
exposes its system-managed public-cloud models through ``libkysdk-genai-nlp``.
This loopback-only service joins those two stable interfaces without copying a
system credential into PIXIU or bypassing the Runtime's tool/approval loop.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import ctypes.util
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Iterable


LOG = logging.getLogger("pixiu.kylin_genai_bridge")
PUBLIC_CLOUD = 1


@dataclass(frozen=True)
class ModelInfo:
    name: str
    display_name: str
    deploy_type: int
    supports_tool_choice: bool


def select_cloud_models(models: Iterable[ModelInfo]) -> list[ModelInfo]:
    """Return only models that can safely drive the Agent tool loop."""

    return [
        model
        for model in models
        if model.deploy_type == PUBLIC_CLOUD and model.supports_tool_choice
    ]


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def sdk_tool_schema(function: dict[str, Any]) -> dict[str, Any]:
    """Build the parameter schema expected by genai_text_register_tool."""

    parameters = function.get("parameters")
    schema = dict(parameters) if isinstance(parameters, dict) else {"type": "object"}
    description = str(function.get("description") or "").strip()
    if description and "description" not in schema:
        schema["description"] = description
    return schema


def tool_choice_policy(value: Any) -> tuple[int, str]:
    """Translate OpenAI tool_choice to the Kylin SDK mode and optional name."""

    if value == "none":
        return 1, ""
    if value == "required":
        return 2, ""
    if isinstance(value, dict):
        function = value.get("function")
        if isinstance(function, dict):
            return 0, str(function.get("name") or "").strip()
    return 0, ""


def openai_tool_calls(payload: str) -> list[dict[str, Any]]:
    """Translate the SDK tool callback to OpenAI function-call objects."""

    raw = json.loads(payload)
    if not isinstance(raw, list) or not raw:
        raise ValueError("Kylin GenAI returned an invalid tool-call list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Kylin GenAI returned a non-object tool call")
        call_id = str(item.get("call_id") or item.get("id") or "").strip()
        name = str(item.get("tool_name") or item.get("name") or "").strip()
        arguments = item.get("arguments_json", item.get("arguments", {}))
        if not call_id or not name or call_id in seen:
            raise ValueError("Kylin GenAI returned an incomplete or duplicate tool call")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise ValueError("Kylin GenAI returned invalid tool arguments") from exc
        seen.add(call_id)
        result.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": _compact_json(arguments)},
            }
        )
    return result


def extract_tool_results(
    messages: Iterable[dict[str, Any]], pending_call_ids: set[str]
) -> tuple[list[str], list[dict[str, str]]]:
    """Validate and translate Runtime tool messages for SDK continuation."""

    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        call_id = str(message.get("tool_call_id") or message.get("id") or "").strip()
        if call_id not in pending_call_ids or call_id in seen:
            raise ValueError("tool result does not match the pending Kylin GenAI call")
        content = message.get("content", "")
        if not isinstance(content, str):
            content = _compact_json(content)
        seen.add(call_id)
        results.append({"id": call_id, "content": content})
    if seen != pending_call_ids:
        raise ValueError("not all pending Kylin GenAI tool calls have results")
    return [item["id"] for item in results], results


@dataclass
class CompletionOutput:
    model: str
    content: str = ""
    reasoning: str = ""
    finish_reason: str = "stop"
    tool_calls: list[dict[str, Any]] | None = None


class KylinGenAiLibrary:
    """Small, typed ctypes boundary around the public Kylin GenAI C ABI."""

    _RESULT_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)
    _TOOL_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_void_p)

    def __init__(self, library: Any | None = None):
        if library is None:
            soname = ctypes.util.find_library("kysdk-genai-nlp")
            if not soname:
                raise RuntimeError("libkysdk-genai-nlp is not installed")
            library = ctypes.CDLL(soname)
        self.lib = library
        self._bind()

    def _bind(self) -> None:
        pointer = ctypes.c_void_p
        self.lib.genai_text_create_session.restype = pointer
        self.lib.genai_text_init_session.argtypes = [pointer]
        self.lib.genai_text_init_session.restype = ctypes.c_int
        self.lib.genai_text_destroy_session.argtypes = [ctypes.POINTER(pointer)]
        self.lib.genai_text_enable_internal_event_loop.argtypes = [pointer, ctypes.c_bool]
        self.lib.genai_text_result_set_callback.argtypes = [pointer, self._RESULT_CALLBACK, pointer]
        self.lib.genai_text_set_tool_handler.argtypes = [pointer, self._TOOL_CALLBACK, pointer]
        self.lib.genai_text_get_model_list.argtypes = [pointer, ctypes.POINTER(ctypes.c_int)]
        self.lib.genai_text_get_model_list.restype = pointer
        self.lib.genai_text_model_list_get_count.argtypes = [pointer]
        self.lib.genai_text_model_list_get_count.restype = ctypes.c_int
        self.lib.genai_text_model_list_get_model_info.argtypes = [pointer, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.lib.genai_text_model_list_get_model_info.restype = pointer
        for name in ("genai_text_model_info_get_model_name", "genai_text_model_info_get_display_name"):
            function = getattr(self.lib, name)
            function.argtypes = [pointer, ctypes.POINTER(ctypes.c_int)]
            function.restype = ctypes.c_char_p
        self.lib.genai_text_model_info_get_deploy_type.argtypes = [pointer, ctypes.POINTER(ctypes.c_int)]
        self.lib.genai_text_model_info_get_deploy_type.restype = ctypes.c_int
        self.lib.genai_text_model_info_supports_tool_choice.argtypes = [pointer, ctypes.POINTER(ctypes.c_int)]
        self.lib.genai_text_model_info_supports_tool_choice.restype = ctypes.c_bool
        self.lib.chat_model_config_create.restype = pointer
        self.lib.chat_model_config_set_name.argtypes = [pointer, ctypes.c_char_p]
        self.lib.chat_model_config_set_deploy_type.argtypes = [pointer, ctypes.c_int]
        self.lib.chat_model_config_set_stream.argtypes = [pointer, ctypes.c_bool]
        self.lib.chat_model_config_destroy.argtypes = [ctypes.POINTER(pointer)]
        self.lib.genai_text_set_model_config.argtypes = [pointer, pointer]
        self.lib.genai_text_register_tool.argtypes = [pointer, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p]
        self.lib.genai_text_register_tool.restype = ctypes.c_int
        self.lib.genai_text_create_tool_choice_config.argtypes = [ctypes.c_int]
        self.lib.genai_text_create_tool_choice_config.restype = pointer
        self.lib.genai_text_tool_choice_config_set_specific_tool.argtypes = [pointer, ctypes.c_char_p]
        self.lib.genai_text_set_tool_choice_config.argtypes = [pointer, pointer]
        self.lib.genai_text_destroy_tool_choice_config.argtypes = [ctypes.POINTER(pointer)]
        self.lib.chat_message_create.restype = pointer
        self.lib.chat_message_destroy.argtypes = [ctypes.POINTER(pointer)]
        for name in ("chat_message_add_system_message", "chat_message_add_user_message", "chat_message_add_assistant_message"):
            getattr(self.lib, name).argtypes = [pointer, ctypes.c_char_p]
        self.lib.genai_text_chat_with_history_messages_async.argtypes = [pointer, pointer]
        self.lib.genai_text_submit_tool_result.argtypes = [pointer, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.genai_text_submit_tool_result.restype = ctypes.c_int
        self.lib.genai_text_stop_chat.argtypes = [pointer]
        self.lib.chat_result_get_assistant_message.argtypes = [pointer]
        self.lib.chat_result_get_assistant_message.restype = ctypes.c_char_p
        self.lib.chat_result_get_reasoning_message.argtypes = [pointer]
        self.lib.chat_result_get_reasoning_message.restype = ctypes.c_char_p
        self.lib.chat_result_get_model_name.argtypes = [pointer]
        self.lib.chat_result_get_model_name.restype = ctypes.c_char_p
        self.lib.chat_result_get_finish_reason_message.argtypes = [pointer]
        self.lib.chat_result_get_finish_reason_message.restype = ctypes.c_char_p
        self.lib.chat_result_get_error_code.argtypes = [pointer]
        self.lib.chat_result_get_error_code.restype = ctypes.c_int
        self.lib.chat_result_get_error_message.argtypes = [pointer]
        self.lib.chat_result_get_error_message.restype = ctypes.c_char_p
        self.lib.chat_result_get_is_end.argtypes = [pointer]
        self.lib.chat_result_get_is_end.restype = ctypes.c_bool

    @staticmethod
    def _text(value: bytes | None) -> str:
        return value.decode("utf-8", errors="replace") if value else ""

    def models(self) -> list[ModelInfo]:
        session = ctypes.c_void_p(self.lib.genai_text_create_session())
        if not session.value:
            raise RuntimeError("Kylin GenAI could not create a text session")
        try:
            self.lib.genai_text_enable_internal_event_loop(session, True)
            error = self.lib.genai_text_init_session(session)
            if error:
                raise RuntimeError(f"Kylin GenAI session initialization failed ({error})")
            error_code = ctypes.c_int(0)
            model_list = self.lib.genai_text_get_model_list(session, ctypes.byref(error_code))
            if error_code.value or not model_list:
                raise RuntimeError(f"Kylin GenAI model discovery failed ({error_code.value})")
            result = []
            for index in range(self.lib.genai_text_model_list_get_count(model_list)):
                info = self.lib.genai_text_model_list_get_model_info(model_list, index, ctypes.byref(error_code))
                if error_code.value or not info:
                    continue
                result.append(
                    ModelInfo(
                        self._text(self.lib.genai_text_model_info_get_model_name(info, None)),
                        self._text(self.lib.genai_text_model_info_get_display_name(info, None)),
                        int(self.lib.genai_text_model_info_get_deploy_type(info, None)),
                        bool(self.lib.genai_text_model_info_supports_tool_choice(info, None)),
                    )
                )
            return result
        finally:
            self.lib.genai_text_destroy_session(ctypes.byref(session))


class NativeConversation:
    def __init__(self, sdk: KylinGenAiLibrary, model: str, tools: list[dict[str, Any]], tool_choice: Any = "auto"):
        self.sdk = sdk
        self.model = "" if model in {"", "default", "kylin-default"} else model
        self.session = ctypes.c_void_p(sdk.lib.genai_text_create_session())
        self.config = ctypes.c_void_p()
        self.history = ctypes.c_void_p()
        self.event = threading.Event()
        self.output = CompletionOutput(model=model or "kylin-default")
        self.error = ""
        self._closed = False
        self._result_callback = sdk._RESULT_CALLBACK(self._on_result)
        self._tool_callback = sdk._TOOL_CALLBACK(self._on_tools)
        if not self.session.value:
            raise RuntimeError("Kylin GenAI could not create a text session")
        sdk.lib.genai_text_enable_internal_event_loop(self.session, True)
        error = sdk.lib.genai_text_init_session(self.session)
        if error:
            self.close()
            raise RuntimeError(f"Kylin GenAI session initialization failed ({error})")
        self.config = ctypes.c_void_p(sdk.lib.chat_model_config_create())
        sdk.lib.chat_model_config_set_deploy_type(self.config, PUBLIC_CLOUD)
        sdk.lib.chat_model_config_set_stream(self.config, True)
        if self.model:
            sdk.lib.chat_model_config_set_name(self.config, self.model.encode())
        sdk.lib.genai_text_set_model_config(self.session, self.config)
        sdk.lib.genai_text_result_set_callback(self.session, self._result_callback, None)
        sdk.lib.genai_text_set_tool_handler(self.session, self._tool_callback, None)
        for tool in tools:
            function = tool.get("function") if isinstance(tool, dict) else None
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "").strip()
            if not name:
                continue
            status = sdk.lib.genai_text_register_tool(
                self.session, name.encode(), 0, _compact_json(sdk_tool_schema(function)).encode()
            )
            if status:
                self.close()
                raise RuntimeError(f"Kylin GenAI rejected tool {name!r} ({status})")
        if tools:
            mode, specific_tool = tool_choice_policy(tool_choice)
            choice = ctypes.c_void_p(sdk.lib.genai_text_create_tool_choice_config(mode))
            try:
                if specific_tool:
                    sdk.lib.genai_text_tool_choice_config_set_specific_tool(
                        choice, specific_tool.encode()
                    )
                sdk.lib.genai_text_set_tool_choice_config(self.session, choice)
            finally:
                sdk.lib.genai_text_destroy_tool_choice_config(ctypes.byref(choice))

    def _on_result(self, result: int, _user_data: int) -> None:
        error = int(self.sdk.lib.chat_result_get_error_code(result))
        if error:
            message = self.sdk._text(self.sdk.lib.chat_result_get_error_message(result))
            self.error = f"Kylin GenAI request failed ({error}): {message}"
            self.event.set()
            return
        self.output.content += self.sdk._text(self.sdk.lib.chat_result_get_assistant_message(result))
        self.output.reasoning += self.sdk._text(self.sdk.lib.chat_result_get_reasoning_message(result))
        model = self.sdk._text(self.sdk.lib.chat_result_get_model_name(result))
        if model:
            self.output.model = model
        reason = self.sdk._text(self.sdk.lib.chat_result_get_finish_reason_message(result))
        if reason:
            self.output.finish_reason = reason
        if self.sdk.lib.chat_result_get_is_end(result):
            self.event.set()

    def _on_tools(self, payload: bytes, _user_data: int) -> None:
        try:
            self.output.tool_calls = openai_tool_calls(self.sdk._text(payload))
            self.output.finish_reason = "tool_calls"
        except Exception as exc:
            self.error = str(exc)
        self.event.set()

    @staticmethod
    def _message_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict) and part.get("type") in {"text", "input_text"}
            )
        return str(content or "")

    def start(self, messages: Iterable[dict[str, Any]]) -> None:
        self.history = ctypes.c_void_p(self.sdk.lib.chat_message_create())
        for message in messages:
            if not isinstance(message, dict) or message.get("role") == "tool":
                continue
            role = str(message.get("role") or "")
            content = self._message_text(message.get("content"))
            if role in {"system", "developer"}:
                function = self.sdk.lib.chat_message_add_system_message
            elif role == "user":
                function = self.sdk.lib.chat_message_add_user_message
            elif role == "assistant" and not message.get("tool_calls"):
                function = self.sdk.lib.chat_message_add_assistant_message
            else:
                continue
            function(self.history, content.encode())
        self.event.clear()
        self.sdk.lib.genai_text_chat_with_history_messages_async(self.session, self.history)

    def continue_with(self, calls: list[dict[str, Any]], results: list[dict[str, str]]) -> None:
        self.output = CompletionOutput(model=self.output.model)
        self.error = ""
        self.event.clear()
        status = self.sdk.lib.genai_text_submit_tool_result(
            self.session, _compact_json(calls).encode(), _compact_json(results).encode()
        )
        if status:
            raise RuntimeError(f"Kylin GenAI rejected tool results ({status})")

    def wait(self, timeout: float) -> CompletionOutput:
        if not self.event.wait(timeout):
            self.sdk.lib.genai_text_stop_chat(self.session)
            raise TimeoutError("Kylin GenAI request timed out")
        if self.error:
            raise RuntimeError(self.error)
        return self.output

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.history.value:
            self.sdk.lib.chat_message_destroy(ctypes.byref(self.history))
        if self.config.value:
            self.sdk.lib.chat_model_config_destroy(ctypes.byref(self.config))
        if self.session.value:
            self.sdk.lib.genai_text_destroy_session(ctypes.byref(self.session))


class KylinCloudBridge:
    def __init__(self, sdk: KylinGenAiLibrary, timeout: float = 180.0):
        self.sdk = sdk
        self.timeout = timeout
        self._lock = threading.Lock()
        self._pending: dict[str, NativeConversation] = {}
        self._pending_until: dict[NativeConversation, float] = {}

    def _remove_locked(self, conversation: NativeConversation) -> None:
        for call_id, owner in list(self._pending.items()):
            if owner is conversation:
                self._pending.pop(call_id, None)
        self._pending_until.pop(conversation, None)

    def expire_pending(self, now: float | None = None) -> int:
        """Close abandoned tool conversations after one request timeout."""

        current = time.monotonic() if now is None else now
        with self._lock:
            expired = [
                conversation
                for conversation, deadline in self._pending_until.items()
                if deadline <= current
            ]
            for conversation in expired:
                self._remove_locked(conversation)
        for conversation in expired:
            conversation.close()
        return len(expired)

    def models(self) -> list[ModelInfo]:
        return select_cloud_models(self.sdk.models())

    def complete(self, body: dict[str, Any]) -> CompletionOutput:
        self.expire_pending()
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages array is required")
        tool_ids = {
            str(item.get("tool_call_id") or item.get("id") or "").strip()
            for item in messages
            if isinstance(item, dict) and item.get("role") == "tool"
        }
        tool_ids.discard("")
        conversation: NativeConversation
        if tool_ids:
            with self._lock:
                conversations = {self._pending.get(call_id) for call_id in tool_ids}
            if None in conversations or len(conversations) != 1:
                raise ValueError("tool results do not match one pending Kylin GenAI request")
            conversation = conversations.pop()  # type: ignore[assignment]
            pending_ids = {
                item["id"] for item in conversation.output.tool_calls or []
            }
            _, results = extract_tool_results(messages, pending_ids)
            conversation.continue_with(conversation.output.tool_calls or [], results)
        else:
            conversation = NativeConversation(
                self.sdk,
                str(body.get("model") or "kylin-default"),
                body.get("tools") if isinstance(body.get("tools"), list) else [],
                body.get("tool_choice", "auto"),
            )
            conversation.start(messages)
        try:
            output = conversation.wait(self.timeout)
        except Exception:
            with self._lock:
                self._remove_locked(conversation)
            conversation.close()
            raise
        with self._lock:
            self._remove_locked(conversation)
            if output.tool_calls:
                for call in output.tool_calls:
                    self._pending[call["id"]] = conversation
                self._pending_until[conversation] = time.monotonic() + self.timeout
            else:
                conversation.close()
        return output


def _response_payload(output: CompletionOutput, completion_id: str) -> dict[str, Any]:
    message: dict[str, Any] = {"role": "assistant", "content": output.content or None}
    if output.tool_calls:
        message["tool_calls"] = output.tool_calls
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": output.model,
        "choices": [{"index": 0, "message": message, "finish_reason": output.finish_reason}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def create_app(bridge: KylinCloudBridge):
    from aiohttp import web

    async def health(_request):
        try:
            models = await asyncio.to_thread(bridge.models)
            return web.json_response({"status": "ready", "provider": "kylin-genai", "model_count": len(models)})
        except Exception as exc:
            return web.json_response({"status": "unavailable", "error": str(exc)}, status=503)

    async def models(_request):
        try:
            available = await asyncio.to_thread(bridge.models)
            return web.json_response(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": model.name,
                            "object": "model",
                            "owned_by": "kylin-genai",
                            "display_name": model.display_name,
                        }
                        for model in available
                    ],
                }
            )
        except Exception as exc:
            return web.json_response({"error": {"message": str(exc), "type": "sdk_unavailable"}}, status=503)

    async def completions(request):
        try:
            body = await request.json()
            output = await asyncio.to_thread(bridge.complete, body)
        except ValueError as exc:
            return web.json_response({"error": {"message": str(exc), "type": "invalid_request_error"}}, status=400)
        except Exception as exc:
            LOG.exception("Kylin GenAI completion failed")
            return web.json_response({"error": {"message": str(exc), "type": "kylin_genai_error"}}, status=502)
        completion_id = f"chatcmpl-kylin-{uuid.uuid4().hex}"
        payload = _response_payload(output, completion_id)
        if not body.get("stream"):
            return web.json_response(payload)
        response = web.StreamResponse(status=200, headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        message = payload["choices"][0]["message"]
        delta = dict(message)
        delta.pop("role", None)
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": payload["created"],
            "model": output.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": output.finish_reason}],
        }
        await response.write(f"data: {_compact_json(chunk)}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
        return response

    app = web.Application(client_max_size=4 * 1024 * 1024)
    app.router.add_get("/health", health)
    app.router.add_get("/v1/models", models)
    app.router.add_post("/v1/chat/completions", completions)
    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PIXIU Kylin GenAI loopback bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args(argv)
    if args.host not in {"127.0.0.1", "::1"}:
        parser.error("the Kylin GenAI bridge is loopback-only")
    logging.basicConfig(level=logging.INFO)
    from aiohttp import web

    bridge = KylinCloudBridge(KylinGenAiLibrary(), timeout=args.timeout)
    web.run_app(create_app(bridge), host=args.host, port=args.port, access_log=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
