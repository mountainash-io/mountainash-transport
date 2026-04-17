"""Tests for the GPG transform. Requires the [encryption] extra and the gpg binary."""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from mountainash_utils_files.storage_transforms import Pipeline

# GPG suite is integration-only: requires the gpg binary on PATH and python-gnupg.
pytestmark = pytest.mark.integration

_RECIPIENT = "test@mountainash.example"
_FIXTURE_SCRIPT = Path(__file__).resolve().parent.parent / "fixtures" / "gpg" / "generate_test_key.sh"


@pytest.fixture
def gpg_home(tmp_path) -> Path:
    if shutil.which("gpg") is None:
        pytest.skip("gpg binary not available on PATH")
    home = tmp_path / "gnupg"
    subprocess.run([str(_FIXTURE_SCRIPT), str(home)], check=True)
    return home


def test_gpg_implements_stream_transform_protocol():
    from mountainash_utils_files.storage_transforms import GPG, StreamTransform
    # recipients not required for protocol conformance (only required for wrap())
    assert isinstance(GPG(), StreamTransform)


def test_gpg_round_trip_via_pipeline(gpg_home):
    from mountainash_utils_files.storage_transforms import GPG

    transform = GPG(
        recipients=[_RECIPIENT],
        gnupghome=str(gpg_home),
        always_trust=True,
    )
    pipeline = Pipeline(transform)
    original = b"the quick brown fox" * 100
    encrypted = pipeline.apply_write(io.BytesIO(original)).read()
    assert encrypted != original
    decrypted = pipeline.apply_read(io.BytesIO(encrypted)).read()
    assert decrypted == original


def test_gpg_wrap_without_recipients_raises_transform_error():
    from mountainash_utils_files.exceptions import TransformError
    from mountainash_utils_files.storage_transforms import GPG

    with pytest.raises(TransformError, match="recipients"):
        GPG().wrap(io.BytesIO(b"data"))


def test_gpg_pipeline_with_gzip_round_trip(gpg_home):
    from mountainash_utils_files.storage_transforms import GPG, Gzip

    pipeline = Pipeline(
        Gzip(),
        GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
    )
    original = b"mixed compression and encryption" * 50
    encoded = pipeline.apply_write(io.BytesIO(original)).read()
    # Encoded bytes must start with the gzip magic 1f 8b — Pipeline(Gzip(), GPG())
    # means gzip is the OUTER layer (applied last on write).
    assert encoded[:2] == b"\x1f\x8b"
    decoded = pipeline.apply_read(io.BytesIO(encoded)).read()
    assert decoded == original
