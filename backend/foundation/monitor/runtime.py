"""Assemble directory watching with the controlled Runtime dreaming service."""
from __future__ import annotations
from typing import Any, Callable
from ..agent_media import AgentMediaClient
from ..documents.access import source_authorized
from .watcher import DirectoryWatcher


async def create_monitor_runtime(
    config_store: Any,
    *,
    debounce_ms: float = 500,
    callbacks: list[Callable[..., Any]] | None = None,
) -> DirectoryWatcher:
    """Return a watcher; every file uses the same authorized dreaming path."""
    capture = AgentMediaClient(
        authorize_source=lambda path: source_authorized(path, config_store.get())
    )
    return DirectoryWatcher(config_store, capture, debounce_ms=debounce_ms, callbacks=callbacks)
