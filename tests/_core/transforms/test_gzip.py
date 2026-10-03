"""Tests for the Gzip transform."""
from __future__ import annotations

import gzip
import io

import pytest

from mountainash_transport._core.transforms import Gzip, Pipeline, StreamTransform


def test_gzip_implements_stream_transform_protocol():
    assert isinstance(Gzip(), StreamTransform)


@pytest.mark.parametrize("size", [0, 1, 17, 64_000, 1_000_000])
def test_gzip_round_trip_via_pipeline(size):
    data = bytes(i % 256 for i in range(size))
    pipeline = Pipeline(Gzip())
    encoded = pipeline.apply_write(io.BytesIO(data)).read()
    decoded = pipeline.apply_read(io.BytesIO(encoded)).read()
    assert decoded == data


def test_gzip_wrap_produces_valid_gzip_bytes():
    """Output of Gzip().wrap must be parseable by stdlib gzip."""
    data = b"hello world" * 100
    encoded = Gzip().wrap(io.BytesIO(data)).read()
    assert gzip.decompress(encoded) == data


def test_gzip_unwrap_decodes_stdlib_gzip_bytes():
    """Gzip().unwrap must accept stdlib-compressed bytes."""
    data = b"the quick brown fox"
    encoded = gzip.compress(data)
    decoded = Gzip().unwrap(io.BytesIO(encoded)).read()
    assert decoded == data


def test_gzip_mtime_zero_is_reproducible():
    """The default gzip header uses a fixed zero timestamp."""
    import struct

    encoded = Gzip().wrap(io.BytesIO(b"reproducibility matters")).read()
    assert struct.unpack("<I", encoded[4:8])[0] == 0


def test_gzip_default_level_is_6():
    assert Gzip().level == 6


def test_gzip_wrap_is_lazy():
    """Wrapping does not consume the source before the consumer reads."""
    data = b"x" * 10_000
    source = io.BytesIO(data)
    wrapped = Gzip().wrap(source)

    assert source.tell() == 0
    assert gzip.decompress(wrapped.read()) == data


def test_gzip_mtime_none_uses_current_time():
    """Passing mtime=None must embed the current time in the gzip header, not 0."""
    import struct
    import time

    before = int(time.time())
    encoded = Gzip(mtime=None).wrap(io.BytesIO(b"data")).read()
    after = int(time.time())

    # gzip mtime is bytes 4..8 (little-endian uint32) of the header.
    header_mtime = struct.unpack("<I", encoded[4:8])[0]
    assert before <= header_mtime <= after
    assert header_mtime != 0
