from __future__ import annotations

import io
import typing
from datetime import datetime
from typing import BinaryIO

import pytest

from mountainash_transport.dataclasses.file_metadata import FileMetadata
from mountainash_transport.storage_protocols import (
    StorageConnectionProtocol,
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageListProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_metadata(path: str = "file.txt") -> FileMetadata:
    return FileMetadata(
        filename="file.txt",
        directory="/tmp",
        full_path=f"/tmp/{path}",
        size=0,
        source="local",
    )


# ---------------------------------------------------------------------------
# StorageConnectionProtocol
# ---------------------------------------------------------------------------

class GoodConnection:
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: return True


class BadConnection:
    def connect(self) -> None: ...
    # missing disconnect and is_connected


class TestStorageConnectionProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodConnection(), StorageConnectionProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodConnection(), StorageConnectionProtocol)

    def test_negative_conformance_missing_methods(self) -> None:
        assert not isinstance(BadConnection(), StorageConnectionProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageConnectionProtocol)


# ---------------------------------------------------------------------------
# StorageReadProtocol
# ---------------------------------------------------------------------------

class GoodRead:
    def read_to_bytes(self, path: str) -> bytes: return b""
    def read_to_stream(self, path: str) -> BinaryIO: return io.BytesIO(b"")


class BadRead:
    def read_to_bytes(self, path: str) -> bytes: return b""
    # missing read_to_stream


class TestStorageReadProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodRead(), StorageReadProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodRead(), StorageReadProtocol)

    def test_negative_conformance_missing_method(self) -> None:
        assert not isinstance(BadRead(), StorageReadProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageReadProtocol)


# ---------------------------------------------------------------------------
# StorageWriteProtocol
# ---------------------------------------------------------------------------

class GoodWrite:
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...


class BadWrite:
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    # missing write_from_stream


class TestStorageWriteProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodWrite(), StorageWriteProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodWrite(), StorageWriteProtocol)

    def test_negative_conformance_missing_method(self) -> None:
        assert not isinstance(BadWrite(), StorageWriteProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageWriteProtocol)


# ---------------------------------------------------------------------------
# StorageListProtocol
# ---------------------------------------------------------------------------

class GoodList:
    def list_files(self, prefix: str) -> list[FileMetadata]: return []
    def list_directories(self, prefix: str) -> list[str]: return []


class BadList:
    def list_files(self, prefix: str) -> list[FileMetadata]: return []
    # missing list_directories


class TestStorageListProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodList(), StorageListProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodList(), StorageListProtocol)

    def test_negative_conformance_missing_method(self) -> None:
        assert not isinstance(BadList(), StorageListProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageListProtocol)


# ---------------------------------------------------------------------------
# StorageDeleteProtocol
# ---------------------------------------------------------------------------

class GoodDelete:
    def delete_file(self, path: str) -> None: ...


class BadDelete:
    def remove(self, path: str) -> None: ...  # wrong method name


class TestStorageDeleteProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodDelete(), StorageDeleteProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodDelete(), StorageDeleteProtocol)

    def test_negative_conformance_wrong_method(self) -> None:
        assert not isinstance(BadDelete(), StorageDeleteProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageDeleteProtocol)


# ---------------------------------------------------------------------------
# StorageMetadataProtocol
# ---------------------------------------------------------------------------

class GoodMetadata:
    def get_metadata(self, path: str) -> FileMetadata: return _make_metadata(path)
    def path_exists(self, path: str) -> bool: return False
    def get_size(self, path: str) -> int: return 0


class BadMetadata:
    def get_metadata(self, path: str) -> FileMetadata: return _make_metadata(path)
    def path_exists(self, path: str) -> bool: return False
    # missing get_size


class TestStorageMetadataProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodMetadata(), StorageMetadataProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodMetadata(), StorageMetadataProtocol)

    def test_negative_conformance_missing_method(self) -> None:
        assert not isinstance(BadMetadata(), StorageMetadataProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageMetadataProtocol)


# ---------------------------------------------------------------------------
# StorageCopyProtocol
# ---------------------------------------------------------------------------

class GoodCopy:
    def copy(self, source: str, destination: str) -> None: ...


class BadCopy:
    def duplicate(self, source: str, destination: str) -> None: ...  # wrong name


class TestStorageCopyProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodCopy(), StorageCopyProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodCopy(), StorageCopyProtocol)

    def test_negative_conformance_wrong_method(self) -> None:
        assert not isinstance(BadCopy(), StorageCopyProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageCopyProtocol)


# ---------------------------------------------------------------------------
# StorageDirectoryProtocol
# ---------------------------------------------------------------------------

class GoodDirectory:
    def mkdir(self, path: str, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


class BadDirectory:
    def mkdir(self, path: str, parents: bool = True) -> None: ...
    # missing rmdir


class TestStorageDirectoryProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodDirectory(), StorageDirectoryProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodDirectory(), StorageDirectoryProtocol)

    def test_negative_conformance_missing_method(self) -> None:
        assert not isinstance(BadDirectory(), StorageDirectoryProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageDirectoryProtocol)


# ---------------------------------------------------------------------------
# Cross-protocol: a class implementing multiple protocols conforms to all
# ---------------------------------------------------------------------------

class FullBackend:
    # connection
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: return True
    # read
    def read_to_bytes(self, path: str) -> bytes: return b""
    def read_to_stream(self, path: str) -> BinaryIO: return io.BytesIO(b"")
    # write
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...
    # list
    def list_files(self, prefix: str) -> list[FileMetadata]: return []
    def list_directories(self, prefix: str) -> list[str]: return []
    # delete
    def delete_file(self, path: str) -> None: ...
    # metadata
    def get_metadata(self, path: str) -> FileMetadata: return _make_metadata(path)
    def path_exists(self, path: str) -> bool: return False
    def get_size(self, path: str) -> int: return 0
    # copy
    def copy(self, source: str, destination: str) -> None: ...
    # directory
    def mkdir(self, path: str, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


class TestFullBackendConformance:
    def test_conforms_to_all_protocols(self) -> None:
        backend = FullBackend()
        assert isinstance(backend, StorageConnectionProtocol)
        assert isinstance(backend, StorageReadProtocol)
        assert isinstance(backend, StorageWriteProtocol)
        assert isinstance(backend, StorageListProtocol)
        assert isinstance(backend, StorageDeleteProtocol)
        assert isinstance(backend, StorageMetadataProtocol)
        assert isinstance(backend, StorageCopyProtocol)
        assert isinstance(backend, StorageDirectoryProtocol)
