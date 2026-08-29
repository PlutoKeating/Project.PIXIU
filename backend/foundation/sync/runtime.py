"""Opt-in lifecycle for mDNS discovery, mTLS serving, and gossip rounds."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from .discovery import (
    MdnsDiscovery,
    TrustedPeerDirectory,
    build_service_info,
)
from .gossip import GossipEngine, NetworkGossipTransport
from .models import PeerStatus
from .protocol import SyncProtocol
from .scheduler import SyncScheduler
from .transport import (
    TlsJsonServer,
    TlsJsonTransport,
    create_mtls_context,
    start_tls_json_server,
)


class SyncRuntime:
    """Own active network resources; construction alone has no side effects."""

    def __init__(
        self,
        *,
        identity,
        store,
        discovery: MdnsDiscovery,
        directory: TrustedPeerDirectory,
        gossip: GossipEngine,
        service_info,
        server_starter: Callable[[], Awaitable[TlsJsonServer]],
        interval_seconds: float = 30.0,
        discovery_timeout_seconds: float = 1.0,
    ) -> None:
        self._identity = identity
        self._store = store
        self._discovery = discovery
        self._directory = directory
        self._gossip = gossip
        self._service_info = service_info
        self._server_starter = server_starter
        self._discovery_timeout = discovery_timeout_seconds
        self._server: TlsJsonServer | None = None
        self._task: asyncio.Task | None = None
        self._scheduler = SyncScheduler(
            self.run_once, interval_seconds=interval_seconds
        )

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def discovery(self) -> MdnsDiscovery:
        """共享的 mDNS 实例，供 GET /sync/discover 依赖复用。"""
        return self._discovery

    async def start(self) -> None:
        if self.running:
            return
        self._server = await self._server_starter()
        try:
            await self._discovery.register(self._service_info)
        except Exception:
            await self._server.close()
            self._server = None
            raise
        self._scheduler.reset()
        self._task = asyncio.create_task(
            self._scheduler.run(), name="pixiu-sync-scheduler"
        )

    async def run_once(self) -> dict[str, int]:
        advertisements = await self._discovery.discover(
            self._discovery_timeout
        )
        trusted = 0
        for advertisement in advertisements:
            if advertisement.device_id == self._identity.id:
                continue
            if await self._directory.accept(advertisement):
                trusted += 1
                await self._store.set_peer_status(
                    advertisement.device_id,
                    PeerStatus.ONLINE,
                    int(time.time()),
                )
        result = await self._gossip.run_once()
        return {**result, "trusted_peers_discovered": trusted}

    async def stop(self) -> None:
        self._scheduler.stop()
        if self._task is not None:
            await self._task
            self._task = None
        await self._discovery.close()
        if self._server is not None:
            await self._server.close()
            self._server = None


async def create_sync_runtime(service, store, settings) -> SyncRuntime:
    """Build the production runtime after explicit configuration enabled it."""
    if not settings.sync_network_enabled:
        raise ValueError("sync networking is disabled")
    identity = await service.initialize()
    discovery = MdnsDiscovery()
    directory = TrustedPeerDirectory(store, identity.domain)
    server_context = create_mtls_context(
        certfile=settings.sync_certfile,
        keyfile=settings.sync_keyfile,
        cafile=settings.sync_cafile,
        server_side=True,
        key_password=settings.sync_tls_key_password,
    )
    client_context = create_mtls_context(
        certfile=settings.sync_certfile,
        keyfile=settings.sync_keyfile,
        cafile=settings.sync_cafile,
        server_side=False,
        key_password=settings.sync_tls_key_password,
    )
    protocol = SyncProtocol(service, store)

    async def start_server() -> TlsJsonServer:
        return await start_tls_json_server(
            host=settings.sync_bind_host,
            port=settings.sync_port,
            context=server_context,
            handler=protocol.handle,
        )

    transport = NetworkGossipTransport(
        directory,
        TlsJsonTransport(client_context),
        sender_id=identity.id,
    )
    gossip = GossipEngine(store, transport)
    service_info = build_service_info(
        device_id=identity.id,
        name=identity.name,
        domain=identity.domain,
        public_key=identity.public_key,
        addresses=settings.sync_advertise_addresses,
        port=settings.sync_port,
        server_name=settings.sync_server_name,
        pairable=True,  # SN-4 运行时开关细化前默认可配对
    )
    return SyncRuntime(
        identity=identity,
        store=store,
        discovery=discovery,
        directory=directory,
        gossip=gossip,
        service_info=service_info,
        server_starter=start_server,
    )
