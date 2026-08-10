"""持久化 Ed25519 设备身份，私钥始终使用口令加密。"""

from __future__ import annotations

import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.foundation.core.idgen import gen_device_id

from .models import DeviceIdentity, validate_shared_scope


class IdentityConfigurationError(RuntimeError):
    """身份配置或解密口令无效。"""


class IdentityManager:
    def __init__(self, store, passphrase: str) -> None:
        if len(passphrase) < 16:
            raise IdentityConfigurationError(
                "PIXIU_SYNC_KEY_PASSPHRASE must contain at least 16 characters"
            )
        self._store = store
        self._passphrase = passphrase.encode("utf-8")

    async def load_or_create(
        self,
        name: str,
        domain: str,
        *,
        now: int | None = None,
    ) -> DeviceIdentity:
        validate_shared_scope(domain)
        existing = await self._store.get_identity()
        if existing is not None:
            if existing.name != name or existing.domain != domain:
                raise IdentityConfigurationError(
                    "stored sync identity does not match configured name/domain"
                )
            self._load_private(existing)
            return existing

        private = Ed25519PrivateKey.generate()
        identity = DeviceIdentity(
            id=gen_device_id(),
            name=name,
            domain=domain,
            encrypted_private_key=private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(self._passphrase),
            ),
            public_key=private.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            ),
            created_at=int(time.time()) if now is None else now,
        )
        await self._store.save_identity(identity)
        return identity

    def _load_private(self, identity: DeviceIdentity) -> Ed25519PrivateKey:
        try:
            private = serialization.load_pem_private_key(
                identity.encrypted_private_key,
                password=self._passphrase,
            )
        except (TypeError, ValueError) as exc:
            raise IdentityConfigurationError(
                "unable to decrypt stored sync identity"
            ) from exc
        if not isinstance(private, Ed25519PrivateKey):
            raise IdentityConfigurationError("stored sync key is not Ed25519")
        return private

    def sign(self, identity: DeviceIdentity, message: bytes) -> bytes:
        return self._load_private(identity).sign(message)

    @staticmethod
    def verify(public_key: bytes, signature: bytes, message: bytes) -> None:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
