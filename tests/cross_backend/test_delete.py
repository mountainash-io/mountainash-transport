"""Cross-backend parametrized tests: delete operations."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest

import mountainash_transport.storage_backends  # noqa: F401 - trigger registrations
from mountainash_transport.exceptions import PathNotFoundError
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
def test_delete_existing_file(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "to_delete.txt")
    facade.write(path, b"delete me")
    facade.delete(path)
    assert facade.exists(path) is False


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_delete_nonexistent_raises(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    path = os.path.join(tmp_dir, "nonexistent.txt")
    with pytest.raises(PathNotFoundError):
        facade.delete(path)
