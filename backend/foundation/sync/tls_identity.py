"""Device-owned TLS credentials and trust established by signed pairing."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import os
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def server_name(device_id: str) -> str:
    return device_id.replace("_", "-") + ".pixiu"


def create_certificate(private, identity) -> str:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, identity.id)])
    created = datetime.fromtimestamp(identity.created_at, timezone.utc)
    certificate = (x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(private.public_key())
        .serial_number(int.from_bytes(hashlib.sha256(identity.public_key).digest()[:19], "big") or 1)
        .not_valid_before(created - timedelta(days=1))
        .not_valid_after(created + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(private.public_key()), critical=False)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(server_name(identity.id))]), critical=False)
        .sign(private, algorithm=None))
    return certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")


def validate_certificate(pem: str, public_key: bytes, device_id: str, timestamp: int) -> None:
    if not isinstance(pem, str) or len(pem) > 4096:
        raise ValueError("invalid pairing certificate")
    cert = x509.load_pem_x509_certificate(pem.encode("ascii"))
    if pem.strip() != cert.public_bytes(serialization.Encoding.PEM).decode("ascii").strip():
        raise ValueError("pairing must contain exactly one certificate")
    key = cert.public_key()
    if not isinstance(key, Ed25519PublicKey) or key.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ) != public_key:
        raise ValueError("certificate does not belong to paired identity")
    key.verify(cert.signature, cert.tbs_certificate_bytes)
    instant = datetime.fromtimestamp(timestamp, timezone.utc)
    if not cert.not_valid_before_utc <= instant < cert.not_valid_after_utc:
        raise ValueError("pairing certificate has expired or is not yet valid")
    try:
        names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound as exc:
        raise ValueError("certificate device name is missing") from exc
    if server_name(device_id) not in names.get_values_for_type(x509.DNSName):
        raise ValueError("certificate device name mismatch")


def _write_private(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise ValueError("TLS material must not be a symlink")
    if path.is_file() and path.read_bytes() == data:
        path.chmod(0o600)
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


async def prepare_credentials(service, store, settings):
    identity = await service.initialize()
    certificate = await service.tls_certificate()
    directory = Path(settings.db_path).resolve().parent / "sync-tls" / identity.id
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    trusted = [certificate]
    for peer in await store.list_peers():
        pem = await store.get_meta("tls_peer_certificate:" + peer.id)
        if pem:
            # Only pairing can install these identity-bound certificates.
            trusted.append(pem)
    paths = [directory / filename for filename in ("device.pem", "device.key", "peers.pem")]
    for path, data in zip(paths, (certificate.encode(), identity.encrypted_private_key,
                                 "\n".join(trusted).encode())):
        _write_private(path, data)
    return dict(certfile=str(paths[0]), keyfile=str(paths[1]), cafile=str(paths[2]),
                key_password=settings.sync_key_passphrase)
