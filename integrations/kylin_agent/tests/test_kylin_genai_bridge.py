import json
import ctypes

from integrations.kylin_agent.kylin_genai_bridge import (
    ModelInfo,
    extract_tool_results,
    initialize_model_session,
    openai_tool_calls,
    sdk_chat_prompt,
    sdk_tool_schema,
    select_cloud_models,
    tool_choice_policy,
)


def test_model_configuration_precedes_sdk_session_initialization():
    calls = []

    class FakeLibrary:
        def chat_model_config_create(self):
            calls.append("create_config")
            return 42

        def chat_model_config_set_deploy_type(self, _config, _deploy_type):
            calls.append("set_deploy_type")

        def chat_model_config_set_stream(self, _config, _stream):
            calls.append("set_stream")

        def chat_model_config_set_name(self, _config, _name):
            calls.append("set_name")

        def genai_text_set_model_config(self, _session, _config):
            calls.append("set_model_config")

        def genai_text_init_session(self, _session):
            calls.append("init_session")
            return 0

    config, error = initialize_model_session(FakeLibrary(), ctypes.c_void_p(7), "qwen")

    assert config.value == 42
    assert error == 0
    assert calls == [
        "create_config",
        "set_deploy_type",
        "set_stream",
        "set_name",
        "set_model_config",
        "init_session",
    ]


def test_only_tool_capable_public_cloud_models_are_agent_candidates():
    models = [
        ModelInfo("local", "端侧", 0, True),
        ModelInfo("qwq", "QwQ", 1, False),
        ModelInfo("deepseek-v3", "DeepSeek V3", 1, True),
        ModelInfo("qwen-plus", "Qwen Plus", 1, True),
    ]

    assert [model.name for model in select_cloud_models(models)] == [
        "deepseek-v3",
        "qwen-plus",
    ]


def test_sdk_tool_callback_is_translated_to_openai_tool_calls():
    payload = json.dumps(
        [
            {
                "name": "pixiu_memory_query",
                "call_id": "call-1",
                "arguments": {"query": "预算"},
            }
        ],
        ensure_ascii=False,
    )

    assert openai_tool_calls(payload) == [
        {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "pixiu_memory_query",
                "arguments": '{"query":"预算"}',
            },
        }
    ]


def test_sdk_registration_receives_named_function_schema():
    function = {
        "name": "pixiu_memory_query",
        "description": "检索记忆",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }

    assert sdk_tool_schema(function) == {
        "name": "pixiu_memory_query",
        "description": "检索记忆",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }


def test_openai_tool_choice_maps_to_sdk_modes():
    assert tool_choice_policy("auto") == (0, "")
    assert tool_choice_policy("none") == (1, "")
    assert tool_choice_policy("required", ["pixiu_memory_query", "other"]) == (
        2,
        "pixiu_memory_query",
    )
    assert tool_choice_policy({"function": {"name": "pixiu_memory_query"}}) == (
        2,
        "pixiu_memory_query",
    )


def test_sdk_prompt_keeps_prior_dialogue_and_uses_latest_user_question():
    system_prompt, question = sdk_chat_prompt(
        [
            {"role": "system", "content": "安全执行工具"},
            {"role": "user", "content": "记住项目名"},
            {"role": "assistant", "content": "项目名是 PIXIU"},
            {"role": "user", "content": "项目名是什么？"},
        ]
    )

    assert question == "项目名是什么？"
    assert '"role":"system","content":"安全执行工具"' in system_prompt
    assert '"role":"assistant","content":"项目名是 PIXIU"' in system_prompt


def test_runtime_tool_messages_are_bound_to_pending_sdk_calls():
    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "pixiu_memory_query", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "content": '{"items":[]}'},
    ]

    calls, results = extract_tool_results(messages, {"call-1"})

    assert calls == ["call-1"]
    assert results == [{"id": "call-1", "content": '{"items":[]}'}]


def test_tool_results_reject_unknown_or_duplicate_call_ids():
    duplicate = [
        {"role": "tool", "tool_call_id": "call-1", "content": "one"},
        {"role": "tool", "tool_call_id": "call-1", "content": "two"},
    ]
    unknown = [{"role": "tool", "tool_call_id": "call-2", "content": "x"}]

    for messages in (duplicate, unknown):
        try:
            extract_tool_results(messages, {"call-1"})
        except ValueError:
            pass
        else:
            raise AssertionError("invalid tool results must fail closed")


def test_abandoned_tool_conversation_is_closed_at_deadline():
    class Conversation:
        closed = False

        def close(self):
            self.closed = True

    conversation = Conversation()
    bridge = __import__(
        "integrations.kylin_agent.kylin_genai_bridge", fromlist=["KylinCloudBridge"]
    ).KylinCloudBridge(object(), timeout=10)
    bridge._pending["call-1"] = conversation
    bridge._pending_until[conversation] = 20

    assert bridge.expire_pending(now=19) == 0
    assert bridge.expire_pending(now=20) == 1
    assert conversation.closed
    assert bridge._pending == {}
