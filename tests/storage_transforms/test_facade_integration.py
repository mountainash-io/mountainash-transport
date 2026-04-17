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
