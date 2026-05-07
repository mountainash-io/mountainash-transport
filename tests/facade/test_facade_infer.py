"""Tests for StorageFacade.read() and read_stream() with infer=True."""
from __future__ import annotations

import gzip as gzlib
from pathlib import Path

import pytest

import mountainash_utils_files.storage_backends  # noqa: F401
from mountainash_utils_files.storage_facade import StorageFacade
from mountainash_utils_files.storage_transforms import Gzip


class TestReadInfer:
    def test_read_infer_false_returns_raw_bytes(self, tmp_path: Path):
        payload = b"hello world"
        compressed = gzlib.compress(payload)
        target = tmp_path / "data.gz"
        target.write_bytes(compressed)

        facade = StorageFacade.for_local()
        result = facade.read(str(target))
        assert result == compressed

    def test_read_infer_true_decompresses_gz(self, tmp_path: Path):
        payload = b"hello world"
        target = tmp_path / "data.gz"
        target.write_bytes(gzlib.compress(payload))

        facade = StorageFacade.for_local()
        result = facade.read(str(target), infer=True)
        assert result == payload

    def test_read_infer_true_no_known_suffix_returns_raw(self, tmp_path: Path):
        payload = b"raw parquet bytes"
        target = tmp_path / "data.parquet"
        target.write_bytes(payload)

        facade = StorageFacade.for_local()
        result = facade.read(str(target), infer=True)
        assert result == payload

    def test_read_infer_true_with_pipeline_raises(self, tmp_path: Path):
        target = tmp_path / "data.gz"
        target.write_bytes(b"irrelevant")

        facade = StorageFacade.for_local()
        with pytest.raises(ValueError, match="Cannot pass both"):
            facade.read(str(target), infer=True, pipeline=Gzip())

    def test_read_infer_gpg_suffix_without_gpg_raises(self, tmp_path: Path):
        target = tmp_path / "data.gpg"
        target.write_bytes(b"irrelevant")

        facade = StorageFacade.for_local()
        with pytest.raises(ValueError, match=r"\.gpg suffix"):
            facade.read(str(target), infer=True)
