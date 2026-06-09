"""Cross-backend parametrized tests: directory listing."""

from __future__ import annotations

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
def test_list_returns_correct_count(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    for i in range(3):
        facade.write(os.path.join(tmp_dir, f"file_{i}.txt"), b"data")
    results = facade.list_files(tmp_dir)
    assert len(results) == 3


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_list_empty_directory(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    results = facade.list_files(tmp_dir)
    assert results == []
