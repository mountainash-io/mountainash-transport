# Protocol-Driven Architecture Redesign — mountainash-utils-files

**Date:** 2026-04-03
**Status:** Approved
**Approach:** B — Protocol-Composed (Protocols + Composition, no AST/Visitor)
**Reference Architecture:** mountainash-expressions (protocols, composition, registry patterns)

---

## 1. Problem Statement

The current architecture suffers from:

- **God-object base class** — `Base_FileHelper` is 1,356 lines with 148 boolean capability flags and 51 abstract methods
- **Massive duplication** — Every subclass repeats ~280 lines of identical `set_interface_attributes()` boilerplate. The S3 family (S3, R2, S3Express, MinIO) duplicates 500+ lines each instead of sharing
- **Dual constant systems** — `CONST_STORAGESYSTEM` ("LOCAL_DISK", "S3") vs `CONST_STORAGE_PROVIDER_TYPE` ("local", "s3") with a manual mapping dict bridging them
- **Duplicate factories** — Old eager-loading factory in `file_helpers/` and new lazy-loading factory in `factories/`, partially integrated
- **Scope creep** — File sync, readers, and writers dumped into core package
- **Dead code** — `s3_file_helper_backup.py` (559 lines, unreferenced), 120+ lines of commented-out abstract methods
- **No custom exceptions** — Generic `ValueError` everywhere
- **Weak test coverage** — No tests for new factory, no protocol alignment enforcement, path helpers under-tested

## 2. Goals

1. Replace inheritance-heavy design with protocol-driven composition following mountainash-expressions patterns
2. Eliminate duplication across storage backends (especially S3 family)
3. Unify constants to a single enum
4. Scope the package to storage operations only — extract sync, readers, writers
5. Enforce protocol alignment in CI
6. Establish clear boundary contracts with external Mountain Ash packages

## 3. Non-Goals

- Cross-repo changes to mountainash-constants or mountainash-settings (phase later)
- AST/visitor compilation pattern (unnecessary for imperative file operations)
- Format-specific file reading/writing (extracted to separate package)
- File synchronization orchestration (extracted to separate package)

## 4. Architecture Overview

Three layers with strict dependency direction:

```
Protocols → Backends → Facade
   ↑            ↑         ↑
   |            |         |
 (no deps)  (imports   (imports protocols
             protocols)  + registry)
```

- **Protocols** define contracts. Import nothing from backends or facade.
- **Backends** implement protocols via focused mixins, composed via multiple inheritance.
- **Facade** dispatches to protocol-checked backends. Cross-backend operations compose two facades.
- **Registry** provides backend discovery via decorator registration.
- **Path Helpers** (existing, kept as-is) handle path formatting, joining, and manipulation. Provider identification logic moves from `PathHelper` to `backend_detection.py` in the registry layer.
- **Settings** (existing, kept as-is) handle auth providers, validation, and connection configuration.

## 5. Protocol Layer

### 5.1 Core Protocols

Each protocol defines one capability category. Backends conform by implementing the methods — structural typing, no inheritance required. All protocols are `@runtime_checkable`.

```
storage_protocols/
├── __init__.py
├── prtcl_connection.py
├── prtcl_read.py
├── prtcl_write.py
├── prtcl_list.py
├── prtcl_delete.py
├── prtcl_metadata.py
├── prtcl_copy.py
├── prtcl_directory.py
├── prtcl_compression.py
└── prtcl_encryption.py
```

**Protocol definitions:**

| Protocol | Methods | Purpose |
|---|---|---|
| `StorageConnectionProtocol` | `connect()`, `disconnect()`, `is_connected()` | Connection lifecycle |
| `StorageReadProtocol` | `read_to_bytes(path)`, `read_to_stream(path)` | Read files |
| `StorageWriteProtocol` | `write_from_bytes(path, data)`, `write_from_stream(path, stream)` | Write files |
| `StorageListProtocol` | `list_files(prefix)`, `list_directories(prefix)` | List contents |
| `StorageDeleteProtocol` | `delete_file(path)` | Delete files |
| `StorageMetadataProtocol` | `get_metadata(path)`, `path_exists(path)`, `get_size(path)` | File metadata |
| `StorageCopyProtocol` | `copy(source, destination)` | Native same-backend copy |
| `StorageDirectoryProtocol` | `mkdir(path, parents)`, `rmdir(path)` | Directory operations |
| `StorageCompressionProtocol` | `read_compressed(path)`, `write_compressed(path, stream)` | Native compression |
| `StorageEncryptionProtocol` | `read_encrypted(path)`, `write_encrypted(path, stream)` | Native encryption |

### 5.2 Design Decisions

- **Protocols, not ABCs** — Structural typing via `typing.Protocol`. Conformance checked with `isinstance()` at runtime.
- **Capability = protocol conformance** — Replaces 148 boolean flags. `isinstance(backend, StorageReadProtocol)` replaces `self.supports_native_get_to_stream`.
- **No combinatorial explosion** — Old system: `supports_{encrypt|decrypt|compress|decompress}_native_{get|put}_{to|from}_{stream|local_path|native_path}` = 48 flags. New system: implement `StorageReadProtocol` + `StorageEncryptionProtocol` and the facade composes them.
- **SmartOpen is an implementation detail** — Not protocol-level. Backends use it internally if needed.

## 6. Backend Layer

### 6.1 Composition Pattern

Each backend is a composition class assembling focused mixin implementations. The composition class body is `pass` (same as expressions).

```
storage_backends/
├── __init__.py              # Triggers all backend registrations
├── local/
│   ├── __init__.py          # @register LocalStorageBackend(pass)
│   ├── local_connection.py
│   ├── local_read.py
│   ├── local_write.py
│   ├── local_list.py
│   ├── local_delete.py
│   ├── local_metadata.py
│   ├── local_copy.py
│   └── local_directory.py
├── s3/
│   ├── __init__.py          # @register S3StorageBackend(pass)
│   ├── s3_connection.py
│   ├── s3_read.py
│   ├── s3_write.py
│   ├── s3_list.py
│   ├── s3_delete.py
│   ├── s3_metadata.py
│   └── s3_copy.py
├── r2/                      # Reuses s3 mixins, overrides connection only
│   ├── __init__.py
│   └── r2_connection.py
├── s3express/
│   ├── __init__.py
│   └── s3express_connection.py
├── minio/
│   ├── __init__.py
│   └── minio_connection.py
├── gcs/
│   ├── __init__.py
│   └── gcs_*.py
├── azure/
│   ├── __init__.py
│   └── azure_*.py
├── sftp/
│   ├── __init__.py
│   └── sftp_*.py
└── ssh/
    ├── __init__.py
    └── ssh_*.py
```

### 6.2 Composition Examples

```python
# S3 backend — full implementation
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
    pass

# R2 — reuses all S3 mixins, only connection differs
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
    pass

# S3Express — different session handling
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
    pass
```

### 6.3 Design Decisions

- **Each mixin = one file, one protocol** — 30-80 lines per file vs 600+ line monoliths
- **S3 family shares mixins** — R2, S3Express, MinIO differ only in connection/auth. Eliminates ~2,000 lines of current duplication.
- **No `set_interface_attributes()`** — The 280-line boilerplate method disappears entirely.
- **Missing capability = missing mixin** — SSH has no `StorageDirectoryProtocol` mixin, so `isinstance(ssh_backend, StorageDirectoryProtocol)` returns `False`.

## 7. Registry & Factory

### 7.1 Structure

```
storage_registry/
├── __init__.py
├── registry.py              # @register_storage_backend + get_storage_backend()
└── backend_detection.py     # Path scheme → CONST_STORAGE_PROVIDER_TYPE
```

### 7.2 Registry

```python
_backend_registry: dict[CONST_STORAGE_PROVIDER_TYPE, type] = {}

def register_storage_backend(provider_type: CONST_STORAGE_PROVIDER_TYPE):
    def decorator(cls):
        _backend_registry[provider_type] = cls
        return cls
    return decorator

def get_storage_backend(provider_type, auth_params):
    cls = _backend_registry.get(provider_type)
    if cls is None:
        raise ValueError(f"No backend registered for {provider_type}")
    return cls(auth_params)

def get_registered_backends() -> dict[CONST_STORAGE_PROVIDER_TYPE, type]:
    return dict(_backend_registry)
```

### 7.3 Backend Detection

```python
_SCHEME_TO_PROVIDER: dict[str, CONST_STORAGE_PROVIDER_TYPE] = {
    "": CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    "s3": CONST_STORAGE_PROVIDER_TYPE.S3,
    "gs": CONST_STORAGE_PROVIDER_TYPE.GCS,
    "az": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "sftp": CONST_STORAGE_PROVIDER_TYPE.SFTP,
    "ssh": CONST_STORAGE_PROVIDER_TYPE.SSH,
    "r2": CONST_STORAGE_PROVIDER_TYPE.R2,
    "b2": CONST_STORAGE_PROVIDER_TYPE.B2,
}

def detect_provider_from_path(path: str) -> CONST_STORAGE_PROVIDER_TYPE:
    scheme = path.split("://")[0] if "://" in path else ""
    provider = _SCHEME_TO_PROVIDER.get(scheme)
    if provider is None:
        raise ValueError(f"Unknown scheme: {scheme}")
    return provider
```

### 7.4 Design Decisions

- **One constant system** — `CONST_STORAGE_PROVIDER_TYPE` only. `CONST_STORAGESYSTEM` and `CONST_STORAGESYSTEM_PREFIX` removed.
- **Registration at import time** — Backend `__init__.py` triggers `@register_storage_backend`. Same as expressions' `@register_expression_system`.
- **No caching** — Backends instantiated fresh with auth params. Old factory cached instances with stale auth state.
- **Detection from path OR settings** — `detect_provider_from_path()` for URLs. `auth_params.provider_type` for settings. Both resolve to same enum.

## 8. Facade Layer

### 8.1 Structure

```
storage_facade/
├── __init__.py
├── facade.py            # StorageFacade
└── cross_backend.py     # copy_between()
```

### 8.2 StorageFacade

Instance-based API. Holds auth state so operations are clean (`s3.read(path)` not `FileInterface.read(path, auth_params)`).

Protocol checks at dispatch time via `_require()` — clear errors like "S3StorageBackend does not support 'mkdir'" instead of boolean flag checks.

Capability introspection via `supports(protocol)`.

### 8.3 Cross-Backend Operations

```python
def copy_between(source_path, destination_path, source_auth, destination_auth):
    source = StorageFacade(source_auth)
    destination = StorageFacade(destination_auth)

    # Same backend with native copy? Use it.
    if (type(source._backend) is type(destination._backend)
            and source.supports(StorageCopyProtocol)):
        source.copy(source_path, destination_path)
        return

    # Different backends: stream through
    stream = source.read_stream(source_path)
    destination.write_stream(destination_path, stream)
```

### 8.4 Design Decisions

- **Instance-based, not classmethods** — Current `FileInterface` is all `@classmethod`. New facade holds backend state.
- **Compression/encryption composable at facade level** — Wrap streams with gzip/GPG decorators without backends needing to know. Eliminates combinatorial flag logic from backends.
- **Cross-backend copy is simple** — Stream from source, write to destination. Backends can override `copy()` for native fast-path within same system.

## 9. Constants & Exceptions

### 9.1 Unified Constants

```python
class CONST_STORAGE_PROVIDER_TYPE(StrEnum):
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
```

Removed: `CONST_STORAGESYSTEM`, `CONST_STORAGESYSTEM_PREFIX`, `CONST_DATAFILEFORMAT` (moves to readers/writers package). Provider types without backend implementations removed (FTP, SMB, NFS, GITHUB, AZURE_FILES) — re-add when implemented.

### 9.2 Custom Exceptions

```python
class StorageError(Exception): ...
class UnsupportedOperationError(StorageError): ...
class StorageConnectionError(StorageError): ...
class PathNotFoundError(StorageError): ...
class AuthenticationError(StorageError): ...
```

## 10. Boundary Contracts (External Packages)

Phase (c) strategy: adapt at boundaries now, propose cross-repo changes later.

| External Package | Current Coupling | Boundary Contract |
|---|---|---|
| `mountainash-constants` | Defines `CONST_STORAGESYSTEM` | This package owns `CONST_STORAGE_PROVIDER_TYPE`. Import from constants when unified there later. |
| `mountainash-settings` | `SettingsParameters` passed everywhere | Depend on `SettingsParameters.provider_type` resolving to our enum. Stable interface. |
| `mountainash-utils-gpg` | `GPG_Helper` in base class | Moves to facade-level stream wrapper. Optional dependency. |
| `mountainash-utils-ssh` | SSH tunnel management | Scoped to SFTP/SSH backend mixins only. |

## 11. Testing Strategy

### 11.1 Test Structure

```
tests/
├── protocol_alignment/
│   ├── test_protocol_conformance.py    # Every backend implements declared protocols
│   └── test_registry_completeness.py   # Every provider type has a registered backend
├── cross_backend/
│   ├── test_read_write.py              # Parametrized across all backends
│   ├── test_list.py
│   ├── test_metadata.py
│   ├── test_delete.py
│   └── test_copy_between.py
├── backends/
│   ├── test_local.py                   # Backend-specific edge cases
│   ├── test_s3.py
│   └── ...
├── facade/
│   ├── test_facade.py
│   └── test_unsupported_ops.py
└── path_helpers/
    └── test_path_utils.py
```

### 11.2 Protocol Alignment Enforcement

CI enforces that every registered backend conforms to its declared protocols. A capability matrix (`EXPECTED_PROTOCOLS` dict) is the single source of truth.

### 11.3 Cross-Backend Parametrized Tests

Same test logic runs across all backends via `@pytest.mark.parametrize`. Local tests always run. Cloud backends gated behind `@pytest.mark.integration`.

## 12. Removal Summary

| File/Directory | Lines | Action |
|---|---|---|
| `file_helpers/base_file_helper.py` | 1,356 | Replaced by protocols + mixins |
| `file_helpers/local_file_helper.py` | 678 | Replaced by `storage_backends/local/` |
| `file_helpers/s3_file_helper.py` | 606 | Replaced by `storage_backends/s3/` |
| `file_helpers/s3_file_helper_backup.py` | 559 | Dead code — deleted |
| `file_helpers/s3express_file_helper.py` | 552 | Replaced by `storage_backends/s3express/` |
| `file_helpers/s3_minio_file_helper.py` | 658 | Replaced by `storage_backends/minio/` |
| `file_helpers/r2_file_helper.py` | 832 | Replaced by `storage_backends/r2/` |
| `file_helpers/sftp_file_helper.py` | 618 | Replaced by `storage_backends/sftp/` |
| `file_helpers/ssh_file_helper.py` | 290 | Replaced by `storage_backends/ssh/` |
| `file_helpers/gcs_file_helper.py` | 316 | Replaced by `storage_backends/gcs/` |
| `file_helpers/azure_file_helper.py` | 161 | Replaced by `storage_backends/azure/` |
| `file_helpers/file_helper_factory.py` | 159 | Replaced by registry |
| `factories/` (all files) | 686 | Replaced by registry |
| `file_interface/` | 576 | Replaced by facade |
| `file_sync/` | 925 | Extracted to separate package |
| `file_readers/` | 250 | Extracted to separate package |
| `file_writers/` | 438 | Extracted to separate package |
| **Total removed** | **~9,660** | |

## 13. Public API

```python
from mountainash_utils_files import (
    # Main API
    StorageFacade,
    storage,              # convenience factory
    copy_between,

    # Registry
    get_storage_backend,
    detect_provider_from_path,

    # Protocols (for isinstance checks / type hints)
    StorageReadProtocol,
    StorageWriteProtocol,
    StorageListProtocol,
    StorageDeleteProtocol,
    StorageMetadataProtocol,
    StorageCopyProtocol,
    StorageDirectoryProtocol,
    StorageConnectionProtocol,
    StorageCompressionProtocol,
    StorageEncryptionProtocol,

    # Utilities
    PathHelper,
    CONST_STORAGE_PROVIDER_TYPE,
    FileMetadata,

    # Exceptions
    StorageError,
    UnsupportedOperationError,
    PathNotFoundError,
    AuthenticationError,
)
```
