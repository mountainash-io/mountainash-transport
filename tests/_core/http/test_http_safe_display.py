"""HTTP errors, response values and logs show only known-safe parts of a location (W8)."""
from __future__ import annotations

import logging
import socket
import traceback
import typing as t

import httpx
import pytest

from mountainash_transport._core.exceptions import StorageConnectionError, StorageError
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import HttpTransportError
from mountainash_transport._core.http.policy import RedirectPolicy, RequestPolicy, RetryPolicy

SENT = ("SENTU", "SENTP", "SENTQ", "SENTF")
URL = "https://SENTU:SENTP@example.com/data/file.bin?sig=SENTQ#SENTF"
SHOWN = "https://example.com/data/file.bin"
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
    text = "".join(traceback.format_exception(exc))
    for link in _chain(exc):
        text += str(link) + repr(link) + repr(link.args) + repr(vars(link))
    for sentinel in SENT:
        assert sentinel not in text, f"{sentinel} in {text[:300]}"


def _engine(handler) -> HttpRequestEngine:
    return HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(handler)), policy=_NO_RETRY)


def _backend(handler):
    import mountainash_transport.storage.backends  # noqa: F401
    from mountainash_transport.storage.backends.http import HTTPStorageBackend

    return HTTPStorageBackend(None, engine=_engine(handler))


@pytest.mark.parametrize("status", [404, 500, 302])
@pytest.mark.parametrize("mode", ["buffered", "stream"])
def test_engine_status_errors_show_display_form(status, mode):
    engine = _engine(lambda r: httpx.Response(status, headers={"location": "/x"} if status == 302 else {}))
    with pytest.raises(HttpTransportError) as ei:
        if mode == "buffered":
            engine.request("GET", URL, policy=_NO_REDIRECT)
        else:
            with engine.stream("GET", URL, policy=_NO_REDIRECT):
                pass
    assert SHOWN in str(ei.value)
    if status != 302:
        assert ei.value.url == SHOWN
    _assert_clean(ei.value)


@pytest.mark.parametrize("mode", ["buffered", "stream"])
@pytest.mark.parametrize("error_type", [httpx.InvalidURL, httpx.ConnectError, httpx.ReadTimeout, httpx.UnsupportedProtocol])
def test_engine_transport_errors_show_class_name_only(mode, error_type):
    def handler(request):
        raise error_type(f"boom {URL}", request=request) if error_type is not httpx.InvalidURL else error_type(f"boom {URL}")
    engine = _engine(handler)
    with pytest.raises(HttpTransportError) as ei:
        if mode == "buffered":
            engine.request("GET", URL)
        else:
            with engine.stream("GET", URL):
                pass
    assert str(ei.value).startswith(f"{SHOWN}: ") and error_type.__name__ in str(ei.value)
    assert ei.value.__cause__ is None and ei.value.__context__ is None
    _assert_clean(ei.value)


@pytest.mark.parametrize("mode", ["buffered", "stream"])
def test_response_error_headers_allowlist(mode):
    headers = [("set-cookie", "s=SENTP"), ("authorization", "Bearer SENTP"), ("x-amz-id-2", "SENTQ"),
               ("location", "https://SENTU:SENTP@h/next?sig=SENTQ#SENTF"), ("etag", '"v1"'),
               ("www-authenticate", 'Bearer realm="api"'), ("content-type", "text/plain")]
    engine = _engine(lambda r: httpx.Response(401, headers=headers))
    with pytest.raises(HttpTransportError) as ei:
        if mode == "buffered":
            engine.request("GET", "https://h/x")
        else:
            with engine.stream("GET", "https://h/x"):
                pass
    assert ei.value.headers == {"location": "https://h/next", "etag": '"v1"',
                                "www-authenticate": "Bearer", "content-type": "text/plain"}
    _assert_clean(ei.value)


@pytest.mark.parametrize("status", [400, 500])
def test_engine_error_does_not_carry_response_body(status):
    engine = _engine(lambda r: httpx.Response(status, text="denied: token=SENTP"))
    with pytest.raises(HttpTransportError) as ei:
        engine.request("GET", "https://example.com/x")
    _assert_clean(ei.value)


def test_success_values_drop_userinfo_keep_query():
    presigned = "https://SENTU:SENTP@h/x.csv?X-Amz-Signature=abc#frag"
    expected = "https://h/x.csv?X-Amz-Signature=abc#frag"
    engine = _engine(lambda r: httpx.Response(200, headers={"content-length": "3"}, content=b"abc"))
    assert engine.request("GET", presigned).url == expected
    with engine.stream("GET", presigned) as response:
        assert response.url == expected
    assert _backend(lambda r: httpx.Response(200, headers={"content-length": "3"})).get_metadata(presigned).path == expected


def _assert_logs_clean(caplog) -> None:
    for record in caplog.records:
        message = record.getMessage()
        for sentinel in SENT:
            assert sentinel not in message, f"{record.name}: {message}"


def test_httpx_and_httpcore_logs_carry_no_location(caplog, library_loggers_debug):
    caplog.set_level(logging.DEBUG)
    engine = _engine(lambda r: httpx.Response(200, content=b"x"))
    engine.request("GET", URL)
    _assert_logs_clean(caplog)


def test_httpx_and_httpcore_logs_carry_no_location_on_real_socket(caplog, library_loggers_debug):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    url = f"http://SENTU:SENTP@127.0.0.1:{port}/data/file.bin?sig=SENTQ#SENTF"
    caplog.set_level(logging.DEBUG)
    with httpx.Client() as client:
        with pytest.raises(HttpTransportError) as ei:
            HttpRequestEngine(client, policy=_NO_RETRY).request("GET", url)
    _assert_logs_clean(caplog)
    _assert_clean(ei.value)


def test_http_backend_errors_show_display_form():
    backend = _backend(lambda r: httpx.Response(404))
    with pytest.raises(StorageError) as ei:
        backend.read_to_bytes(URL)
    assert str(ei.value) == SHOWN
    _assert_clean(ei.value)


@pytest.mark.parametrize("value", ["abc", URL])
def test_invalid_content_length_shows_display_form(value):
    backend = _backend(lambda r: httpx.Response(200, headers={"content-length": value}))
    with pytest.raises(StorageError) as ei:
        backend.get_metadata(URL)
    assert str(ei.value) == f"{SHOWN}: invalid Content-Length"
    _assert_clean(ei.value)


@pytest.mark.parametrize("fault", ["read", "close", "range"])
@pytest.mark.parametrize("sensitive", [False, True])
def test_deferred_failures_preserve_classification_without_leaking(fault: str, sensitive: bool) -> None:
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
def test_stream_error_response_close_failure_is_clean(status: int) -> None:
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


def _error_headers(mode, headers, url="https://h/dir/x"):
    engine = _engine(lambda r: httpx.Response(404, headers=headers))
    with pytest.raises(HttpTransportError) as ei:
        if mode == "buffered":
            engine.request("GET", url)
        else:
            with engine.stream("GET", url):
                pass
    _assert_clean(ei.value)
    return ei.value.headers


@pytest.mark.parametrize("mode", ["buffered", "stream"])
@pytest.mark.parametrize("value, expected", [
    ('Bearer realm="api", error_uri="https://SENTU:SENTP@h/x?sig=SENTQ#SENTF"', "Bearer"),
    ('Basic realm="x", Bearer', "Basic, Bearer"),
    ('Negotiate SENTP, Basic realm="a, SENTQ"', "Negotiate, Basic"),
])
def test_www_authenticate_keeps_only_schemes(mode, value, expected):
    assert _error_headers(mode, {"www-authenticate": value}) == {"www-authenticate": expected}


@pytest.mark.parametrize("mode", ["buffered", "stream"])
@pytest.mark.parametrize("name", ["location", "content-location"])
@pytest.mark.parametrize("value, expected", [
    ("/next?sig=SENTQ#SENTF", "https://h/next"),
    ("other?sig=SENTQ#SENTF", "https://h/dir/other"),
    ("//SENTU:SENTP@o/p?sig=SENTQ", "https://o/p"),
    ("https://SENTU:SENTP@o/p?sig=SENTQ#SENTF", "https://o/p"),
    ("https://SENTU:SENTP@[bad]/next?sig=SENTQ#SENTF", "https://[bad]/next"),
    ("//SENTU:SENTP@[bad]/next?sig=SENTQ#SENTF", "//[bad]/next"),
    ("ht\ttps://SENTU:SENTP@[bad]/x?sig=SENTQ#SENTF", "https://[bad]/x"),
    ("\x00https://SENTU:SENTP@[bad]/x?sig=SENTQ#SENTF", "https://[bad]/x"),
])
def test_location_headers_resolved_then_displayed(mode, name, value, expected):
    assert _error_headers(mode, {name: value}) == {name: expected}


def test_relative_location_without_base_shows_only_path():
    from mountainash_transport._core.http.errors import HttpResponseError

    for value, expected in [("/next?sig=SENTQ#SENTF", "/next"), ("//SENTU:SENTP@o/p?sig=SENTQ", "//o/p"),
                            ("a/b#SENTF", "a/b"),
                            ("https://SENTU:SENTP@[bad]/n?sig=SENTQ#SENTF", "https://[bad]/n"),
                            ("ht\ttps://SENTU:SENTP@[bad]/x?sig=SENTQ#SENTF", "https://[bad]/x"),
                            ("\x00https://SENTU:SENTP@[bad]/x?sig=SENTQ#SENTF", "https://[bad]/x")]:
        error = HttpResponseError("x", headers={"location": value})
        assert error.headers == {"location": expected}
