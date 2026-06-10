from __future__ import annotations

import io
from typing import BinaryIO

from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult, StorageEntry
from mountainash_transport.storage.protocols import (
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageEnumerateProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(path: str = "/tmp/file.txt") -> StorageEntry:
    return StorageEntry(path=path, name="file.txt", size=0)


def _make_enumerate_result() -> EnumerateResult:
    return EnumerateResult(objects=(), common_prefixes=())


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
# StorageEnumerateProtocol
# ---------------------------------------------------------------------------

class GoodEnumerate:
    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        return _make_enumerate_result()


class BadEnumerate:
    # wrong method name
    def list_files(self, prefix: str) -> list[StorageEntry]: return []


class TestStorageEnumerateProtocol:
    def test_is_runtime_checkable(self) -> None:
        assert isinstance(GoodEnumerate(), StorageEnumerateProtocol)

    def test_positive_conformance(self) -> None:
        assert isinstance(GoodEnumerate(), StorageEnumerateProtocol)

    def test_negative_conformance_wrong_method(self) -> None:
        assert not isinstance(BadEnumerate(), StorageEnumerateProtocol)

    def test_empty_class_does_not_conform(self) -> None:
        assert not isinstance(object(), StorageEnumerateProtocol)


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
    def get_metadata(self, path: str) -> StorageEntry: return _make_entry(path)
    def path_exists(self, path: str) -> bool: return False
    def get_size(self, path: str) -> int | None: return 0


class BadMetadata:
    def get_metadata(self, path: str) -> StorageEntry: return _make_entry(path)
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
    def list_dir(self, path: str) -> list[StorageEntry]: return []
    def mkdir(self, path: str, *, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


class BadDirectory:
    # has mkdir + rmdir but no list_dir
    def mkdir(self, path: str, *, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


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
    # read
    def read_to_bytes(self, path: str) -> bytes: return b""
    def read_to_stream(self, path: str) -> BinaryIO: return io.BytesIO(b"")
    # write
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...
    # enumerate
    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        return _make_enumerate_result()
    # delete
    def delete_file(self, path: str) -> None: ...
    # metadata
    def get_metadata(self, path: str) -> StorageEntry: return _make_entry(path)
    def path_exists(self, path: str) -> bool: return False
    def get_size(self, path: str) -> int | None: return 0
    # copy
    def copy(self, source: str, destination: str) -> None: ...
    # directory
    def list_dir(self, path: str) -> list[StorageEntry]: return []
    def mkdir(self, path: str, *, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


class TestFullBackendConformance:
    def test_conforms_to_all_protocols(self) -> None:
        backend = FullBackend()
        assert isinstance(backend, StorageReadProtocol)
        assert isinstance(backend, StorageWriteProtocol)
        assert isinstance(backend, StorageEnumerateProtocol)
        assert isinstance(backend, StorageDeleteProtocol)
        assert isinstance(backend, StorageMetadataProtocol)
        assert isinstance(backend, StorageCopyProtocol)
        assert isinstance(backend, StorageDirectoryProtocol)
