"""httpx/httpcore log records carry no location, whatever level the application sets (W8)."""
from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.http.errors import HttpTransportError
from mountainash_transport._core.http.policy import RequestPolicy, RetryPolicy

SENT = ("SENTU", "SENTP", "SENTQ", "SENTF")
_NO_RETRY = RequestPolicy(retry=RetryPolicy(max_attempts=1, retry_on_transport=False))
HTTPCORE_LOGGERS = ("httpcore.connection", "httpcore.http11", "httpcore.http2", "httpcore.proxy", "httpcore.socks")


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def records():
    names = ("httpx", "httpcore", *HTTPCORE_LOGGERS)
    saved = {n: logging.getLogger(n).level for n in names}
    handler = _Collect()
    root = logging.getLogger()
    root_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("httpcore").setLevel(logging.DEBUG)
    yield handler.records
    root.removeHandler(handler)
    root.setLevel(root_level)
    for n, level in saved.items():
        logging.getLogger(n).setLevel(level)


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            self.send_response(404)
            self.send_header("Set-Cookie", "s=SENTP")
            self.send_header("Location", "http://SENTU:SENTP@127.0.0.1/x?sig=SENTQ#SENTF")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def _messages(records):
    return [r.getMessage() for r in records]


def _assert_clean(records):
    for record in records:
        text = record.getMessage() + repr(record.args) + str(record.msg)
        for sentinel in SENT:
            assert sentinel not in text, f"{record.name}: {text}"


def test_mock_transport_request_line_is_rewritten_not_dropped(records):
    url = "https://SENTU:SENTP@example.com/data/file.bin?sig=SENTQ#SENTF"
    engine = HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x"))))
    engine.request("GET", url)
    _assert_clean(records)
    lines = [m for m in _messages(records) if m.startswith("HTTP Request:")]
    assert lines == ['HTTP Request: GET https://example.com/data/file.bin "HTTP/1.1 200 OK"']


@pytest.mark.parametrize("mode", ["buffered", "stream"])
def test_real_socket_records_carry_no_sentinel(records, server, mode):
    url = f"http://SENTU:SENTP@127.0.0.1:{server}/x.csv?sig=SENTQ#SENTF"
    with httpx.Client() as client:
        engine = HttpRequestEngine(client, policy=_NO_RETRY)
        with pytest.raises(HttpTransportError):
            if mode == "buffered":
                engine.request("GET", url)
            else:
                with engine.stream("GET", url):
                    pass
    _assert_clean(records)
    assert any(r.name.startswith("httpcore.") for r in records), "httpcore never emitted"
    request_lines = [m for m in _messages(records) if m.startswith("HTTP Request:")]
    assert request_lines == [f'HTTP Request: GET http://127.0.0.1:{server}/x.csv "HTTP/1.1 404 Not Found"']


def test_every_emitting_httpcore_logger_is_filtered(records, server):
    with httpx.Client() as client:
        client.get(f"http://127.0.0.1:{server}/x")
    emitting = {r.name for r in records if r.name.startswith("httpcore")}
    assert emitting, "httpcore never emitted"
    assert emitting <= set(HTTPCORE_LOGGERS)
    for name in emitting:
        assert any(getattr(f, "_w8_log_filter", False) for f in logging.getLogger(name).filters), name


def test_filters_attach_once():
    from mountainash_transport._core.http import engine

    engine._install_log_filters()
    engine._install_log_filters()
    for name in ("httpx", *HTTPCORE_LOGGERS):
        assert sum(getattr(f, "_w8_log_filter", False) for f in logging.getLogger(name).filters) == 1, name


def test_import_sets_no_level():
    import subprocess
    import sys

    code = (
        "import logging, mountainash_transport._core.http.engine\n"
        "assert logging.getLogger('httpx').level == logging.NOTSET\n"
        "assert logging.getLogger('httpcore').level == logging.NOTSET\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
