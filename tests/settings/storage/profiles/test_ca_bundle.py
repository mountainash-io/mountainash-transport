"""#67: S3 and HTTP profiles can name a private CA bundle (design table)."""
from __future__ import annotations

import ssl
import typing as t
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mountainash_auth_client.targets import TargetFamily
from mountainash_transport.settings.storage.profiles.http_storage_profile import HTTPStorageProfile
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

certifi = pytest.importorskip("certifi")
BUNDLE = certifi.where()


def _s3_flat(**fields: t.Any) -> dict[str, t.Any]:
    out = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", **fields).emit(TargetFamily.BOTO)
    return {k: v for k, v in out.items() if k != "config"}


def test_s3_verify_off_wins_over_bundle():
    assert _s3_flat(VERIFY_SSL=False)["verify"] is False
    assert _s3_flat(VERIFY_SSL=False, CA_BUNDLE=BUNDLE)["verify"] is False


def test_s3_bundle_reaches_botocore_as_path():
    assert _s3_flat(CA_BUNDLE=BUNDLE)["verify"] == BUNDLE


def test_s3_default_leaves_verify_to_botocore():
    # No verify key: botocore then resolves AWS_CA_BUNDLE / the ca_bundle config key.
    assert "verify" not in _s3_flat()


def test_http_verify_off_wins_over_bundle():
    assert HTTPStorageProfile(VERIFY_SSL=False).emit(TargetFamily.HTTP)["verify"] is False
    assert HTTPStorageProfile(VERIFY_SSL=False, CA_BUNDLE=BUNDLE).emit(TargetFamily.HTTP)["verify"] is False


def test_http_default_keeps_httpx_default():
    assert HTTPStorageProfile().emit(TargetFamily.HTTP)["verify"] is True


@pytest.mark.parametrize("as_directory", [False, True])
def test_http_bundle_becomes_ssl_context(tmp_path: Path, as_directory: bool):
    bundle = BUNDLE
    if as_directory:
        # capath directories need OpenSSL hash names; an empty directory is enough to
        # prove the context is built from capath rather than cafile.
        bundle = str(tmp_path)
    verify = HTTPStorageProfile(CA_BUNDLE=bundle).emit(TargetFamily.HTTP)["verify"]
    assert isinstance(verify, ssl.SSLContext)
    assert verify.verify_mode == ssl.CERT_REQUIRED and verify.check_hostname
    stats = verify.cert_store_stats()
    if as_directory:
        assert stats["x509_ca"] == 0
    else:
        assert stats["x509_ca"] > 0


@pytest.mark.parametrize("bundle", [
    "/nonexistent/SENTP/ca.pem",
    "https://SENTU:SENTP@host/\ud800?token=SENTQ#SENTF",   # unencodable: UnicodeEncodeError carries the input
], ids=["missing", "unencodable"])
def test_http_bundle_load_failure_shows_no_input(bundle):
    """W8: a bad CA_BUNDLE fails at connection creation without echoing the value."""
    import traceback
    from mountainash_auth_client import TokenAuthProfile
    from mountainash_transport import create_connection

    with pytest.raises(ValueError) as caught:
        create_connection(HTTPStorageProfile(CA_BUNDLE=bundle), TokenAuthProfile(TOKEN="t"))
    exc = caught.value
    text = "".join(traceback.format_exception(exc)) + repr(exc.args) + repr(vars(exc))
    assert exc.__cause__ is None or (isinstance(exc.__cause__, OSError) and exc.__cause__.filename is None)
    assert exc.__context__ is None
    for sentinel in ("SENTU", "SENTP", "SENTQ", "SENTF"):
        assert sentinel not in text
    assert str(exc).startswith("CA_BUNDLE could not be loaded (")



def test_http_bundle_builds_client_without_deprecation_warning(recwarn):
    import httpx

    with httpx.Client(**HTTPStorageProfile(CA_BUNDLE=BUNDLE).emit(TargetFamily.HTTP)):
        pass
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


@pytest.mark.parametrize(("fields", "expected"), [
    ({}, None),
    ({"CA_BUNDLE": BUNDLE}, BUNDLE),
    ({"VERIFY_SSL": False}, False),
])
def test_s3_connection_passes_verify_only_when_emitted(monkeypatch, fields, expected):
    """Session path and assume-role STS client: no default verify=True."""
    import boto3
    from mountainash_transport.connections.s3 import S3Connection

    client_calls: list[dict[str, t.Any]] = []
    sts_calls: list[dict[str, t.Any]] = []

    class _BotocoreSession:
        def get_credentials(self):
            return object()

        def create_client(self, *args, **kwargs):
            sts_calls.append(kwargs)
            return object()

    class _Session:
        def __init__(self, **kwargs):
            self._session = _BotocoreSession()

        def client(self, service, **kwargs):
            client_calls.append(kwargs)
            return MagicMock()  # stands in for an S3 client; the connection installs its hooks on it

    class _Fetcher:
        def __init__(self, client_creator, **kwargs):
            client_creator("sts")

        def fetch_credentials(self):
            return {}

    monkeypatch.setattr(boto3, "Session", _Session)
    import botocore.credentials
    monkeypatch.setattr(botocore.credentials, "AssumeRoleCredentialFetcher", _Fetcher)
    import botocore.session
    monkeypatch.setattr(botocore.session, "get_session", lambda: type("S", (), {"set_config_variable": lambda *a: None})())

    flat = _s3_flat(**fields)
    for role_arn in (None, "arn:aws:iam::1:role/r"):
        client_calls.clear()
        sts_calls.clear()
        env = {"session": {"region_name": "us-east-1"}, "client_config": dict(flat)}
        if role_arn:
            env["role_arn"] = role_arn
        S3Connection(env).connect()
        assert client_calls[-1].get("verify", None) == expected
        assert ("verify" in client_calls[-1]) is (expected is not None)
        if role_arn:
            assert sts_calls[0].get("verify", None) == expected
            assert ("verify" in sts_calls[0]) is (expected is not None)
