"""User-selected Agent read spaces and default destination for explicit memories."""
from __future__ import annotations

import time
from pydantic import BaseModel, Field, field_validator
from .core.idgen import gen_pref_id
from .core.models import Preference, PreferenceCategory, validate_scope


class AgentMemorySettings(BaseModel):
    include_capture: bool = True
    shared_scopes: list[str] = Field(default_factory=list, max_length=10)
    write_scope: str | None = None

    @field_validator('shared_scopes')
    @classmethod
    def shared_only(cls, values):
        for value in values:
            if not validate_scope(value).startswith('shared:'):
                raise ValueError('Choose a shared memory space')
        return list(dict.fromkeys(values))

    @field_validator('write_scope')
    @classmethod
    def valid_destination(cls, value):
        return validate_scope(value) if value is not None else None


async def load_settings(repo) -> AgentMemorySettings:
    saved = await repo.get_by_key('agent.memory_access', 'user:local')
    return AgentMemorySettings.model_validate(saved.value if saved else {})


async def save_settings(repo, settings: AgentMemorySettings) -> None:
    now = int(time.time())
    await repo.save(Preference(id=gen_pref_id(), category=PreferenceCategory.SECURITY_POLICY,
        key='agent.memory_access', value=settings.model_dump(), scope='user:local',
        confidence=1, created_at=now, updated_at=now))


def read_scopes(scope: str, settings: AgentMemorySettings) -> list[str]:
    scopes = [scope]
    # Only the two shipped personal spaces are connected automatically.
    # Custom user scopes retain their explicit isolation.
    if settings.include_capture and scope in {'user:default', 'user:local'}:
        scopes.extend(['user:default', 'user:local'])
    scopes.extend(settings.shared_scopes)
    return list(dict.fromkeys(scopes))
