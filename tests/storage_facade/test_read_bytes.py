"""Tests for the top-level read_bytes helper."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from mountainash_utils_files import read_bytes


def test_read_bytes_reads_local_file(tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_bytes(b"hello world")
    assert read_bytes(str(target)) == b"hello world"


def test_read_bytes_http_uses_urllib(monkeypatch):
    captured: dict[str, str] = {}

    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return self._payload

    def _fake_urlopen(url):
        captured["url"] = url
        return _FakeResponse(b"http body")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    assert read_bytes("http://example.com/file") == b"http body"
    assert captured["url"] == "http://example.com/file"


def test_read_bytes_https_uses_urllib(monkeypatch):
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return b"https body"

    import urllib.request
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda url: _FakeResponse()
    )

    assert read_bytes("https://example.com/file") == b"https body"


def test_read_bytes_unrecognised_scheme_raises():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        read_bytes("gopher://example.com/")


def test_read_bytes_describe_only_scheme_raises():
    with pytest.raises(ValueError, match="has no registered backend"):
        read_bytes("hdfs://cluster/file")


def test_read_bytes_routes_s3_through_facade(monkeypatch):
    """s3:// → StorageFacade.from_path(...).read(...) with no urllib involvement."""
    calls: list[str] = []

    class _StreamBackend:
        """Minimal backend implementing StorageReadProtocol via read_to_stream."""

        def read_to_stream(self, path: str):
            calls.append(path)
            return io.BytesIO(b"s3 body")

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, auth=None: _StreamBackend()
    )
    # _require() does an isinstance check against StorageReadProtocol; our
    # stub backend isn't registered with that protocol, so bypass the gate.
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("s3://bucket/key") == b"s3 body"
    assert calls == ["s3://bucket/key"]
