"""#38: a tunnelled target keeps its real identity (URL, TLS name, Host, SSH host key)."""
from __future__ import annotations

import socket
import typing as t
from pathlib import Path

import httpx
import pytest

from mountainash_auth_client import IAMAuthProfile, PasswordAuthProfile
from mountainash_transport.connections import create_tunnelled_connection
from mountainash_transport.connections.errors import TransportConnectionError
from mountainash_transport.connections.tunnel import TunnelledConnection
from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTPStorageProfile
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile

from .tunnel_rig import TARGET, Bastion, HTTPTarget, SFTPTarget, write_pki

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pki(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    return write_pki(tmp_path_factory.mktemp("pki"))


@pytest.fixture(scope="module")
def tls_target(pki: tuple[Path, Path]) -> t.Iterator[HTTPTarget]:
    server = HTTPTarget(cert=pki[1])
    yield server
    server.close()


@pytest.fixture(scope="module")
def plain_target() -> t.Iterator[HTTPTarget]:
    server = HTTPTarget()
    yield server
    server.close()


@pytest.fixture(scope="module")
def sftp_target() -> t.Iterator[SFTPTarget]:
    server = SFTPTarget()
    yield server
    server.close()


@pytest.fixture
def bastion(tmp_path: Path) -> t.Iterator[tuple[Bastion, SFTPStorageProfile]]:
    server = Bastion()
    known = tmp_path / "bastion_known_hosts"
    known.write_text(server.known_hosts_line("127.0.0.1"))
    profile = SFTPStorageProfile(
        HOST="127.0.0.1", PORT=server.port, USERNAME="u",
        KNOWN_HOSTS_FILE=str(known), LOOK_FOR_KEYS=False, ALLOW_AGENT=False,
    )
    yield server, profile
    server.close()


@pytest.fixture(autouse=True)
def trust_test_ca(pki: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSL_CERT_FILE", str(pki[0]))
    # The S3 profile always passes verify=True, which makes botocore ignore
    # AWS_CA_BUNDLE; point its default bundle at the test CA instead.
    import botocore.httpsession
    monkeypatch.setattr(botocore.httpsession, "where", lambda: str(pki[0]))
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"):
        monkeypatch.delenv(name, raising=False)


_BASTION_AUTH = PasswordAuthProfile(USERNAME="u", PASSWORD="p")


def _http_tunnel(bastion: t.Any, port: int) -> TunnelledConnection:
    return create_tunnelled_connection(bastion[1], _BASTION_AUTH, HTTPStorageProfile(), None, TARGET, port)


def test_https_keeps_url_host_and_tls_name(bastion, tls_target) -> None:
    tls_target.seen.clear()
    with _http_tunnel(bastion, tls_target.port).connect() as conn:
        response = conn.client.get(f"https://{TARGET}:{tls_target.port}/prefix/x")
    assert (response.status_code, response.content) == (200, b"payload")
    assert tls_target.seen == [("GET", "/prefix/x", f"{TARGET}:{tls_target.port}", TARGET)]


def test_plain_http_keeps_path(bastion, plain_target) -> None:
    plain_target.seen.clear()
    with _http_tunnel(bastion, plain_target.port).connect() as conn:
        response = conn.client.get(f"http://{TARGET}:{plain_target.port}/prefix/y")
    assert response.status_code == 200
    method, path, host, _ = plain_target.seen[0]
    assert (method, path.endswith("/prefix/y"), host) == ("GET", True, f"{TARGET}:{plain_target.port}")


def test_host_match_ignores_case(bastion, tls_target) -> None:
    with _http_tunnel(bastion, tls_target.port).connect() as conn:
        assert conn.client.get(f"https://TARGET.test:{tls_target.port}/x").status_code == 200


@pytest.mark.parametrize("url", [
    "https://other.test:{port}/x",
    "https://" + TARGET + ":1/x",
    "http://127.0.0.1:{local}/x",
], ids=["other_host", "other_port", "old_local_url"])
def test_request_for_another_destination_is_refused(bastion, tls_target, url) -> None:
    with _http_tunnel(bastion, tls_target.port).connect() as conn:
        with pytest.raises(httpx.HTTPError) as caught:
            response = conn.client.get(url.format(port=tls_target.port, local=conn.local_port))
            response.raise_for_status()
    assert "403" in str(caught.value)
    assert bastion[0].destinations == []


def _s3_head(bastion: t.Any, port: int, auth: IAMAuthProfile) -> None:
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=f"https://{TARGET}:{port}", REGION="us-east-1")
    with create_tunnelled_connection(bastion[1], _BASTION_AUTH, profile, auth, TARGET, port).connect() as conn:
        conn.client.head_bucket(Bucket="reports")


@pytest.fixture
def aws_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "aws_config"
    config.write_text("[profile plain]\nregion = us-east-1\naws_access_key_id = AKIAY\naws_secret_access_key = s\n")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))


@pytest.mark.parametrize("auth", [
    lambda: IAMAuthProfile(ACCESS_KEY_ID="AKIAX", SECRET_ACCESS_KEY="secret"),
    lambda: IAMAuthProfile(PROFILE_NAME="plain"),
], ids=["static_keys", "session_envelope"])
def test_s3_over_https_keeps_endpoint_identity(bastion, tls_target, aws_profile, auth) -> None:
    tls_target.seen.clear()
    _s3_head(bastion, tls_target.port, auth())
    assert tls_target.seen == [("HEAD", "/reports", f"{TARGET}:{tls_target.port}", TARGET)]


@pytest.mark.parametrize("variable", ["NO_PROXY", "HTTPS_PROXY"])
def test_environment_proxy_settings_do_not_bypass_tunnel(bastion, tls_target, monkeypatch, variable) -> None:
    # target.test resolves only on the bastion, and 127.0.0.1:9 accepts nothing:
    # success proves the tunnel carried both clients.
    monkeypatch.setenv(variable, TARGET if variable == "NO_PROXY" else "http://127.0.0.1:9")
    with _http_tunnel(bastion, tls_target.port).connect() as conn:
        assert conn.client.get(f"https://{TARGET}:{tls_target.port}/x").status_code == 200
    _s3_head(bastion, tls_target.port, IAMAuthProfile(ACCESS_KEY_ID="AKIAX", SECRET_ACCESS_KEY="secret"))


def test_base_url_path_prefix_survives(bastion, tls_target) -> None:
    class PrefixedProfile(HTTPStorageProfile):
        def emit(self, family: t.Any, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
            return {**super().emit(family, *args, **kwargs), "base_url": f"https://{TARGET}:{tls_target.port}/prefix/"}

    tls_target.seen.clear()
    connection = create_tunnelled_connection(
        bastion[1], _BASTION_AUTH, PrefixedProfile(), None, TARGET, tls_target.port,
    )
    with connection.connect() as conn:
        assert conn.client.get("x").status_code == 200
    assert tls_target.seen == [("GET", "/prefix/x", f"{TARGET}:{tls_target.port}", TARGET)]


def test_plain_http_connection_carries_one_request(bastion, plain_target) -> None:
    # Clients that pool plain-HTTP proxy connections by proxy rather than by
    # destination (urllib3's ProxyManager) would send a second host's request
    # down the checked connection; the listener forces Connection: close.
    plain_target.seen.clear()
    first = f"GET http://{TARGET}:{plain_target.port}/first HTTP/1.1\r\nHost: {TARGET}\r\n\r\n"
    second = "POST http://other.test/private HTTP/1.1\r\nHost: other.test\r\nContent-Length: 6\r\n\r\nsecret"
    with _http_tunnel(bastion, plain_target.port).connect() as conn:
        assert conn.local_port is not None
        with socket.create_connection(("127.0.0.1", conn.local_port), timeout=5) as raw:
            raw.sendall(first.encode())
            response = b""
            while b"payload" not in response:
                response += raw.recv(4096)
            try:
                raw.sendall(second.encode())
                assert raw.recv(4096) == b""
            except (BrokenPipeError, ConnectionResetError):
                pass
    assert [path for _, path, _, _ in plain_target.seen] == [f"http://{TARGET}:{plain_target.port}/first"]


def test_ipv6_destination_matches_as_httpx_sends_it(bastion, plain_target) -> None:
    connection = create_tunnelled_connection(
        bastion[1], _BASTION_AUTH, HTTPStorageProfile(), None, "::1", plain_target.port,
    )
    with connection.connect() as conn:
        assert conn.client.get(f"http://[::1]:{plain_target.port}/v6").status_code == 200
        assert conn.local_port is not None
        for authority in (f"::1:{plain_target.port}", f"[::1]:{plain_target.port}"):
            with socket.create_connection(("127.0.0.1", conn.local_port), timeout=5) as raw:
                raw.sendall(f"CONNECT {authority} HTTP/1.1\r\n\r\n".encode())
                assert raw.recv(1024).startswith(b"HTTP/1.1 200 Connection established")



@pytest.mark.parametrize("head", [
    b"CONNECT " + b"a" * (70 * 1024),
    b"CONNECT " + TARGET.encode() + b":1 HTTP/1.1\r\nX-Pad: " + b"a" * (64 * 1024) + b"\r\n\r\n",
    b"CONNECT [" + TARGET.encode() + b":1 HTTP/1.1\r\n\r\n",
    b"CONNECT\r\n\r\n",
], ids=["unterminated", "terminated_oversized", "bad_authority", "no_target"])
def test_bad_request_head_is_refused_without_channel(bastion, tls_target, head) -> None:
    conn = _http_tunnel(bastion, tls_target.port).connect()
    try:
        assert conn.local_port is not None
        with socket.create_connection(("127.0.0.1", conn.local_port), timeout=5) as raw:
            raw.sendall(head)
            assert raw.recv(1024).startswith(b"HTTP/1.1 400 Bad Request\r\n")
        assert bastion[0].destinations == []
    finally:
        conn.disconnect()


def _sftp_tunnel(bastion: t.Any, target: SFTPTarget, known_hosts: Path) -> TunnelledConnection:
    profile = SFTPStorageProfile(
        HOST=TARGET, PORT=target.port, USERNAME="u",
        KNOWN_HOSTS_FILE=str(known_hosts), LOOK_FOR_KEYS=False, ALLOW_AGENT=False,
    )
    return create_tunnelled_connection(bastion[1], _BASTION_AUTH, profile, _BASTION_AUTH, TARGET, target.port)


def test_sftp_checks_real_target_host_key(bastion, sftp_target, tmp_path) -> None:
    known = tmp_path / "known_hosts"
    known.write_text(sftp_target.known_hosts_line(TARGET))
    with _sftp_tunnel(bastion, sftp_target, known).connect() as conn:
        assert conn.client.listdir(".") == ["remote.csv"]


@pytest.mark.parametrize("entry", ["other_key", "local_address_only"])
def test_sftp_refuses_unknown_target_key(bastion, sftp_target, tmp_path, entry) -> None:
    import paramiko

    known = tmp_path / "known_hosts"
    if entry == "other_key":
        other = paramiko.ECDSAKey.generate()
        known.write_text(f"[{TARGET}]:{sftp_target.port} {other.get_name()} {other.get_base64()}\n")
    else:
        known.write_text(sftp_target.known_hosts_line("127.0.0.1"))
    connection = _sftp_tunnel(bastion, sftp_target, known)
    with pytest.raises(TransportConnectionError):
        connection.connect()
    assert connection.client is None
