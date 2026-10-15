"""RangedReader: positioning, bounded fetching and lifecycle over fsspec caches."""
from __future__ import annotations

import io

import pytest

from mountainash_transport._core.exceptions import StorageError
from mountainash_transport._core.ranged_io import RangedReader, RangedSource, RangePolicy

DATA = bytes(range(256)) * 40  # 10_240 bytes, not a multiple of 4096


class _Counting:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.calls: list[tuple[int, int]] = []

    def __call__(self, start: int, end: int) -> bytes:
        self.calls.append((start, end))
        return self.data[start:end]

    @property
    def fetched(self) -> int:
        return sum(e - s for s, e in self.calls)


def _reader(data: bytes = DATA, *, cache: str = "readahead", block: int = 4096, on_close=None):
    fetch = _Counting(data)
    src = RangedSource(size=len(data), fetch=fetch, on_close=on_close)
    return RangedReader(src, RangePolicy(cache=cache, block_size=block)), fetch  # type: ignore[arg-type]


@pytest.mark.parametrize("cache", ["readahead", "blockcache", "bytes", "none"])
def test_tail_and_interior_reads_return_exact_bytes_with_bounded_fetch(cache: str) -> None:
    r, fetch = _reader(cache=cache)
    assert r.seek(-8, io.SEEK_END) == len(DATA) - 8
    assert r.read(8) == DATA[-8:]
    assert fetch.fetched <= 4096
    r.seek(5000)
    assert r.read(1000) == DATA[5000:6000]
    assert r.tell() == 6000
    r.seek(-10, io.SEEK_CUR)
    assert r.read(10) == DATA[5990:6000]


def test_fetch_clamped_at_eof_for_non_aligned_size() -> None:
    r, fetch = _reader(cache="blockcache")
    r.seek(len(DATA) - 3)
    assert r.read(100) == DATA[-3:]
    assert all(end <= len(DATA) for _, end in fetch.calls)


def test_read_at_or_past_eof_returns_empty() -> None:
    r, _ = _reader()
    r.seek(len(DATA) + 50)
    assert r.read(10) == b""
    assert r.read() == b""


def test_seek_performs_no_io() -> None:
    r, fetch = _reader()
    r.seek(-1, io.SEEK_END)
    r.seek(0)
    assert fetch.calls == []


def test_negative_absolute_seek_raises() -> None:
    r, _ = _reader()
    with pytest.raises(ValueError):
        r.seek(-1)


def test_short_fetch_raises_storage_error() -> None:
    src = RangedSource(size=100, fetch=lambda s, e: b"x" * (e - s - 1))
    r = RangedReader(src, RangePolicy(cache="none"))
    with pytest.raises(StorageError):
        r.read(10)


def test_empty_source_reads_empty() -> None:
    r, fetch = _reader(b"")
    assert r.read() == b""
    assert fetch.calls == []


def test_read_and_seek_after_close_raise_without_fetching() -> None:
    r, fetch = _reader()
    r.close()
    with pytest.raises(ValueError):
        r.read(2)
    with pytest.raises(ValueError):
        r.seek(0)
    assert fetch.calls == []


def test_close_calls_on_close_once() -> None:
    closed: list[int] = []
    r, _ = _reader(on_close=lambda: closed.append(1))
    r.close()
    r.close()
    assert closed == [1]
    assert r.closed


@pytest.mark.parametrize(
    "kwargs", [{"cache": "lru"}, {"block_size": 0}, {"cache": "blockcache", "max_blocks": 0}],
)
def test_invalid_policy_raises(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        RangePolicy(**kwargs)


def test_max_blocks_ignored_outside_blockcache() -> None:
    assert RangePolicy(cache="none", max_blocks=0).cache == "none"