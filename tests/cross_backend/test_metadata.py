"""Cross-backend parametrized tests: metadata operations."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

import mountainash_transport.storage_backends  # noqa: F401 - trigger registrations
from mountainash_transport.storage_facade import StorageFacade

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
def test_exists_true(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "present.txt")
    facade.write(path, b"present")
    assert facade.exists(path) is True


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_exists_false(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "absent.txt")
    assert facade.exists(path) is False


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_get_size(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    data = b"size check content"
    path = os.path.join(tmp_dir, "sized.bin")
    facade.write(path, data)
    assert facade.get_size(path) == len(data)


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_metadata_returns_filename(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "named_file.txt")
    facade.write(path, b"content")
    meta = facade.metadata(path)
    assert meta.filename == "named_file.txt"
