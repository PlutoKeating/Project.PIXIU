"""TLS 1.3 mutual-authentication transport for bounded JSON messages."""

from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 10.0


class TransportError(RuntimeError):
    """The authenticated transport or wire framing failed."""


def create_mtls_context(
    *,
    certfile: str,
    keyfile: str,
    cafile: str,
    server_side: bool,
    key_password: str | None = None,
) -> ssl.SSLContext:
    """Create a TLS-1.3-only context that always requires a peer certificate."""
    for label, value in (
        ("certificate", certfile),
        ("private key", keyfile),
        ("CA bundle", cafile),
    ):
        if not value or not Path(value).is_file():
            raise TransportError(f"sync TLS {label} file does not exist")
    purpose = ssl.Purpose.CLIENT_AUTH if server_side else ssl.Purpose.SERVER_AUTH
    context = ssl.create_default_context(purpose=purpose, cafile=cafile)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = not server_side
    try:
        context.load_cert_chain(
            certfile=certfile,
            keyfile=keyfile,
            password=key_password,
        )
    except (OSError, ssl.SSLError) as exc:
        raise TransportError("unable to load sync TLS certificate or key") from exc
    return context


def _encode_message(message: dict[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            message, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TransportError("message is not JSON serializable") from exc
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise TransportError("message exceeds the 1 MiB limit")
    return encoded + b"\n"


async def _read_message(reader: asyncio.StreamReader) -> dict[str, Any]:
    try:
        encoded = await reader.readuntil(b"\n")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
        raise TransportError("invalid or oversized JSON frame") from exc
    if len(encoded) - 1 > MAX_MESSAGE_BYTES:
        raise TransportError("message exceeds the 1 MiB limit")
    try:
        decoded = json.loads(encoded)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TransportError("message is not valid UTF-8 JSON") from exc
    if not isinstance(decoded, dict):
        raise TransportError("message root must be an object")
    return decoded


class TlsJsonTransport:
    """One-request-per-connection client with hostname and mTLS verification."""

    def __init__(
        self,
        context: ssl.SSLContext,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("transport timeout must be positive")
        if context.minimum_version != ssl.TLSVersion.TLSv1_3:
            raise TransportError("TLS context must require TLS 1.3")
        if context.verify_mode != ssl.CERT_REQUIRED:
            raise TransportError("TLS context must require peer certificates")
        self._context = context
        self._timeout = timeout_seconds

    async def request(
        self,
        host: str,
        port: int,
        message: dict[str, Any],
        *,
        server_hostname: str,
    ) -> dict[str, Any]:
        if not server_hostname:
            raise TransportError("TLS server hostname is required")
        frame = _encode_message(message)

        async def exchange() -> dict[str, Any]:
            reader, writer = await asyncio.open_connection(
                host,
                port,
                ssl=self._context,
                server_hostname=server_hostname,
                limit=MAX_MESSAGE_BYTES + 1,
            )
            try:
                ssl_object = writer.get_extra_info("ssl_object")
                if ssl_object is None or not ssl_object.getpeercert(binary_form=True):
                    raise TransportError("server did not present a certificate")
                writer.write(frame)
                await writer.drain()
                return await _read_message(reader)
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            return await asyncio.wait_for(exchange(), timeout=self._timeout)
        except asyncio.TimeoutError as exc:
            raise TransportError("TLS request timed out") from exc
        except (ConnectionError, OSError, ssl.SSLError) as exc:
            raise TransportError("TLS request failed") from exc


class TlsJsonServer:
    """Lifecycle wrapper around an asyncio TLS server."""

    def __init__(self, server: asyncio.AbstractServer) -> None:
        self._server = server

    @property
    def addresses(self) -> tuple[Any, ...]:
        return tuple(sock.getsockname() for sock in (self._server.sockets or ()))

    async def close(self) -> None:
        self._server.close()
        await self._server.wait_closed()


async def start_tls_json_server(
    *,
    host: str,
    port: int,
    context: ssl.SSLContext,
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> TlsJsonServer:
    """Start a bounded mTLS server. Callers must opt in by invoking this function."""
    if context.minimum_version != ssl.TLSVersion.TLSv1_3:
        raise TransportError("TLS context must require TLS 1.3")
    if context.verify_mode != ssl.CERT_REQUIRED:
        raise TransportError("TLS context must require peer certificates")

    async def accept(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            ssl_object = writer.get_extra_info("ssl_object")
            if ssl_object is None or not ssl_object.getpeercert(binary_form=True):
                raise TransportError("client did not present a certificate")
            request = await _read_message(reader)
            response = await handler(request)
            writer.write(_encode_message(response))
            await writer.drain()
        except (TransportError, ValueError):
            try:
                writer.write(_encode_message({"ok": False, "error": "INVALID_REQUEST"}))
                await writer.drain()
            except (ConnectionError, TransportError):
                pass
        finally:
            writer.close()
            await writer.wait_closed()

    try:
        server = await asyncio.start_server(
            accept,
            host,
            port,
            ssl=context,
            limit=MAX_MESSAGE_BYTES + 1,
        )
    except (OSError, ssl.SSLError) as exc:
        raise TransportError("unable to start sync TLS server") from exc
    return TlsJsonServer(server)
