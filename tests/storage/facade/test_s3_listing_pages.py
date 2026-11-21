"""S3 listing stops fetching pages once max_results entries are held (#4)."""
from __future__ import annotations

import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest
from mountainash_auth_client import IAMAuthProfile

from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

KEYS = [f"logs/{index:03d}.csv" for index in range(25)]
SERVER_PAGE = 10  # the endpoint never returns more than this, as S3 caps pages at 1000


@pytest.fixture
def paging_endpoint() -> t.Iterator[tuple[str, list[dict[str, list[str]]]]]:
    requests: list[dict[str, list[str]]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            requests.append(query)
            start = int(query.get("continuation-token", ["0"])[0])
            size = min(int(query.get("max-keys", ["1000"])[0]), SERVER_PAGE)
            page = KEYS[start:start + size]
            document = Element("ListBucketResult", xmlns="http://s3.amazonaws.com/doc/2006-03-01/")
            truncated = start + size < len(KEYS)
            SubElement(document, "IsTruncated").text = "true" if truncated else "false"
            if truncated:
                SubElement(document, "NextContinuationToken").text = str(start + size)
            for key in page:
                entry = SubElement(document, "Contents")
                SubElement(entry, "Key").text = key
                SubElement(entry, "Size").text = "1"
            payload = tostring(document)
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: t.Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _facade(endpoint: str) -> StorageFacade:
    profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", BUCKET="probe", ENDPOINT_URL=endpoint)
    return StorageFacade.from_path(
        "s3://probe/", profile, auth_profile=IAMAuthProfile(ACCESS_KEY_ID="probe", SECRET_ACCESS_KEY="probe"),
    )


@pytest.mark.parametrize("limit, pages", [(0, 0), (4, 1), (10, 1), (15, 2)])
def test_listing_stops_at_max_results(paging_endpoint, limit: int, pages: int) -> None:
    endpoint, requests = paging_endpoint
    with _facade(endpoint) as storage:
        result = storage.list_objects("s3://probe/logs/", delimiter=None, max_results=limit)
    assert [entry.path for entry in result.objects] == [f"s3://probe/{key}" for key in KEYS[:limit]]
    assert len(requests) == pages
    assert all(int(query["max-keys"][0]) <= limit for query in requests)


def test_unlimited_listing_reads_every_page(paging_endpoint) -> None:
    endpoint, requests = paging_endpoint
    with _facade(endpoint) as storage:
        result = storage.list_objects("s3://probe/logs/", delimiter=None)
    assert len(result.objects) == len(KEYS)
    assert len(requests) == 3
