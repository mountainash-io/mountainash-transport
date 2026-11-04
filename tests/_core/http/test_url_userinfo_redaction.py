"""URL credentials (userinfo, query values) must never leak through HTTP errors or attributes."""
from __future__ import annotations

import traceback
import typing as t

import httpx
import pytest

from mountainash_transport._core.exceptions import StorageConnectionError, StorageError
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import HttpTransportError
from mountainash_transport._core.http.policy import RedirectPolicy, RequestPolicy, RetryPolicy
from mountainash_transport._core.redact import redact_url, redact_userinfo

SECRET = "s3cr3t-sentinel-pw"
URL = f"https://alice:{SECRET}@example.com/data/file.bin"
QUERY_URL = f"https://example.com/data/file.bin?sig={SECRET}&X-Amz-Expires=60"
AT_URL = f"https://alice:pa@{SECRET}@example.com/data/file.bin"  # raw "@" inside the password
ERROR_URLS = [URL, QUERY_URL, AT_URL]
_NO_RETRY = RequestPolicy(retry=RetryPolicy(max_attempts=1, retry_on_transport=False))
_NO_REDIRECT = RequestPolicy(
    retry=RetryPolicy(max_attempts=1, retry_on_transport=False),
    redirect=RedirectPolicy(follow_redirects=False),
)


def _chain(exc: BaseException) -> t.Iterator[BaseException]:
    """Every exception reachable through __cause__ and __context__, displayed or not."""
    pending, seen = [exc], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)


def _assert_clean(exc: BaseException) -> None:
    assert SECRET not in "".join(traceback.format_exception(exc))
    for link in _chain(exc):
        for text in (str(link), repr(link), repr(link.args), repr(vars(link))):
            assert SECRET not in text, f"{type(link).__name__} carries the secret: {text[:200]}"


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
    assert redact_userinfo(AT_URL) == "https://***@example.com/data/file.bin"
    assert redact_userinfo("https://a@b:c@d@h/x?q=e@f") == "https://***@h/x?q=e@f"


def test_redaction_regexes_are_linear():
    import time

    for text in ("a" * 200_000, "a://" + "b" * 200_000, ("x://" + "@" * 50) * 4_000):
        started = time.perf_counter()
        redact_url(text)
        assert time.perf_counter() - started < 1.0


def test_redact_url_helper():
    assert redact_url(URL) == "https://***@example.com/data/file.bin"
    assert redact_url(QUERY_URL) == "https://example.com/data/file.bin?sig=***&X-Amz-Expires=***"
    assert redact_url(f"HTTP 404 GET https://u:p@h/x?{SECRET}#f") == "HTTP 404 GET https://***@h/x?***#f"
    assert redact_url("https://h/x?") == "https://h/x?"
    assert redact_url("no url ?a=b") == "no url ?a=b"


@pytest.mark.parametrize("url", ERROR_URLS)
@pytest.mark.parametrize("status", [404, 500, 302])
def test_engine_request_errors_redact_userinfo(status, url):
    engine = _engine(lambda r: httpx.Response(status, headers={"location": "/x"} if status == 302 else {}))
    with pytest.raises(HttpTransportError) as ei:
        engine.request("GET", url, policy=_NO_REDIRECT)
    _assert_clean(ei.value)


@pytest.mark.parametrize("url", ERROR_URLS)
def test_engine_stream_error_redacts_userinfo(url):
    engine = _engine(lambda r: httpx.Response(500))
    with pytest.raises(HttpTransportError) as ei:
        with engine.stream("GET", url):
            pass
    _assert_clean(ei.value)
    assert ei.value.url == redact_url(url)


@pytest.mark.parametrize("status", [400, 500])
def test_engine_error_does_not_carry_response_body(status):
    engine = _engine(lambda r: httpx.Response(status, text=f"denied: token={SECRET}"))
    with pytest.raises(HttpTransportError) as ei:
        engine.request("GET", "https://example.com/x")
    _assert_clean(ei.value)


@pytest.mark.parametrize("mode", ["buffered", "stream"])
def test_engine_error_redacts_credential_headers_keeps_others(mode):
    headers = [("set-cookie", f"session={SECRET}; HttpOnly"), ("set-cookie", f"csrf={SECRET}"),
               ("etag", '"v1"'), ("www-authenticate", 'Bearer realm="api"')]
    engine = _engine(lambda r: httpx.Response(401, headers=headers))
    with pytest.raises(HttpTransportError) as ei:
        if mode == "buffered":
            engine.request("GET", "https://example.com/x")
        else:
            with engine.stream("GET", "https://example.com/x"):
                pass
    _assert_clean(ei.value)
    assert ei.value.headers["set-cookie"] == "***"
    assert ei.value.headers["etag"] == '"v1"'
    assert ei.value.headers["www-authenticate"] == 'Bearer realm="api"'


@pytest.mark.parametrize("url", ERROR_URLS)
@pytest.mark.parametrize("mode", ["buffered", "stream"])
@pytest.mark.parametrize("error_type", [httpx.InvalidURL, httpx.ConnectError, httpx.ReadTimeout])
def test_engine_transport_error_redacts_userinfo(mode: str, error_type: type[Exception], url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error_type(f"request failed for {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpTransportError) as ei:
            if mode == "buffered":
                engine.request("GET", url)
            else:
                with engine.stream("GET", url):
                    pass
        _assert_clean(ei.value)


def test_response_url_attributes_redacted():
    engine = _engine(lambda r: httpx.Response(200, content=b"ok"))
    resp = engine.request("GET", URL)
    assert SECRET not in resp.url
    with engine.stream("GET", URL) as s:
        assert SECRET not in s.url


@pytest.mark.parametrize("url", ERROR_URLS)
@pytest.mark.parametrize("status", [404, 401, 403, 500])
def test_storage_backend_errors_redact_userinfo(status, url):
    with pytest.raises(StorageError) as ei:
        _backend(lambda r: httpx.Response(status, text=SECRET)).read_to_bytes(url)
    _assert_clean(ei.value)
    assert SECRET not in repr(ei.value.__cause__.__dict__)


@pytest.mark.parametrize("url", ERROR_URLS)
def test_storage_backend_connection_error_redacts_userinfo(url):
    def handler(request):
        raise httpx.ConnectError(f"cannot reach {request.url}", request=request)

    with pytest.raises(StorageError) as ei:
        _backend(handler).read_to_bytes(url)
    _assert_clean(ei.value)


@pytest.mark.parametrize("url", ERROR_URLS)
@pytest.mark.parametrize("value", ["abc", URL])
def test_storage_backend_invalid_content_length_redacts_userinfo(value: str, url: str) -> None:
    backend = _backend(lambda r: httpx.Response(200, headers={"content-length": value}))
    with pytest.raises(StorageError) as ei:
        backend.get_metadata(url)
    _assert_clean(ei.value)


def test_storage_backend_metadata_entry_redacts_userinfo():
    backend = _backend(lambda r: httpx.Response(200, headers={"content-length": "3"}))
    entry = backend.get_metadata(URL)
    assert SECRET not in entry.path
    assert SECRET not in repr(entry)


@pytest.mark.parametrize("fault", ["read", "close", "range"])
@pytest.mark.parametrize("sensitive", [False, True])
def test_deferred_failures_preserve_classification_without_leaking(
    fault: str, sensitive: bool,
) -> None:
    from mountainash_transport.storage.backends.http import HTTPStorageBackend

    url = URL if sensitive else "https://example.com/data/file.bin"
    original = httpx.ReadError(f"read failed for {url}")

    class Body(httpx.SyncByteStream):
        def __iter__(self) -> t.Iterator[bytes]:
            yield b"x"
            if fault != "close":
                raise original

        def close(self) -> None:
            if fault == "close":
                raise original

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("range") == "bytes=0-0":
            return httpx.Response(206, headers={"content-range": "bytes 0-0/3"}, content=b"x")
        headers = {"content-range": "bytes 1-2/3"} if fault == "range" else {}
        return httpx.Response(206 if fault == "range" else 200, headers=headers, stream=Body())

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        backend = HTTPStorageBackend(None, engine=HttpRequestEngine(client, policy=_NO_RETRY))
        with pytest.raises(StorageConnectionError) as ei:
            if fault == "range":
                backend.open_ranged(url).fetch(1, 3)
            else:
                with backend.read_to_stream(url) as stream:
                    if fault == "read":
                        stream.read()
        _assert_clean(ei.value)
        if not sensitive:
            cause = ei.value.__cause__
            assert cause is original or (cause is not None and cause.__cause__ is original)


@pytest.mark.parametrize("source", ["redirect", "cause", "context", "note", "request"])
def test_clean_initial_url_does_not_expose_sensitive_failure(source: str) -> None:
    initial = "https://example.com/start"

    def handler(request: httpx.Request) -> httpx.Response:
        if source in ("redirect", "request") and request.url.path == "/start":
            return httpx.Response(302, headers={"location": URL})
        error = httpx.ConnectError("connection failed", request=request)
        if source in ("cause", "context"):
            try:
                raise OSError(f"failed at {URL}")
            except OSError as native:
                if source == "cause":
                    raise error from native
                raise error
        if source == "note":
            error.add_note(f"failed at {URL}")
        if source == "redirect":
            error = httpx.ConnectError(f"failed at {request.url}", request=request)
        raise error

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(HttpTransportError) as ei:
            HttpRequestEngine(client, policy=_NO_RETRY).request("GET", initial)
        _assert_clean(ei.value)
        assert ei.value.__cause__ is None


@pytest.mark.parametrize("status", [302, 401, 404, 429, 503])
def test_stream_error_response_close_failure_is_redacted(status: int) -> None:
    class Body(httpx.SyncByteStream):
        def __iter__(self) -> t.Iterator[bytes]:
            yield b""

        def close(self) -> None:
            raise httpx.ReadError(f"close failed for {URL}")

    policy = RequestPolicy(
        retry=RetryPolicy(max_attempts=2, backoff_base=0, backoff_jitter=False),
        redirect=RedirectPolicy(follow_redirects=False),
    )
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, stream=Body())
    )) as client:
        with pytest.raises(HttpTransportError) as ei:
            with HttpRequestEngine(client, policy=policy).stream("GET", URL):
                pytest.fail("error response must not yield a stream")
        _assert_clean(ei.value)
