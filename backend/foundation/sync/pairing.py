"""签名配对令牌与 PIN/QR 信任建立。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from cryptography.exceptions import InvalidSignature

from .identity import IdentityManager
from .models import DeviceIdentity, PairingMethod, Peer, PeerStatus

_TOKEN_VERSION = 1
_MAX_TOKEN_BYTES = 16 * 1024
_PIN_ROUNDS = 200_000


class PairingError(ValueError):
    """配对令牌、PIN、域或签名验证失败。"""


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _unb64(value: str) -> bytes:
    try:
        return base64.b64decode(value, altchars=b"-_", validate=True)
    except (ValueError, TypeError) as exc:
        raise PairingError("invalid base64 in pairing token") from exc


def _canonical(payload: dict) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(
        unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _pin_digest(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("ascii"), salt, _PIN_ROUNDS)


def _validate_pin(pin: str | None) -> str:
    if pin is None or len(pin) != 6 or not pin.isascii() or not pin.isdigit():
        raise PairingError("PIN must contain exactly 6 ASCII digits")
    return pin


class PairingManager:
    def __init__(
        self,
        store,
        identity_manager: IdentityManager,
        identity: DeviceIdentity,
    ) -> None:
        self._store = store
        self._identity_manager = identity_manager
        self._identity = identity

    def create_token(
        self,
        method: PairingMethod,
        *,
        pin: str | None = None,
        ttl_seconds: int = 300,
        now: int | None = None,
    ) -> str:
        if ttl_seconds <= 0 or ttl_seconds > 900:
            raise PairingError("pairing token TTL must be between 1 and 900 seconds")
        timestamp = int(time.time()) if now is None else now
        salt = os.urandom(16)
        pin_digest = None
        if method == PairingMethod.PIN:
            pin_digest = _b64(_pin_digest(_validate_pin(pin), salt))
        payload = {
            "version": _TOKEN_VERSION,
            "method": method.value,
            "device_id": self._identity.id,
            "device_name": self._identity.name,
            "domain": self._identity.domain,
            "public_key": _b64(self._identity.public_key),
            "expires_at": timestamp + ttl_seconds,
            "nonce": _b64(os.urandom(16)),
            "pin_salt": _b64(salt),
            "pin_digest": pin_digest,
        }
        payload["signature"] = _b64(
            self._identity_manager.sign(self._identity, _canonical(payload))
        )
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        return _b64(encoded)

    async def pair(
        self,
        method: PairingMethod,
        token: str,
        *,
        pin: str | None = None,
        now: int | None = None,
    ) -> Peer:
        timestamp = int(time.time()) if now is None else now
        if len(token) > _MAX_TOKEN_BYTES:
            raise PairingError("pairing token is too large")
        try:
            payload = json.loads(_unb64(token))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PairingError("invalid pairing token") from exc
        required = {
            "version", "method", "device_id", "device_name", "domain",
            "public_key", "expires_at", "nonce", "pin_salt", "pin_digest",
            "signature",
        }
        if not isinstance(payload, dict) or set(payload) != required:
            raise PairingError("pairing token fields are invalid")
        if not isinstance(payload["version"], int):
            raise PairingError("pairing token version is invalid")
        if not isinstance(payload["expires_at"], int):
            raise PairingError("pairing token expiry is invalid")
        if not all(
            isinstance(payload[key], str)
            for key in (
                "method", "device_id", "device_name", "domain", "public_key",
                "nonce", "pin_salt", "signature",
            )
        ):
            raise PairingError("pairing token field types are invalid")
        if payload["pin_digest"] is not None and not isinstance(payload["pin_digest"], str):
            raise PairingError("pairing PIN digest is invalid")
        if payload["version"] != _TOKEN_VERSION or payload["method"] != method.value:
            raise PairingError("pairing method or token version mismatch")
        if payload["expires_at"] < timestamp:
            raise PairingError("pairing token has expired")
        if payload["domain"] != self._identity.domain:
            raise PairingError("pairing token belongs to another shared domain")
        if payload["device_id"] == self._identity.id:
            raise PairingError("cannot pair a device with itself")

        public_key = _unb64(payload["public_key"])
        if len(public_key) != 32:
            raise PairingError("invalid Ed25519 public key")
        try:
            self._identity_manager.verify(
                public_key, _unb64(payload["signature"]), _canonical(payload)
            )
        except (InvalidSignature, ValueError) as exc:
            raise PairingError("pairing token signature is invalid") from exc

        if method == PairingMethod.PIN:
            expected = _unb64(payload["pin_digest"] or "")
            actual = _pin_digest(_validate_pin(pin), _unb64(payload["pin_salt"]))
            if not hmac.compare_digest(actual, expected):
                raise PairingError("pairing PIN is invalid")

        nonce_key = f"pairing_nonce:{payload['nonce']}"
        if await self._store.get_meta(nonce_key) is not None:
            raise PairingError("pairing token has already been used")
        peer = Peer(
            id=payload["device_id"],
            name=payload["device_name"],
            domain=payload["domain"],
            public_key=public_key,
            status=PeerStatus.ONLINE,
            paired_at=timestamp,
            last_seen_ts=timestamp,
        )
        await self._store.save_peer(peer)
        await self._store.set_meta(nonce_key, str(timestamp))
        return peer
