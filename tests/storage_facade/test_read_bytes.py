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


def test_read_bytes_http_routes_through_facade(monkeypatch):
    """http:// → StorageFacade.from_path(...).read(...) — no urllib."""
    calls: list[str] = []

    class _StreamBackend:
        def read_to_stream(self, path: str):
            calls.append(path)
            return io.BytesIO(b"http body")

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, storage_profile=None, **kw: _StreamBackend()
    )
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("http://example.com/file") == b"http body"
    assert calls == ["http://example.com/file"]


def test_read_bytes_https_routes_through_facade(monkeypatch):
    """https:// → StorageFacade.from_path(...).read(...) — no urllib."""
    class _StreamBackend:
        def read_to_stream(self, path: str):
            return io.BytesIO(b"https body")

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, storage_profile=None, **kw: _StreamBackend()
    )
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

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
        facade_mod, "get_storage_backend", lambda provider, storage_profile=None, **kw: _StreamBackend()
    )
    # _require() does an isinstance check against StorageReadProtocol; our
    # stub backend isn't registered with that protocol, so bypass the gate.
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("s3://bucket/key") == b"s3 body"
    assert calls == ["s3://bucket/key"]


def test_read_bytes_infer_false_preserves_existing_behaviour(tmp_path: Path):
    target = tmp_path / "data.gz"
    target.write_bytes(b"\x1f\x8braw-gz-bytes")  # not valid gzip, but that's the point
    # infer=False must NOT touch the bytes.
    assert read_bytes(str(target)) == b"\x1f\x8braw-gz-bytes"
    assert read_bytes(str(target), infer=False) == b"\x1f\x8braw-gz-bytes"


def test_read_bytes_infer_true_no_known_suffix_falls_through(tmp_path: Path):
    target = tmp_path / "plain.txt"
    target.write_bytes(b"plain bytes")
    assert read_bytes(str(target), infer=True) == b"plain bytes"


def test_read_bytes_infer_gpg_suffix_without_gpg_raises(tmp_path: Path):
    target = tmp_path / "data.gpg"
    target.write_bytes(b"irrelevant")
    with pytest.raises(ValueError, match=r"\.gpg suffix"):
        read_bytes(str(target), infer=True)


def test_read_bytes_http_infer_applies_pipeline_to_bytes(monkeypatch):
    """http body with a .gz suffix + infer=True must be gunzipped."""
    import gzip as gzlib
    payload = gzlib.compress(b"plain text from web")

    class _StreamBackend:
        def read_to_stream(self, path: str):
            return io.BytesIO(payload)

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, storage_profile=None, **kw: _StreamBackend()
    )
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("https://example.com/file.gz", infer=True) == b"plain text from web"


def test_read_bytes_profile_accepted_as_keyword(tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_bytes(b"hello")
    # profile is keyword-only — passing by keyword must work.
    assert read_bytes(str(target), storage_profile=None) == b"hello"
