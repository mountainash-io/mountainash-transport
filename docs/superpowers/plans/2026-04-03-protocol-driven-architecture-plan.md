# Protocol-Driven Architecture Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inheritance-heavy file helpers architecture with protocol-driven composition, matching mountainash-expressions patterns.

**Architecture:** Three layers — protocols (contracts), backends (mixin compositions), facade (user API) — with a decorator-based registry for backend discovery. Each storage backend composes focused mixin classes via multiple inheritance. The facade dispatches to protocol-checked backends.

**Tech Stack:** Python 3.10+, typing.Protocol, pydantic (FileMetadata), pytest with parametrize, boto3 (S3), os/shutil/pathlib (local)

**Spec:** `docs/superpowers/specs/2026-04-03-protocol-driven-architecture-design.md`

---

## File Map

### New Files (by task)

| Task | File | Responsibility |
|------|------|---------------|
| 1 | `src/mountainash_utils_files/exceptions.py` | Custom exception hierarchy |
| 2 | `src/mountainash_utils_files/storage_protocols/__init__.py` | Protocol exports |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_connection.py` | StorageConnectionProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_read.py` | StorageReadProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_write.py` | StorageWriteProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_list.py` | StorageListProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_delete.py` | StorageDeleteProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_metadata.py` | StorageMetadataProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_copy.py` | StorageCopyProtocol |
| 2 | `src/mountainash_utils_files/storage_protocols/prtcl_directory.py` | StorageDirectoryProtocol |
| 3 | `src/mountainash_utils_files/storage_registry/__init__.py` | Registry exports |
| 3 | `src/mountainash_utils_files/storage_registry/registry.py` | Backend registration + lookup |
| 3 | `src/mountainash_utils_files/storage_registry/backend_detection.py` | Path scheme → provider type |
| 4 | `src/mountainash_utils_files/storage_backends/__init__.py` | Triggers all registrations |
| 4 | `src/mountainash_utils_files/storage_backends/local/__init__.py` | LocalStorageBackend composition |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_connection.py` | LocalConnectionMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_read.py` | LocalReadMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_write.py` | LocalWriteMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_list.py` | LocalListMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_delete.py` | LocalDeleteMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_metadata.py` | LocalMetadataMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_copy.py` | LocalCopyMixin |
| 4 | `src/mountainash_utils_files/storage_backends/local/local_directory.py` | LocalDirectoryMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/__init__.py` | S3StorageBackend composition |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_connection.py` | S3ConnectionMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_read.py` | S3ReadMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_write.py` | S3WriteMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_list.py` | S3ListMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_delete.py` | S3DeleteMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_metadata.py` | S3MetadataMixin |
| 5 | `src/mountainash_utils_files/storage_backends/s3/s3_copy.py` | S3CopyMixin |
| 6 | `src/mountainash_utils_files/storage_backends/r2/__init__.py` | R2StorageBackend composition |
| 6 | `src/mountainash_utils_files/storage_backends/r2/r2_connection.py` | R2ConnectionMixin |
| 6 | `src/mountainash_utils_files/storage_backends/s3express/__init__.py` | S3ExpressStorageBackend |
| 6 | `src/mountainash_utils_files/storage_backends/s3express/s3express_connection.py` | S3ExpressConnectionMixin |
| 6 | `src/mountainash_utils_files/storage_backends/minio/__init__.py` | MinIOStorageBackend |
| 6 | `src/mountainash_utils_files/storage_backends/minio/minio_connection.py` | MinIOConnectionMixin |
| 7 | `src/mountainash_utils_files/storage_facade/__init__.py` | Facade exports |
| 7 | `src/mountainash_utils_files/storage_facade/facade.py` | StorageFacade |
| 7 | `src/mountainash_utils_files/storage_facade/cross_backend.py` | copy_between() |
| 8 | `tests/protocol_alignment/test_protocol_conformance.py` | Protocol alignment tests |
| 8 | `tests/protocol_alignment/test_registry_completeness.py` | Registry tests |
| 9 | `tests/cross_backend/test_read_write.py` | Parametrized read/write |
| 9 | `tests/cross_backend/test_list.py` | Parametrized list |
| 9 | `tests/cross_backend/test_metadata.py` | Parametrized metadata |
| 9 | `tests/cross_backend/test_delete.py` | Parametrized delete |
| 7 | `tests/facade/test_facade.py` | Facade dispatch + unsupported ops + cross-backend copy |

### Modified Files

| Task | File | Change |
|------|------|--------|
| 1 | `src/mountainash_utils_files/constants.py` | Remove old enums, keep `CONST_STORAGE_PROVIDER_TYPE` |
| 11 | `src/mountainash_utils_files/__init__.py` | Replace all exports with new public API |
| 11 | `tests/conftest.py` | Update fixtures for new architecture |

### Deleted Files (Task 12)

All files listed in spec Section 12 — `file_helpers/`, `factories/`, `file_interface/`, `file_sync/`, `file_readers/`, `file_writers/`.

---

## Phase 1: Foundation (Tasks 1-3)

### Task 1: Constants Consolidation & Custom Exceptions

**Files:**
- Modify: `src/mountainash_utils_files/constants.py`
- Create: `src/mountainash_utils_files/exceptions.py`
- Test: `tests/test_constants_and_exceptions.py`

- [ ] **Step 1: Write test for unified constants**

```python
# tests/test_constants_and_exceptions.py

import pytest
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


class TestStorageProviderType:
    """Verify unified constant enum has all expected members."""

    def test_has_all_provider_types(self):
        expected = {"local", "s3", "s3express", "r2", "minio", "gcs", "azure_blob", "sftp", "ssh", "b2"}
        actual = {member.value for member in CONST_STORAGE_PROVIDER_TYPE}
        assert actual == expected

    def test_is_str_enum(self):
        assert isinstance(CONST_STORAGE_PROVIDER_TYPE.LOCAL, str)
        assert CONST_STORAGE_PROVIDER_TYPE.LOCAL == "local"

    def test_old_enums_removed(self):
        """CONST_STORAGESYSTEM and CONST_STORAGESYSTEM_PREFIX must not exist."""
        from mountainash_utils_files import constants
        assert not hasattr(constants, "CONST_STORAGESYSTEM")
        assert not hasattr(constants, "CONST_STORAGESYSTEM_PREFIX")
        assert not hasattr(constants, "CONST_DATAFILEFORMAT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/test_constants_and_exceptions.py::TestStorageProviderType -v`
Expected: `test_old_enums_removed` FAILS (old enums still exist)

- [ ] **Step 3: Update constants.py — remove old enums, trim provider type**

Replace the entire contents of `src/mountainash_utils_files/constants.py` with:

```python
"""Unified constants for mountainash-utils-files."""

from enum import StrEnum


class CONST_STORAGE_PROVIDER_TYPE(StrEnum):
    """Storage provider types — single source of truth."""
    LOCAL = "local"
    S3 = "s3"
    S3EXPRESS = "s3express"
    R2 = "r2"
    MINIO = "minio"
    GCS = "gcs"
    AZURE_BLOB = "azure_blob"
    SFTP = "sftp"
    SSH = "ssh"
    B2 = "b2"


class CONST_STORAGE_AUTH_METHOD(StrEnum):
    """Authentication methods."""
    NONE = "none"
    KEY = "key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    IAM = "iam"
    MANAGED_IDENTITY = "managed_identity"
    KERBEROS = "kerberos"
    SERVICE_ACCOUNT = "service_account"


class CONST_STORAGE_ACCESS_TYPE(StrEnum):
    """Storage access types."""
    READ_ONLY = "read_only"
    WRITE_ONLY = "write_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"


class CONST_STORAGE_ENCRYPTION_TYPE(StrEnum):
    """Storage encryption types."""
    NONE = "none"
    AES256 = "aes256"
    AES256_GCM = "aes256_gcm"
    CLIENT_SIDE = "client_side"
    SERVER_SIDE = "server_side"


class CONST_STORAGE_CONNECTION_STATUS(StrEnum):
    """Storage connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    CLOSED = "closed"


class CONST_STORAGE_TRANSFER_MODE(StrEnum):
    """Storage transfer modes."""
    BINARY = "binary"
    TEXT = "text"
    AUTO = "auto"


class CONST_STORAGE_COMPRESSION_TYPE(StrEnum):
    """Storage compression types."""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    ZSTD = "zstd"
    LZ4 = "lz4"
```

- [ ] **Step 4: Run constants test to verify it passes**

Run: `hatch run test:test tests/test_constants_and_exceptions.py::TestStorageProviderType -v`
Expected: PASS

- [ ] **Step 5: Write test for custom exceptions**

Add to `tests/test_constants_and_exceptions.py`:

```python
from mountainash_utils_files.exceptions import (
    StorageError,
    UnsupportedOperationError,
    StorageConnectionError,
    PathNotFoundError,
    AuthenticationError,
)


class TestExceptions:
    """Verify exception hierarchy."""

    def test_all_inherit_from_storage_error(self):
        assert issubclass(UnsupportedOperationError, StorageError)
        assert issubclass(StorageConnectionError, StorageError)
        assert issubclass(PathNotFoundError, StorageError)
        assert issubclass(AuthenticationError, StorageError)

    def test_storage_error_inherits_from_exception(self):
        assert issubclass(StorageError, Exception)

    def test_exceptions_carry_message(self):
        err = UnsupportedOperationError("S3 does not support mkdir")
        assert str(err) == "S3 does not support mkdir"

    def test_storage_connection_error_does_not_shadow_builtin(self):
        """StorageConnectionError is distinct from builtins.ConnectionError."""
        assert StorageConnectionError is not ConnectionError
```

- [ ] **Step 6: Run exception tests to verify they fail**

Run: `hatch run test:test tests/test_constants_and_exceptions.py::TestExceptions -v`
Expected: FAIL (module does not exist)

- [ ] **Step 7: Create exceptions.py**

```python
# src/mountainash_utils_files/exceptions.py
"""Custom exceptions for storage operations."""


class StorageError(Exception):
    """Base exception for all storage operations."""


class UnsupportedOperationError(StorageError):
    """Backend does not support the requested operation."""


class StorageConnectionError(StorageError):
    """Failed to connect to storage backend."""


class PathNotFoundError(StorageError):
    """File or directory not found in storage."""


class AuthenticationError(StorageError):
    """Authentication or authorization failure."""
```

- [ ] **Step 8: Run all Task 1 tests**

Run: `hatch run test:test tests/test_constants_and_exceptions.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/mountainash_utils_files/constants.py src/mountainash_utils_files/exceptions.py tests/test_constants_and_exceptions.py
git commit -m "refactor: consolidate constants to single enum, add custom exceptions"
```

---

### Task 2: Protocol Layer

**Files:**
- Create: `src/mountainash_utils_files/storage_protocols/__init__.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_connection.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_read.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_write.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_list.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_delete.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_metadata.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_copy.py`
- Create: `src/mountainash_utils_files/storage_protocols/prtcl_directory.py`
- Test: `tests/test_protocols.py`

- [ ] **Step 1: Write tests for protocol definitions**

```python
# tests/test_protocols.py

import pytest
from typing import BinaryIO, runtime_checkable, Protocol

from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)


class TestProtocolsAreRuntimeCheckable:
    """All protocols must be runtime_checkable for isinstance() checks."""

    @pytest.mark.parametrize("protocol", [
        StorageConnectionProtocol,
        StorageReadProtocol,
        StorageWriteProtocol,
        StorageListProtocol,
        StorageDeleteProtocol,
        StorageMetadataProtocol,
        StorageCopyProtocol,
        StorageDirectoryProtocol,
    ])
    def test_protocol_is_runtime_checkable(self, protocol):
        assert issubclass(protocol, Protocol)


class TestProtocolConformanceByImplementation:
    """Verify that a class implementing the right methods conforms to the protocol."""

    def test_read_protocol_conformance(self):
        class FakeReader:
            def read_to_bytes(self, path: str) -> bytes:
                return b""
            def read_to_stream(self, path: str) -> BinaryIO:
                return None  # type: ignore
        assert isinstance(FakeReader(), StorageReadProtocol)

    def test_write_protocol_conformance(self):
        class FakeWriter:
            def write_from_bytes(self, path: str, data: bytes) -> None:
                pass
            def write_from_stream(self, path: str, stream: BinaryIO) -> None:
                pass
        assert isinstance(FakeWriter(), StorageWriteProtocol)

    def test_missing_method_does_not_conform(self):
        class IncompleteReader:
            def read_to_bytes(self, path: str) -> bytes:
                return b""
            # Missing read_to_stream
        assert not isinstance(IncompleteReader(), StorageReadProtocol)

    def test_connection_protocol_conformance(self):
        class FakeConnection:
            def connect(self) -> None:
                pass
            def disconnect(self) -> None:
                pass
            def is_connected(self) -> bool:
                return True
        assert isinstance(FakeConnection(), StorageConnectionProtocol)

    def test_list_protocol_conformance(self):
        class FakeLister:
            def list_files(self, prefix: str) -> list:
                return []
            def list_directories(self, prefix: str) -> list[str]:
                return []
        assert isinstance(FakeLister(), StorageListProtocol)

    def test_metadata_protocol_conformance(self):
        class FakeMetadata:
            def get_metadata(self, path: str):
                return None
            def path_exists(self, path: str) -> bool:
                return False
            def get_size(self, path: str) -> int:
                return 0
        assert isinstance(FakeMetadata(), StorageMetadataProtocol)

    def test_delete_protocol_conformance(self):
        class FakeDeleter:
            def delete_file(self, path: str) -> None:
                pass
        assert isinstance(FakeDeleter(), StorageDeleteProtocol)

    def test_copy_protocol_conformance(self):
        class FakeCopier:
            def copy(self, source: str, destination: str) -> None:
                pass
        assert isinstance(FakeCopier(), StorageCopyProtocol)

    def test_directory_protocol_conformance(self):
        class FakeDir:
            def mkdir(self, path: str, parents: bool = True) -> None:
                pass
            def rmdir(self, path: str) -> None:
                pass
        assert isinstance(FakeDir(), StorageDirectoryProtocol)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/test_protocols.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Create protocol files**

```python
# src/mountainash_utils_files/storage_protocols/prtcl_connection.py
"""Connection lifecycle protocol."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageConnectionProtocol(Protocol):
    """Backends that require connection lifecycle management."""

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_read.py
"""Read operations protocol."""
from __future__ import annotations
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageReadProtocol(Protocol):
    """Read a file to bytes or stream."""

    def read_to_bytes(self, path: str) -> bytes: ...
    def read_to_stream(self, path: str) -> BinaryIO: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_write.py
"""Write operations protocol."""
from __future__ import annotations
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StorageWriteProtocol(Protocol):
    """Write bytes or stream to a file."""

    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_list.py
"""List operations protocol."""
from __future__ import annotations
from typing import Protocol, runtime_checkable

from mountainash_utils_files.dataclasses.file_metadata import FileMetadata


@runtime_checkable
class StorageListProtocol(Protocol):
    """List files and directories."""

    def list_files(self, prefix: str) -> list[FileMetadata]: ...
    def list_directories(self, prefix: str) -> list[str]: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_delete.py
"""Delete operations protocol."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageDeleteProtocol(Protocol):
    """Delete files."""

    def delete_file(self, path: str) -> None: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_metadata.py
"""Metadata operations protocol."""
from __future__ import annotations
from typing import Protocol, runtime_checkable

from mountainash_utils_files.dataclasses.file_metadata import FileMetadata


@runtime_checkable
class StorageMetadataProtocol(Protocol):
    """File metadata operations."""

    def get_metadata(self, path: str) -> FileMetadata: ...
    def path_exists(self, path: str) -> bool: ...
    def get_size(self, path: str) -> int: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_copy.py
"""Copy operations protocol."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageCopyProtocol(Protocol):
    """Native copy within same backend."""

    def copy(self, source: str, destination: str) -> None: ...
```

```python
# src/mountainash_utils_files/storage_protocols/prtcl_directory.py
"""Directory operations protocol."""
from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageDirectoryProtocol(Protocol):
    """Directory operations — not all backends support this."""

    def mkdir(self, path: str, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...
```

```python
# src/mountainash_utils_files/storage_protocols/__init__.py
"""Storage protocols — capability contracts for storage backends."""

from .prtcl_connection import StorageConnectionProtocol
from .prtcl_read import StorageReadProtocol
from .prtcl_write import StorageWriteProtocol
from .prtcl_list import StorageListProtocol
from .prtcl_delete import StorageDeleteProtocol
from .prtcl_metadata import StorageMetadataProtocol
from .prtcl_copy import StorageCopyProtocol
from .prtcl_directory import StorageDirectoryProtocol

__all__ = [
    "StorageConnectionProtocol",
    "StorageReadProtocol",
    "StorageWriteProtocol",
    "StorageListProtocol",
    "StorageDeleteProtocol",
    "StorageMetadataProtocol",
    "StorageCopyProtocol",
    "StorageDirectoryProtocol",
]
```

- [ ] **Step 4: Run protocol tests**

Run: `hatch run test:test tests/test_protocols.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_protocols/
git add tests/test_protocols.py
git commit -m "feat: add storage protocol layer — runtime-checkable capability contracts"
```

---

### Task 3: Registry & Backend Detection

**Files:**
- Create: `src/mountainash_utils_files/storage_registry/__init__.py`
- Create: `src/mountainash_utils_files/storage_registry/registry.py`
- Create: `src/mountainash_utils_files/storage_registry/backend_detection.py`
- Test: `tests/test_registry.py`

- [ ] **Step 1: Write tests for registry and detection**

```python
# tests/test_registry.py

import pytest
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry.registry import (
    register_storage_backend,
    get_storage_backend,
    get_registered_backends,
    clear_registry,
)
from mountainash_utils_files.storage_registry.backend_detection import (
    detect_provider_from_path,
)


class TestBackendDetection:
    """Path scheme → provider type mapping."""

    @pytest.mark.parametrize("path, expected", [
        ("/home/user/file.txt", CONST_STORAGE_PROVIDER_TYPE.LOCAL),
        ("relative/path.csv", CONST_STORAGE_PROVIDER_TYPE.LOCAL),
        ("s3://bucket/key", CONST_STORAGE_PROVIDER_TYPE.S3),
        ("gs://bucket/key", CONST_STORAGE_PROVIDER_TYPE.GCS),
        ("az://container/blob", CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB),
        ("sftp://host/path", CONST_STORAGE_PROVIDER_TYPE.SFTP),
        ("ssh://host/path", CONST_STORAGE_PROVIDER_TYPE.SSH),
        ("r2://bucket/key", CONST_STORAGE_PROVIDER_TYPE.R2),
        ("b2://bucket/key", CONST_STORAGE_PROVIDER_TYPE.B2),
    ])
    def test_detect_provider_from_path(self, path, expected):
        assert detect_provider_from_path(path) == expected

    def test_unknown_scheme_raises(self):
        with pytest.raises(ValueError, match="Unknown scheme"):
            detect_provider_from_path("ftp://host/path")


class TestRegistry:
    """Backend registration and lookup."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def test_register_and_retrieve(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class FakeLocal:
            def __init__(self, auth_params):
                self.auth = auth_params
        backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL, auth_params="test")
        assert isinstance(backend, FakeLocal)
        assert backend.auth == "test"

    def test_get_unregistered_raises(self):
        with pytest.raises(ValueError, match="No backend registered"):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=None)

    def test_get_registered_backends_returns_copy(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class FakeLocal:
            pass
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.LOCAL in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.LOCAL] is FakeLocal

    def test_duplicate_registration_overwrites(self):
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class FakeLocal1:
            pass
        @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
        class FakeLocal2:
            pass
        backends = get_registered_backends()
        assert backends[CONST_STORAGE_PROVIDER_TYPE.LOCAL] is FakeLocal2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/test_registry.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Create registry.py**

```python
# src/mountainash_utils_files/storage_registry/registry.py
"""Backend registration and lookup."""
from __future__ import annotations
from typing import Any

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}


def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE):
    """Decorator that registers a backend class for a provider type."""
    def decorator(cls: type) -> type:
        _backend_registry[provider_type] = cls
        return cls
    return decorator


def get_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE, auth_params: Any) -> Any:
    """Instantiate and return a backend for the given provider type."""
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type!r}")
    return cls(auth_params)


def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    """Return a copy of all registered backends (for testing/introspection)."""
    return dict(_backend_registry)


def clear_registry() -> None:
    """Clear all registered backends. For testing only."""
    _backend_registry.clear()
```

- [ ] **Step 4: Create backend_detection.py**

```python
# src/mountainash_utils_files/storage_registry/backend_detection.py
"""Detect storage provider type from path scheme."""
from __future__ import annotations

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

_SCHEME_TO_PROVIDER: dict[str, CONST_STORAGE_PROVIDER_TYPE] = {
    "s3": CONST_STORAGE_PROVIDER_TYPE.S3,
    "gs": CONST_STORAGE_PROVIDER_TYPE.GCS,
    "az": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "sftp": CONST_STORAGE_PROVIDER_TYPE.SFTP,
    "ssh": CONST_STORAGE_PROVIDER_TYPE.SSH,
    "r2": CONST_STORAGE_PROVIDER_TYPE.R2,
    "b2": CONST_STORAGE_PROVIDER_TYPE.B2,
}


def detect_provider_from_path(path: str) -> CONST_STORAGE_PROVIDER_TYPE:
    """Determine provider type from path scheme.

    Local paths (no scheme, or absolute/relative paths) return LOCAL.
    """
    if "://" in path:
        scheme = path.split("://", 1)[0].lower()
        provider = _SCHEME_TO_PROVIDER.get(scheme)
        if provider is None:
            raise ValueError(f"Unknown scheme: {scheme!r} in path {path!r}")
        return provider
    return CONST_STORAGE_PROVIDER_TYPE.LOCAL
```

- [ ] **Step 5: Create __init__.py**

```python
# src/mountainash_utils_files/storage_registry/__init__.py
"""Storage backend registry and detection."""

from .registry import (
    register_storage_backend,
    get_storage_backend,
    get_registered_backends,
    clear_registry,
)
from .backend_detection import detect_provider_from_path

__all__ = [
    "register_storage_backend",
    "get_storage_backend",
    "get_registered_backends",
    "clear_registry",
    "detect_provider_from_path",
]
```

- [ ] **Step 6: Run registry tests**

Run: `hatch run test:test tests/test_registry.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_utils_files/storage_registry/
git add tests/test_registry.py
git commit -m "feat: add storage registry — decorator-based backend discovery and path detection"
```

---

## Phase 2: Backend Implementations (Tasks 4-6)

### Task 4: Local Storage Backend

**Files:**
- Create: `src/mountainash_utils_files/storage_backends/__init__.py`
- Create: `src/mountainash_utils_files/storage_backends/local/__init__.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_connection.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_read.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_write.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_list.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_delete.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_metadata.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_copy.py`
- Create: `src/mountainash_utils_files/storage_backends/local/local_directory.py`
- Test: `tests/backends/test_local.py`

- [ ] **Step 1: Write tests for local backend**

```python
# tests/backends/test_local.py

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)
from mountainash_utils_files.storage_registry import get_registered_backends
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def local_backend():
    # Import triggers registration
    from mountainash_utils_files.storage_backends.local import LocalStorageBackend
    return LocalStorageBackend(auth_params=None)


class TestLocalBackendProtocolConformance:
    """LocalStorageBackend must implement all expected protocols."""

    def test_implements_connection(self, local_backend):
        assert isinstance(local_backend, StorageConnectionProtocol)

    def test_implements_read(self, local_backend):
        assert isinstance(local_backend, StorageReadProtocol)

    def test_implements_write(self, local_backend):
        assert isinstance(local_backend, StorageWriteProtocol)

    def test_implements_list(self, local_backend):
        assert isinstance(local_backend, StorageListProtocol)

    def test_implements_delete(self, local_backend):
        assert isinstance(local_backend, StorageDeleteProtocol)

    def test_implements_metadata(self, local_backend):
        assert isinstance(local_backend, StorageMetadataProtocol)

    def test_implements_copy(self, local_backend):
        assert isinstance(local_backend, StorageCopyProtocol)

    def test_implements_directory(self, local_backend):
        assert isinstance(local_backend, StorageDirectoryProtocol)

    def test_registered_in_registry(self):
        from mountainash_utils_files.storage_backends.local import LocalStorageBackend
        backends = get_registered_backends()
        assert backends[CONST_STORAGE_PROVIDER_TYPE.LOCAL] is LocalStorageBackend


class TestLocalReadWrite:
    """Test local read/write operations."""

    def test_write_and_read_bytes(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "test.txt")
        data = b"hello mountainash"
        local_backend.write_from_bytes(path, data)
        result = local_backend.read_to_bytes(path)
        assert result == data

    def test_write_and_read_stream(self, local_backend, temp_dir):
        import io
        path = os.path.join(temp_dir, "test_stream.txt")
        data = b"stream content"
        local_backend.write_from_stream(path, io.BytesIO(data))
        stream = local_backend.read_to_stream(path)
        assert stream.read() == data
        stream.close()

    def test_write_creates_parent_dirs(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "sub", "dir", "file.txt")
        local_backend.write_from_bytes(path, b"nested")
        assert os.path.exists(path)


class TestLocalList:
    """Test local list operations."""

    def test_list_files(self, local_backend, temp_dir):
        # Create test files
        for name in ["a.txt", "b.csv", "c.json"]:
            Path(os.path.join(temp_dir, name)).write_bytes(b"x")
        result = local_backend.list_files(temp_dir)
        filenames = [m.filename for m in result]
        assert sorted(filenames) == ["a.txt", "b.csv", "c.json"]

    def test_list_directories(self, local_backend, temp_dir):
        os.makedirs(os.path.join(temp_dir, "sub1"))
        os.makedirs(os.path.join(temp_dir, "sub2"))
        Path(os.path.join(temp_dir, "file.txt")).write_bytes(b"x")
        result = local_backend.list_directories(temp_dir)
        assert sorted(result) == sorted([
            os.path.join(temp_dir, "sub1"),
            os.path.join(temp_dir, "sub2"),
        ])


class TestLocalMetadata:
    """Test local metadata operations."""

    def test_path_exists(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "exists.txt")
        assert not local_backend.path_exists(path)
        Path(path).write_bytes(b"x")
        assert local_backend.path_exists(path)

    def test_get_size(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "sized.txt")
        data = b"twelve bytes"
        Path(path).write_bytes(data)
        assert local_backend.get_size(path) == len(data)

    def test_get_metadata(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "meta.txt")
        Path(path).write_bytes(b"metadata test")
        meta = local_backend.get_metadata(path)
        assert meta.filename == "meta.txt"
        assert meta.size == len(b"metadata test")


class TestLocalDelete:
    """Test local delete operations."""

    def test_delete_file(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "to_delete.txt")
        Path(path).write_bytes(b"delete me")
        local_backend.delete_file(path)
        assert not os.path.exists(path)


class TestLocalCopy:
    """Test local copy operations."""

    def test_copy(self, local_backend, temp_dir):
        src = os.path.join(temp_dir, "src.txt")
        dst = os.path.join(temp_dir, "dst.txt")
        Path(src).write_bytes(b"copy me")
        local_backend.copy(src, dst)
        assert Path(dst).read_bytes() == b"copy me"


class TestLocalDirectory:
    """Test local directory operations."""

    def test_mkdir(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "new", "nested", "dir")
        local_backend.mkdir(path, parents=True)
        assert os.path.isdir(path)

    def test_rmdir(self, local_backend, temp_dir):
        path = os.path.join(temp_dir, "to_remove")
        os.makedirs(path)
        local_backend.rmdir(path)
        assert not os.path.exists(path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/backends/test_local.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Create local mixin files**

```python
# src/mountainash_utils_files/storage_backends/local/local_connection.py
"""Local filesystem connection mixin — no-op for local storage."""
from __future__ import annotations


class LocalConnectionMixin:
    """Local storage needs no connection management."""

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True
```

```python
# src/mountainash_utils_files/storage_backends/local/local_read.py
"""Local filesystem read operations."""
from __future__ import annotations
import io
from typing import BinaryIO


class LocalReadMixin:
    """Read files from local filesystem."""

    def read_to_bytes(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    def read_to_stream(self, path: str) -> BinaryIO:
        return open(path, "rb")
```

```python
# src/mountainash_utils_files/storage_backends/local/local_write.py
"""Local filesystem write operations."""
from __future__ import annotations
import os
from typing import BinaryIO


class LocalWriteMixin:
    """Write files to local filesystem."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            while chunk := stream.read(8192):
                f.write(chunk)
```

```python
# src/mountainash_utils_files/storage_backends/local/local_list.py
"""Local filesystem list operations."""
from __future__ import annotations
import os
from pathlib import Path

from mountainash_utils_files.dataclasses.file_metadata import FileMetadata


class LocalListMixin:
    """List files and directories on local filesystem."""

    def list_files(self, prefix: str) -> list[FileMetadata]:
        p = Path(prefix)
        results = []
        for entry in p.iterdir():
            if entry.is_file():
                stat = entry.stat()
                results.append(FileMetadata(
                    filename=entry.name,
                    directory=str(entry.parent),
                    full_path=str(entry),
                    size=stat.st_size,
                    source="local",
                ))
        return results

    def list_directories(self, prefix: str) -> list[str]:
        p = Path(prefix)
        return [str(entry) for entry in p.iterdir() if entry.is_dir()]
```

```python
# src/mountainash_utils_files/storage_backends/local/local_delete.py
"""Local filesystem delete operations."""
from __future__ import annotations
import os

from mountainash_utils_files.exceptions import PathNotFoundError


class LocalDeleteMixin:
    """Delete files from local filesystem."""

    def delete_file(self, path: str) -> None:
        if not os.path.exists(path):
            raise PathNotFoundError(f"File not found: {path}")
        os.remove(path)
```

```python
# src/mountainash_utils_files/storage_backends/local/local_metadata.py
"""Local filesystem metadata operations."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from pathlib import Path

from mountainash_utils_files.dataclasses.file_metadata import FileMetadata


class LocalMetadataMixin:
    """File metadata for local filesystem."""

    def get_metadata(self, path: str) -> FileMetadata:
        p = Path(path)
        stat = p.stat()
        return FileMetadata(
            filename=p.name,
            directory=str(p.parent),
            full_path=str(p),
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            source="local",
        )

    def path_exists(self, path: str) -> bool:
        return os.path.exists(path)

    def get_size(self, path: str) -> int:
        return os.path.getsize(path)
```

```python
# src/mountainash_utils_files/storage_backends/local/local_copy.py
"""Local filesystem copy operations."""
from __future__ import annotations
import os
import shutil


class LocalCopyMixin:
    """Copy files on local filesystem."""

    def copy(self, source: str, destination: str) -> None:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
```

```python
# src/mountainash_utils_files/storage_backends/local/local_directory.py
"""Local filesystem directory operations."""
from __future__ import annotations
import os
import shutil


class LocalDirectoryMixin:
    """Directory operations for local filesystem."""

    def mkdir(self, path: str, parents: bool = True) -> None:
        os.makedirs(path, exist_ok=True) if parents else os.mkdir(path)

    def rmdir(self, path: str) -> None:
        shutil.rmtree(path)
```

- [ ] **Step 4: Create composition class and registration**

```python
# src/mountainash_utils_files/storage_backends/local/__init__.py
"""Local storage backend — composed from focused mixins."""

from mountainash_utils_files.storage_registry import register_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

from .local_connection import LocalConnectionMixin
from .local_read import LocalReadMixin
from .local_write import LocalWriteMixin
from .local_list import LocalListMixin
from .local_delete import LocalDeleteMixin
from .local_metadata import LocalMetadataMixin
from .local_copy import LocalCopyMixin
from .local_directory import LocalDirectoryMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
class LocalStorageBackend(
    LocalConnectionMixin,
    LocalReadMixin,
    LocalWriteMixin,
    LocalListMixin,
    LocalDeleteMixin,
    LocalMetadataMixin,
    LocalCopyMixin,
    LocalDirectoryMixin,
):
    """Local filesystem storage — all protocols supported."""

    def __init__(self, auth_params):
        self.auth_params = auth_params
```

```python
# src/mountainash_utils_files/storage_backends/__init__.py
"""Storage backends — import to trigger registrations."""

from . import local  # noqa: F401
# Future: from . import s3, r2, gcs, azure, sftp, ssh, s3express, minio
```

- [ ] **Step 5: Create tests/__init__.py files for test packages**

```bash
touch tests/__init__.py tests/backends/__init__.py
```

(Note: these may already exist. Create only if missing.)

- [ ] **Step 6: Run local backend tests**

Run: `hatch run test:test tests/backends/test_local.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/
git add tests/backends/
git commit -m "feat: add local storage backend — mixin composition with protocol conformance"
```

---

### Task 5: S3 Storage Backend

**Files:**
- Create: `src/mountainash_utils_files/storage_backends/s3/__init__.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_connection.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_read.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_write.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_list.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_delete.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_metadata.py`
- Create: `src/mountainash_utils_files/storage_backends/s3/s3_copy.py`
- Modify: `src/mountainash_utils_files/storage_backends/__init__.py`
- Test: `tests/backends/test_s3.py`

- [ ] **Step 1: Write tests for S3 backend (mocked)**

```python
# tests/backends/test_s3.py

import pytest
import io
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
)
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry import get_registered_backends


@pytest.fixture
def mock_auth_params():
    auth = Mock()
    settings = Mock()
    settings.ENDPOINT = "https://s3.amazonaws.com"
    settings.ACCESS_KEY_ID = "test-key"
    settings.SECRET_KEY = "test-secret"
    settings.REGION = "us-east-1"
    settings.USE_SSL = True
    settings.PROVIDER_TYPE = "s3"
    auth.settings = settings
    return auth


@pytest.fixture
def s3_backend(mock_auth_params):
    with patch("boto3.client") as mock_boto:
        mock_client = MagicMock()
        mock_boto.return_value = mock_client
        from mountainash_utils_files.storage_backends.s3 import S3StorageBackend
        backend = S3StorageBackend(mock_auth_params)
        backend._client = mock_client
        yield backend


class TestS3ProtocolConformance:
    """S3 backend must implement expected protocols (no directory protocol)."""

    def test_implements_connection(self, s3_backend):
        assert isinstance(s3_backend, StorageConnectionProtocol)

    def test_implements_read(self, s3_backend):
        assert isinstance(s3_backend, StorageReadProtocol)

    def test_implements_write(self, s3_backend):
        assert isinstance(s3_backend, StorageWriteProtocol)

    def test_implements_list(self, s3_backend):
        assert isinstance(s3_backend, StorageListProtocol)

    def test_implements_delete(self, s3_backend):
        assert isinstance(s3_backend, StorageDeleteProtocol)

    def test_implements_metadata(self, s3_backend):
        assert isinstance(s3_backend, StorageMetadataProtocol)

    def test_implements_copy(self, s3_backend):
        assert isinstance(s3_backend, StorageCopyProtocol)

    def test_registered(self):
        with patch("boto3.client"):
            from mountainash_utils_files.storage_backends.s3 import S3StorageBackend
            backends = get_registered_backends()
            assert backends[CONST_STORAGE_PROVIDER_TYPE.S3] is S3StorageBackend


class TestS3ReadWrite:
    """Test S3 read/write with mocked boto3."""

    def test_read_to_bytes(self, s3_backend):
        body_mock = MagicMock()
        body_mock.read.return_value = b"s3 content"
        s3_backend._client.get_object.return_value = {"Body": body_mock}
        result = s3_backend.read_to_bytes("s3://mybucket/key.txt")
        assert result == b"s3 content"
        s3_backend._client.get_object.assert_called_once_with(
            Bucket="mybucket", Key="key.txt"
        )

    def test_write_from_bytes(self, s3_backend):
        s3_backend.write_from_bytes("s3://mybucket/key.txt", b"data")
        s3_backend._client.put_object.assert_called_once_with(
            Bucket="mybucket", Key="key.txt", Body=b"data"
        )

    def test_write_from_stream(self, s3_backend):
        stream = io.BytesIO(b"stream data")
        s3_backend.write_from_stream("s3://mybucket/key.txt", stream)
        s3_backend._client.put_object.assert_called_once()
        call_args = s3_backend._client.put_object.call_args
        assert call_args.kwargs["Bucket"] == "mybucket"
        assert call_args.kwargs["Key"] == "key.txt"


class TestS3Delete:
    """Test S3 delete operations."""

    def test_delete_file(self, s3_backend):
        s3_backend.delete_file("s3://mybucket/key.txt")
        s3_backend._client.delete_object.assert_called_once_with(
            Bucket="mybucket", Key="key.txt"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/backends/test_s3.py -v`
Expected: FAIL (module does not exist)

- [ ] **Step 3: Create S3 path parsing utility**

All S3 mixins need to parse `s3://bucket/key` paths. Add a shared helper:

```python
# src/mountainash_utils_files/storage_backends/s3/s3_path.py
"""S3 path parsing utility."""
from __future__ import annotations


def parse_s3_path(path: str) -> tuple[str, str]:
    """Parse 's3://bucket/key' into (bucket, key).

    Also handles paths without scheme for cases where bucket/key
    are passed directly.
    """
    if path.startswith("s3://"):
        path = path[5:]
    parts = path.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    return bucket, key
```

- [ ] **Step 4: Create S3 mixin files**

```python
# src/mountainash_utils_files/storage_backends/s3/s3_connection.py
"""S3 connection management via boto3."""
from __future__ import annotations
from typing import Any

import boto3

from mountainash_utils_files.exceptions import StorageConnectionError


class S3ConnectionMixin:
    """Manage boto3 S3 client connection."""

    _client: Any = None
    auth_params: Any = None

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            settings = self.auth_params.settings
            self._client = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "ENDPOINT", None),
                aws_access_key_id=settings.ACCESS_KEY_ID,
                aws_secret_access_key=settings.SECRET_KEY,
                region_name=getattr(settings, "REGION", None),
                use_ssl=getattr(settings, "USE_SSL", True),
            )
        except Exception as e:
            raise StorageConnectionError(f"Failed to connect to S3: {e}") from e

    def disconnect(self) -> None:
        self._client = None

    def is_connected(self) -> bool:
        return self._client is not None
```

```python
# src/mountainash_utils_files/storage_backends/s3/s3_read.py
"""S3 read operations."""
from __future__ import annotations
import io
from typing import BinaryIO

from .s3_path import parse_s3_path


class S3ReadMixin:
    """Read files from S3."""

    def read_to_bytes(self, path: str) -> bytes:
        bucket, key = parse_s3_path(path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def read_to_stream(self, path: str) -> BinaryIO:
        bucket, key = parse_s3_path(path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        return io.BytesIO(response["Body"].read())
```

```python
# src/mountainash_utils_files/storage_backends/s3/s3_write.py
"""S3 write operations."""
from __future__ import annotations
from typing import BinaryIO

from .s3_path import parse_s3_path


class S3WriteMixin:
    """Write files to S3."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        bucket, key = parse_s3_path(path)
        self._client.put_object(Bucket=bucket, Key=key, Body=data)

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        bucket, key = parse_s3_path(path)
        data = stream.read()
        self._client.put_object(Bucket=bucket, Key=key, Body=data)
```

```python
# src/mountainash_utils_files/storage_backends/s3/s3_list.py
"""S3 list operations."""
from __future__ import annotations

from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from .s3_path import parse_s3_path


class S3ListMixin:
    """List files and directories in S3."""

    def list_files(self, prefix: str) -> list[FileMetadata]:
        bucket, key_prefix = parse_s3_path(prefix)
        response = self._client.list_objects_v2(Bucket=bucket, Prefix=key_prefix)
        results = []
        for obj in response.get("Contents", []):
            key = obj["Key"]
            filename = key.rsplit("/", 1)[-1] if "/" in key else key
            directory = key.rsplit("/", 1)[0] if "/" in key else ""
            results.append(FileMetadata(
                filename=filename,
                directory=f"s3://{bucket}/{directory}",
                full_path=f"s3://{bucket}/{key}",
                size=obj.get("Size", 0),
                etag=obj.get("ETag", ""),
                storage_class=obj.get("StorageClass", ""),
                source="s3",
            ))
        return results

    def list_directories(self, prefix: str) -> list[str]:
        bucket, key_prefix = parse_s3_path(prefix)
        if key_prefix and not key_prefix.endswith("/"):
            key_prefix += "/"
        response = self._client.list_objects_v2(
            Bucket=bucket, Prefix=key_prefix, Delimiter="/"
        )
        return [
            f"s3://{bucket}/{cp['Prefix']}"
            for cp in response.get("CommonPrefixes", [])
        ]
```

```python
# src/mountainash_utils_files/storage_backends/s3/s3_delete.py
"""S3 delete operations."""
from __future__ import annotations

from .s3_path import parse_s3_path


class S3DeleteMixin:
    """Delete files from S3."""

    def delete_file(self, path: str) -> None:
        bucket, key = parse_s3_path(path)
        self._client.delete_object(Bucket=bucket, Key=key)
```

```python
# src/mountainash_utils_files/storage_backends/s3/s3_metadata.py
"""S3 metadata operations."""
from __future__ import annotations
from datetime import datetime, timezone

from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from .s3_path import parse_s3_path


class S3MetadataMixin:
    """File metadata operations for S3."""

    def get_metadata(self, path: str) -> FileMetadata:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)
        filename = key.rsplit("/", 1)[-1] if "/" in key else key
        directory = key.rsplit("/", 1)[0] if "/" in key else ""
        return FileMetadata(
            filename=filename,
            directory=f"s3://{bucket}/{directory}",
            full_path=f"s3://{bucket}/{key}",
            size=response.get("ContentLength", 0),
            last_modified=response.get("LastModified"),
            etag=response.get("ETag", ""),
            source="s3",
        )

    def path_exists(self, path: str) -> bool:
        bucket, key = parse_s3_path(path)
        try:
            self._client.head_object(Bucket=bucket, Key=key)
            return True
        except self._client.exceptions.ClientError:
            return False
        except Exception:
            # Fallback: check via list
            response = self._client.list_objects_v2(
                Bucket=bucket, Prefix=key, MaxKeys=1
            )
            return response.get("KeyCount", 0) > 0

    def get_size(self, path: str) -> int:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)
        return response.get("ContentLength", 0)
```

```python
# src/mountainash_utils_files/storage_backends/s3/s3_copy.py
"""S3 native copy operations."""
from __future__ import annotations

from .s3_path import parse_s3_path


class S3CopyMixin:
    """Copy files within S3 using native server-side copy."""

    def copy(self, source: str, destination: str) -> None:
        src_bucket, src_key = parse_s3_path(source)
        dst_bucket, dst_key = parse_s3_path(destination)
        self._client.copy_object(
            Bucket=dst_bucket,
            Key=dst_key,
            CopySource={"Bucket": src_bucket, "Key": src_key},
        )
```

- [ ] **Step 5: Create S3 composition class**

```python
# src/mountainash_utils_files/storage_backends/s3/__init__.py
"""S3 storage backend — composed from focused mixins."""

from mountainash_utils_files.storage_registry import register_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

from .s3_connection import S3ConnectionMixin
from .s3_read import S3ReadMixin
from .s3_write import S3WriteMixin
from .s3_list import S3ListMixin
from .s3_delete import S3DeleteMixin
from .s3_metadata import S3MetadataMixin
from .s3_copy import S3CopyMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
class S3StorageBackend(
    S3ConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """S3 storage — all protocols except directory."""

    def __init__(self, auth_params):
        self.auth_params = auth_params
        self._client = None
```

- [ ] **Step 6: Register S3 backend**

Add to `src/mountainash_utils_files/storage_backends/__init__.py`:

```python
"""Storage backends — import to trigger registrations."""

from . import local  # noqa: F401
from . import s3  # noqa: F401
```

- [ ] **Step 7: Run S3 tests**

Run: `hatch run test:test tests/backends/test_s3.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/s3/
git add src/mountainash_utils_files/storage_backends/__init__.py
git add tests/backends/test_s3.py
git commit -m "feat: add S3 storage backend — mixin composition with shared path parsing"
```

---

### Task 6: S3-Family Backends (R2, S3Express, MinIO)

**Files:**
- Create: `src/mountainash_utils_files/storage_backends/r2/__init__.py`
- Create: `src/mountainash_utils_files/storage_backends/r2/r2_connection.py`
- Create: `src/mountainash_utils_files/storage_backends/s3express/__init__.py`
- Create: `src/mountainash_utils_files/storage_backends/s3express/s3express_connection.py`
- Create: `src/mountainash_utils_files/storage_backends/minio/__init__.py`
- Create: `src/mountainash_utils_files/storage_backends/minio/minio_connection.py`
- Modify: `src/mountainash_utils_files/storage_backends/__init__.py`
- Test: `tests/backends/test_s3_family.py`

- [ ] **Step 1: Write tests for S3 family protocol conformance**

```python
# tests/backends/test_s3_family.py

import pytest
from unittest.mock import Mock, patch, MagicMock

from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry import get_registered_backends


@pytest.fixture
def mock_auth():
    auth = Mock()
    settings = Mock()
    settings.ENDPOINT = "https://example.r2.cloudflarestorage.com"
    settings.ACCESS_KEY_ID = "key"
    settings.SECRET_KEY = "secret"
    settings.REGION = "auto"
    settings.USE_SSL = True
    settings.ACCOUNT_ID = "test-account"
    settings.PROVIDER_TYPE = "r2"
    auth.settings = settings
    return auth


class TestR2Backend:
    """R2 backend reuses S3 mixins with R2 connection."""

    def test_registered(self, mock_auth):
        with patch("boto3.client"):
            from mountainash_utils_files.storage_backends.r2 import R2StorageBackend
            backends = get_registered_backends()
            assert backends[CONST_STORAGE_PROVIDER_TYPE.R2] is R2StorageBackend

    def test_conforms_to_s3_protocols(self, mock_auth):
        with patch("boto3.client"):
            from mountainash_utils_files.storage_backends.r2 import R2StorageBackend
            backend = R2StorageBackend(mock_auth)
            assert isinstance(backend, StorageConnectionProtocol)
            assert isinstance(backend, StorageReadProtocol)
            assert isinstance(backend, StorageWriteProtocol)
            assert isinstance(backend, StorageListProtocol)
            assert isinstance(backend, StorageDeleteProtocol)
            assert isinstance(backend, StorageMetadataProtocol)
            assert isinstance(backend, StorageCopyProtocol)
            assert not isinstance(backend, StorageDirectoryProtocol)


class TestS3ExpressBackend:
    """S3Express backend reuses S3 mixins."""

    def test_registered(self, mock_auth):
        with patch("boto3.client"):
            from mountainash_utils_files.storage_backends.s3express import S3ExpressStorageBackend
            backends = get_registered_backends()
            assert backends[CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS] is S3ExpressStorageBackend


class TestMinIOBackend:
    """MinIO backend reuses S3 mixins with MinIO connection."""

    def test_registered(self, mock_auth):
        with patch("boto3.client"):
            from mountainash_utils_files.storage_backends.minio import MinIOStorageBackend
            backends = get_registered_backends()
            assert backends[CONST_STORAGE_PROVIDER_TYPE.MINIO] is MinIOStorageBackend
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/backends/test_s3_family.py -v`
Expected: FAIL

- [ ] **Step 3: Create R2 backend (connection override only)**

```python
# src/mountainash_utils_files/storage_backends/r2/r2_connection.py
"""R2 connection — Cloudflare R2 endpoint configuration."""
from __future__ import annotations
from typing import Any

import boto3

from mountainash_utils_files.exceptions import StorageConnectionError


class R2ConnectionMixin:
    """Manage boto3 client configured for Cloudflare R2."""

    _client: Any = None
    auth_params: Any = None

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            settings = self.auth_params.settings
            account_id = getattr(settings, "ACCOUNT_ID", "")
            endpoint = getattr(settings, "ENDPOINT", None)
            if not endpoint and account_id:
                endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=settings.ACCESS_KEY_ID,
                aws_secret_access_key=settings.SECRET_KEY,
                region_name="auto",
            )
        except Exception as e:
            raise StorageConnectionError(f"Failed to connect to R2: {e}") from e

    def disconnect(self) -> None:
        self._client = None

    def is_connected(self) -> bool:
        return self._client is not None
```

```python
# src/mountainash_utils_files/storage_backends/r2/__init__.py
"""R2 storage backend — reuses S3 mixins with R2 connection."""

from mountainash_utils_files.storage_registry import register_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

from .r2_connection import R2ConnectionMixin
from mountainash_utils_files.storage_backends.s3.s3_read import S3ReadMixin
from mountainash_utils_files.storage_backends.s3.s3_write import S3WriteMixin
from mountainash_utils_files.storage_backends.s3.s3_list import S3ListMixin
from mountainash_utils_files.storage_backends.s3.s3_delete import S3DeleteMixin
from mountainash_utils_files.storage_backends.s3.s3_metadata import S3MetadataMixin
from mountainash_utils_files.storage_backends.s3.s3_copy import S3CopyMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.R2)
class R2StorageBackend(
    R2ConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """Cloudflare R2 storage — S3-compatible with R2 endpoint."""

    def __init__(self, auth_params):
        self.auth_params = auth_params
        self._client = None
```

- [ ] **Step 4: Create S3Express backend**

```python
# src/mountainash_utils_files/storage_backends/s3express/s3express_connection.py
"""S3Express connection — S3 Express One Zone session management."""
from __future__ import annotations
from typing import Any

import boto3

from mountainash_utils_files.exceptions import StorageConnectionError


class S3ExpressConnectionMixin:
    """Manage boto3 client for S3 Express One Zone."""

    _client: Any = None
    auth_params: Any = None

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            settings = self.auth_params.settings
            self._client = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "ENDPOINT", None),
                aws_access_key_id=settings.ACCESS_KEY_ID,
                aws_secret_access_key=settings.SECRET_KEY,
                region_name=getattr(settings, "REGION", None),
                use_ssl=getattr(settings, "USE_SSL", True),
            )
        except Exception as e:
            raise StorageConnectionError(f"Failed to connect to S3Express: {e}") from e

    def disconnect(self) -> None:
        self._client = None

    def is_connected(self) -> bool:
        return self._client is not None
```

```python
# src/mountainash_utils_files/storage_backends/s3express/__init__.py
"""S3 Express One Zone storage backend."""

from mountainash_utils_files.storage_registry import register_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

from .s3express_connection import S3ExpressConnectionMixin
from mountainash_utils_files.storage_backends.s3.s3_read import S3ReadMixin
from mountainash_utils_files.storage_backends.s3.s3_write import S3WriteMixin
from mountainash_utils_files.storage_backends.s3.s3_list import S3ListMixin
from mountainash_utils_files.storage_backends.s3.s3_delete import S3DeleteMixin
from mountainash_utils_files.storage_backends.s3.s3_metadata import S3MetadataMixin
from mountainash_utils_files.storage_backends.s3.s3_copy import S3CopyMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS)
class S3ExpressStorageBackend(
    S3ExpressConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """S3 Express One Zone — S3-compatible with express session handling."""

    def __init__(self, auth_params):
        self.auth_params = auth_params
        self._client = None
```

- [ ] **Step 5: Create MinIO backend**

```python
# src/mountainash_utils_files/storage_backends/minio/minio_connection.py
"""MinIO connection — S3-compatible with MinIO endpoint."""
from __future__ import annotations
from typing import Any

import boto3

from mountainash_utils_files.exceptions import StorageConnectionError


class MinIOConnectionMixin:
    """Manage boto3 client configured for MinIO."""

    _client: Any = None
    auth_params: Any = None

    def connect(self) -> None:
        if self._client is not None:
            return
        try:
            settings = self.auth_params.settings
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.ENDPOINT,
                aws_access_key_id=settings.ACCESS_KEY_ID,
                aws_secret_access_key=settings.SECRET_KEY,
                region_name=getattr(settings, "REGION", "us-east-1"),
                use_ssl=getattr(settings, "USE_SSL", False),
            )
        except Exception as e:
            raise StorageConnectionError(f"Failed to connect to MinIO: {e}") from e

    def disconnect(self) -> None:
        self._client = None

    def is_connected(self) -> bool:
        return self._client is not None
```

```python
# src/mountainash_utils_files/storage_backends/minio/__init__.py
"""MinIO storage backend — S3-compatible with MinIO endpoint."""

from mountainash_utils_files.storage_registry import register_storage_backend
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

from .minio_connection import MinIOConnectionMixin
from mountainash_utils_files.storage_backends.s3.s3_read import S3ReadMixin
from mountainash_utils_files.storage_backends.s3.s3_write import S3WriteMixin
from mountainash_utils_files.storage_backends.s3.s3_list import S3ListMixin
from mountainash_utils_files.storage_backends.s3.s3_delete import S3DeleteMixin
from mountainash_utils_files.storage_backends.s3.s3_metadata import S3MetadataMixin
from mountainash_utils_files.storage_backends.s3.s3_copy import S3CopyMixin


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.MINIO)
class MinIOStorageBackend(
    MinIOConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    """MinIO storage — S3-compatible."""

    def __init__(self, auth_params):
        self.auth_params = auth_params
        self._client = None
```

- [ ] **Step 6: Register all S3-family backends**

Update `src/mountainash_utils_files/storage_backends/__init__.py`:

```python
"""Storage backends — import to trigger registrations."""

from . import local  # noqa: F401
from . import s3  # noqa: F401
from . import r2  # noqa: F401
from . import s3express  # noqa: F401
from . import minio  # noqa: F401
```

- [ ] **Step 7: Run S3 family tests**

Run: `hatch run test:test tests/backends/test_s3_family.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/r2/
git add src/mountainash_utils_files/storage_backends/s3express/
git add src/mountainash_utils_files/storage_backends/minio/
git add src/mountainash_utils_files/storage_backends/__init__.py
git add tests/backends/test_s3_family.py
git commit -m "feat: add S3-family backends (R2, S3Express, MinIO) — shared S3 mixins"
```

---

## Phase 3: Facade & Integration (Tasks 7-8)

### Task 7: Storage Facade

**Files:**
- Create: `src/mountainash_utils_files/storage_facade/__init__.py`
- Create: `src/mountainash_utils_files/storage_facade/facade.py`
- Create: `src/mountainash_utils_files/storage_facade/cross_backend.py`
- Test: `tests/facade/test_facade.py`

- [ ] **Step 1: Write tests for facade**

```python
# tests/facade/test_facade.py

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from mountainash_utils_files.storage_facade import StorageFacade, copy_between
from mountainash_utils_files.storage_protocols import (
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageDirectoryProtocol,
)
from mountainash_utils_files.exceptions import UnsupportedOperationError


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def local_facade():
    return StorageFacade.for_local()


class TestStorageFacade:
    """Test facade dispatching and protocol checks."""

    def test_supports_returns_true_for_implemented(self, local_facade):
        assert local_facade.supports(StorageReadProtocol)
        assert local_facade.supports(StorageWriteProtocol)
        assert local_facade.supports(StorageDirectoryProtocol)

    def test_read_write_roundtrip(self, local_facade, temp_dir):
        path = os.path.join(temp_dir, "facade_test.txt")
        local_facade.write(path, b"facade content")
        result = local_facade.read(path)
        assert result == b"facade content"

    def test_exists(self, local_facade, temp_dir):
        path = os.path.join(temp_dir, "exists_test.txt")
        assert not local_facade.exists(path)
        local_facade.write(path, b"x")
        assert local_facade.exists(path)

    def test_delete(self, local_facade, temp_dir):
        path = os.path.join(temp_dir, "delete_test.txt")
        local_facade.write(path, b"delete me")
        local_facade.delete(path)
        assert not local_facade.exists(path)

    def test_metadata(self, local_facade, temp_dir):
        path = os.path.join(temp_dir, "meta_test.txt")
        local_facade.write(path, b"metadata")
        meta = local_facade.metadata(path)
        assert meta.filename == "meta_test.txt"
        assert meta.size == len(b"metadata")

    def test_list_files(self, local_facade, temp_dir):
        for name in ["a.txt", "b.txt"]:
            Path(os.path.join(temp_dir, name)).write_bytes(b"x")
        result = local_facade.list_files(temp_dir)
        assert len(result) == 2

    def test_copy(self, local_facade, temp_dir):
        src = os.path.join(temp_dir, "src.txt")
        dst = os.path.join(temp_dir, "dst.txt")
        local_facade.write(src, b"copy this")
        local_facade.copy(src, dst)
        assert local_facade.read(dst) == b"copy this"

    def test_mkdir(self, local_facade, temp_dir):
        path = os.path.join(temp_dir, "new", "dir")
        local_facade.mkdir(path)
        assert os.path.isdir(path)


class TestUnsupportedOperations:
    """Test that unsupported operations raise clear errors."""

    def test_unsupported_operation_raises(self):
        """Create a facade with a backend that doesn't support directories."""
        from unittest.mock import Mock, patch, MagicMock

        mock_auth = Mock()
        mock_auth.settings = Mock()
        mock_auth.settings.ENDPOINT = "https://s3.amazonaws.com"
        mock_auth.settings.ACCESS_KEY_ID = "key"
        mock_auth.settings.SECRET_KEY = "secret"
        mock_auth.settings.REGION = "us-east-1"
        mock_auth.settings.USE_SSL = True
        mock_auth.settings.PROVIDER_TYPE = "s3"

        with patch("boto3.client"):
            from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
            facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, mock_auth)
            with pytest.raises(UnsupportedOperationError, match="does not support"):
                facade.mkdir("/some/path")


class TestCopyBetween:
    """Test cross-backend copy operations."""

    def test_copy_between_local_paths(self, temp_dir):
        src = os.path.join(temp_dir, "src.txt")
        dst = os.path.join(temp_dir, "dst.txt")
        Path(src).write_bytes(b"cross copy")

        src_facade = StorageFacade.for_local()
        dst_facade = StorageFacade.for_local()
        copy_between(src, dst, src_facade, dst_facade)

        assert Path(dst).read_bytes() == b"cross copy"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/facade/test_facade.py -v`
Expected: FAIL

- [ ] **Step 3: Create facade.py**

```python
# src/mountainash_utils_files/storage_facade/facade.py
"""StorageFacade — unified user-facing API for storage operations."""
from __future__ import annotations
from typing import Any, BinaryIO

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from mountainash_utils_files.exceptions import UnsupportedOperationError
from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)
from mountainash_utils_files.storage_registry import get_storage_backend


class StorageFacade:
    """Unified storage operations API.

    Dispatches to a protocol-checked backend. Raises
    UnsupportedOperationError if the backend doesn't implement
    the required protocol.
    """

    def __init__(self, provider_type: CONST_STORAGE_PROVIDER_TYPE, auth_params: Any = None):
        self._backend = get_storage_backend(provider_type, auth_params)

    @classmethod
    def for_local(cls) -> StorageFacade:
        """Convenience factory for local filesystem."""
        return cls(CONST_STORAGE_PROVIDER_TYPE.LOCAL, auth_params=None)

    # --- Capability introspection ---

    def supports(self, protocol: type) -> bool:
        """Check if backend supports a capability."""
        return isinstance(self._backend, protocol)

    def _require(self, protocol: type, operation: str) -> None:
        if not isinstance(self._backend, protocol):
            raise UnsupportedOperationError(
                f"{type(self._backend).__name__} does not support '{operation}'"
            )

    # --- Core operations ---

    def read(self, path: str) -> bytes:
        self._require(StorageReadProtocol, "read")
        return self._backend.read_to_bytes(path)

    def read_stream(self, path: str) -> BinaryIO:
        self._require(StorageReadProtocol, "read_stream")
        return self._backend.read_to_stream(path)

    def write(self, path: str, data: bytes) -> None:
        self._require(StorageWriteProtocol, "write")
        self._backend.write_from_bytes(path, data)

    def write_stream(self, path: str, stream: BinaryIO) -> None:
        self._require(StorageWriteProtocol, "write_stream")
        self._backend.write_from_stream(path, stream)

    def list_files(self, prefix: str) -> list[FileMetadata]:
        self._require(StorageListProtocol, "list_files")
        return self._backend.list_files(prefix)

    def list_directories(self, prefix: str) -> list[str]:
        self._require(StorageListProtocol, "list_directories")
        return self._backend.list_directories(prefix)

    def delete(self, path: str) -> None:
        self._require(StorageDeleteProtocol, "delete")
        self._backend.delete_file(path)

    def exists(self, path: str) -> bool:
        self._require(StorageMetadataProtocol, "exists")
        return self._backend.path_exists(path)

    def metadata(self, path: str) -> FileMetadata:
        self._require(StorageMetadataProtocol, "metadata")
        return self._backend.get_metadata(path)

    def get_size(self, path: str) -> int:
        self._require(StorageMetadataProtocol, "get_size")
        return self._backend.get_size(path)

    def copy(self, source: str, destination: str) -> None:
        self._require(StorageCopyProtocol, "copy")
        self._backend.copy(source, destination)

    def mkdir(self, path: str, parents: bool = True) -> None:
        self._require(StorageDirectoryProtocol, "mkdir")
        self._backend.mkdir(path, parents=parents)

    def rmdir(self, path: str) -> None:
        self._require(StorageDirectoryProtocol, "rmdir")
        self._backend.rmdir(path)
```

- [ ] **Step 4: Create cross_backend.py**

```python
# src/mountainash_utils_files/storage_facade/cross_backend.py
"""Cross-backend file operations."""
from __future__ import annotations

from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_protocols import StorageCopyProtocol


def copy_between(
    source_path: str,
    destination_path: str,
    source_facade: StorageFacade,
    destination_facade: StorageFacade,
) -> None:
    """Copy a file between two storage backends.

    Uses native copy if both facades share the same backend type
    and the backend supports copy. Otherwise streams through memory.
    """
    # Same backend type with native copy? Use it.
    if (
        type(source_facade._backend) is type(destination_facade._backend)
        and source_facade.supports(StorageCopyProtocol)
    ):
        source_facade.copy(source_path, destination_path)
        return

    # Different backends: stream through
    stream = source_facade.read_stream(source_path)
    try:
        destination_facade.write_stream(destination_path, stream)
    finally:
        stream.close()
```

- [ ] **Step 5: Create __init__.py**

```python
# src/mountainash_utils_files/storage_facade/__init__.py
"""Storage facade — unified user-facing API."""

from .facade import StorageFacade
from .cross_backend import copy_between

__all__ = ["StorageFacade", "copy_between"]
```

- [ ] **Step 6: Create tests/facade/__init__.py**

```bash
touch tests/facade/__init__.py
```

- [ ] **Step 7: Run facade tests**

Run: `hatch run test:test tests/facade/test_facade.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/
git add tests/facade/
git commit -m "feat: add StorageFacade — protocol-checked dispatch with cross-backend copy"
```

---

### Task 8: Protocol Alignment Tests

**Files:**
- Create: `tests/protocol_alignment/__init__.py`
- Create: `tests/protocol_alignment/test_protocol_conformance.py`
- Create: `tests/protocol_alignment/test_registry_completeness.py`

- [ ] **Step 1: Write protocol conformance test**

```python
# tests/protocol_alignment/test_protocol_conformance.py
"""Enforce that every registered backend conforms to its declared protocols.

This test is the CI enforcement mechanism — if a mixin is missing a method,
this test fails.
"""
import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)
from mountainash_utils_files.storage_registry import get_registered_backends

# Single source of truth: what protocols each backend MUST implement
EXPECTED_PROTOCOLS = {
    CONST_STORAGE_PROVIDER_TYPE.LOCAL: {
        StorageConnectionProtocol,
        StorageReadProtocol,
        StorageWriteProtocol,
        StorageListProtocol,
        StorageDeleteProtocol,
        StorageMetadataProtocol,
        StorageCopyProtocol,
        StorageDirectoryProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.S3: {
        StorageConnectionProtocol,
        StorageReadProtocol,
        StorageWriteProtocol,
        StorageListProtocol,
        StorageDeleteProtocol,
        StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.R2: {
        StorageConnectionProtocol,
        StorageReadProtocol,
        StorageWriteProtocol,
        StorageListProtocol,
        StorageDeleteProtocol,
        StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: {
        StorageConnectionProtocol,
        StorageReadProtocol,
        StorageWriteProtocol,
        StorageListProtocol,
        StorageDeleteProtocol,
        StorageMetadataProtocol,
        StorageCopyProtocol,
    },
    CONST_STORAGE_PROVIDER_TYPE.MINIO: {
        StorageConnectionProtocol,
        StorageReadProtocol,
        StorageWriteProtocol,
        StorageListProtocol,
        StorageDeleteProtocol,
        StorageMetadataProtocol,
        StorageCopyProtocol,
    },
}

# Protocols that specific backends must NOT implement
EXCLUDED_PROTOCOLS = {
    CONST_STORAGE_PROVIDER_TYPE.S3: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.R2: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS: {StorageDirectoryProtocol},
    CONST_STORAGE_PROVIDER_TYPE.MINIO: {StorageDirectoryProtocol},
}


class TestProtocolConformance:
    """Every registered backend conforms to its declared protocols."""

    @pytest.mark.parametrize(
        "provider_type",
        list(EXPECTED_PROTOCOLS.keys()),
    )
    def test_backend_implements_required_protocols(self, provider_type):
        backends = get_registered_backends()
        assert provider_type in backends, f"No backend registered for {provider_type}"
        backend_cls = backends[provider_type]
        for protocol in EXPECTED_PROTOCOLS[provider_type]:
            assert issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} does not implement {protocol.__name__}"
            )

    @pytest.mark.parametrize(
        "provider_type",
        list(EXCLUDED_PROTOCOLS.keys()),
    )
    def test_backend_excludes_unsupported_protocols(self, provider_type):
        backends = get_registered_backends()
        backend_cls = backends[provider_type]
        for protocol in EXCLUDED_PROTOCOLS[provider_type]:
            assert not issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} should NOT implement {protocol.__name__}"
            )
```

- [ ] **Step 2: Write registry completeness test**

```python
# tests/protocol_alignment/test_registry_completeness.py
"""Verify every expected provider type has a registered backend."""

import pytest
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry import get_registered_backends

# Provider types that MUST have a backend registered
REQUIRED_BACKENDS = {
    CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    CONST_STORAGE_PROVIDER_TYPE.S3,
    CONST_STORAGE_PROVIDER_TYPE.R2,
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    CONST_STORAGE_PROVIDER_TYPE.MINIO,
}

# Provider types that are known to not yet have backends
ASPIRATIONAL_BACKENDS = {
    CONST_STORAGE_PROVIDER_TYPE.GCS,
    CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    CONST_STORAGE_PROVIDER_TYPE.SFTP,
    CONST_STORAGE_PROVIDER_TYPE.SSH,
    CONST_STORAGE_PROVIDER_TYPE.B2,
}


class TestRegistryCompleteness:

    def test_all_required_backends_registered(self):
        backends = get_registered_backends()
        for provider in REQUIRED_BACKENDS:
            assert provider in backends, f"Missing backend for {provider}"

    @pytest.mark.parametrize("provider", list(ASPIRATIONAL_BACKENDS))
    def test_aspirational_backends_tracked(self, provider):
        """These backends are expected to be added later."""
        backends = get_registered_backends()
        if provider in backends:
            pytest.skip(f"{provider} has been implemented — move to REQUIRED_BACKENDS")
        else:
            pytest.skip(f"{provider} not yet implemented — aspirational")
```

- [ ] **Step 3: Create __init__.py**

```bash
touch tests/protocol_alignment/__init__.py
```

- [ ] **Step 4: Run protocol alignment tests**

Run: `hatch run test:test tests/protocol_alignment/ -v`
Expected: All PASS (with aspirational backends skipped)

- [ ] **Step 5: Commit**

```bash
git add tests/protocol_alignment/
git commit -m "feat: add protocol alignment tests — CI enforcement of backend contracts"
```

---

## Phase 4: Cross-Backend Tests & Public API (Tasks 9-11)

### Task 9: Cross-Backend Parametrized Tests

**Files:**
- Create: `tests/cross_backend/__init__.py`
- Create: `tests/cross_backend/test_read_write.py`
- Create: `tests/cross_backend/test_list.py`
- Create: `tests/cross_backend/test_metadata.py`
- Create: `tests/cross_backend/test_delete.py`

- [ ] **Step 1: Write cross-backend read/write tests**

```python
# tests/cross_backend/__init__.py
# (empty)
```

```python
# tests/cross_backend/test_read_write.py
"""Cross-backend read/write tests — same logic, all backends."""

import pytest
import os
import io
import tempfile
import shutil

from mountainash_utils_files.storage_facade import StorageFacade


LOCAL_BACKENDS = ["local"]


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def make_facade(backend_name: str) -> StorageFacade:
    if backend_name == "local":
        return StorageFacade.for_local()
    pytest.skip(f"Backend {backend_name} requires integration credentials")


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
class TestReadWriteRoundtrip:

    def test_write_then_read_bytes(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "roundtrip.txt")
        data = b"hello mountainash"
        facade.write(path, data)
        assert facade.read(path) == data

    def test_write_then_read_stream(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "stream_roundtrip.txt")
        data = b"stream content"
        facade.write(path, data)
        stream = facade.read_stream(path)
        assert stream.read() == data
        stream.close()

    def test_write_empty_file(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "empty.txt")
        facade.write(path, b"")
        assert facade.read(path) == b""

    def test_write_large_content(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "large.bin")
        data = b"x" * (1024 * 1024)  # 1MB
        facade.write(path, data)
        assert facade.read(path) == data

    def test_overwrite_existing(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "overwrite.txt")
        facade.write(path, b"first")
        facade.write(path, b"second")
        assert facade.read(path) == b"second"
```

- [ ] **Step 2: Write cross-backend list, metadata, and delete tests**

```python
# tests/cross_backend/test_list.py
"""Cross-backend list tests."""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from mountainash_utils_files.storage_facade import StorageFacade

LOCAL_BACKENDS = ["local"]


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def make_facade(backend_name: str) -> StorageFacade:
    if backend_name == "local":
        return StorageFacade.for_local()
    pytest.skip(f"Backend {backend_name} requires integration credentials")


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
class TestListFiles:

    def test_list_returns_correct_count(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        for name in ["a.txt", "b.csv", "c.json"]:
            Path(os.path.join(temp_dir, name)).write_bytes(b"x")
        result = facade.list_files(temp_dir)
        assert len(result) == 3

    def test_list_empty_directory(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        result = facade.list_files(temp_dir)
        assert result == []
```

```python
# tests/cross_backend/test_metadata.py
"""Cross-backend metadata tests."""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from mountainash_utils_files.storage_facade import StorageFacade

LOCAL_BACKENDS = ["local"]


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def make_facade(backend_name: str) -> StorageFacade:
    if backend_name == "local":
        return StorageFacade.for_local()
    pytest.skip(f"Backend {backend_name} requires integration credentials")


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
class TestMetadata:

    def test_exists_true(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "exists.txt")
        Path(path).write_bytes(b"x")
        assert facade.exists(path)

    def test_exists_false(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        assert not facade.exists(os.path.join(temp_dir, "nope.txt"))

    def test_get_size(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "sized.txt")
        data = b"twelve bytes"
        Path(path).write_bytes(data)
        assert facade.get_size(path) == len(data)

    def test_metadata_returns_filename(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "meta.txt")
        Path(path).write_bytes(b"content")
        meta = facade.metadata(path)
        assert meta.filename == "meta.txt"
```

```python
# tests/cross_backend/test_delete.py
"""Cross-backend delete tests."""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

from mountainash_utils_files.storage_facade import StorageFacade
from mountainash_utils_files.exceptions import PathNotFoundError

LOCAL_BACKENDS = ["local"]


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def make_facade(backend_name: str) -> StorageFacade:
    if backend_name == "local":
        return StorageFacade.for_local()
    pytest.skip(f"Backend {backend_name} requires integration credentials")


@pytest.mark.parametrize("backend_name", LOCAL_BACKENDS)
class TestDelete:

    def test_delete_existing_file(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        path = os.path.join(temp_dir, "delete_me.txt")
        Path(path).write_bytes(b"gone")
        facade.delete(path)
        assert not facade.exists(path)

    def test_delete_nonexistent_raises(self, backend_name, temp_dir):
        facade = make_facade(backend_name)
        with pytest.raises(PathNotFoundError):
            facade.delete(os.path.join(temp_dir, "nope.txt"))
```

- [ ] **Step 3: Run all cross-backend tests**

Run: `hatch run test:test tests/cross_backend/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/cross_backend/
git commit -m "feat: add cross-backend parametrized tests — unified test logic across all backends"
```

---

### Task 10: Run Full Test Suite

- [ ] **Step 1: Run all new tests together**

Run: `hatch run test:test tests/test_constants_and_exceptions.py tests/test_protocols.py tests/test_registry.py tests/backends/ tests/facade/ tests/protocol_alignment/ tests/cross_backend/ -v`
Expected: All PASS

- [ ] **Step 2: Fix any failures**

If any tests fail, diagnose and fix. Do not proceed until green.

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve test failures from full suite run"
```

---

### Task 11: Update Public API (__init__.py)

**Files:**
- Modify: `src/mountainash_utils_files/__init__.py`

- [ ] **Step 1: Write test for new public API**

```python
# tests/test_public_api.py
"""Verify the new public API exports are correct."""

import pytest


class TestPublicAPI:

    def test_facade_importable(self):
        from mountainash_utils_files import StorageFacade, copy_between, storage
        assert callable(StorageFacade)
        assert callable(copy_between)
        assert callable(storage)

    def test_protocols_importable(self):
        from mountainash_utils_files import (
            StorageReadProtocol,
            StorageWriteProtocol,
            StorageListProtocol,
            StorageDeleteProtocol,
            StorageMetadataProtocol,
            StorageCopyProtocol,
            StorageDirectoryProtocol,
            StorageConnectionProtocol,
        )

    def test_registry_importable(self):
        from mountainash_utils_files import (
            get_storage_backend,
            detect_provider_from_path,
        )

    def test_constants_importable(self):
        from mountainash_utils_files import CONST_STORAGE_PROVIDER_TYPE

    def test_exceptions_importable(self):
        from mountainash_utils_files import (
            StorageError,
            UnsupportedOperationError,
            PathNotFoundError,
            AuthenticationError,
        )

    def test_path_helper_importable(self):
        from mountainash_utils_files import PathHelper

    def test_storage_convenience(self):
        """storage() returns a StorageFacade for local."""
        from mountainash_utils_files import storage
        facade = storage()
        assert facade.supports(StorageReadProtocol)
        # Import needed for check
        from mountainash_utils_files import StorageReadProtocol
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/test_public_api.py -v`
Expected: FAIL

- [ ] **Step 3: Update __init__.py**

Replace `src/mountainash_utils_files/__init__.py` with:

```python
"""mountainash-utils-files — unified storage operations across backends."""

from .__version__ import __version__

# Facade — main user API
from .storage_facade import StorageFacade, copy_between

# Registry
from .storage_registry import get_storage_backend, detect_provider_from_path

# Protocols — for isinstance checks and type hints
from .storage_protocols import (
    StorageConnectionProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
)

# Constants
from .constants import CONST_STORAGE_PROVIDER_TYPE

# Dataclasses
from .dataclasses.file_metadata import FileMetadata

# Exceptions
from .exceptions import (
    StorageError,
    UnsupportedOperationError,
    StorageConnectionError,
    PathNotFoundError,
    AuthenticationError,
)

# Path utilities
from .path_helpers import PathHelper

# Trigger backend registrations
from . import storage_backends  # noqa: F401


def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            auth_params=None) -> StorageFacade:
    """Convenience factory for creating a StorageFacade."""
    return StorageFacade(provider_type, auth_params)


__all__ = [
    "__version__",
    # Facade
    "StorageFacade",
    "copy_between",
    "storage",
    # Registry
    "get_storage_backend",
    "detect_provider_from_path",
    # Protocols
    "StorageConnectionProtocol",
    "StorageReadProtocol",
    "StorageWriteProtocol",
    "StorageListProtocol",
    "StorageDeleteProtocol",
    "StorageMetadataProtocol",
    "StorageCopyProtocol",
    "StorageDirectoryProtocol",
    # Constants
    "CONST_STORAGE_PROVIDER_TYPE",
    # Dataclasses
    "FileMetadata",
    # Exceptions
    "StorageError",
    "UnsupportedOperationError",
    "StorageConnectionError",
    "PathNotFoundError",
    "AuthenticationError",
    # Utilities
    "PathHelper",
]
```

- [ ] **Step 4: Run public API tests**

Run: `hatch run test:test tests/test_public_api.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/__init__.py tests/test_public_api.py
git commit -m "feat: update public API exports — facade, protocols, registry, exceptions"
```

---

## Phase 5: Cleanup (Task 12)

### Task 12: Remove Old Architecture

**IMPORTANT:** This task removes the old code. Run the full new test suite first to confirm everything works. The old tests that depend on old code will also be removed.

- [ ] **Step 1: Run full new test suite to confirm green**

Run: `hatch run test:test tests/test_constants_and_exceptions.py tests/test_protocols.py tests/test_registry.py tests/test_public_api.py tests/backends/ tests/facade/ tests/protocol_alignment/ tests/cross_backend/ -v`
Expected: All PASS

- [ ] **Step 2: Remove old directories**

```bash
# Old file helpers (replaced by storage_backends)
rm -rf src/mountainash_utils_files/file_helpers/

# Old factories (replaced by storage_registry)
rm -rf src/mountainash_utils_files/factories/

# Old file interface (replaced by storage_facade)
rm -rf src/mountainash_utils_files/file_interface/

# Extracted to separate packages
rm -rf src/mountainash_utils_files/file_sync/
rm -rf src/mountainash_utils_files/file_readers/
rm -rf src/mountainash_utils_files/file_writers/

# Old storage_utils.py if it exists
rm -f src/mountainash_utils_files/storage_utils.py
```

- [ ] **Step 3: Remove old test files that depend on removed code**

```bash
rm -f tests/test_data_storage.py
rm -f tests/test_file_helpers.py
rm -f tests/test_file_interface.py
rm -f tests/test_file_readers_writers.py
rm -f tests/test_file_sync.py
rm -f tests/test_ssh_file_helper.py
```

- [ ] **Step 4: Update conftest.py — remove old fixtures**

Replace `tests/conftest.py` with:

```python
"""Shared test fixtures for mountainash-utils-files tests."""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator

from mountainash_utils_files import StorageFacade


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_file(temp_directory: Path) -> Path:
    """Create a temporary file for tests."""
    temp_file = temp_directory / "test_file.txt"
    temp_file.write_text("This is test content for file operations.\nLine 2\nLine 3")
    return temp_file


@pytest.fixture
def local_facade() -> StorageFacade:
    """Provide a local storage facade."""
    return StorageFacade.for_local()
```

- [ ] **Step 5: Run full test suite**

Run: `hatch run test:test tests/ -v`
Expected: All PASS (only new tests remain)

- [ ] **Step 6: Run linter**

Run: `hatch run ruff:check`
Expected: No errors (or fix any that appear)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove old architecture — file_helpers, factories, file_interface, sync, readers, writers

Removed ~9,660 lines of old code replaced by protocol-driven architecture:
- file_helpers/ → storage_backends/ (protocol-composed mixins)
- factories/ → storage_registry/ (decorator-based registration)
- file_interface/ → storage_facade/ (protocol-checked dispatch)
- file_sync/, file_readers/, file_writers/ → extracted for separate packages"
```

---

## Summary

| Phase | Tasks | What It Delivers |
|-------|-------|-----------------|
| 1: Foundation | 1-3 | Constants, exceptions, protocols, registry |
| 2: Backends | 4-6 | Local + S3 + S3-family backends |
| 3: Facade | 7-8 | User API + protocol alignment enforcement |
| 4: Integration | 9-11 | Cross-backend tests + public API |
| 5: Cleanup | 12 | Remove old architecture |

Each phase produces working, testable software. Phase 1-3 can be reviewed before proceeding to 4-5.
