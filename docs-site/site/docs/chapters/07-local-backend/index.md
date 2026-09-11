---
title: "Chapter 7: Local Backend"
description: "The local filesystem storage backend with full eight-protocol coverage through mixin composition"
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 7: Local Backend

## Summary

This chapter presents the local filesystem storage backend -- the only backend
that implements all eight storage protocols. It introduces the
LocalStorageBackend class and walks through each of its eight composing mixins:
LocalConnectionMixin, LocalReadMixin, LocalWriteMixin, LocalListMixin,
LocalDeleteMixin, LocalMetadataMixin, LocalCopyMixin, and LocalDirectoryMixin.
The chapter concludes by verifying that the composed class satisfies full
protocol coverage.

## Concepts Covered

- LocalStorageBackend Class
- LocalConnectionMixin
- LocalReadMixin
- LocalWriteMixin
- LocalListMixin
- LocalDeleteMixin
- LocalMetadataMixin
- LocalCopyMixin
- LocalDirectoryMixin
- Full Protocol Coverage Local

## Learning Graph IDs

53, 54, 55, 56, 57, 58, 59, 60, 61, 62

## Prerequisites

- Chapter 1: Foundation Concepts (File Systems, Mixin Pattern, Registry Pattern)
- Chapter 2: Storage Protocols (all eight protocols)

---

## The Reference Implementation

The local filesystem backend serves as the library's reference implementation. It is the only backend that implements all eight storage protocols, providing a complete demonstration of how the protocol and mixin patterns work together. When developing or testing new features, the local backend is the first place they are validated because it supports every operation.

Local filesystem storage is also the most commonly used backend during development and testing. Developers prototype pipelines locally before deploying against cloud storage, and test suites use the local backend to verify facade behavior without requiring network access or cloud credentials.

<!-- concept:53 -->
## LocalStorageBackend Class

The `LocalStorageBackend` class is assembled from eight mixins and registered for the `LOCAL` provider type using the `@register_storage_backend` decorator:

```python
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
    """Unified local filesystem storage backend composed from mixins."""

    def __init__(self, auth_params: Any) -> None:
        self.auth_params = auth_params
```

The class body is minimal -- just an `__init__` that stores `auth_params`. All storage logic lives in the mixins. The `auth_params` parameter is accepted for interface consistency with other backends (which need credentials), but for local storage it is typically `None`.

The `@register_storage_backend` decorator places this class in the backend registry under `CONST_STORAGE_PROVIDER_TYPE.LOCAL`. When `StorageFacade(CONST_STORAGE_PROVIDER_TYPE.LOCAL)` or `StorageFacade.for_local()` is called, the registry returns this class for instantiation.

The mixin ordering in the class definition follows Python's Method Resolution Order (MRO) rules. While the local backend has no method name collisions between mixins (each mixin implements methods from a different protocol), the ordering establishes a predictable MRO that tools like `help()` and IDE autocompletion use.

<!-- concept:54 -->
## LocalConnectionMixin

The **`LocalConnectionMixin`** implements `StorageConnectionProtocol` as a no-op:

```python
class LocalConnectionMixin:
    def connect(self) -> None:
        """No-op: local filesystem requires no connection."""

    def disconnect(self) -> None:
        """No-op: local filesystem requires no disconnection."""

    def is_connected(self) -> bool:
        """Always connected for local filesystem."""
        return True
```

The local filesystem is always available (assuming the OS is running), so connection management is meaningless. However, the mixin still implements all three protocol methods to satisfy `StorageConnectionProtocol`. This means the facade's `isinstance` check passes, and calling code can treat local and remote backends uniformly.

The `is_connected` method always returns `True`, which makes the pattern `if facade.supports(StorageConnectionProtocol)` and `backend.is_connected()` work without special-casing local storage.

<!-- concept:55 -->
## LocalReadMixin

The **`LocalReadMixin`** provides file reading via Python's built-in `open()`:

```python
class LocalReadMixin:
    def read_to_bytes(self, path: str) -> bytes:
        with open(path, "rb") as fh:
            return fh.read()

    def read_to_stream(self, path: str) -> BinaryIO:
        return open(path, "rb")
```

The `read_to_bytes` method opens the file, reads its entire contents, and closes the file handle within a `with` block. The `read_to_stream` method opens the file and returns the file handle directly -- the caller is responsible for closing it (typically via a context manager or the facade's `_PairedStream`).

| Method | File Handle | Caller Responsibility |
|---|---|---|
| `read_to_bytes` | Opened and closed internally | None -- data returned as bytes |
| `read_to_stream` | Opened, returned to caller | Must close the stream |

Both methods use binary mode (`"rb"`) because the storage protocols operate exclusively on bytes. Text decoding, if needed, is the caller's responsibility.

<!-- concept:56 -->
## LocalWriteMixin

The **`LocalWriteMixin`** provides file writing with automatic directory creation:

```python
_CHUNK_SIZE = 65_536  # 64 KiB

class LocalWriteMixin:
    def write_from_bytes(self, path: str, data: bytes) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as fh:
            while True:
                chunk = stream.read(_CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
```

Both methods call `os.makedirs(exist_ok=True)` on the parent directory before writing. This convention eliminates the need for callers to manually create directory trees -- a common source of `FileNotFoundError` in raw Python file operations. The `exist_ok=True` flag prevents errors when the directory already exists.

The `write_from_stream` method reads the input stream in 64 KiB chunks rather than calling `stream.read()` (which would load the entire payload into memory). This chunked approach keeps memory usage bounded regardless of file size. The chunk size of 65,536 bytes balances system call overhead against memory consumption.

#### Diagram: Write Method Flow with Auto-Directory Creation

<iframe src="../../sims/local-write-flow/main.html" width="100%" height="400px" scrolling="no"></iframe>
<details markdown="1">
<summary>Write Method Flow with Auto-Directory Creation</summary>
Type: workflow
**sim-id:** local-write-flow<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show the step-by-step flow of both write methods, emphasizing the auto-directory creation step that happens before any file I/O.

**Components:**

- Two parallel swim lanes: write_from_bytes and write_from_stream
- Shared first step: os.makedirs (highlighted as the key safety feature)
- write_from_bytes: single fh.write(data) call
- write_from_stream: loop showing chunk reads (64 KiB) with iteration counter
- Error paths: permission denied, disk full

**Interactions:** Click "write_from_bytes" or "write_from_stream" to highlight that lane. Hover over the chunk loop to see the CHUNK_SIZE constant. Toggle "directory exists" to see the exist_ok=True behavior.

**Learning Objective:** Trace the write flow including automatic directory creation (Bloom: Apply)
</details>

<!-- concept:57 -->
## LocalListMixin

The **`LocalListMixin`** provides directory enumeration using `os.scandir()`:

```python
class LocalListMixin:
    def list_files(self, prefix: str) -> list[FileMetadata]:
        results = []
        if not os.path.isdir(prefix):
            return results
        for entry in os.scandir(prefix):
            if entry.is_file(follow_symlinks=False):
                stat = entry.stat()
                results.append(FileMetadata(
                    filename=entry.name,
                    directory=prefix,
                    full_path=entry.path,
                    size=stat.st_size,
                    source="local",
                ))
        return results

    def list_directories(self, prefix: str) -> list[str]:
        results = []
        if not os.path.isdir(prefix):
            return results
        for entry in os.scandir(prefix):
            if entry.is_dir(follow_symlinks=False):
                results.append(entry.path)
        return results
```

Both methods return empty lists when the prefix is not a valid directory rather than raising an error. This graceful behavior matches the expectation from S3, where listing a non-existent prefix returns an empty result set.

The `list_files` method returns `FileMetadata` instances with `source="local"` and populates the filename, directory, full path, and size. It does not follow symlinks (`follow_symlinks=False`) to avoid infinite loops in directory trees with circular symlinks.

The `list_directories` method returns absolute path strings for subdirectories. Both methods are non-recursive -- they list only the immediate contents of the specified directory, not nested subdirectories.

<!-- concept:58 -->
## LocalDeleteMixin

The **`LocalDeleteMixin`** provides file deletion with existence checking:

```python
class LocalDeleteMixin:
    def delete_file(self, path: str) -> None:
        if not os.path.exists(path):
            raise PathNotFoundError(f"Path not found: {path!r}")
        os.remove(path)
```

Unlike S3's `delete_object` (which silently succeeds even for non-existent keys), the local delete method raises `PathNotFoundError` when the path does not exist. This stricter behavior is appropriate for local filesystems where the caller typically expects the file to be present and wants to know if something went wrong.

The method uses `os.remove()`, which deletes a single file. It does not handle directories -- that responsibility belongs to `LocalDirectoryMixin.rmdir()`.

<!-- concept:59 -->
## LocalMetadataMixin

The **`LocalMetadataMixin`** provides file introspection through `os.stat()` and related functions:

```python
class LocalMetadataMixin:
    def get_metadata(self, path: str) -> FileMetadata:
        stat = os.stat(path)
        return FileMetadata(
            filename=os.path.basename(path),
            directory=os.path.dirname(os.path.abspath(path)),
            full_path=os.path.abspath(path),
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            source="local",
        )

    def path_exists(self, path: str) -> bool:
        return os.path.exists(path)

    def get_size(self, path: str) -> int:
        return os.path.getsize(path)
```

The `get_metadata` method converts the `os.stat` result into a `FileMetadata` Pydantic model. The modification time is converted to a UTC-aware `datetime` object for consistency with cloud backends that always use UTC timestamps. The path is converted to an absolute path using `os.path.abspath()`.

Note that the local backend does not populate the `etag`, `storage_class`, or `checksum` fields -- these are cloud-specific concepts. The `FileMetadata` model provides sensible defaults (empty strings and empty lists) for fields that a particular backend does not populate.

<!-- concept:60 -->
## LocalCopyMixin

The **`LocalCopyMixin`** copies files using `shutil.copy2`:

```python
class LocalCopyMixin:
    def copy(self, source: str, destination: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        shutil.copy2(source, destination)
```

The `shutil.copy2` function preserves file metadata (modification time and permissions) during the copy, unlike `shutil.copy` which only copies the file data. This makes local copies behave like the `cp -p` command.

Like the write mixin, the copy mixin creates destination parent directories automatically. This consistency means callers never need to think about directory creation regardless of the operation.

<!-- concept:61 -->
## LocalDirectoryMixin

The **`LocalDirectoryMixin`** manages directory lifecycle:

```python
class LocalDirectoryMixin:
    def mkdir(self, path: str, parents: bool = True) -> None:
        os.makedirs(path, exist_ok=True) if parents else os.mkdir(path)

    def rmdir(self, path: str) -> None:
        shutil.rmtree(path)
```

The `mkdir` method delegates to `os.makedirs` (with `exist_ok=True`) when `parents=True`, creating the entire directory tree as needed. When `parents=False`, it uses `os.mkdir`, which creates only the leaf directory and raises `FileNotFoundError` if parent directories are missing.

The `rmdir` method uses `shutil.rmtree`, which recursively removes the directory and all its contents. This is a destructive operation with no undo -- callers should use it carefully.

!!! warning "rmdir Deletes Everything"
    `shutil.rmtree()` removes the directory and all files and subdirectories within it, recursively and without confirmation. There is no recycle bin or undo. Use `facade.rmdir()` only when you are certain the entire directory tree should be removed.

<!-- concept:62 -->
## Full Protocol Coverage Local

The composed `LocalStorageBackend` satisfies all eight storage protocols. This can be verified at runtime using `isinstance` checks:

```python
backend = LocalStorageBackend(auth_params=None)

assert isinstance(backend, StorageConnectionProtocol)  # LocalConnectionMixin
assert isinstance(backend, StorageReadProtocol)         # LocalReadMixin
assert isinstance(backend, StorageWriteProtocol)        # LocalWriteMixin
assert isinstance(backend, StorageListProtocol)         # LocalListMixin
assert isinstance(backend, StorageDeleteProtocol)       # LocalDeleteMixin
assert isinstance(backend, StorageMetadataProtocol)     # LocalMetadataMixin
assert isinstance(backend, StorageCopyProtocol)         # LocalCopyMixin
assert isinstance(backend, StorageDirectoryProtocol)    # LocalDirectoryMixin
```

Every `isinstance` check passes because each mixin provides the methods required by its corresponding protocol. The runtime-checkable nature of the protocols makes these checks work without any explicit inheritance from the protocol classes.

#### Diagram: Local Backend Mixin Composition

<iframe src="../../sims/local-mixin-composition/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Local Backend Mixin Composition</summary>
Type: diagram
**sim-id:** local-mixin-composition<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show the eight mixins composing into LocalStorageBackend, with each mixin connected to its corresponding protocol and the stdlib functions it wraps.

**Components:**

- Central node: LocalStorageBackend
- Eight mixin nodes arranged in a ring around the center
- Each mixin connected to: its protocol (left side) and the stdlib functions it uses (right side)
- Protocol nodes: StorageConnectionProtocol through StorageDirectoryProtocol
- Stdlib nodes: open(), os.stat(), os.scandir(), os.remove(), shutil.copy2, shutil.rmtree, os.makedirs
- Color: mixins in lime green, protocols in dark slate blue, stdlib in gray

**Interactions:** Click a mixin to highlight its protocol and stdlib dependencies. Hover over a stdlib function to see all mixins that use it. Click the central node to see the full MRO.

**Learning Objective:** Map the composition from mixins through protocols to underlying stdlib operations (Bloom: Analyze)
</details>

Full protocol coverage means the local backend is the most versatile in the library. Every facade method works against a local backend, making it ideal for:

- **Development**: prototype storage workflows locally before deploying to cloud.
- **Testing**: validate facade behavior without network dependencies.
- **Staging**: use local directories as stand-ins for cloud buckets in CI/CD pipelines.
- **Reference**: understand how a protocol should be implemented by studying the local mixin.

#### Diagram: Protocol-to-Mixin-to-Stdlib Mapping

<iframe src="../../sims/protocol-mixin-stdlib-map/main.html" width="100%" height="400px" scrolling="no"></iframe>
<details markdown="1">
<summary>Protocol-to-Mixin-to-Stdlib Mapping</summary>
Type: chart
**sim-id:** protocol-mixin-stdlib-map<br/>
**Library:** Chart.js<br/>
**Status:** Specified

**Purpose:** Tabular visualization mapping each protocol method to its local mixin implementation and the underlying stdlib call.

**Components:**

- Horizontal grouped bar chart or Sankey diagram
- Left column: Protocol method names (connect, read_to_bytes, write_from_bytes, etc.)
- Middle column: Mixin class names
- Right column: stdlib function calls (open, os.stat, os.scandir, etc.)
- Method count per mixin shown as bar height

**Interactions:** Hover over a bar to see the full method signature. Click a mixin group to filter to its methods only.

**Learning Objective:** Map the three layers of abstraction in the local backend (Bloom: Analyze)
</details>

## Design Patterns in the Local Backend

The local backend demonstrates several consistent design patterns that other backends follow:

- **Auto-directory creation**: write and copy operations create parent directories automatically, eliminating `FileNotFoundError` surprises.
- **Graceful empty results**: list operations return empty lists for invalid prefixes rather than raising exceptions.
- **Strict existence checking**: delete raises `PathNotFoundError` for missing files, providing clear feedback.
- **Binary-only I/O**: all file operations use `"rb"` or `"wb"` mode, delegating text encoding to callers.
- **Chunk-based streaming**: write-from-stream uses 64 KiB chunks rather than loading the entire payload.
- **UTC timestamps**: metadata timestamps are always UTC-aware for consistency with cloud backends.

These patterns establish conventions that the S3 and HTTP backends also follow (where applicable), creating a predictable experience regardless of the underlying storage system.

## Key Takeaways

- **`LocalStorageBackend`** is composed from eight mixins and is the only backend implementing all eight storage protocols.
- **`LocalConnectionMixin`** implements no-op connection management -- the local filesystem is always "connected."
- **`LocalReadMixin`** provides both `read_to_bytes` (self-closing) and `read_to_stream` (caller-closing) using Python's built-in `open()`.
- **`LocalWriteMixin`** automatically creates parent directories before writing and uses 64 KiB chunked streaming for `write_from_stream`.
- **`LocalListMixin`** uses `os.scandir()` for efficient, non-recursive directory enumeration and returns `FileMetadata` objects.
- **`LocalDeleteMixin`** raises `PathNotFoundError` for missing files, unlike S3's silent success behavior.
- **`LocalMetadataMixin`** converts `os.stat()` results into `FileMetadata` with UTC-aware timestamps.
- **`LocalCopyMixin`** uses `shutil.copy2` to preserve metadata and creates destination directories automatically.
- **`LocalDirectoryMixin`** provides `mkdir` (with optional parent creation) and `rmdir` (recursive deletion via `shutil.rmtree`).
- **Full protocol coverage** makes the local backend ideal for development, testing, and as a reference implementation for new backends.
