# Storage Protocol Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `FileMetadata` with `StorageEntry`, replace `StorageListProtocol` with `StorageEnumerateProtocol` + reworked `StorageDirectoryProtocol`, and update all four backends and the facade.

**Architecture:** Bottom-up: new dataclass and enum first, then protocols, then backends (S3/Local/SFTP/HTTP), then facade, then exports and tests. Each task produces a green test suite.

**Tech Stack:** Python 3.12, dataclasses, typing.Protocol, pytest, boto3 (mocked), paramiko (mocked), httpx (mocked)

---

## File Structure

**Create:**
- `src/mountainash_transport/_core/dataclasses/storage_entry.py` — `EntryType` enum + `StorageEntry` dataclass + `EnumerateResult` dataclass
- `src/mountainash_transport/storage/protocols/prtcl_enumerate.py` — `StorageEnumerateProtocol`
- `src/mountainash_transport/storage/backends/s3/s3_enumerate.py` — `S3EnumerateMixin` (replaces `s3_list.py`)

**Modify:**
- `src/mountainash_transport/_core/dataclasses/__init__.py` — export `StorageEntry`, `EntryType`, `EnumerateResult`
- `src/mountainash_transport/storage/protocols/prtcl_metadata.py` — return `StorageEntry`, `get_size -> int | None`
- `src/mountainash_transport/storage/protocols/prtcl_directory.py` — add `list_dir()`
- `src/mountainash_transport/storage/protocols/__init__.py` — replace `StorageListProtocol` with `StorageEnumerateProtocol`
- `src/mountainash_transport/storage/backends/s3/__init__.py` — swap `S3ListMixin` → `S3EnumerateMixin`
- `src/mountainash_transport/storage/backends/s3/s3_metadata.py` — return `StorageEntry` with version_id + checksum
- `src/mountainash_transport/storage/backends/local/__init__.py` — remove `LocalListMixin`
- `src/mountainash_transport/storage/backends/local/local_metadata.py` — return `StorageEntry`
- `src/mountainash_transport/storage/backends/local/local_list.py` — rewrite as `list_dir()` returning `StorageEntry`
- `src/mountainash_transport/storage/backends/local/local_directory.py` — add `list_dir()` (absorb listing)
- `src/mountainash_transport/storage/backends/ssh/__init__.py` — `get_metadata` → `StorageEntry`, add `list_dir`/`mkdir`/`rmdir`, rename `delete_path` → `delete_file`
- `src/mountainash_transport/storage/backends/http/__init__.py` — `get_metadata` → `StorageEntry` with content_type + checksum, `get_size -> int | None`
- `src/mountainash_transport/storage/facade/facade.py` — replace `list_files`/`list_directories` with `list_objects`/`list_dir`, update `metadata` return type
- `src/mountainash_transport/__init__.py` — update exports

**Delete:**
- `src/mountainash_transport/_core/dataclasses/file_metadata.py` — replaced by `storage_entry.py`
- `src/mountainash_transport/storage/protocols/prtcl_list.py` — replaced by `prtcl_enumerate.py`
- `src/mountainash_transport/storage/backends/s3/s3_list.py` — replaced by `s3_enumerate.py`

**Test files (modify):**
- `tests/storage/protocols/test_protocol_shapes.py`
- `tests/storage/protocols/test_backend_conformance.py`
- `tests/storage/backends/test_s3.py`
- `tests/storage/backends/test_local.py`
- `tests/storage/backends/test_sftp.py`
- `tests/storage/backends/test_http.py`
- `tests/storage/facade/test_facade.py`
- `tests/storage/cross_backend/test_list.py`
- `tests/test_public_api.py`

---

### Task 1: StorageEntry + EntryType + EnumerateResult

**Files:**
- Create: `src/mountainash_transport/_core/dataclasses/storage_entry.py`
- Modify: `src/mountainash_transport/_core/dataclasses/__init__.py`
- Test: `tests/_core/test_storage_entry.py`

- [ ] **Step 1: Write tests for StorageEntry, EntryType, and EnumerateResult**

```python
"""Tests for StorageEntry, EntryType, and EnumerateResult."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)


class TestEntryType:
    def test_values(self):
        assert EntryType.FILE == "file"
        assert EntryType.DIRECTORY == "directory"
        assert EntryType.PREFIX == "prefix"

    def test_is_str(self):
        assert isinstance(EntryType.FILE, str)


class TestStorageEntry:
    def test_minimal_construction(self):
        entry = StorageEntry(path="/tmp/file.txt", name="file.txt")
        assert entry.path == "/tmp/file.txt"
        assert entry.name == "file.txt"
        assert entry.size is None
        assert entry.last_modified is None
        assert entry.etag == ""
        assert entry.content_type == ""
        assert entry.entry_type == EntryType.FILE
        assert entry.storage_class == ""
        assert entry.source == ""
        assert entry.version_id == ""
        assert entry.checksum == ""
        assert entry.checksum_algorithm == ""

    def test_full_construction(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        entry = StorageEntry(
            path="s3://bucket/key.txt",
            name="key.txt",
            size=1024,
            last_modified=ts,
            etag="abc123",
            content_type="text/plain",
            entry_type=EntryType.FILE,
            storage_class="STANDARD",
            source="s3",
            version_id="v1",
            checksum="abc==",
            checksum_algorithm="SHA256",
        )
        assert entry.size == 1024
        assert entry.version_id == "v1"
        assert entry.checksum == "abc=="
        assert entry.checksum_algorithm == "SHA256"

    def test_frozen(self):
        entry = StorageEntry(path="/tmp/f.txt", name="f.txt")
        with pytest.raises(AttributeError):
            entry.path = "/other"  # type: ignore[misc]

    def test_size_none_vs_zero(self):
        none_entry = StorageEntry(path="/a", name="a", size=None)
        zero_entry = StorageEntry(path="/b", name="b", size=0)
        assert none_entry.size is None
        assert zero_entry.size == 0

    def test_prefix_entry(self):
        entry = StorageEntry(
            path="s3://bucket/data",
            name="data",
            entry_type=EntryType.PREFIX,
            source="s3",
        )
        assert entry.entry_type == EntryType.PREFIX
        assert entry.size is None

    def test_directory_entry(self):
        entry = StorageEntry(
            path="/tmp/mydir",
            name="mydir",
            entry_type=EntryType.DIRECTORY,
            source="local",
        )
        assert entry.entry_type == EntryType.DIRECTORY


class TestEnumerateResult:
    def test_construction(self):
        obj = StorageEntry(path="s3://b/k", name="k", source="s3")
        prefix = StorageEntry(
            path="s3://b/dir", name="dir",
            entry_type=EntryType.PREFIX, source="s3",
        )
        result = EnumerateResult(objects=(obj,), common_prefixes=(prefix,))
        assert len(result.objects) == 1
        assert len(result.common_prefixes) == 1
        assert result.objects[0].name == "k"
        assert result.common_prefixes[0].entry_type == EntryType.PREFIX

    def test_empty(self):
        result = EnumerateResult(objects=(), common_prefixes=())
        assert result.objects == ()
        assert result.common_prefixes == ()

    def test_frozen(self):
        result = EnumerateResult(objects=(), common_prefixes=())
        with pytest.raises(AttributeError):
            result.objects = ()  # type: ignore[misc]

    def test_tuples_are_immutable(self):
        result = EnumerateResult(objects=(), common_prefixes=())
        with pytest.raises(TypeError):
            result.objects.append(None)  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/_core/test_storage_entry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement StorageEntry, EntryType, and EnumerateResult**

Create `src/mountainash_transport/_core/dataclasses/storage_entry.py`:

```python
"""StorageEntry — unified resource descriptor for all storage backends."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EntryType(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    PREFIX = "prefix"


@dataclass(frozen=True, slots=True)
class StorageEntry:
    """A single storage resource — file, directory, or object-store prefix."""

    path: str
    name: str
    size: int | None = None
    last_modified: datetime | None = None
    etag: str = ""
    content_type: str = ""
    entry_type: EntryType = EntryType.FILE
    storage_class: str = ""
    source: str = ""
    version_id: str = ""
    checksum: str = ""
    checksum_algorithm: str = ""


@dataclass(frozen=True, slots=True)
class EnumerateResult:
    """Structured return type for object-store listings."""

    objects: tuple[StorageEntry, ...]
    common_prefixes: tuple[StorageEntry, ...]
```

- [ ] **Step 4: Update `_core/dataclasses/__init__.py`**

Replace the contents of `src/mountainash_transport/_core/dataclasses/__init__.py` with:

```python
from .file_metadata import FileMetadata
from .storage_entry import EntryType, EnumerateResult, StorageEntry


__all__ = (
    "EntryType",
    "EnumerateResult",
    "FileMetadata",
    "StorageEntry",
)
```

Note: `FileMetadata` stays here temporarily — it will be deleted in Task 8 after all references are migrated.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/_core/test_storage_entry.py -v`
Expected: All PASS

- [ ] **Step 6: Run full test suite to check no regressions**

Run: `hatch run test:test`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/_core/dataclasses/storage_entry.py \
        src/mountainash_transport/_core/dataclasses/__init__.py \
        tests/_core/test_storage_entry.py
git commit -m "feat: add StorageEntry, EntryType, and EnumerateResult dataclasses"
```

---

### Task 2: StorageEnumerateProtocol + Updated StorageDirectoryProtocol + StorageMetadataProtocol

**Files:**
- Create: `src/mountainash_transport/storage/protocols/prtcl_enumerate.py`
- Modify: `src/mountainash_transport/storage/protocols/prtcl_directory.py`
- Modify: `src/mountainash_transport/storage/protocols/prtcl_metadata.py`
- Modify: `src/mountainash_transport/storage/protocols/__init__.py`
- Modify: `tests/storage/protocols/test_protocol_shapes.py`

- [ ] **Step 1: Write tests for new/updated protocols**

Replace the full contents of `tests/storage/protocols/test_protocol_shapes.py`:

```python
from __future__ import annotations

import io
from typing import BinaryIO

import pytest

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)
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
    return StorageEntry(path=path, name="file.txt", source="local")


# ---------------------------------------------------------------------------
# StorageReadProtocol
# ---------------------------------------------------------------------------

class GoodRead:
    def read_to_bytes(self, path: str) -> bytes: return b""
    def read_to_stream(self, path: str) -> BinaryIO: return io.BytesIO(b"")


class BadRead:
    def read_to_bytes(self, path: str) -> bytes: return b""


class TestStorageReadProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodRead(), StorageReadProtocol)

    def test_negative_conformance(self) -> None:
        assert not isinstance(BadRead(), StorageReadProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), StorageReadProtocol)


# ---------------------------------------------------------------------------
# StorageWriteProtocol
# ---------------------------------------------------------------------------

class GoodWrite:
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...


class BadWrite:
    def write_from_bytes(self, path: str, data: bytes) -> None: ...


class TestStorageWriteProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodWrite(), StorageWriteProtocol)

    def test_negative_conformance(self) -> None:
        assert not isinstance(BadWrite(), StorageWriteProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), StorageWriteProtocol)


# ---------------------------------------------------------------------------
# StorageEnumerateProtocol (replaces StorageListProtocol)
# ---------------------------------------------------------------------------

class GoodEnumerate:
    def list_objects(
        self, prefix: str, *, delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        return EnumerateResult(objects=(), common_prefixes=())


class BadEnumerate:
    pass


class TestStorageEnumerateProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodEnumerate(), StorageEnumerateProtocol)

    def test_negative_conformance(self) -> None:
        assert not isinstance(BadEnumerate(), StorageEnumerateProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), StorageEnumerateProtocol)


# ---------------------------------------------------------------------------
# StorageDeleteProtocol
# ---------------------------------------------------------------------------

class GoodDelete:
    def delete_file(self, path: str) -> None: ...


class BadDelete:
    def remove(self, path: str) -> None: ...


class TestStorageDeleteProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodDelete(), StorageDeleteProtocol)

    def test_negative_conformance(self) -> None:
        assert not isinstance(BadDelete(), StorageDeleteProtocol)

    def test_empty_class(self) -> None:
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


class TestStorageMetadataProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodMetadata(), StorageMetadataProtocol)

    def test_negative_conformance(self) -> None:
        assert not isinstance(BadMetadata(), StorageMetadataProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), StorageMetadataProtocol)


# ---------------------------------------------------------------------------
# StorageCopyProtocol
# ---------------------------------------------------------------------------

class GoodCopy:
    def copy(self, source: str, destination: str) -> None: ...


class BadCopy:
    def duplicate(self, source: str, destination: str) -> None: ...


class TestStorageCopyProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodCopy(), StorageCopyProtocol)

    def test_negative_conformance(self) -> None:
        assert not isinstance(BadCopy(), StorageCopyProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), StorageCopyProtocol)


# ---------------------------------------------------------------------------
# StorageDirectoryProtocol (now includes list_dir)
# ---------------------------------------------------------------------------

class GoodDirectory:
    def list_dir(self, path: str) -> list[StorageEntry]: return []
    def mkdir(self, path: str, *, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


class BadDirectory:
    def mkdir(self, path: str, *, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...


class TestStorageDirectoryProtocol:
    def test_positive_conformance(self) -> None:
        assert isinstance(GoodDirectory(), StorageDirectoryProtocol)

    def test_negative_conformance_missing_list_dir(self) -> None:
        assert not isinstance(BadDirectory(), StorageDirectoryProtocol)

    def test_empty_class(self) -> None:
        assert not isinstance(object(), StorageDirectoryProtocol)


# ---------------------------------------------------------------------------
# Cross-protocol: a class implementing multiple protocols conforms to all
# ---------------------------------------------------------------------------

class FullBackend:
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: return True
    def read_to_bytes(self, path: str) -> bytes: return b""
    def read_to_stream(self, path: str) -> BinaryIO: return io.BytesIO(b"")
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...
    def list_objects(
        self, prefix: str, *, delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        return EnumerateResult(objects=(), common_prefixes=())
    def delete_file(self, path: str) -> None: ...
    def get_metadata(self, path: str) -> StorageEntry: return _make_entry(path)
    def path_exists(self, path: str) -> bool: return False
    def get_size(self, path: str) -> int | None: return 0
    def copy(self, source: str, destination: str) -> None: ...
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/protocols/test_protocol_shapes.py -v`
Expected: FAIL (StorageEnumerateProtocol doesn't exist yet, StorageDirectoryProtocol missing list_dir)

- [ ] **Step 3: Create StorageEnumerateProtocol**

Create `src/mountainash_transport/storage/protocols/prtcl_enumerate.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult


@runtime_checkable
class StorageEnumerateProtocol(Protocol):
    """Protocol for bucket/object-store listing via prefix enumeration."""

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult: ...
```

- [ ] **Step 4: Update StorageDirectoryProtocol to add list_dir**

Replace the contents of `src/mountainash_transport/storage/protocols/prtcl_directory.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageDirectoryProtocol(Protocol):
    """Protocol for filesystem-style directory operations."""

    def list_dir(self, path: str) -> list[StorageEntry]: ...

    def mkdir(self, path: str, *, parents: bool = True) -> None: ...

    def rmdir(self, path: str) -> None: ...
```

- [ ] **Step 5: Update StorageMetadataProtocol**

Replace the contents of `src/mountainash_transport/storage/protocols/prtcl_metadata.py`:

```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


@runtime_checkable
class StorageMetadataProtocol(Protocol):
    """Protocol for retrieving resource metadata from storage."""

    def get_metadata(self, path: str) -> StorageEntry: ...

    def path_exists(self, path: str) -> bool: ...

    def get_size(self, path: str) -> int | None: ...
```

- [ ] **Step 6: Update protocols `__init__.py`**

Replace the contents of `src/mountainash_transport/storage/protocols/__init__.py`:

```python
from __future__ import annotations

from mountainash_transport.storage.protocols.prtcl_copy import StorageCopyProtocol
from mountainash_transport.storage.protocols.prtcl_delete import StorageDeleteProtocol
from mountainash_transport.storage.protocols.prtcl_directory import StorageDirectoryProtocol
from mountainash_transport.storage.protocols.prtcl_enumerate import StorageEnumerateProtocol
from mountainash_transport.storage.protocols.prtcl_metadata import StorageMetadataProtocol
from mountainash_transport.storage.protocols.prtcl_read import StorageReadProtocol
from mountainash_transport.storage.protocols.prtcl_write import StorageWriteProtocol

__all__ = [
    "StorageCopyProtocol",
    "StorageDeleteProtocol",
    "StorageDirectoryProtocol",
    "StorageEnumerateProtocol",
    "StorageMetadataProtocol",
    "StorageReadProtocol",
    "StorageWriteProtocol",
]
```

- [ ] **Step 7: Run protocol shape tests**

Run: `pytest tests/storage/protocols/test_protocol_shapes.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_transport/storage/protocols/prtcl_enumerate.py \
        src/mountainash_transport/storage/protocols/prtcl_directory.py \
        src/mountainash_transport/storage/protocols/prtcl_metadata.py \
        src/mountainash_transport/storage/protocols/__init__.py \
        tests/storage/protocols/test_protocol_shapes.py
git commit -m "feat: add StorageEnumerateProtocol, update DirectoryProtocol and MetadataProtocol"
```

---

### Task 3: S3 Backend — S3EnumerateMixin + Updated S3MetadataMixin

**Files:**
- Create: `src/mountainash_transport/storage/backends/s3/s3_enumerate.py`
- Modify: `src/mountainash_transport/storage/backends/s3/s3_metadata.py`
- Modify: `src/mountainash_transport/storage/backends/s3/__init__.py`
- Modify: `tests/storage/backends/test_s3.py`

- [ ] **Step 1: Write tests for S3EnumerateMixin and updated S3MetadataMixin**

Replace the full contents of `tests/storage/backends/test_s3.py`:

```python
"""Tests for the S3StorageBackend."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.registry import get_registered_backends

import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport.storage.backends.s3 import S3StorageBackend
from mountainash_transport.storage.backends.s3.s3_path import parse_s3_path


def _make_backend(mock_client=None):
    backend = S3StorageBackend(None)
    backend._client = mock_client or MagicMock()
    return backend


def _paginator_for(pages):
    paginator = MagicMock()
    paginator.paginate.return_value = iter(pages)
    return paginator


class TestParseS3Path:
    def test_with_s3_scheme(self):
        assert parse_s3_path("s3://my-bucket/path/to/key.txt") == ("my-bucket", "path/to/key.txt")

    def test_without_scheme(self):
        assert parse_s3_path("my-bucket/some/key") == ("my-bucket", "some/key")

    def test_bucket_only_with_scheme(self):
        assert parse_s3_path("s3://my-bucket") == ("my-bucket", "")

    def test_bucket_only_no_scheme(self):
        assert parse_s3_path("my-bucket") == ("my-bucket", "")

    def test_bucket_with_trailing_slash(self):
        bucket, key = parse_s3_path("s3://my-bucket/prefix/")
        assert bucket == "my-bucket"
        assert key == "prefix"


class TestRegistration:
    def test_registered_in_registry(self):
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.S3 in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.S3] is S3StorageBackend


class TestConnection:
    def test_connect_raises_storage_connection_error_on_failure(self):
        backend = S3StorageBackend(None)
        with pytest.raises(StorageConnectionError, match="requires a connection"):
            backend.connect()

    def test_disconnect_clears_client(self):
        backend = _make_backend()
        assert backend.is_connected()
        backend.disconnect()
        assert not backend.is_connected()

    def test_is_connected_false_initially(self):
        backend = S3StorageBackend(None)
        assert not backend.is_connected()


class TestRead:
    def test_read_to_bytes(self):
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"hello s3")}
        backend = _make_backend(mock_client)
        result = backend.read_to_bytes("s3://my-bucket/data/file.txt")
        mock_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="data/file.txt")
        assert result == b"hello s3"

    def test_read_to_stream_returns_bytes_io(self):
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"stream data")}
        backend = _make_backend(mock_client)
        stream = backend.read_to_stream("s3://my-bucket/key.bin")
        assert stream.read() == b"stream data"

    def test_read_without_scheme(self):
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"no scheme")}
        backend = _make_backend(mock_client)
        result = backend.read_to_bytes("my-bucket/key.txt")
        mock_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="key.txt")
        assert result == b"no scheme"


class TestWrite:
    def test_write_from_bytes(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.write_from_bytes("s3://bucket/path/file.txt", b"write me")
        mock_client.put_object.assert_called_once_with(
            Bucket="bucket", Key="path/file.txt", Body=b"write me"
        )

    def test_write_from_stream_uses_upload_fileobj(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        stream = io.BytesIO(b"from stream")
        backend.write_from_stream("s3://bucket/path/stream.bin", stream)
        mock_client.upload_fileobj.assert_called_once_with(stream, "bucket", "path/stream.bin")
        mock_client.put_object.assert_not_called()

    def test_write_without_scheme(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.write_from_bytes("bucket/key.txt", b"data")
        mock_client.put_object.assert_called_once_with(Bucket="bucket", Key="key.txt", Body=b"data")


class TestEnumerate:
    def test_list_objects_returns_enumerate_result(self):
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {
                "Contents": [
                    {
                        "Key": "prefix/file1.txt",
                        "Size": 100,
                        "LastModified": ts,
                        "ETag": '"abc123"',
                        "StorageClass": "STANDARD",
                    }
                ]
            }
        ])
        backend = _make_backend(mock_client)
        result = backend.list_objects("s3://my-bucket/prefix/")
        assert isinstance(result, EnumerateResult)
        assert len(result.objects) == 1
        entry = result.objects[0]
        assert isinstance(entry, StorageEntry)
        assert entry.name == "file1.txt"
        assert entry.size == 100
        assert entry.last_modified == ts
        assert entry.etag == "abc123"
        assert entry.source == "s3"
        assert entry.path == "s3://my-bucket/prefix/file1.txt"
        assert entry.entry_type == EntryType.FILE

    def test_list_objects_empty(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([{"Contents": []}])
        backend = _make_backend(mock_client)
        result = backend.list_objects("s3://bucket/empty/")
        assert result.objects == ()
        assert result.common_prefixes == ()

    def test_list_objects_no_contents_key(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([{}])
        backend = _make_backend(mock_client)
        result = backend.list_objects("s3://bucket/prefix/")
        assert result.objects == ()

    def test_list_objects_with_delimiter(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {
                "CommonPrefixes": [
                    {"Prefix": "top/subdir1/"},
                    {"Prefix": "top/subdir2/"},
                ]
            }
        ])
        backend = _make_backend(mock_client)
        result = backend.list_objects("s3://bucket/top/", delimiter="/")
        assert len(result.common_prefixes) == 2
        assert result.common_prefixes[0].entry_type == EntryType.PREFIX
        assert result.common_prefixes[0].name == "subdir1"
        assert result.common_prefixes[0].path == "s3://bucket/top/subdir1/"

    def test_list_objects_delimiter_passes_to_paginator(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = iter([{}])
        mock_client.get_paginator.return_value = paginator
        backend = _make_backend(mock_client)
        backend.list_objects("s3://bucket/prefix/", delimiter="/")
        paginator.paginate.assert_called_once_with(
            Bucket="bucket", Prefix="prefix", Delimiter="/"
        )

    def test_list_objects_no_delimiter_omits_param(self):
        mock_client = MagicMock()
        paginator = MagicMock()
        paginator.paginate.return_value = iter([{}])
        mock_client.get_paginator.return_value = paginator
        backend = _make_backend(mock_client)
        backend.list_objects("s3://bucket/prefix/")
        paginator.paginate.assert_called_once_with(
            Bucket="bucket", Prefix="prefix"
        )

    def test_list_objects_max_results(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {"Contents": [{"Key": f"k/{i}", "Size": i} for i in range(10)]}
        ])
        backend = _make_backend(mock_client)
        result = backend.list_objects("s3://bucket/k/", max_results=3)
        assert len(result.objects) == 3

    def test_delimiter_suffixed_key_is_file(self):
        mock_client = MagicMock()
        mock_client.get_paginator.return_value = _paginator_for([
            {"Contents": [{"Key": "data/", "Size": 0}]}
        ])
        backend = _make_backend(mock_client)
        result = backend.list_objects("s3://bucket/")
        assert len(result.objects) == 1
        assert result.objects[0].entry_type == EntryType.FILE
        assert result.objects[0].size == 0


class TestMetadata:
    def test_get_metadata_returns_storage_entry(self):
        ts = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 512,
            "LastModified": ts,
            "ETag": '"deadbeef"',
            "StorageClass": "STANDARD",
            "ContentType": "text/csv",
        }
        backend = _make_backend(mock_client)
        meta = backend.get_metadata("s3://bucket/folder/file.csv")
        mock_client.head_object.assert_called_once_with(Bucket="bucket", Key="folder/file.csv")
        assert isinstance(meta, StorageEntry)
        assert meta.name == "file.csv"
        assert meta.size == 512
        assert meta.last_modified == ts
        assert meta.etag == "deadbeef"
        assert meta.source == "s3"
        assert meta.path == "s3://bucket/folder/file.csv"
        assert meta.content_type == "text/csv"

    def test_get_metadata_with_version_id(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 10,
            "VersionId": "abc-123",
        }
        backend = _make_backend(mock_client)
        meta = backend.get_metadata("s3://bucket/key.txt")
        assert meta.version_id == "abc-123"

    def test_get_metadata_with_checksum_sha256(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 10,
            "ChecksumSHA256": "abc123==",
        }
        backend = _make_backend(mock_client)
        meta = backend.get_metadata("s3://bucket/key.txt")
        assert meta.checksum == "abc123=="
        assert meta.checksum_algorithm == "SHA256"

    def test_get_metadata_checksum_preference_order(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 10,
            "ChecksumCRC32": "crc==",
            "ChecksumCRC32C": "crc32c==",
            "ChecksumSHA256": "sha==",
        }
        backend = _make_backend(mock_client)
        meta = backend.get_metadata("s3://bucket/key.txt")
        assert meta.checksum == "sha=="
        assert meta.checksum_algorithm == "SHA256"

    def test_path_exists_true(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 10}
        backend = _make_backend(mock_client)
        assert backend.path_exists("s3://bucket/key.txt") is True

    def test_path_exists_false_on_404(self):
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        exc = Exception("Not Found")
        exc.response = error_response
        mock_client.head_object.side_effect = exc
        mock_client.list_objects_v2.return_value = {"Contents": []}
        backend = _make_backend(mock_client)
        assert backend.path_exists("s3://bucket/missing.txt") is False

    def test_get_size_returns_int(self):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {"ContentLength": 1024}
        backend = _make_backend(mock_client)
        size = backend.get_size("s3://bucket/big-file.bin")
        assert size == 1024


class TestDelete:
    def test_delete_file_calls_delete_object(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.delete_file("s3://bucket/path/to/file.txt")
        mock_client.delete_object.assert_called_once_with(
            Bucket="bucket", Key="path/to/file.txt"
        )

    def test_delete_without_scheme(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.delete_file("bucket/key.txt")
        mock_client.delete_object.assert_called_once_with(Bucket="bucket", Key="key.txt")


class TestCopy:
    def test_copy_calls_copy_object(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.copy("s3://src-bucket/src/file.txt", "s3://dst-bucket/dst/file.txt")
        mock_client.copy_object.assert_called_once_with(
            Bucket="dst-bucket", Key="dst/file.txt",
            CopySource={"Bucket": "src-bucket", "Key": "src/file.txt"},
        )

    def test_copy_same_bucket(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.copy("s3://bucket/original.txt", "s3://bucket/copy.txt")
        mock_client.copy_object.assert_called_once_with(
            Bucket="bucket", Key="copy.txt",
            CopySource={"Bucket": "bucket", "Key": "original.txt"},
        )

    def test_copy_without_scheme(self):
        mock_client = MagicMock()
        backend = _make_backend(mock_client)
        backend.copy("src-bucket/a.txt", "dst-bucket/b.txt")
        mock_client.copy_object.assert_called_once_with(
            Bucket="dst-bucket", Key="b.txt",
            CopySource={"Bucket": "src-bucket", "Key": "a.txt"},
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/backends/test_s3.py -v`
Expected: FAIL (S3EnumerateMixin doesn't exist, S3MetadataMixin returns FileMetadata)

- [ ] **Step 3: Create S3EnumerateMixin**

Create `src/mountainash_transport/storage/backends/s3/s3_enumerate.py`:

```python
"""S3EnumerateMixin — object enumeration for S3-family backends."""
from __future__ import annotations

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)
from mountainash_transport.storage.protocols import StorageEnumerateProtocol

from .s3_path import parse_s3_path


class S3EnumerateMixin(StorageEnumerateProtocol):
    """Enumerate mixin for AWS S3."""

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        bucket, key_prefix = parse_s3_path(prefix)
        objects: list[StorageEntry] = []
        common_prefixes: list[StorageEntry] = []

        paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[attr-defined]
        paginate_kwargs: dict = {"Bucket": bucket, "Prefix": key_prefix}
        if delimiter is not None:
            paginate_kwargs["Delimiter"] = delimiter

        for page in paginator.paginate(**paginate_kwargs):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                name = key.rsplit("/", 1)[-1] if "/" in key else key
                objects.append(
                    StorageEntry(
                        path=f"s3://{bucket}/{key}",
                        name=name,
                        size=obj.get("Size", 0),
                        last_modified=obj.get("LastModified"),
                        etag=obj.get("ETag", "").strip('"'),
                        storage_class=obj.get("StorageClass", ""),
                        source="s3",
                    )
                )
            for cp in page.get("CommonPrefixes", []) or []:
                raw_prefix: str = cp.get("Prefix", "")
                stripped = raw_prefix.rstrip("/")
                name = stripped.rsplit("/", 1)[-1] if "/" in stripped else stripped
                common_prefixes.append(
                    StorageEntry(
                        path=f"s3://{bucket}/{raw_prefix}",
                        name=name,
                        entry_type=EntryType.PREFIX,
                        source="s3",
                    )
                )

        all_entries = objects + common_prefixes
        if max_results is not None and len(all_entries) > max_results:
            objects = objects[:max_results]
            remaining = max_results - len(objects)
            common_prefixes = common_prefixes[:max(0, remaining)]

        return EnumerateResult(
            objects=tuple(objects),
            common_prefixes=tuple(common_prefixes),
        )
```

- [ ] **Step 4: Update S3MetadataMixin to return StorageEntry with version_id and checksum**

Replace the contents of `src/mountainash_transport/storage/backends/s3/s3_metadata.py`:

```python
"""S3MetadataMixin — metadata operations for AWS S3."""
from __future__ import annotations

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport.storage.protocols import StorageMetadataProtocol

from .s3_path import parse_s3_path

_CHECKSUM_PREFERENCE = (
    ("ChecksumSHA256", "SHA256"),
    ("ChecksumCRC32C", "CRC32C"),
    ("ChecksumCRC32", "CRC32"),
    ("ChecksumSHA1", "SHA1"),
)


def _pick_checksum(response: dict) -> tuple[str, str]:
    for key, algorithm in _CHECKSUM_PREFERENCE:
        value = response.get(key)
        if value:
            return value, algorithm
    return "", ""


class S3MetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for AWS S3."""

    def get_metadata(self, path: str) -> StorageEntry:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        name = key.rsplit("/", 1)[-1] if "/" in key else key
        checksum, checksum_algorithm = _pick_checksum(response)
        return StorageEntry(
            path=f"s3://{bucket}/{key}",
            name=name,
            size=response.get("ContentLength", 0),
            last_modified=response.get("LastModified"),
            etag=response.get("ETag", "").strip('"'),
            content_type=response.get("ContentType", ""),
            storage_class=response.get("StorageClass", ""),
            source="s3",
            version_id=response.get("VersionId", ""),
            checksum=checksum,
            checksum_algorithm=checksum_algorithm,
        )

    def path_exists(self, path: str) -> bool:
        bucket, key = parse_s3_path(path)
        if not key:
            response = self._client.list_objects_v2(Bucket=bucket, MaxKeys=1)  # type: ignore[attr-defined]
            return response.get("ResponseMetadata", {}).get("HTTPStatusCode", 404) == 200
        try:
            self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
            return True
        except Exception as exc:
            error_code = ""
            response_attr = getattr(exc, "response", None)
            if isinstance(response_attr, dict):
                error_code = response_attr.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            list_response = self._client.list_objects_v2(  # type: ignore[attr-defined]
                Bucket=bucket, Prefix=key, MaxKeys=1
            )
            return bool(list_response.get("Contents"))

    def get_size(self, path: str) -> int | None:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return response.get("ContentLength")
```

- [ ] **Step 5: Update S3StorageBackend `__init__.py`**

In `src/mountainash_transport/storage/backends/s3/__init__.py`, replace the import and mixin:

Replace `from .s3_list import S3ListMixin` with `from .s3_enumerate import S3EnumerateMixin`.

In the class definition, replace `S3ListMixin` with `S3EnumerateMixin`.

In `__all__`, replace `"S3ListMixin"` with `"S3EnumerateMixin"`.

- [ ] **Step 6: Run S3 tests**

Run: `pytest tests/storage/backends/test_s3.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/storage/backends/s3/s3_enumerate.py \
        src/mountainash_transport/storage/backends/s3/s3_metadata.py \
        src/mountainash_transport/storage/backends/s3/__init__.py \
        tests/storage/backends/test_s3.py
git commit -m "feat: S3 backend — S3EnumerateMixin + StorageEntry metadata with checksum/version"
```

---

### Task 4: Local Backend — list_dir + StorageEntry Metadata

**Files:**
- Modify: `src/mountainash_transport/storage/backends/local/local_list.py`
- Modify: `src/mountainash_transport/storage/backends/local/local_metadata.py`
- Modify: `src/mountainash_transport/storage/backends/local/local_directory.py`
- Modify: `src/mountainash_transport/storage/backends/local/__init__.py`
- Modify: `tests/storage/backends/test_local.py`

- [ ] **Step 1: Write tests for local backend list_dir and StorageEntry metadata**

The existing `tests/storage/backends/test_local.py` references `FileMetadata`, `list_files`, and `list_directories`. The test file needs to be updated to use `StorageEntry`, `list_dir`, and the new metadata return type. Read the current file, then replace:

- All `FileMetadata` imports → `StorageEntry` from `_core.dataclasses.storage_entry`
- All `isinstance(meta, FileMetadata)` → `isinstance(meta, StorageEntry)`
- All `meta.filename` → `meta.name`
- All `meta.full_path` → `meta.path`
- The `TestList` class tests for `list_files`/`list_directories` → tests for `list_dir` returning `StorageEntry` items with `entry_type` set correctly
- Add tests for symlink handling (broken symlinks skipped, symlinks to dirs show as DIRECTORY)

Add these tests to the `TestList` section:

```python
class TestListDir:
    def test_list_dir_returns_storage_entries(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("hello")
        os.makedirs(os.path.join(tmp_dir, "subdir"))
        results = backend.list_dir(tmp_dir)
        assert len(results) == 2
        names = {e.name for e in results}
        assert names == {"a.txt", "subdir"}

    def test_list_dir_entry_types(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("hello")
        os.makedirs(os.path.join(tmp_dir, "subdir"))
        results = backend.list_dir(tmp_dir)
        by_name = {e.name: e for e in results}
        assert by_name["a.txt"].entry_type == EntryType.FILE
        assert by_name["subdir"].entry_type == EntryType.DIRECTORY

    def test_list_dir_empty(self, backend, tmp_dir):
        results = backend.list_dir(tmp_dir)
        assert results == []

    def test_list_dir_file_has_size(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("12345")
        results = backend.list_dir(tmp_dir)
        assert results[0].size == 5

    def test_list_dir_directory_has_none_size(self, backend, tmp_dir):
        os.makedirs(os.path.join(tmp_dir, "subdir"))
        results = backend.list_dir(tmp_dir)
        assert results[0].size is None

    def test_list_dir_symlink_to_file(self, backend, tmp_dir):
        target = os.path.join(tmp_dir, "real.txt")
        link = os.path.join(tmp_dir, "link.txt")
        with open(target, "w") as f:
            f.write("data")
        os.symlink(target, link)
        results = backend.list_dir(tmp_dir)
        by_name = {e.name: e for e in results}
        assert by_name["link.txt"].entry_type == EntryType.FILE

    def test_list_dir_symlink_to_dir(self, backend, tmp_dir):
        target = os.path.join(tmp_dir, "realdir")
        link = os.path.join(tmp_dir, "linkdir")
        os.makedirs(target)
        os.symlink(target, link)
        results = backend.list_dir(tmp_dir)
        by_name = {e.name: e for e in results}
        assert by_name["linkdir"].entry_type == EntryType.DIRECTORY

    def test_list_dir_broken_symlink_skipped(self, backend, tmp_dir):
        link = os.path.join(tmp_dir, "broken")
        os.symlink("/nonexistent/target", link)
        results = backend.list_dir(tmp_dir)
        assert len(results) == 0

    def test_list_dir_source_is_local(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("x")
        results = backend.list_dir(tmp_dir)
        assert results[0].source == "local"

    def test_list_dir_path_is_absolute(self, backend, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("x")
        results = backend.list_dir(tmp_dir)
        assert os.path.isabs(results[0].path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/backends/test_local.py::TestListDir -v`
Expected: FAIL

- [ ] **Step 3: Rewrite local_list.py as list_dir returning StorageEntry**

Replace the contents of `src/mountainash_transport/storage/backends/local/local_list.py`:

```python
"""LocalListMixin — directory listing for local filesystem using StorageEntry."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    StorageEntry,
)


class LocalListMixin:
    """List mixin for local filesystem — implements list_dir."""

    def list_dir(self, path: str) -> list[StorageEntry]:
        """Return StorageEntry for every immediate child of *path*.

        Symlinks are resolved via stat(). Broken symlinks are skipped.
        """
        results: list[StorageEntry] = []
        if not os.path.isdir(path):
            return results

        for entry in os.scandir(path):
            try:
                is_dir = entry.is_dir(follow_symlinks=True)
                is_file = entry.is_file(follow_symlinks=True)
            except OSError:
                continue

            if not is_dir and not is_file:
                continue

            stat = entry.stat(follow_symlinks=True)
            results.append(
                StorageEntry(
                    path=os.path.abspath(entry.path),
                    name=entry.name,
                    size=stat.st_size if is_file else None,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                    entry_type=EntryType.DIRECTORY if is_dir else EntryType.FILE,
                    source="local",
                )
            )
        return results
```

- [ ] **Step 4: Update local_metadata.py to return StorageEntry**

Replace the contents of `src/mountainash_transport/storage/backends/local/local_metadata.py`:

```python
"""LocalMetadataMixin — file metadata operations for local filesystem."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry


class LocalMetadataMixin:
    """Metadata mixin for local filesystem."""

    def get_metadata(self, path: str) -> StorageEntry:
        """Return StorageEntry for the file at *path*."""
        stat = os.stat(path)
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return StorageEntry(
            path=os.path.abspath(path),
            name=os.path.basename(path),
            size=stat.st_size,
            last_modified=last_modified,
            storage_class="local",
            source="local",
        )

    def path_exists(self, path: str) -> bool:
        return os.path.exists(path)

    def get_size(self, path: str) -> int | None:
        try:
            return os.path.getsize(path)
        except OSError:
            return None
```

- [ ] **Step 5: Remove list_files/list_directories from LocalStorageBackend composition**

In `src/mountainash_transport/storage/backends/local/__init__.py`, the `LocalListMixin` is still included (it now provides `list_dir` instead of `list_files`/`list_directories`). No change needed to the class hierarchy — `LocalListMixin` is already in the mixin list and now implements the new interface.

- [ ] **Step 6: Run local backend tests**

Run: `pytest tests/storage/backends/test_local.py -v`
Expected: The new `TestListDir` tests PASS. Existing tests that reference `FileMetadata`/`list_files`/`list_directories` will fail — update those too (replace all `FileMetadata` references with `StorageEntry`, replace `list_files`/`list_directories` calls with `list_dir`, update assertions for new field names).

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_transport/storage/backends/local/local_list.py \
        src/mountainash_transport/storage/backends/local/local_metadata.py \
        tests/storage/backends/test_local.py
git commit -m "feat: local backend — list_dir with StorageEntry, symlink handling"
```

---

### Task 5: SFTP Backend — list_dir + mkdir/rmdir + StorageEntry Metadata

**Files:**
- Modify: `src/mountainash_transport/storage/backends/ssh/__init__.py`
- Modify: `tests/storage/backends/test_sftp.py`

- [ ] **Step 1: Write tests for SFTP list_dir, mkdir, rmdir, and StorageEntry metadata**

Add these test classes to `tests/storage/backends/test_sftp.py` (and update existing metadata tests to expect `StorageEntry`):

```python
class TestListDir:
    def test_list_dir_returns_storage_entries(self):
        mock_sftp = MagicMock()
        attr_file = MagicMock()
        attr_file.filename = "file.txt"
        attr_file.st_size = 100
        attr_file.st_mtime = 1700000000.0
        attr_file.st_mode = 0o100644  # regular file

        attr_dir = MagicMock()
        attr_dir.filename = "subdir"
        attr_dir.st_size = 4096
        attr_dir.st_mtime = 1700000000.0
        attr_dir.st_mode = 0o040755  # directory

        mock_sftp.listdir_attr.return_value = [attr_file, attr_dir]
        backend, _ = _make_backend(mock_sftp)
        results = backend.list_dir("/remote/path")
        assert len(results) == 2
        by_name = {e.name: e for e in results}
        assert by_name["file.txt"].entry_type == EntryType.FILE
        assert by_name["file.txt"].size == 100
        assert by_name["subdir"].entry_type == EntryType.DIRECTORY

    def test_list_dir_empty(self):
        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.return_value = []
        backend, _ = _make_backend(mock_sftp)
        results = backend.list_dir("/remote/empty")
        assert results == []

    def test_list_dir_path_not_found(self):
        mock_sftp = MagicMock()
        mock_sftp.listdir_attr.side_effect = FileNotFoundError("no such dir")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.list_dir("/remote/missing")


class TestMkdir:
    def test_mkdir_calls_sftp_mkdir(self):
        mock_sftp = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        backend.mkdir("/remote/newdir")
        mock_sftp.mkdir.assert_called_once_with("/remote/newdir")

    def test_mkdir_not_found_raises(self):
        mock_sftp = MagicMock()
        mock_sftp.mkdir.side_effect = FileNotFoundError("parent missing")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.mkdir("/remote/deep/newdir")


class TestRmdir:
    def test_rmdir_calls_sftp_rmdir(self):
        mock_sftp = MagicMock()
        backend, _ = _make_backend(mock_sftp)
        backend.rmdir("/remote/olddir")
        mock_sftp.rmdir.assert_called_once_with("/remote/olddir")

    def test_rmdir_not_found_raises(self):
        mock_sftp = MagicMock()
        mock_sftp.rmdir.side_effect = FileNotFoundError("no such dir")
        backend, _ = _make_backend(mock_sftp)
        with pytest.raises(PathNotFoundError):
            backend.rmdir("/remote/missing")
```

Also add `from mountainash_transport._core.dataclasses.storage_entry import EntryType, StorageEntry` to the imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/backends/test_sftp.py::TestListDir -v`
Expected: FAIL

- [ ] **Step 3: Update SFTPStorageBackend**

In `src/mountainash_transport/storage/backends/ssh/__init__.py`, update the import and add the new methods:

Replace `from mountainash_transport._core.dataclasses.file_metadata import FileMetadata` with:
```python
from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    StorageEntry,
)
```

Add `import stat as stat_module` to the imports.

Replace the `list_paths` method with `list_dir`:

```python
    def list_dir(self, path: str) -> list[StorageEntry]:
        sftp = self._get_client()
        try:
            entries = sftp.listdir_attr(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

        results: list[StorageEntry] = []
        for attr in entries:
            is_dir = stat_module.S_ISDIR(attr.st_mode) if attr.st_mode is not None else False
            mtime = getattr(attr, "st_mtime", None)
            last_modified = None
            if mtime is not None:
                try:
                    last_modified = datetime.fromtimestamp(mtime)
                except (ValueError, OSError):
                    pass
            child_path = f"{path.rstrip('/')}/{attr.filename}"
            results.append(
                StorageEntry(
                    path=child_path,
                    name=attr.filename,
                    size=getattr(attr, "st_size", None) if not is_dir else None,
                    last_modified=last_modified,
                    entry_type=EntryType.DIRECTORY if is_dir else EntryType.FILE,
                    source="sftp",
                )
            )
        return results
```

Replace the `delete_path` method name with `delete_file`:

```python
    def delete_file(self, path: str) -> None:
        sftp = self._get_client()
        try:
            sftp.remove(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc
```

Replace `get_metadata` to return `StorageEntry`:

```python
    def get_metadata(self, path: str) -> StorageEntry:
        sftp = self._get_client()
        try:
            stat = sftp.stat(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

        name = path.rsplit("/", 1)[-1] if "/" in path else path
        last_modified = None
        mtime = getattr(stat, "st_mtime", None)
        if mtime is not None:
            try:
                last_modified = datetime.fromtimestamp(mtime)
            except (ValueError, OSError):
                pass

        return StorageEntry(
            path=path,
            name=name,
            size=getattr(stat, "st_size", None),
            last_modified=last_modified,
            source="sftp",
        )
```

Replace `get_size` to return `int | None`:

```python
    def get_size(self, path: str) -> int | None:
        sftp = self._get_client()
        try:
            stat = sftp.stat(path)
            return getattr(stat, "st_size", None)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc
```

Add `mkdir` and `rmdir`:

```python
    def mkdir(self, path: str, *, parents: bool = True) -> None:
        sftp = self._get_client()
        try:
            sftp.mkdir(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc

    def rmdir(self, path: str) -> None:
        sftp = self._get_client()
        try:
            sftp.rmdir(path)
        except (FileNotFoundError, IOError, PermissionError) as exc:
            raise _wrap_sftp_error(exc, path) from exc
```

- [ ] **Step 4: Update existing SFTP test assertions**

In `tests/storage/backends/test_sftp.py`, update the existing `test_builds_file_metadata` test to check `StorageEntry` fields (`.name` instead of `.filename`, `.path` instead of `.full_path`). Update the `test_delete_path` tests to call `delete_file` instead.

- [ ] **Step 5: Run SFTP tests**

Run: `pytest tests/storage/backends/test_sftp.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/storage/backends/ssh/__init__.py \
        tests/storage/backends/test_sftp.py
git commit -m "feat: SFTP backend — list_dir, mkdir, rmdir, StorageEntry metadata"
```

---

### Task 6: HTTP Backend — StorageEntry Metadata with content_type and checksum

**Files:**
- Modify: `src/mountainash_transport/storage/backends/http/__init__.py`
- Modify: `tests/storage/backends/test_http.py`

- [ ] **Step 1: Write tests for HTTP StorageEntry metadata**

Update `tests/storage/backends/test_http.py` — change the existing metadata test and add checksum/content_type tests:

```python
    def test_get_metadata_returns_storage_entry(self):
        # ... (same mock setup as current test_builds_file_metadata_from_headers)
        meta = backend.get_metadata("https://example.com/path/file.txt")
        assert isinstance(meta, StorageEntry)
        assert meta.path == "https://example.com/path/file.txt"
        assert meta.name == "file.txt"
        assert meta.content_type == "application/json"
        assert meta.source == "http"

    def test_get_metadata_with_content_md5(self):
        # Mock HEAD response with Content-MD5 header
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            "content-length": "100",
            "content-md5": "abc123==",
            "content-type": "text/plain",
        }
        # ... setup client mock ...
        meta = backend.get_metadata("https://example.com/file.txt")
        assert meta.checksum == "abc123=="
        assert meta.checksum_algorithm == "MD5"

    def test_get_size_returns_none_without_header(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        # ... setup client mock ...
        size = backend.get_size("https://example.com/file.txt")
        assert size is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/backends/test_http.py -v`
Expected: FAIL (still returns FileMetadata)

- [ ] **Step 3: Update HTTPStorageBackend**

In `src/mountainash_transport/storage/backends/http/__init__.py`:

Replace `from mountainash_transport._core.dataclasses.file_metadata import FileMetadata` with:
```python
from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
```

Replace `get_metadata` to return `StorageEntry`:

```python
    def get_metadata(self, path: str) -> StorageEntry:
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

        headers = response.headers
        size_str = headers.get("content-length")
        size = int(size_str) if size_str else None
        etag = headers.get("etag", "")
        content_type = headers.get("content-type", "")
        content_md5 = headers.get("content-md5", "")

        last_modified = None
        lm_header = headers.get("last-modified")
        if lm_header:
            try:
                last_modified = parsedate_to_datetime(lm_header)
            except (ValueError, TypeError):
                pass

        return StorageEntry(
            path=path,
            name=_filename_from_url(path),
            size=size,
            last_modified=last_modified,
            etag=etag,
            content_type=content_type,
            source="http",
            checksum=content_md5,
            checksum_algorithm="MD5" if content_md5 else "",
        )
```

Replace `get_size` to return `int | None`:

```python
    def get_size(self, path: str) -> int | None:
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        size_str = response.headers.get("content-length")
        return int(size_str) if size_str else None
```

Remove `_directory_from_url` helper — no longer needed (StorageEntry has no `directory` field).

- [ ] **Step 4: Run HTTP tests**

Run: `pytest tests/storage/backends/test_http.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/storage/backends/http/__init__.py \
        tests/storage/backends/test_http.py
git commit -m "feat: HTTP backend — StorageEntry metadata with content_type and checksum"
```

---

### Task 7: Facade — list_objects + list_dir + Updated Metadata

**Files:**
- Modify: `src/mountainash_transport/storage/facade/facade.py`
- Modify: `tests/storage/facade/test_facade.py`
- Modify: `tests/storage/cross_backend/test_list.py`

- [ ] **Step 1: Write tests for facade list_objects and list_dir**

Add tests to `tests/storage/facade/test_facade.py`:

```python
class TestListDir:
    def test_list_dir_returns_storage_entries(self, local_facade, tmp_dir):
        with open(os.path.join(tmp_dir, "a.txt"), "w") as f:
            f.write("hello")
        results = local_facade.list_dir(tmp_dir)
        assert len(results) == 1
        assert isinstance(results[0], StorageEntry)

    def test_list_dir_raises_for_http(self):
        facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.HTTP)
        with pytest.raises(UnsupportedOperationError):
            facade.list_dir("/some/path")


class TestListObjects:
    def test_list_objects_raises_for_local(self, local_facade):
        with pytest.raises(UnsupportedOperationError):
            local_facade.list_objects("some/prefix")
```

Also update `tests/storage/facade/test_facade.py` imports — replace `FileMetadata` with `StorageEntry`, replace `StorageListProtocol` with `StorageEnumerateProtocol`. Update the `TestSupports` test that checks `StorageListProtocol` to check `StorageDirectoryProtocol` instead (local backend has directory, not enumerate). Update `test_metadata_returns_file_metadata` to check `StorageEntry`. Remove `test_list_files_returns_file_metadata_list` and `test_list_directories_returns_directories`.

Update `tests/storage/cross_backend/test_list.py`:

```python
"""Cross-backend parametrized tests: directory listing."""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest

import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
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
def test_list_dir_returns_correct_count(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    for i in range(3):
        facade.write(os.path.join(tmp_dir, f"file_{i}.txt"), b"data")
    results = facade.list_dir(tmp_dir)
    assert len(results) == 3


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
def test_list_dir_empty(backend_name: str, tmp_dir: str) -> None:
    facade = make_facade(backend_name)
    results = facade.list_dir(tmp_dir)
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/storage/facade/test_facade.py -v`
Expected: FAIL (facade still has `list_files`/`list_directories`, no `list_dir`/`list_objects`)

- [ ] **Step 3: Update StorageFacade**

In `src/mountainash_transport/storage/facade/facade.py`:

Replace `from mountainash_transport._core.dataclasses.file_metadata import FileMetadata` with:
```python
from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult, StorageEntry
```

Replace `StorageListProtocol` import with `StorageEnumerateProtocol`:
```python
from mountainash_transport.storage.protocols import (
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageEnumerateProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)
```

Replace the list operations section (lines 265-276):

```python
    # ------------------------------------------------------------------
    # Enumerate operations (StorageEnumerateProtocol)
    # ------------------------------------------------------------------

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = "/",
        max_results: int | None = None,
    ) -> EnumerateResult:
        """Bucket-store listing. Requires StorageEnumerateProtocol."""
        self._require(StorageEnumerateProtocol, "list_objects")
        return self._backend.list_objects(prefix, delimiter=delimiter, max_results=max_results)

    # ------------------------------------------------------------------
    # Directory operations (StorageDirectoryProtocol)
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[StorageEntry]:
        """Filesystem listing. Requires StorageDirectoryProtocol."""
        self._require(StorageDirectoryProtocol, "list_dir")
        return self._backend.list_dir(path)
```

Update `metadata` return type:

```python
    def metadata(self, path: str) -> StorageEntry:
        """Return metadata for the resource at *path*."""
        self._require(StorageMetadataProtocol, "metadata")
        return self._backend.get_metadata(path)

    def get_size(self, path: str) -> int | None:
        """Return the size in bytes of the file at *path*, or None if unknown."""
        self._require(StorageMetadataProtocol, "get_size")
        return self._backend.get_size(path)
```

Keep the existing `mkdir` and `rmdir` methods under the Directory operations section.

- [ ] **Step 4: Run facade and cross-backend tests**

Run: `pytest tests/storage/facade/ tests/storage/cross_backend/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/storage/facade/facade.py \
        tests/storage/facade/test_facade.py \
        tests/storage/cross_backend/test_list.py
git commit -m "feat: facade — list_objects + list_dir, remove unified list"
```

---

### Task 8: Backend Conformance Tests + Delete FileMetadata + Exports

**Files:**
- Delete: `src/mountainash_transport/_core/dataclasses/file_metadata.py`
- Delete: `src/mountainash_transport/storage/protocols/prtcl_list.py`
- Delete: `src/mountainash_transport/storage/backends/s3/s3_list.py`
- Modify: `src/mountainash_transport/_core/dataclasses/__init__.py`
- Modify: `src/mountainash_transport/__init__.py`
- Modify: `tests/storage/protocols/test_backend_conformance.py`
- Modify: `tests/test_public_api.py`

- [ ] **Step 1: Update backend conformance tests**

Replace the contents of `tests/storage/protocols/test_backend_conformance.py`:

```python
"""Enforce that every registered backend conforms to its declared protocols."""
import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage.protocols import (
    StorageReadProtocol, StorageWriteProtocol,
    StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
    StorageCopyProtocol, StorageDirectoryProtocol,
)
from mountainash_transport.storage.registry import get_registered_backends
import mountainash_transport.storage.backends  # noqa: F401

EXPECTED_PROTOCOLS = {
    CONST_STORAGE_PROVIDER_TYPE.LOCAL: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol, StorageDirectoryProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.S3: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.R2: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.MINIO: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.SSH: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageDeleteProtocol, StorageMetadataProtocol,
        StorageDirectoryProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.HTTP: {
        StorageReadProtocol, StorageWriteProtocol, StorageMetadataProtocol,
    },
}

EXCLUDED_PROTOCOLS = {
    CONST_STORAGE_PROVIDER_TYPE.S3: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.R2: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.MINIO: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.SSH: {StorageEnumerateProtocol, StorageCopyProtocol},
    CONST_STORAGE_PROVIDER_TYPE.HTTP: {
        StorageEnumerateProtocol,
        StorageDeleteProtocol, StorageCopyProtocol, StorageDirectoryProtocol,
    },
}


class TestProtocolConformance:
    @pytest.mark.parametrize("provider_type", list(EXPECTED_PROTOCOLS.keys()))
    def test_backend_implements_required_protocols(self, provider_type):
        backends = get_registered_backends()
        assert provider_type in backends
        backend_cls = backends[provider_type]
        for protocol in EXPECTED_PROTOCOLS[provider_type]:
            assert issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} does not implement {protocol.__name__}"
            )

    @pytest.mark.parametrize("provider_type", list(EXCLUDED_PROTOCOLS.keys()))
    def test_backend_excludes_unsupported_protocols(self, provider_type):
        backends = get_registered_backends()
        backend_cls = backends[provider_type]
        for protocol in EXCLUDED_PROTOCOLS[provider_type]:
            assert not issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} should NOT implement {protocol.__name__}"
            )
```

- [ ] **Step 2: Delete FileMetadata, prtcl_list.py, and s3_list.py**

```bash
rm src/mountainash_transport/_core/dataclasses/file_metadata.py
rm src/mountainash_transport/storage/protocols/prtcl_list.py
rm src/mountainash_transport/storage/backends/s3/s3_list.py
```

- [ ] **Step 3: Update `_core/dataclasses/__init__.py`**

```python
from .storage_entry import EntryType, EnumerateResult, StorageEntry


__all__ = (
    "EntryType",
    "EnumerateResult",
    "StorageEntry",
)
```

- [ ] **Step 4: Update top-level `__init__.py`**

In `src/mountainash_transport/__init__.py`:

Replace imports:
- `from ._core.dataclasses.file_metadata import FileMetadata` → `from ._core.dataclasses.storage_entry import EntryType, EnumerateResult, StorageEntry`
- `StorageListProtocol` → `StorageEnumerateProtocol` in the protocols import block

Update `__all__`:
- Replace `"StorageListProtocol"` with `"StorageEnumerateProtocol"`
- Replace `"FileMetadata"` with `"StorageEntry", "EntryType", "EnumerateResult"`

- [ ] **Step 5: Update public API test**

In `tests/test_public_api.py`, update:

```python
    def test_protocols_importable(self):
        from mountainash_transport import (
            StorageReadProtocol, StorageWriteProtocol, StorageEnumerateProtocol,
            StorageDeleteProtocol, StorageMetadataProtocol, StorageCopyProtocol,
            StorageDirectoryProtocol, ConnectionProtocol, TransportConnectionError,
        )

    def test_dataclasses_importable(self):
        from mountainash_transport import StorageEntry, EntryType, EnumerateResult
        assert EntryType.FILE == "file"
```

Remove any test that imports `FileMetadata` or `StorageListProtocol`.

- [ ] **Step 6: Run full test suite**

Run: `hatch run test:test`
Expected: All tests pass. No references to `FileMetadata`, `StorageListProtocol`, `list_files`, or `list_directories` remain.

- [ ] **Step 7: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: delete FileMetadata + StorageListProtocol, update exports"
```

---

### Task 9: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `hatch run test:test`
Expected: All pass

- [ ] **Step 2: Run lint**

Run: `hatch run ruff:check`
Expected: Clean

- [ ] **Step 3: Verify no stale references**

```bash
grep -rn "FileMetadata\|StorageListProtocol\|list_files\|list_directories\|prtcl_list\|s3_list\|file_metadata" \
  src/ tests/ --include="*.py" | grep -v __pycache__
```

Expected: No output (zero matches)

- [ ] **Step 4: Verify StorageEntry is used everywhere**

```bash
grep -rn "StorageEntry\|EnumerateResult\|EntryType" src/ --include="*.py" | grep -v __pycache__ | wc -l
```

Expected: Non-zero count across dataclasses, protocols, backends, and facade

- [ ] **Step 5: Commit any remaining fixes**

```bash
git add -A
git commit -m "chore: final cleanup for storage protocol redesign"
```
