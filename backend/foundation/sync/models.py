"""P2P 同步领域模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from backend.foundation.core.models import validate_id, validate_scope


def validate_shared_scope(value: str) -> str:
    scope = validate_scope(value)
    if not scope.startswith("shared:"):
        raise ValueError("only shared:* scopes may leave the device")
    return scope


class PairingMethod(str, Enum):
    QR = "QR"
    PIN = "PIN"


class PeerStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    REVOKED = "REVOKED"


class DeviceIdentity(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=128)
    domain: str
    encrypted_private_key: bytes
    public_key: bytes
    created_at: int

    @field_validator("id")
    @classmethod
    def _device_id(cls, value: str) -> str:
        return validate_id("device", value)

    @field_validator("domain")
    @classmethod
    def _domain(cls, value: str) -> str:
        return validate_shared_scope(value)


class Peer(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=128)
    domain: str
    public_key: bytes
    status: PeerStatus = PeerStatus.OFFLINE
    paired_at: int
    last_seen_ts: int | None = None
    last_sync_ts: int | None = None
    total_ops_synced: int = Field(default=0, ge=0)
    pending_ops: int = Field(default=0, ge=0)

    @field_validator("id")
    @classmethod
    def _device_id(cls, value: str) -> str:
        return validate_id("device", value)

    @field_validator("domain")
    @classmethod
    def _domain(cls, value: str) -> str:
        return validate_shared_scope(value)


class SyncRecord(BaseModel):
    entity: str = Field(min_length=1, max_length=256)
    payload: dict = Field(default_factory=dict)
    vclock: dict[str, int] = Field(default_factory=dict)
    ts: int
    op_id: str
    tombstone: bool = False

    @field_validator("op_id")
    @classmethod
    def _op_id(cls, value: str) -> str:
        return validate_id("sync_op", value)

    @field_validator("vclock")
    @classmethod
    def _clock(cls, value: dict[str, int]) -> dict[str, int]:
        if any(not key or counter < 0 for key, counter in value.items()):
            raise ValueError("vector clock entries require names and non-negative counters")
        return value


class SyncStatus(BaseModel):
    domain: str
    peers_online: int = Field(ge=0)
    peers_total: int = Field(ge=0)
    pending_outgoing_ops: int = Field(ge=0)
    last_anti_entropy_ts: int | None = None
    total_ops_synced: int = Field(ge=0)
    # SN-4 运行时开关（GET /sync/status 契约扩展；默认 False 保持向后兼容）
    enabled: bool = False
    paused: bool = False
