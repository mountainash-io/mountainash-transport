"""Real HTTP requests through facade construction (no injected client/engine)."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import typing as t

import pytest
from mountainash_auth_client import TokenAuthProfile

from mountainash_transport import StorageFacade
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import PathNotFoundError
from mountainash_transport.settings.storage.profiles import HTTPStorageProfile


@pytest.fixture
def http_server() -> t.Iterator[tuple[str, list[dict[str, str]]]]:
    requests: list[dict[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(dict(self.headers))
            self.send_response(404 if self.path == "/missing.csv" else 200)
            self.end_headers()
            self.wfile.write(b"name,value\nalpha,1\n")

        def log_message(self, format: str, *args: t.Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def close_facade() -> t.Iterator[t.Callable[[StorageFacade], None]]:
    facades: list[StorageFacade] = []
    yield facades.append
    for facade in facades:
        # Public facade lifecycle is tracked separately in backlog #2.
        connection = facade._backend._connection
        if connection is not None:
            connection.disconnect()


@pytest.mark.parametrize("direct", [False, True])
def test_anonymous_http_read(
    http_server: tuple[str, list[dict[str, str]]],
    close_facade: t.Callable[[StorageFacade], None],
    direct: bool,
) -> None:
    url, _ = http_server
    facade = (
        StorageFacade(CONST_STORAGE_PROVIDER_TYPE.HTTP)
        if direct else StorageFacade.from_path(url)
    )
    close_facade(facade)
    assert facade.read(url + "/data.csv") == b"name,value\nalpha,1\n"


@pytest.mark.parametrize("explicit_profile", [False, True])
def test_http_auth_and_profile_headers(
    http_server: tuple[str, list[dict[str, str]]],
    close_facade: t.Callable[[StorageFacade], None],
    explicit_profile: bool,
) -> None:
    url, requests = http_server
    profile = HTTPStorageProfile(HEADERS={"X-Probe": "kept"}) if explicit_profile else None
    facade = StorageFacade.from_path(url, profile, auth_profile=TokenAuthProfile(TOKEN="probe"))
    close_facade(facade)
    assert facade.read(url + "/data.csv") == b"name,value\nalpha,1\n"
    assert requests[-1]["Authorization"] == "Bearer probe"
    if explicit_profile:
        assert requests[-1]["X-Probe"] == "kept"


def test_http_missing_resource(
    http_server: tuple[str, list[dict[str, str]]],
    close_facade: t.Callable[[StorageFacade], None],
) -> None:
    url, _ = http_server
    facade = StorageFacade.from_path(url)
    close_facade(facade)
    with pytest.raises(PathNotFoundError):
        facade.read(url + "/missing.csv")
