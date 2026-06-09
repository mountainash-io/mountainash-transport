"""Cross-backend parametrized tests: read/write roundtrips."""

from __future__ import annotations

import io
import os
import shutil
import tempfile

import pytest

import mountainash_transport.storage.backends  # noqa: F401 - trigger registrations
from mountainash_transport.storage.facade import StorageFacade

LOCAL_BACKENDS = ["local"]


def make_facade(backend_name: str) -> StorageFacade:
    if backend_name == "local":
        return StorageFacade.for_local()
    pytest.skip(f"Backend {backend_name} requires integration credentials")


@pytest.fixture()
def tmp_dir():
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_write_then_read_bytes(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "roundtrip.bin")
    data = b"roundtrip bytes content"
    facade.write(path, data)
    assert facade.read(path) == data


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_write_then_read_stream(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "stream.bin")
    data = b"streamed content"
    facade.write_stream(path, io.BytesIO(data))
    with facade.read_stream(path) as fh:
        assert fh.read() == data


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_write_empty_file(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "empty.bin")
    facade.write(path, b"")
    assert facade.read(path) == b""


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_write_large_content(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "large.bin")
    data = b"x" * 1024 * 1024  # 1 MB
    facade.write(path, data)
    assert facade.read(path) == data


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_overwrite_existing(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "overwrite.bin")
    facade.write(path, b"first write")
    facade.write(path, b"second write")
    assert facade.read(path) == b"second write"
