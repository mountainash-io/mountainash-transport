"""S3 presigned URLs (#10 §2): SigV4 for every flavor, method and Content-Type signed, refusals before signing."""
from __future__ import annotations

import datetime as dt
import typing as t
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from mountainash_auth_client import IAMAuthProfile

from mountainash_transport import StorageFacade, UnsupportedOperationError
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.settings.storage.profiles import S3StorageProfile

AUTH = IAMAuthProfile(ACCESS_KEY_ID="AKIDEXAMPLE", SECRET_ACCESS_KEY="secret")
NOW = dt.datetime(2026, 11, 22, 10, 0, 0)


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("botocore.auth.get_current_datetime", lambda: NOW)


def _query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def _resign(url: str, method: str, region: str, headers: dict[str, str]) -> str:
    """X-Amz-Signature that botocore's own SigV4 query signer gives the same request."""
    from botocore.auth import S3SigV4QueryAuth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials

    parts = urlsplit(url)
    expires = int(_query(url)["X-Amz-Expires"])
    request = AWSRequest(method=method, url=f"{parts.scheme}://{parts.netloc}{parts.path}", headers=headers)
    S3SigV4QueryAuth(Credentials("AKIDEXAMPLE", "secret"), "s3", region, expires=expires).add_auth(request)
    return _query(str(request.url))["X-Amz-Signature"]


FLAVORS = [
    ("aws", S3StorageProfile(FLAVOR="aws", REGION="us-east-1", BUCKET="reports"), P.S3,
     "s3://reports/2026/sales.csv", "reports.s3.amazonaws.com", "us-east-1"),
    ("r2", S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="acct123", BUCKET="reports"), P.R2,
     "s3://reports/2026/sales.csv", "acct123.r2.cloudflarestorage.com", "auto"),
    ("minio", S3StorageProfile(FLAVOR="minio", ENDPOINT_URL="http://127.0.0.1:9000", BUCKET="reports"), P.MINIO,
     "s3://reports/2026/sales.csv", "127.0.0.1:9000", "us-east-1"),
    ("b2", S3StorageProfile(FLAVOR="b2", REGION="us-west-004", BUCKET="reports"), P.B2,
     "s3://reports/2026/sales.csv", "s3.us-west-004.backblazeb2.com", "us-west-004"),
]


@pytest.mark.parametrize(("flavor", "profile", "provider", "path", "host", "region"), FLAVORS,
                         ids=[f[0] for f in FLAVORS])
def test_each_flavor_signs_sigv4_for_its_own_host(
    flavor: str, profile: S3StorageProfile, provider: t.Any, path: str, host: str, region: str,
) -> None:
    with StorageFacade(provider, profile, auth_profile=AUTH) as s3:
        url = s3.presign(path, expires_in=900)
    query = _query(url)
    assert host in urlsplit(url).netloc
    assert query["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert query["X-Amz-Expires"] == "900"
    assert f"/{region}/s3/aws4_request" in query["X-Amz-Credential"]


def test_s3_express_signs_with_a_session_from_create_session() -> None:
    from botocore.stub import Stubber

    bucket = "reports--use1-az4--x-s3"
    profile = S3StorageProfile(FLAVOR="express", REGION="us-east-1", BUCKET=bucket)
    with StorageFacade(P.S3EXPRESS, profile, auth_profile=AUTH) as s3:
        client = s3._backend._client
        with Stubber(client) as stub:
            stub.add_response("create_session", {"Credentials": {
                "AccessKeyId": "ASIASESSION", "SecretAccessKey": "s", "SessionToken": "token",
                "Expiration": dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)}})
            url = s3.presign(f"s3://{bucket}/sales.csv", expires_in=60)
            stub.assert_no_pending_responses()
    query = _query(url)
    assert "s3express-use1-az4.us-east-1.amazonaws.com" in urlsplit(url).netloc
    assert query["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert query["X-Amz-Credential"].startswith("ASIASESSION/")  # the session's key, not the base key
    assert query["X-Amz-Expires"] == "60"


def test_s3_express_session_denial_is_a_permission_error() -> None:
    from botocore.stub import Stubber

    from mountainash_transport import PermissionDeniedError

    bucket = "reports--use1-az4--x-s3"
    profile = S3StorageProfile(FLAVOR="express", REGION="us-east-1", BUCKET=bucket)
    with StorageFacade(P.S3EXPRESS, profile, auth_profile=AUTH) as s3:
        with Stubber(s3._backend._client) as stub, pytest.raises(PermissionDeniedError):
            stub.add_client_error("create_session", service_error_code="AccessDenied", http_status_code=403)
            s3.presign(f"s3://{bucket}/sales.csv")


@pytest.fixture
def aws() -> t.Iterator[StorageFacade]:
    profile = S3StorageProfile(FLAVOR="aws", REGION="eu-west-1", BUCKET="reports")
    with StorageFacade(P.S3, profile, auth_profile=AUTH) as s3:
        yield s3


@pytest.mark.parametrize("key", ["2026/sales.csv", "a b+c.csv", "rapport-été.csv"])
@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_the_signature_covers_the_method_and_the_object(
    aws: StorageFacade, method: t.Literal["GET", "PUT"], key: str,
) -> None:
    url = aws.presign(f"s3://reports/{key}", method=method)
    host = urlsplit(url).netloc
    assert urlsplit(url).path == "/" + quote(key, safe="/~")
    signature = _query(url)["X-Amz-Signature"]
    assert _resign(url, method, "eu-west-1", {"host": host}) == signature
    other = "PUT" if method == "GET" else "GET"
    assert _resign(url, other, "eu-west-1", {"host": host}) != signature


@pytest.mark.parametrize("content_type", ["text/csv", ""])
def test_a_put_content_type_is_signed_so_the_uploader_must_send_it(aws: StorageFacade, content_type: str) -> None:
    url = aws.presign("s3://reports/sales.csv", method="PUT", content_type=content_type)
    host = urlsplit(url).netloc
    signature = _query(url)["X-Amz-Signature"]
    assert "content-type" in _query(url)["X-Amz-SignedHeaders"].split(";")
    assert _resign(url, "PUT", "eu-west-1", {"host": host, "content-type": content_type}) == signature
    assert _resign(url, "PUT", "eu-west-1", {"host": host, "content-type": "application/json"}) != signature


@pytest.mark.parametrize(("kwargs", "message"), [
    ({"method": "DELETE"}, "GET' or 'PUT"),
    ({"expires_in": 0}, "between 1 and 604800"),
    ({"expires_in": 604_801}, "between 1 and 604800"),
    ({"content_type": "text/csv"}, "only to method='PUT'"),
    ({"method": "PUT", "content_type": "application/x-www-form-urlencoded; charset=utf-8"}, "cannot be enforced"),
])
def test_refusals_happen_before_signing(aws: StorageFacade, kwargs: dict[str, t.Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        aws.presign("s3://reports/sales.csv", **kwargs)


def test_stores_without_signing_refuse(tmp_path: t.Any) -> None:
    with StorageFacade.for_local() as local, pytest.raises(UnsupportedOperationError):
        local.presign(str(tmp_path / "a.csv"))
    with StorageFacade.from_path("https://example.com/a.csv") as web, pytest.raises(UnsupportedOperationError):
        web.presign("https://example.com/a.csv")
