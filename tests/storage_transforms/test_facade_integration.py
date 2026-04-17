"""Facade integration tests for the pipeline= kwarg."""
from __future__ import annotations

import gzip
import io
from pathlib import Path

import pytest

from mountainash_utils_files import StorageFacade
from mountainash_utils_files.storage_transforms import Gzip, Pipeline


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
