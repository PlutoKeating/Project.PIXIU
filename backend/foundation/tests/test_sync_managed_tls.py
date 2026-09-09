"""Real TLS handshakes with credentials exchanged through product pairing."""
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from backend.foundation.sync import PairingMethod
from backend.foundation.sync.tls_identity import prepare_credentials, server_name, validate_certificate
from backend.foundation.sync.transport import create_mtls_context, start_tls_json_server, TlsJsonTransport, TransportError
from backend.foundation.tests.test_sync_service import _node, PASSPHRASE


@pytest.mark.asyncio
async def test_managed_tls_requires_pairing_and_revocation_removes_trust(tmp_path):
    a, sa, da = await _node(tmp_path, "a.db", "A")
    b, sb, db = await _node(tmp_path, "b.db", "B")
    settings = SimpleNamespace(db_path=str(tmp_path / "data.db"), sync_key_passphrase=PASSPHRASE)
    server = None
    try:
        ia, ib = await a.initialize(), await b.initialize()
        ca = await prepare_credentials(a, sa, settings)
        cb = await prepare_credentials(b, sb, settings)
        assert Path(ca["keyfile"]).stat().st_mode & 0o777 == 0o600
        assert b"ENCRYPTED PRIVATE KEY" in Path(ca["keyfile"]).read_bytes()
        original = Path(ca["certfile"]).read_bytes()
        assert (await prepare_credentials(a, sa, settings)) == ca
        assert Path(ca["certfile"]).read_bytes() == original
        with pytest.raises(ValueError):
            validate_certificate(await a.tls_certificate(), ib.public_key, ib.id, int(time.time()))
        with pytest.raises(ValueError, match="exactly one"):
            validate_certificate((await a.tls_certificate()) * 2, ia.public_key, ia.id, int(time.time()))

        async def handler(message):
            return {"received": message["value"]}

        async def start(credentials):
            return await start_tls_json_server(host="127.0.0.1", port=0,
                context=create_mtls_context(**credentials, server_side=True), handler=handler)

        async def request(credentials):
            return await TlsJsonTransport(create_mtls_context(**credentials, server_side=False)).request(
                "127.0.0.1", server.addresses[0][1], {"value": "paired document"},
                server_hostname=server_name(ia.id))

        server = await start(ca)
        with pytest.raises(TransportError):
            await request(cb)
        await server.close()

        await a.pair(PairingMethod.QR, await b.create_pairing_token(PairingMethod.QR))
        await b.pair(PairingMethod.QR, await a.create_pairing_token(PairingMethod.QR))
        ca = await prepare_credentials(a, sa, settings)
        cb = await prepare_credentials(b, sb, settings)
        server = await start(ca)
        assert await request(cb) == {"received": "paired document"}
        await server.close()

        await a.revoke(ib.id)
        ca = await prepare_credentials(a, sa, settings)
        assert await b.tls_certificate() not in Path(ca["cafile"]).read_text()
        server = await start(ca)
        with pytest.raises(TransportError):
            await request(cb)
    finally:
        if server:
            await server.close()
        await da.close()
        await db.close()
