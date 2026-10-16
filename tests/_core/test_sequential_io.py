from __future__ import annotations

import io

import pytest

from mountainash_transport._core.sequential_io import ForwardOnlyReader, IterBytesReader


def test_forward_only_reader_reads_in_requested_sizes_and_is_not_seekable() -> None:
    src = io.BytesIO(b"abcdef")
    sizes: list[int] = []

    def read(n: int) -> bytes:
        sizes.append(n)
        return src.read(n)

    r = ForwardOnlyReader(read, close=lambda: None)
    assert not r.seekable()
    with pytest.raises(io.UnsupportedOperation):
        r.seek(0)
    assert r.read(2) == b"ab"
    assert r.read() == b"cdef"
    assert all(n > 0 for n in sizes)


def test_iter_bytes_reader_holds_at_most_one_chunk() -> None:
    produced: list[int] = []

    def chunks():
        for i in range(3):
            produced.append(i)
            yield bytes([65 + i]) * 4

    r = IterBytesReader(chunks(), close=lambda: None)
    assert r.read(2) == b"AA"
    assert produced == [0]
    assert r.read() == b"AABBBBCCCC"
    assert produced == [0, 1, 2]


def test_forward_only_reader_maps_mid_read_failure() -> None:
    from mountainash_transport._core.exceptions import StorageError

    def read(n: int) -> bytes:
        raise OSError("connection dropped")

    r = ForwardOnlyReader(read, close=lambda: None, map_error=lambda e: StorageError(str(e)))
    with pytest.raises(StorageError, match="connection dropped"):
        r.read(4)


def test_iter_bytes_reader_maps_failure_while_advancing() -> None:
    from mountainash_transport._core.exceptions import StorageError

    def chunks():
        yield b"ab"
        raise OSError("reset")

    r = IterBytesReader(chunks(), close=lambda: None, map_error=lambda e: StorageError(str(e)))
    assert r.read(2) == b"ab"
    with pytest.raises(StorageError, match="reset"):
        r.read(2)


def test_readers_close_once() -> None:
    closed: list[str] = []
    a = ForwardOnlyReader(lambda n: b"", close=lambda: closed.append("a"))
    b = IterBytesReader(iter(()), close=lambda: closed.append("b"))
    a.close(); a.close(); b.close(); b.close()
    assert closed == ["a", "b"]


def test_deferred_close_maps_error_and_remains_closed() -> None:
    from mountainash_transport import StorageError
    original = OSError("close failed")
    closes: list[bool] = []
    def close() -> None:
        closes.append(True)
        raise original
    reader = ForwardOnlyReader(lambda n: b"", close, lambda exc: StorageError("backend"))
    with pytest.raises(StorageError) as caught:
        reader.close()
    assert caught.value.__cause__ is original
    assert reader.closed
    reader.close()
    assert closes == [True]


def test_existing_public_error_is_not_self_chained() -> None:
    from mountainash_transport import ObjectChangedError
    original = ObjectChangedError("changed")
    def read(n: int) -> bytes:
        raise original
    with ForwardOnlyReader(read, lambda: None, lambda exc: exc) as reader:
        with pytest.raises(ObjectChangedError) as caught:
            reader.read(1)
    assert caught.value is original
    assert caught.value.__cause__ is None