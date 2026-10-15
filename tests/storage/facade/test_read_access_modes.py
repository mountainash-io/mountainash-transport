from __future__ import annotations

import gzip
import io
import importlib
import typing as t

import pytest

from mountainash_transport import StorageFacade
from mountainash_transport._core.exceptions import UnsupportedOperationError
from mountainash_transport._core.ranged_io import RangePolicy
from mountainash_transport._core.transforms import Gzip


@pytest.fixture
def facade() -> StorageFacade:
    return StorageFacade.for_local()


DATA = bytes(range(256)) * 64  # 16_384 bytes


def _remote_facade(fetched: list[tuple[int, int]]) -> StorageFacade:
    """Facade over a ranged + sequential fake backend that records fetch ranges and closes."""
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    from mountainash_transport._core.ranged_io import RangedSource
    from mountainash_transport._core.sequential_io import ForwardOnlyReader

    class _Backend:
        storage_profile: object | None = None

        def __init__(self) -> None:
            self.closed: list[str] = []

        def read_to_bytes(self, path: str) -> bytes:
            return DATA

        def read_to_stream(self, path: str) -> io.BufferedReader:
            buf = io.BytesIO(DATA)
            return io.BufferedReader(ForwardOnlyReader(buf.read, close=lambda: self.closed.append("seq")))

        def open_ranged(self, path: str) -> RangedSource:
            def fetch(s: int, e: int) -> bytes:
                fetched.append((s, e))
                return DATA[s:e]
            return RangedSource(size=len(DATA), fetch=fetch, on_close=lambda: self.closed.append("ranged"))

    f = StorageFacade.for_local()
    f._backend = _Backend()
    f._provider_type = CONST_STORAGE_PROVIDER_TYPE.HTTP
    return f


@pytest.fixture
def plain(tmp_path) -> str:
    p = tmp_path / "plain.bin"
    p.write_bytes(b"abcdefgh")
    return str(p)


@pytest.mark.parametrize("access", ["sequential", "random", "buffered"])
def test_each_mode_reads_bytes_and_seeks_on_local(facade, plain, access) -> None:
    with facade.read_stream(plain, access=access) as s:
        assert s.seekable()
        s.seek(-3, io.SEEK_END)
        assert s.read() == b"fgh"


def test_random_with_transform_raises_value_error(facade, tmp_path) -> None:
    p = tmp_path / "d.gz"
    p.write_bytes(gzip.compress(b"x"))
    with pytest.raises(ValueError, match="random"):
        facade.read_stream(str(p), access="random", pipeline=Gzip())
    with pytest.raises(ValueError, match="random"):
        facade.read_stream(str(p), access="random", infer=True)


@pytest.mark.parametrize("access", ["sequential", "buffered"])
def test_range_policy_requires_random(facade, plain, access) -> None:
    with pytest.raises(ValueError, match="range_policy"):
        facade.read_stream(plain, access=access, range_policy=RangePolicy())


def test_unknown_access_raises(facade: StorageFacade, plain: str) -> None:
    with pytest.raises(ValueError, match="access"):
        facade.read_stream(plain, access="mmap")  # type: ignore[arg-type]


def test_buffered_decodes_then_buffers(facade, tmp_path) -> None:
    p = tmp_path / "d.gz"
    p.write_bytes(gzip.compress(b"hello world"))
    with facade.read_stream(str(p), infer=True, access="buffered") as s:
        s.seek(6)
        assert s.read() == b"world"


def test_random_without_capability_raises_unsupported(facade, plain, monkeypatch) -> None:
    class _NoRanged:
        def read_to_bytes(self, path): return b""
        def read_to_stream(self, path): return io.BytesIO(b"")
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    monkeypatch.setattr(facade, "_backend", _NoRanged())
    monkeypatch.setattr(facade, "_provider_type", CONST_STORAGE_PROVIDER_TYPE.HTTP, raising=False)
    with pytest.raises(UnsupportedOperationError):
        facade.read_stream("remote://obj", access="random")


def _first_fetch_len(f: StorageFacade, fetched: list[tuple[int, int]], **kw: t.Any) -> int:
    fetched.clear()
    with f.read_stream("remote://obj", access="random", **kw) as s:
        s.read(10)
    return fetched[0][1] - fetched[0][0]


def test_policy_precedence_call_over_profile_over_default() -> None:
    fetched: list[tuple[int, int]] = []
    f = _remote_facade(fetched)
    assert _first_fetch_len(f, fetched) == len(DATA)  # default readahead 1 MiB, clamped to size
    f._backend.storage_profile = type("P", (), {"RANGE_CACHE": "none", "RANGE_BLOCK_SIZE": None,
                                                "RANGE_MAX_BLOCKS": None})()
    assert _first_fetch_len(f, fetched) == 10  # profile: exact reads
    assert _first_fetch_len(f, fetched, range_policy=RangePolicy("readahead", block_size=1024)) == 1034


@pytest.mark.parametrize("access", ["sequential", "random", "buffered"])
def test_remote_modes_seekability_and_closure(access: str) -> None:
    fetched: list[tuple[int, int]] = []
    f = _remote_facade(fetched)
    with f.read_stream("remote://obj", access=access) as s:  # type: ignore[arg-type]
        assert s.seekable() is (access != "sequential")
        assert s.read(4) == DATA[:4]
    assert f._backend.closed == (["ranged"] if access == "random" else ["seq"])


def test_random_constructor_failure_closes_source(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("mountainash_transport.storage.facade.facade")
    f = _remote_facade([])

    def boom(*a: t.Any, **k: t.Any) -> t.NoReturn:
        raise RuntimeError("reader failed")

    monkeypatch.setattr(mod, "RangedReader", boom)
    with pytest.raises(RuntimeError):
        f.read_stream("remote://obj", access="random")
    assert f._backend.closed == ["ranged"]


def test_buffered_materialize_failure_closes_source(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("mountainash_transport.storage.facade.facade")
    f = _remote_facade([])

    def boom(*a: t.Any, **k: t.Any) -> t.NoReturn:
        raise RuntimeError("materialize failed")

    monkeypatch.setattr(mod, "materialize", boom)
    with pytest.raises(RuntimeError):
        f.read_stream("remote://obj", access="buffered")
    assert f._backend.closed == ["seq"]


@pytest.mark.parametrize("access", ["sequential", "random", "buffered"])
def test_every_mode_closes_on_consumer_exception(facade, plain, access, monkeypatch) -> None:
    opened: list[io.IOBase] = []
    real_open = open

    def tracking_open(*a, **k):
        f = real_open(*a, **k)
        opened.append(f)
        return f

    monkeypatch.setattr("builtins.open", tracking_open)
    with pytest.raises(RuntimeError):
        with facade.read_stream(plain, access=access) as s:
            s.read(1)
            raise RuntimeError("consumer failed")
    assert opened and all(f.closed for f in opened)