"""Selected results through real boto3 HTTP requests and public facade setup."""
from __future__ import annotations

import typing as t
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring

import pytest
from mountainash_auth_client import IAMAuthProfile

from mountainash_transport import PathNotFoundError, PermissionDeniedError, StorageFacade
from mountainash_transport._core.dataclasses.storage_entry import EntryType
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile


KEYS = (
    "reports/", "reports/a.csv", "reports/a.csv.bak", "reports/a.csv/chunk",
    "reports/sub/b.csv", "reports-old/c.csv", "reports//double", "reports/./dot",
    "reports/../up", "/leading", "reports/http://example",
)


@pytest.fixture(scope="module")
def s3_endpoint() -> t.Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlsplit(self.path)
            bucket = url.path.strip("/")
            if bucket != "probe":
                document = Element("Error")
                SubElement(document, "Code").text = "AccessDenied" if bucket == "denied" else "NoSuchBucket"
                status = 403 if bucket == "denied" else 404
            else:
                query = parse_qs(url.query, keep_blank_values=True)
                prefix = query.get("prefix", [""])[0]
                delimiter = query.get("delimiter", [""])[0]
                document = Element("ListBucketResult", xmlns="http://s3.amazonaws.com/doc/2006-03-01/")
                SubElement(document, "IsTruncated").text = "false"
                groups: set[str] = set()
                for key in KEYS:
                    if not key.startswith(prefix):
                        continue
                    suffix = key[len(prefix):]
                    if delimiter and delimiter in suffix:
                        groups.add(prefix + suffix.split(delimiter, 1)[0] + delimiter)
                        continue
                    entry = SubElement(document, "Contents")
                    for name, value in (
                        ("Key", key), ("Size", "17"), ("LastModified", "2024-01-15T12:00:00Z"),
                        ("ETag", '"abc123"'), ("StorageClass", "STANDARD"),
                    ):
                        SubElement(entry, name).text = value
                for group in sorted(groups):
                    SubElement(SubElement(document, "CommonPrefixes"), "Prefix").text = group
                status = 200
            payload = tostring(document)
            self.send_response(status)
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
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture(scope="module")
def s3_facade(s3_endpoint: str) -> t.Iterator[StorageFacade]:
    profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", BUCKET="probe", ENDPOINT_URL=s3_endpoint)
    auth = IAMAuthProfile(ACCESS_KEY_ID="probe", SECRET_ACCESS_KEY="probe")
    with StorageFacade.from_path("s3://probe/", profile, auth_profile=auth) as facade:
        yield facade


@pytest.mark.parametrize("form", ["s3://probe/", "probe/"])
@pytest.mark.parametrize("prefix, expected", [
    ("reports/", {"reports/", "reports/a.csv", "reports/a.csv.bak", "reports/a.csv/chunk",
                  "reports/sub/b.csv", "reports//double", "reports/./dot", "reports/../up", "reports/http://example"}),
    ("rep", {"reports/", "reports/a.csv", "reports/a.csv.bak", "reports/a.csv/chunk", "reports/sub/b.csv",
             "reports-old/c.csv", "reports//double", "reports/./dot", "reports/../up", "reports/http://example"}),
    ("reports/a.csv", {"reports/a.csv", "reports/a.csv.bak", "reports/a.csv/chunk"}),
    ("reports/a.csv/", {"reports/a.csv/chunk"}),
    ("reports//", {"reports//double"}),
    ("reports/./", {"reports/./dot"}),
    ("reports/../", {"reports/../up"}),
    ("/leading", {"/leading"}),
    ("reports/http://example", {"reports/http://example"}),
    ("absent/", set()),
])
def test_literal_prefix_selects_objects(
    s3_facade: StorageFacade, form: str, prefix: str, expected: set[str],
) -> None:
    result = s3_facade.list_objects(form + prefix, delimiter=None)
    assert {entry.path for entry in result.objects} == {"s3://probe/" + key for key in expected}
    assert result.common_prefixes == ()


@pytest.mark.parametrize("scheme", ["s3express", "r2", "minio", "b2"])
def test_registered_family_scheme_preserves_literal_prefix(s3_facade: StorageFacade, scheme: str) -> None:
    # Common parsing under one AWS endpoint profile, not five service qualifications.
    result = s3_facade.list_objects(f"{scheme}://probe/reports/a.csv/", delimiter=None)
    assert [entry.path for entry in result.objects] == ["s3://probe/reports/a.csv/chunk"]
    assert result.common_prefixes == ()


def test_grouping_retains_marker_objects_and_metadata(s3_facade: StorageFacade) -> None:
    result = s3_facade.list_objects("s3://probe/reports/", delimiter="/")
    assert {entry.path for entry in result.objects} == {
        "s3://probe/reports/", "s3://probe/reports/a.csv", "s3://probe/reports/a.csv.bak",
    }
    assert {entry.path for entry in result.common_prefixes} == {
        "s3://probe/reports/a.csv/", "s3://probe/reports/sub/", "s3://probe/reports//",
        "s3://probe/reports/./", "s3://probe/reports/../", "s3://probe/reports/http:/",
    }
    by_path = {entry.path: entry for entry in result.objects}
    marker = by_path["s3://probe/reports/"]
    assert marker.entry_type == EntryType.FILE
    assert marker.name == ""
    entry = by_path["s3://probe/reports/a.csv"]
    assert (entry.name, entry.size, entry.etag, entry.storage_class, entry.source, entry.entry_type) == (
        "a.csv", 17, "abc123", "STANDARD", "s3", EntryType.FILE,
    )
    assert entry.last_modified == datetime(2024, 1, 15, 12, tzinfo=timezone.utc)
    assert all(entry.entry_type == EntryType.PREFIX and entry.source == "s3" for entry in result.common_prefixes)
    sub = next(entry for entry in result.common_prefixes if entry.path == "s3://probe/reports/sub/")
    assert sub.name == "sub"


@pytest.mark.parametrize("limit", [0, 1, 4, 12])
def test_combined_cap_includes_common_prefixes(s3_facade: StorageFacade, limit: int) -> None:
    result = s3_facade.list_objects("s3://probe/reports/", delimiter="/", max_results=limit)
    entries = result.objects + result.common_prefixes
    assert len(entries) == min(limit, 9)
    assert len({entry.path for entry in entries}) == len(entries)
    if limit > 3:
        assert len(result.common_prefixes) == min(limit - 3, 6)


@pytest.mark.parametrize("bucket, expected", [("denied", PermissionDeniedError), ("missing", PathNotFoundError)])
def test_bucket_failure_is_not_empty_selection(
    s3_facade: StorageFacade, bucket: str, expected: type[Exception],
) -> None:
    with pytest.raises(expected):
        s3_facade.list_objects(f"s3://{bucket}/reports/", delimiter=None)
