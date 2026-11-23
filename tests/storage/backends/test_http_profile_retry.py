"""HTTP storage retries follow the profile's RETRY_* fields (#5)."""
from __future__ import annotations

import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest

from mountainash_transport import StorageFacade, StorageError
from mountainash_transport.settings.storage.profiles import HTTPStorageProfile


@pytest.fixture(scope="module")
def unavailable() -> t.Iterator[tuple[str, list[str]]]:
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            seen.append(self.path)
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args: t.Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/a.csv", seen
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize("fields, attempts", [({}, 3), ({"RETRY_MAX_ATTEMPTS": 1}, 1), ({"RETRY_MAX_ATTEMPTS": 5}, 5)])
def test_profile_sets_http_attempts(unavailable: tuple[str, list[str]], fields: dict[str, t.Any], attempts: int) -> None:
    url, seen = unavailable
    seen.clear()
    profile = HTTPStorageProfile(**fields)
    with patch("mountainash_transport._core.http.engine.time.sleep"), \
            StorageFacade.from_path(url, profile) as facade, pytest.raises(StorageError):
        facade.read(url)
    assert len(seen) == attempts


def test_profile_sets_http_backoff(unavailable: tuple[str, list[str]]) -> None:
    url, seen = unavailable
    profile = HTTPStorageProfile(RETRY_MAX_ATTEMPTS=3, RETRY_BACKOFF_BASE=0.25, RETRY_BACKOFF_MAX=0.3)
    with patch("mountainash_transport._core.http.engine.time.sleep") as sleep, \
            patch("mountainash_transport._core.retry.random.uniform", lambda low, high: high), \
            StorageFacade.from_path(url, profile) as facade, pytest.raises(StorageError):
        facade.read(url)
    assert [c.args[0] for c in sleep.call_args_list] == [0.25, 0.3]
