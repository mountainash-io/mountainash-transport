"""One replay rule for request bodies (#4, #58).

bytes and seekable streams are re-sent from their starting position for every
kind of re-send; a non-seekable stream is sent once and never re-sent.

Re-sends are exercised against a real loopback server: httpx's MockTransport
reads (buffers) every request body, which would hide whether a stream can be
sent twice.
"""
from __future__ import annotations

import io
import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpx
import pytest

from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpConnectionError,
    HttpRateLimitError,
    HttpRequestError,
    HttpServiceUnavailableError,
)
from mountainash_transport._core.http.policy import RedirectPolicy, RequestPolicy, RetryPolicy

BODY = b"0123456789" * 1000
FIRST_STATUS = {"429": 429, "503": 503, "401": 401, "307": 307}
FAILURES = [*FIRST_STATUS, "transport"]
NON_SEEKABLE_ERROR = {
    "429": HttpRateLimitError, "503": HttpServiceUnavailableError, "transport": HttpConnectionError,
    "401": HttpAuthenticationError, "307": HttpRequestError,
}


class OneShot(io.RawIOBase):
    """A readable stream that cannot seek, like a pipe or a decoder."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def read(self, size: int | None = -1) -> bytes:
        return self._data.read(-1 if size is None else size)


class Refreshing:
    def __init__(self) -> None:
        self.token = "old"

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return kwargs

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def refresh(self) -> bool:
        self.token = "new"
        return True


def _body(kind: str) -> dict[str, t.Any]:
    if kind == "bytes":
        return {"content": BODY}
    if kind == "seekable":
        return {"stream": io.BytesIO(BODY)}
    if kind == "seekable_offset":
        stream = io.BytesIO(b"skip" + BODY)
        stream.seek(4)  # sending starts where the caller left the stream
        return {"stream": stream}
    return {"stream": OneShot(BODY)}


class Server:
    """Records each request's body and headers; answers the first request with ``first``."""

    def __init__(self) -> None:
        self.first = 200
        self.bodies: list[bytes] = []
        self.headers: list[dict[str, str]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_PUT(self) -> None:
                if self.headers.get("Transfer-Encoding") == "chunked":
                    body = b""
                    while size := int(self.rfile.readline().strip(), 16):
                        body += self.rfile.read(size)
                        self.rfile.readline()
                    self.rfile.readline()
                else:
                    body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                server.bodies.append(body)
                server.headers.append({key.lower(): value for key, value in self.headers.items()})
                status = server.first if len(server.bodies) == 1 else 200
                self.send_response(status)
                if status == 307:
                    self.send_header("Location", "/moved")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args: t.Any) -> None:
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}/upload"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def reset(self, first: int) -> None:
        self.first, self.bodies, self.headers = first, [], []

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


@pytest.fixture(scope="module")
def server() -> t.Iterator[Server]:
    running = Server()
    yield running
    running.close()


def _engine(failure: str, sent: list[bytes]) -> HttpRequestEngine:
    policy = RequestPolicy(retry=RetryPolicy(max_attempts=3, backoff_jitter=False),
                           redirect=RedirectPolicy(follow_redirects=True))
    auth = Refreshing() if failure == "401" else None
    if failure != "transport":
        return HttpRequestEngine(httpx.Client(), policy=policy, auth_strategy=auth)

    def refuse_first(request: httpx.Request) -> httpx.Response:
        sent.append(b"".join(t.cast(t.Iterable[bytes], request.stream)))
        if len(sent) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200)

    return HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(refuse_first)), policy=policy)


def _sent(server: Server, failure: str, sent: list[bytes]) -> list[bytes]:
    return sent if failure == "transport" else server.bodies


@pytest.mark.parametrize("failure", FAILURES)
@pytest.mark.parametrize("kind", ["bytes", "seekable", "seekable_offset"])
@patch("mountainash_transport._core.http.engine.time.sleep")
def test_replayable_bodies_are_resent_whole_for_every_resend(
    _sleep: t.Any, server: Server, kind: str, failure: str,
) -> None:
    server.reset(FIRST_STATUS.get(failure, 200))
    sent: list[bytes] = []
    response = _engine(failure, sent).request("PUT", server.url, **_body(kind))
    assert response.status_code == 200
    assert _sent(server, failure, sent) == [BODY, BODY]


@pytest.mark.parametrize("failure", FAILURES)
@patch("mountainash_transport._core.http.engine.time.sleep")
def test_non_seekable_body_is_sent_once(_sleep: t.Any, server: Server, failure: str) -> None:
    server.reset(FIRST_STATUS.get(failure, 200))
    sent: list[bytes] = []
    with pytest.raises(NON_SEEKABLE_ERROR[failure]):
        _engine(failure, sent).request("PUT", server.url, **_body("non_seekable"))
    assert _sent(server, failure, sent) == [BODY]


@pytest.mark.parametrize("kind, framing", [
    ("seekable", ("content-length", str(len(BODY)))),
    ("seekable_offset", ("content-length", str(len(BODY)))),
    ("non_seekable", ("transfer-encoding", "chunked")),
])
def test_stream_bodies_are_framed_without_buffering(server: Server, kind: str, framing: tuple[str, str]) -> None:
    server.reset(200)
    HttpRequestEngine(httpx.Client()).request("PUT", server.url, **_body(kind))
    name, value = framing
    assert server.headers[0][name] == value
    assert server.bodies == [BODY]
