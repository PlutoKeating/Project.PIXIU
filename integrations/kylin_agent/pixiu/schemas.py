"""OpenAI-compatible tool schemas exposed through MemoryProvider."""

SEARCH = {
    "name": "pixiu_memory_search",
    "description": "Search scoped PIXIU memory with citations before answering.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["query"],
    },
}

REMEMBER = {
    "name": "pixiu_memory_remember",
    "description": "Store an explicit user-approved fact or tool result in PIXIU memory.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "tool_name": {"type": "string"},
        },
        "required": ["content"],
    },
}

UPDATE = {
    "name": "pixiu_memory_update",
    "description": (
        "Update a recalled PIXIU memory when the user supplies corrected information. "
        "Use the knowledge_id and version returned by pixiu_memory_search."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "knowledge_id": {
                "type": "string",
                "pattern": "^knw_[A-Za-z0-9_-]{8,128}$",
            },
            "expected_version": {"type": "integer", "minimum": 1},
            "content": {"type": "string"},
            "title": {"type": "string"},
        },
        "required": ["knowledge_id", "expected_version", "content"],
    },
}

FORGET = {
    "name": "pixiu_memory_forget",
    "description": (
        "Preview a forget request. Execute only after the user explicitly confirms, "
        "by repeating the call with the returned one-time confirmation_token."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "confirmation_token": {"type": "string"},
        },
        "required": ["command"],
    },
}

SYNC_STATUS = {
    "name": "pixiu_sync_status",
    "description": "Read the local PIXIU distributed-memory synchronization status.",
    "parameters": {"type": "object", "properties": {}},
}

ALL = [SEARCH, REMEMBER, UPDATE, FORGET, SYNC_STATUS]
