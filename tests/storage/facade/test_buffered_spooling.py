"""access="buffered" keeps small objects in memory and spills large ones to a temp file (#25)."""
from __future__ import annotations

import os
import tempfile
import tracemalloc
import typing as t
from pathlib import Path

import pytest

from mountainash_transport import StorageFacade
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.settings.storage.profiles import LocalStorageProfile

MIB = 1024 * 1024
PAYLOAD = os.urandom(8 * MIB)


@pytest.fixture
def stored(tmp_path: Path) -> str:
    path = tmp_path / "big.bin"
    path.write_bytes(PAYLOAD)
    return str(path)


@pytest.fixture
def temp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    spool = tmp_path / "spool"
    spool.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool))
    return spool


def _peak_while_buffering(facade: StorageFacade, path: str, **kwargs: t.Any) -> int:
    tracemalloc.start()
    try:
        with facade.read_stream(path, access="buffered", **kwargs) as stream:
            peak = tracemalloc.get_traced_memory()[1]
            assert stream.seekable()
            stream.seek(len(PAYLOAD) - 16)
            assert stream.read() == PAYLOAD[-16:]
            stream.seek(0)
            assert stream.read() == PAYLOAD
    finally:
        tracemalloc.stop()
    return peak


def test_object_over_the_default_limit_spills_and_under_it_stays_in_memory(stored: str, temp_dir: Path) -> None:
    with StorageFacade.for_local() as facade:
        assert _peak_while_buffering(facade, stored) >= len(PAYLOAD)          # 8 MiB < 64 MiB: in memory
        assert _peak_while_buffering(facade, stored, buffer_memory_limit=MIB) < 3 * MIB


def test_profile_limit_applies_and_the_call_overrides_it(stored: str, temp_dir: Path) -> None:
    with StorageFacade(P.LOCAL, LocalStorageProfile(BUFFER_MEMORY_LIMIT=MIB)) as facade:
        assert _peak_while_buffering(facade, stored) < 3 * MIB
        assert _peak_while_buffering(facade, stored, buffer_memory_limit=64 * MIB) >= len(PAYLOAD)


def test_spilled_buffer_leaves_no_file_behind(stored: str, temp_dir: Path) -> None:
    with StorageFacade.for_local() as facade:
        with pytest.raises(RuntimeError):
            with facade.read_stream(stored, access="buffered", buffer_memory_limit=MIB) as stream:
                stream.read(10)
                raise RuntimeError("consumer failed")
        with facade.read_stream(stored, access="buffered", buffer_memory_limit=MIB) as stream:
            stream.read()
    assert list(temp_dir.iterdir()) == []


@pytest.mark.parametrize("access", ["sequential", "random"])
def test_buffer_limit_requires_buffered_access(stored: str, access: str) -> None:
    with StorageFacade.for_local() as facade, pytest.raises(ValueError, match="buffered"):
        facade.read_stream(stored, access=access, buffer_memory_limit=MIB)  # type: ignore[arg-type]


@pytest.mark.parametrize("limit", [0, -1])
def test_buffer_limit_must_be_positive(stored: str, limit: int) -> None:
    with StorageFacade.for_local() as facade, pytest.raises(ValueError, match="positive"):
        facade.read_stream(stored, access="buffered", buffer_memory_limit=limit)
