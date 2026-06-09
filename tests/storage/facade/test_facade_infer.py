"""Tests for StorageFacade.read() and read_stream() with infer=True."""
from __future__ import annotations

import gzip as gzlib
import io
import shutil
import subprocess
from pathlib import Path

import pytest

import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport.storage.facade import StorageFacade
from mountainash_transport._core.transforms import GPG, Gzip, Pipeline


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


class TestReadStreamInfer:
    def test_read_stream_infer_true_decompresses_gz(self, tmp_path: Path):
        payload = b"streamed decompression test"
        target = tmp_path / "data.gz"
        target.write_bytes(gzlib.compress(payload))

        facade = StorageFacade.for_local()
        stream = facade.read_stream(str(target), infer=True)
        assert stream.read() == payload
        stream.close()

    def test_read_stream_infer_true_with_pipeline_raises(self, tmp_path: Path):
        target = tmp_path / "data.gz"
        target.write_bytes(b"irrelevant")

        facade = StorageFacade.for_local()
        with pytest.raises(ValueError, match="Cannot pass both"):
            facade.read_stream(str(target), infer=True, pipeline=Gzip())

    def test_read_stream_infer_true_no_known_suffix_returns_raw(
        self, tmp_path: Path,
    ):
        payload = b"raw stream bytes"
        target = tmp_path / "data.parquet"
        target.write_bytes(payload)

        facade = StorageFacade.for_local()
        stream = facade.read_stream(str(target), infer=True)
        assert stream.read() == payload
        stream.close()


_RECIPIENT = "test@mountainash.example"
_FIXTURE_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures" / "gpg" / "generate_test_key.sh"
)


@pytest.mark.integration
class TestReadInferGPG:
    @pytest.fixture
    def gpg_home(self, tmp_path: Path) -> Path:
        if shutil.which("gpg") is None:
            pytest.skip("gpg binary not available on PATH")
        home = tmp_path / "gnupg"
        subprocess.run([str(_FIXTURE_SCRIPT), str(home)], check=True)
        return home

    def test_read_infer_true_decompresses_gz_gpg(
        self, tmp_path: Path, gpg_home: Path,
    ):
        payload = b"encrypted and compressed payload" * 50
        encoded = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
            Gzip(),
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.parquet.gz.gpg"
        target.write_bytes(encoded)

        facade = StorageFacade.for_local()
        gpg = GPG(gnupghome=str(gpg_home))
        result = facade.read(str(target), infer=True, gpg=gpg)
        assert result == payload

    def test_read_stream_infer_true_decompresses_gz_gpg(
        self, tmp_path: Path, gpg_home: Path,
    ):
        payload = b"streamed encrypted compressed" * 50
        encoded = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
            Gzip(),
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.parquet.gz.gpg"
        target.write_bytes(encoded)

        facade = StorageFacade.for_local()
        gpg = GPG(gnupghome=str(gpg_home))
        stream = facade.read_stream(str(target), infer=True, gpg=gpg)
        assert stream.read() == payload
        stream.close()
