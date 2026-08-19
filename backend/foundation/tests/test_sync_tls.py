"""TLS sync transport integration on loopback only."""

from __future__ import annotations

import ssl
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from backend.foundation.sync.transport import (
    TlsJsonTransport,
    TransportError,
    create_mtls_context,
    start_tls_json_server,
)


def _certificate_files(root: Path) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PIXIU Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    def issue(name: str, usage, *, server: bool) -> tuple[bytes, bytes]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
            )
            .issuer_name(ca_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=None,
                    decipher_only=None,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .add_extension(x509.ExtendedKeyUsage([usage]), False)
        )
        if server:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]), False
            )
        certificate = builder.sign(ca_key, hashes.SHA256())
        return (
            certificate.public_bytes(serialization.Encoding.PEM),
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )

    server_cert, server_key = issue(
        "localhost", ExtendedKeyUsageOID.SERVER_AUTH, server=True
    )
    client_cert, client_key = issue(
        "pixiu-client", ExtendedKeyUsageOID.CLIENT_AUTH, server=False
    )
    values = {
        "ca": ca_cert.public_bytes(serialization.Encoding.PEM),
        "server_cert": server_cert,
        "server_key": server_key,
        "client_cert": client_cert,
        "client_key": client_key,
    }
    paths: dict[str, str] = {}
    for name, data in values.items():
        path = root / f"{name}.pem"
        path.write_bytes(data)
        paths[name] = str(path)
    return paths


@pytest.mark.asyncio
async def test_tls13_mutual_authentication_on_loopback(tmp_path: Path):
    files = _certificate_files(tmp_path)
    server_context = create_mtls_context(
        certfile=files["server_cert"],
        keyfile=files["server_key"],
        cafile=files["ca"],
        server_side=True,
    )
    client_context = create_mtls_context(
        certfile=files["client_cert"],
        keyfile=files["client_key"],
        cafile=files["ca"],
        server_side=False,
    )
    assert server_context.minimum_version == ssl.TLSVersion.TLSv1_3
    assert server_context.maximum_version == ssl.TLSVersion.TLSv1_3
    assert server_context.verify_mode == ssl.CERT_REQUIRED

    async def handler(message):
        return {"ok": True, "echo": message["value"]}

    server = await start_tls_json_server(
        host="127.0.0.1",
        port=0,
        context=server_context,
        handler=handler,
    )
    try:
        port = server.addresses[0][1]
        response = await TlsJsonTransport(client_context).request(
            "127.0.0.1",
            port,
            {"value": "loopback"},
            server_hostname="localhost",
        )
        assert response == {"ok": True, "echo": "loopback"}

        unauthenticated = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=files["ca"]
        )
        unauthenticated.minimum_version = ssl.TLSVersion.TLSv1_3
        unauthenticated.maximum_version = ssl.TLSVersion.TLSv1_3
        with pytest.raises(TransportError):
            await TlsJsonTransport(unauthenticated).request(
                "127.0.0.1",
                port,
                {"value": "rejected"},
                server_hostname="localhost",
            )
    finally:
        await server.close()
