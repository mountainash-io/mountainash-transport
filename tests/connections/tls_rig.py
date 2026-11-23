"""Test-only TLS material: a CA, a server certificate for 127.0.0.1, and a client identity.

Key material is generated at runtime (``cryptography``, installed with paramiko) and
written only under the caller's directory. ``mtls_server`` serves one body over
HTTPS and refuses any client without a certificate from the test CA.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import ipaddress
import ssl
import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class TLSFiles(t.NamedTuple):
    ca: Path
    server_cert: Path
    server_key: Path
    client_cert: Path
    client_key: Path

    @property
    def client_cert_pem(self) -> str:
        return self.client_cert.read_text()

    @property
    def client_key_pem(self) -> str:
        return self.client_key.read_text()


def _issue(subject: str, issuer: t.Any, issuer_key: t.Any, *, ca: bool = False,
           server: bool = False) -> tuple[t.Any, t.Any]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    now = dt.datetime.now(dt.timezone.utc)
    builder = (x509.CertificateBuilder().subject_name(name).issuer_name(issuer or name)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=1))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False,
        ).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
    elif not ca:
        builder = builder.add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
    return builder.sign(issuer_key or key, hashes.SHA256()), key


def make_tls_files(directory: Path) -> TLSFiles:
    """Write a test CA, a 127.0.0.1 server identity and a client identity under *directory*."""
    from cryptography.hazmat.primitives import serialization

    def cert_pem(cert: t.Any) -> bytes:
        return t.cast(bytes, cert.public_bytes(serialization.Encoding.PEM))

    def key_pem(key: t.Any) -> bytes:
        return t.cast(bytes, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))

    ca_cert, ca_key = _issue("test-ca", None, None, ca=True)
    server_cert, server_key = _issue("127.0.0.1", ca_cert.subject, ca_key, server=True)
    client_cert, client_key = _issue("client", ca_cert.subject, ca_key)
    files = TLSFiles(*(directory / name for name in ("ca.pem", "server.pem", "server.key", "client.pem", "client.key")))
    for path, data in zip(files, (cert_pem(ca_cert), cert_pem(server_cert), key_pem(server_key),
                                  cert_pem(client_cert), key_pem(client_key))):
        path.write_bytes(data)
    return files


@contextlib.contextmanager
def mtls_server(files: TLSFiles, body: bytes) -> t.Iterator[str]:
    """Serve *body* at the yielded HTTPS URL to clients presenting a certificate from the test CA."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(files.server_cert, files.server_key)
    context.load_verify_locations(files.ca)
    context.verify_mode = ssl.CERT_REQUIRED

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: t.Any) -> None:
            pass

        def handle(self) -> None:
            with contextlib.suppress(ssl.SSLError, ConnectionError):
                super().handle()  # a client without a certificate is refused in the handshake

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.socket = context.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}/data/sales.csv"
    finally:
        server.shutdown()
        server.server_close()
