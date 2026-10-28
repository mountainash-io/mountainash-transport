"""URL userinfo (credentials) must never leak through HTTP errors or attributes."""
from __future__ import annotations

import httpx
import pytest

from mountainash_transport._core.exceptions import StorageError
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import HttpTransportError
from mountainash_transport._core.http.policy import RedirectPolicy, RequestPolicy, RetryPolicy
from mountainash_transport._core.http.redact import redact_userinfo

SECRET = "s3cr3t-sentinel-pw"
URL = f"https://alice:{SECRET}@example.com/data/file.bin"
_NO_RETRY = RequestPolicy(retry=RetryPolicy(max_attempts=1, retry_on_transport=False))
_NO_REDIRECT = RequestPolicy(
    retry=RetryPolicy(max_attempts=1, retry_on_transport=False),
    redirect=RedirectPolicy(follow_redirects=False),
)


def _assert_clean(exc: BaseException) -> None:
    assert SECRET not in repr(exc)
    assert SECRET not in str(exc)
    assert SECRET not in repr(exc.__dict__)


def _engine(handler) -> HttpRequestEngine:
    return HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(handler)), policy=_NO_RETRY)


def _backend(handler):
    import mountainash_transport.storage.backends  # noqa: F401
    from mountainash_transport.storage.backends.http import HTTPStorageBackend

    return HTTPStorageBackend(None, engine=_engine(handler))


def test_redact_userinfo_helper():
    assert redact_userinfo(URL) == "https://***@example.com/data/file.bin"
    assert redact_userinfo("see https://u@h/x and http://a:b@h2") == "see https://***@h/x and http://***@h2"
    assert redact_userinfo("https://example.com/a@b") == "https://example.com/a@b"


@pytest.mark.parametrize("status", [404, 500, 302])
def test_engine_request_errors_redact_userinfo(status):
    engine = _engine(lambda r: httpx.Response(status, headers={"location": "/x"} if status == 302 else {}))
    with pytest.raises(HttpTransportError) as ei:
        engine.request("GET", URL, policy=_NO_REDIRECT)
    _assert_clean(ei.value)


def test_engine_stream_error_redacts_userinfo():
    engine = _engine(lambda r: httpx.Response(500))
    with pytest.raises(HttpTransportError) as ei:
        with engine.stream("GET", URL):
            pass
    _assert_clean(ei.value)
    assert ei.value.url == "https://***@example.com/data/file.bin"


def test_engine_transport_error_redacts_userinfo():
    def handler(request):
        raise httpx.ConnectError(f"connect failed for {request.url}", request=request)

    with pytest.raises(HttpTransportError) as ei:
        _engine(handler).request("GET", URL)
    _assert_clean(ei.value)


def test_response_url_attributes_redacted():
    engine = _engine(lambda r: httpx.Response(200, content=b"ok"))
    resp = engine.request("GET", URL)
    assert SECRET not in resp.url
    with engine.stream("GET", URL) as s:
        assert SECRET not in s.url


@pytest.mark.parametrize("status", [404, 401, 403, 500])
def test_storage_backend_errors_redact_userinfo(status):
    with pytest.raises(StorageError) as ei:
        _backend(lambda r: httpx.Response(status)).read_to_bytes(URL)
    _assert_clean(ei.value)
    assert SECRET not in repr(ei.value.__cause__.__dict__)


def test_storage_backend_connection_error_redacts_userinfo():
    def handler(request):
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    with pytest.raises(StorageError) as ei:
        _backend(handler).read_to_bytes(URL)
    _assert_clean(ei.value)


def test_storage_backend_invalid_content_length_redacts_userinfo():
    backend = _backend(lambda r: httpx.Response(200, headers={"content-length": "abc"}))
    with pytest.raises(StorageError) as ei:
        backend.get_metadata(URL)
    _assert_clean(ei.value)
