"""S3 retries belong to botocore; RETRY_MAX_ATTEMPTS sets its attempt count (#5)."""
from __future__ import annotations

import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mountainash_transport.settings.storage.profiles import S3StorageProfile


@pytest.fixture(scope="module")
def unavailable() -> t.Iterator[tuple[str, list[str]]]:
    """An S3 endpoint that answers every request with 503."""
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_HEAD(self) -> None:
            seen.append(self.path)
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args: t.Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", seen
    server.shutdown()
    server.server_close()


def _attempts(profile: S3StorageProfile, seen: list[str]) -> int:
    import boto3
    from botocore.exceptions import ClientError

    kwargs = profile.to_handler_kwargs()
    client = boto3.client(**kwargs, aws_access_key_id="k", aws_secret_access_key="s")
    seen.clear()
    with pytest.raises(ClientError):
        client.head_object(Bucket="b", Key="k")
    return len(seen)


@pytest.fixture(autouse=True)
def no_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("botocore.endpoint.time.sleep", lambda seconds: None)


def test_profile_sets_botocore_total_attempts(unavailable: tuple[str, list[str]]) -> None:
    endpoint, seen = unavailable
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=endpoint, RETRY_MAX_ATTEMPTS=2)
    assert _attempts(profile, seen) == 2


def test_one_attempt_disables_retry(unavailable: tuple[str, list[str]]) -> None:
    endpoint, seen = unavailable
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=endpoint, RETRY_MAX_ATTEMPTS=1)
    assert _attempts(profile, seen) == 1


def test_unset_leaves_retries_to_the_aws_environment(
    unavailable: tuple[str, list[str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint, seen = unavailable
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("AWS_RETRY_MODE", "standard")
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=endpoint)
    assert _attempts(profile, seen) == 4
