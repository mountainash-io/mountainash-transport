"""Facade integration tests for the pipeline= kwarg."""
from __future__ import annotations

import gzip
import io
from pathlib import Path

import pytest

from mountainash_transport import StorageFacade
from mountainash_transport.storage_transforms import Gzip, Pipeline


@pytest.fixture
def local_facade() -> StorageFacade:
    return StorageFacade.for_local()


def test_facade_read_with_pipeline_decompresses(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"hello"))
    assert local_facade.read(str(path), pipeline=Gzip()) == b"hello"


def test_facade_read_stream_with_pipeline_decompresses(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"streamed"))
    with local_facade.read_stream(str(path), pipeline=Gzip()) as stream:
        assert stream.read() == b"streamed"


def test_facade_read_with_none_pipeline_is_unchanged(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"abc")
    assert local_facade.read(str(path), pipeline=None) == b"abc"
    assert local_facade.read(str(path)) == b"abc"


def test_facade_read_accepts_bare_transform_or_pipeline(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"ok"))
    assert local_facade.read(str(path), pipeline=Gzip()) == b"ok"
    assert local_facade.read(str(path), pipeline=Pipeline(Gzip())) == b"ok"


def test_facade_read_closes_source_stream(local_facade, tmp_path):
    """Regression: read() must close the underlying backend source stream."""
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"payload"))

    # Patch read_to_stream to capture the source for inspection
    opened_streams = []
    original = local_facade._backend.read_to_stream

    def tracking_read(p):
        s = original(p)
        opened_streams.append(s)
        return s

    local_facade._backend.read_to_stream = tracking_read
    try:
        local_facade.read(str(path), pipeline=Gzip())
    finally:
        local_facade._backend.read_to_stream = original

    assert len(opened_streams) == 1
    assert opened_streams[0].closed, "source stream was not closed"


def test_facade_read_stream_closes_source_on_exit(local_facade, tmp_path):
    """Regression: read_stream() returned object closes source when its close() is called."""
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"payload"))

    opened_streams = []
    original = local_facade._backend.read_to_stream

    def tracking_read(p):
        s = original(p)
        opened_streams.append(s)
        return s

    local_facade._backend.read_to_stream = tracking_read
    try:
        with local_facade.read_stream(str(path), pipeline=Gzip()) as s:
            s.read()
    finally:
        local_facade._backend.read_to_stream = original

    assert len(opened_streams) == 1
    assert opened_streams[0].closed, "source stream was not closed after with-block exit"


def test_facade_write_with_pipeline_compresses(local_facade, tmp_path):
    path = tmp_path / "out.gz"
    local_facade.write(str(path), b"payload", pipeline=Gzip())
    assert gzip.decompress(path.read_bytes()) == b"payload"


def test_facade_write_stream_with_pipeline_compresses(local_facade, tmp_path):
    path = tmp_path / "out.gz"
    local_facade.write_stream(str(path), io.BytesIO(b"streamed"), pipeline=Gzip())
    assert gzip.decompress(path.read_bytes()) == b"streamed"


def test_facade_write_read_roundtrip_through_pipeline(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    local_facade.write(str(path), b"roundtrip", pipeline=Gzip())
    assert local_facade.read(str(path), pipeline=Gzip()) == b"roundtrip"


def test_facade_write_with_none_pipeline_is_unchanged(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    local_facade.write(str(path), b"raw", pipeline=None)
    assert path.read_bytes() == b"raw"


def test_copy_between_source_pipeline_decodes(local_facade, tmp_path):
    """Copy a gzipped source to a plaintext destination using source_pipeline."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.gz"
    dst_path = tmp_path / "dest.bin"
    src_path.write_bytes(gzip.compress(b"hello world"))

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        source_pipeline=Gzip(),
    )
    assert dst_path.read_bytes() == b"hello world"


def test_copy_between_destination_pipeline_encodes(local_facade, tmp_path):
    """Copy a plaintext source to a gzipped destination using destination_pipeline."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.gz"
    src_path.write_bytes(b"hello world")

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        destination_pipeline=Gzip(),
    )
    assert gzip.decompress(dst_path.read_bytes()) == b"hello world"


def test_copy_between_no_pipeline_uses_native_copy(local_facade, tmp_path):
    """With no pipelines, same-backend copy uses the native copy fast-path."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.bin"
    src_path.write_bytes(b"payload")

    copy_between(str(src_path), str(dst_path), local_facade, local_facade)
    assert dst_path.read_bytes() == b"payload"


def test_copy_between_forces_stream_when_pipeline_present(local_facade, tmp_path, monkeypatch):
    """When any pipeline is given, native copy is skipped even for same-backend."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.gz"
    src_path.write_bytes(b"x")

    copy_called = {"value": False}
    orig_copy = local_facade.copy

    def tracking_copy(*args, **kwargs):
        copy_called["value"] = True
        return orig_copy(*args, **kwargs)

    monkeypatch.setattr(local_facade, "copy", tracking_copy)

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        destination_pipeline=Gzip(),
    )
    assert copy_called["value"] is False  # native copy was NOT used
    assert gzip.decompress(dst_path.read_bytes()) == b"x"
