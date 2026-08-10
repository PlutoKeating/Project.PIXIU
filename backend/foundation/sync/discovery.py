"""Opt-in mDNS discovery for paired PIXIU peers on the local network."""

from __future__ import annotations

import asyncio
import base64
import ipaddress
from dataclasses import dataclass

from zeroconf import IPVersion, ServiceInfo, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

from backend.foundation.core.models import validate_id

from .models import PeerStatus, validate_shared_scope

SERVICE_TYPE = "_pixiu._tcp.local."
_PROPERTY_VERSION = b"1"


class DiscoveryError(ValueError):
    """An mDNS advertisement is invalid or outside the LAN boundary."""


@dataclass(frozen=True)
class PeerAdvertisement:
    device_id: str
    name: str
    domain: str
    public_key: bytes
    addresses: tuple[str, ...]
    port: int
    server_name: str


def _lan_address(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise DiscoveryError(f"invalid advertised IP address: {value}") from exc
    if not (address.is_private or address.is_link_local or address.is_loopback):
        raise DiscoveryError("only private, link-local, or loopback addresses are allowed")
    if address.is_unspecified or address.is_multicast:
        raise DiscoveryError("unspecified and multicast addresses cannot be advertised")
    return str(address)


def _property(properties: dict[bytes, bytes | None], key: bytes) -> str:
    value = properties.get(key)
    if value is None:
        raise DiscoveryError(f"missing mDNS property: {key.decode('ascii')}")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DiscoveryError("mDNS property is not valid UTF-8") from exc


def build_service_info(
    *,
    device_id: str,
    name: str,
    domain: str,
    public_key: bytes,
    addresses: list[str] | tuple[str, ...],
    port: int,
    server_name: str,
) -> ServiceInfo:
    """Build a minimal advertisement containing public identity metadata only."""
    validate_id("device", device_id)
    validate_shared_scope(domain)
    if not name or len(name) > 128:
        raise DiscoveryError("device name must contain 1-128 characters")
    if len(public_key) != 32:
        raise DiscoveryError("Ed25519 public key must contain 32 bytes")
    if not 1 <= port <= 65535:
        raise DiscoveryError("port must be between 1 and 65535")
    normalized = tuple(_lan_address(value) for value in addresses)
    if not normalized:
        raise DiscoveryError("at least one LAN address must be advertised")
    host = server_name.rstrip(".")
    if not host or len(host) > 253:
        raise DiscoveryError("invalid TLS server name")
    return ServiceInfo(
        type_=SERVICE_TYPE,
        name=f"{device_id}.{SERVICE_TYPE}",
        addresses=[ipaddress.ip_address(value).packed for value in normalized],
        port=port,
        properties={
            b"version": _PROPERTY_VERSION,
            b"device_id": device_id.encode("ascii"),
            b"name": name.encode("utf-8"),
            b"domain": domain.encode("ascii"),
            b"public_key": base64.b64encode(public_key),
            b"server_name": host.encode("utf-8"),
        },
        server=f"{host}.",
    )


def parse_service_info(info: ServiceInfo) -> PeerAdvertisement:
    """Parse and validate an advertisement without granting it trust."""
    if info.type != SERVICE_TYPE:
        raise DiscoveryError("unexpected mDNS service type")
    properties = info.properties
    if properties.get(b"version") != _PROPERTY_VERSION:
        raise DiscoveryError("unsupported mDNS advertisement version")
    device_id = validate_id("device", _property(properties, b"device_id"))
    domain = validate_shared_scope(_property(properties, b"domain"))
    try:
        public_key = base64.b64decode(
            _property(properties, b"public_key"), validate=True
        )
    except ValueError as exc:
        raise DiscoveryError("invalid advertised public key") from exc
    if len(public_key) != 32:
        raise DiscoveryError("invalid advertised Ed25519 public key")
    name = _property(properties, b"name")
    if not name or len(name) > 128:
        raise DiscoveryError("invalid advertised device name")
    server_name = _property(properties, b"server_name").rstrip(".")
    addresses = tuple(
        _lan_address(value) for value in info.parsed_addresses(IPVersion.All)
    )
    if not addresses:
        raise DiscoveryError("advertisement has no usable LAN address")
    if not 1 <= info.port <= 65535:
        raise DiscoveryError("invalid advertised port")
    return PeerAdvertisement(
        device_id=device_id,
        name=name,
        domain=domain,
        public_key=public_key,
        addresses=addresses,
        port=info.port,
        server_name=server_name,
    )


class TrustedPeerDirectory:
    """Accept discovery results only when they exactly match paired state."""

    def __init__(self, store, domain: str) -> None:
        self._store = store
        self._domain = validate_shared_scope(domain)
        self._entries: dict[str, PeerAdvertisement] = {}

    async def accept(self, advertisement: PeerAdvertisement) -> bool:
        peer = await self._store.get_peer(advertisement.device_id)
        if (
            peer is None
            or peer.status == PeerStatus.REVOKED
            or peer.domain != self._domain
            or advertisement.domain != self._domain
            or peer.public_key != advertisement.public_key
        ):
            return False
        self._entries[peer.id] = advertisement
        return True

    async def resolve(self, peer_id: str) -> PeerAdvertisement | None:
        advertisement = self._entries.get(peer_id)
        if advertisement is None:
            return None
        peer = await self._store.get_peer(peer_id)
        if (
            peer is None
            or peer.status == PeerStatus.REVOKED
            or peer.domain != advertisement.domain
            or peer.public_key != advertisement.public_key
        ):
            self._entries.pop(peer_id, None)
            return None
        return advertisement

    def remove(self, peer_id: str) -> None:
        self._entries.pop(peer_id, None)


class MdnsDiscovery:
    """Small async wrapper; no socket is opened until register/discover is called."""

    def __init__(self, zeroconf: AsyncZeroconf | None = None) -> None:
        self._zeroconf = zeroconf
        self._owns_zeroconf = zeroconf is None
        self._registered: ServiceInfo | None = None

    async def _instance(self) -> AsyncZeroconf:
        if self._zeroconf is None:
            self._zeroconf = AsyncZeroconf(ip_version=IPVersion.All)
        return self._zeroconf

    async def register(self, info: ServiceInfo) -> None:
        if self._registered is not None:
            raise RuntimeError("mDNS service is already registered")
        zeroconf = await self._instance()
        await zeroconf.async_register_service(info)
        self._registered = info

    async def discover(self, timeout_seconds: float = 1.0) -> list[PeerAdvertisement]:
        if timeout_seconds <= 0:
            raise ValueError("discovery timeout must be positive")
        zeroconf = await self._instance()
        found: dict[str, PeerAdvertisement] = {}
        tasks: set[asyncio.Task] = set()

        async def load(service_type: str, service_name: str) -> None:
            info = await zeroconf.async_get_service_info(
                service_type, service_name, timeout=int(timeout_seconds * 1000)
            )
            if info is None:
                return
            try:
                advertisement = parse_service_info(info)
            except (DiscoveryError, ValueError):
                return
            found[advertisement.device_id] = advertisement

        def on_change(zc, service_type, service_name, state_change) -> None:
            if state_change not in (
                ServiceStateChange.Added,
                ServiceStateChange.Updated,
            ):
                return
            task = asyncio.create_task(load(service_type, service_name))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

        browser = AsyncServiceBrowser(
            zeroconf.zeroconf, SERVICE_TYPE, handlers=[on_change]
        )
        try:
            await asyncio.sleep(timeout_seconds)
            if tasks:
                await asyncio.gather(*tuple(tasks), return_exceptions=True)
        finally:
            await browser.async_cancel()
        return sorted(found.values(), key=lambda item: item.device_id)

    async def close(self) -> None:
        if self._zeroconf is None:
            return
        if self._registered is not None:
            await self._zeroconf.async_unregister_service(self._registered)
            self._registered = None
        if self._owns_zeroconf:
            await self._zeroconf.async_close()
            self._zeroconf = None
