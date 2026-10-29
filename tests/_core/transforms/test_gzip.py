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


class TestDecompressionLimit:
    """Backlog 385: gzip unwrap is bounded by max_decompressed_bytes."""

    BOMB = gzip.compress(b"\0" * (64 * 1024 * 1024))
    LIMIT = 1024 * 1024

    class _NoSeek(io.RawIOBase):
        def __init__(self, data: bytes) -> None:
            self._inner = io.BytesIO(data)

        def readable(self) -> bool:
            return True

        def readinto(self, b) -> int:
            return self._inner.readinto(b)

    def _sources(self):
        return [io.BytesIO(self.BOMB), io.BufferedReader(self._NoSeek(self.BOMB))]

    def test_read_all_over_limit_raises_without_large_allocation(self):
        import tracemalloc

        from mountainash_transport import TransformError

        for src in self._sources():
            tracemalloc.start()
            with pytest.raises(TransformError, match="max_decompressed_bytes"):
                Gzip(max_decompressed_bytes=self.LIMIT).unwrap(src).read()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert peak < 16 * 1024 * 1024

    def test_chunked_reads_and_lines_over_limit_raise(self):
        from mountainash_transport import TransformError

        with pytest.raises(TransformError):
            s = Gzip(max_decompressed_bytes=self.LIMIT).unwrap(io.BytesIO(self.BOMB))
            while s.read(4096):
                pass
        with pytest.raises(TransformError):
            Gzip(max_decompressed_bytes=self.LIMIT).unwrap(io.BytesIO(self.BOMB)).readline()

    def test_seek_past_limit_raises(self):
        from mountainash_transport import TransformError

        s = Gzip(max_decompressed_bytes=self.LIMIT).unwrap(io.BytesIO(self.BOMB))
        with pytest.raises(TransformError):
            s.seek(2 * self.LIMIT)

    def test_exact_limit_and_none_allowed(self):
        data = b"x" * 5000
        assert Gzip(max_decompressed_bytes=5000).unwrap(io.BytesIO(gzip.compress(data))).read() == data
        assert len(Gzip(max_decompressed_bytes=None).unwrap(io.BytesIO(self.BOMB)).read()) == 64 * 1024 * 1024

    def test_default_is_bounded(self):
        assert Gzip().max_decompressed_bytes == 1024**3

    def test_facade_read_with_inferred_gzip_raises(self, tmp_path):
        from mountainash_transport import TransformError
        from mountainash_transport.storage.facade import StorageFacade

        p = tmp_path / "bomb.csv.gz"
        p.write_bytes(self.BOMB)
        facade = StorageFacade.for_local()
        with pytest.raises(TransformError):
            facade.read(str(p), infer=True, gzip=Gzip(max_decompressed_bytes=self.LIMIT))
