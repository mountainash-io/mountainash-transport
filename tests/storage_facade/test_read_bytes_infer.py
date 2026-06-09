"""Integration tests for read_bytes with infer=True.

Local-filesystem fixtures only — no network. The GPG-backed tests reuse
the throwaway-keyring fixture pattern from tests/storage_transforms/test_gpg.py.
"""
from __future__ import annotations

import gzip as gzlib
import io
import shutil
import subprocess
from pathlib import Path

import pytest

from mountainash_transport import read_bytes
from mountainash_transport._core.transforms import GPG, Gzip, Pipeline

_RECIPIENT = "test@mountainash.example"
_FIXTURE_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "fixtures" / "gpg" / "generate_test_key.sh"
)


def test_read_bytes_infer_gzip_local_round_trip(tmp_path: Path):
    payload = b"the quick brown fox jumps over the lazy dog" * 20
    target = tmp_path / "data.gz"
    target.write_bytes(gzlib.compress(payload))

    assert read_bytes(str(target), infer=True) == payload


def test_read_bytes_infer_gzip_custom_instance_threaded(tmp_path: Path):
    payload = b"hello"
    target = tmp_path / "data.gz"
    target.write_bytes(gzlib.compress(payload, compresslevel=9))

    # Custom Gzip() on the read side — level is irrelevant for decode, but
    # threading a caller-supplied instance must not break the round trip.
    assert read_bytes(str(target), infer=True, gzip=Gzip(level=9)) == payload


def test_read_bytes_infer_preserves_plain_read_when_no_suffix(tmp_path: Path):
    target = tmp_path / "plain"
    target.write_bytes(b"not-encoded")
    assert read_bytes(str(target), infer=True) == b"not-encoded"


@pytest.mark.integration
class TestReadBytesInferGPG:
    @pytest.fixture
    def gpg_home(self, tmp_path: Path) -> Path:
        if shutil.which("gpg") is None:
            pytest.skip("gpg binary not available on PATH")
        home = tmp_path / "gnupg"
        subprocess.run([str(_FIXTURE_SCRIPT), str(home)], check=True)
        return home

    def test_read_bytes_infer_gpg_round_trip(self, tmp_path: Path, gpg_home: Path):
        payload = b"secret payload" * 20
        encrypted = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True)
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.gpg"
        target.write_bytes(encrypted)

        gpg = GPG(gnupghome=str(gpg_home))
        assert read_bytes(str(target), infer=True, gpg=gpg) == payload

    def test_read_bytes_infer_gz_gpg_combined_round_trip(
        self, tmp_path: Path, gpg_home: Path,
    ):
        payload = b"combined encoding" * 50
        # Pipeline(GPG, Gzip) = write gzip inside, gpg outside.
        encoded = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
            Gzip(),
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.parquet.gz.gpg"
        target.write_bytes(encoded)

        gpg = GPG(gnupghome=str(gpg_home))
        assert read_bytes(str(target), infer=True, gpg=gpg) == payload
