---
title: "Chapter 2: Storage Protocols"
description: "Eight fine-grained, runtime-checkable protocols that define the capability contract for storage backends"
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 2: Storage Protocols

## Summary

This chapter defines the eight fine-grained, runtime-checkable protocols that
form the capability contract between the StorageFacade and its backend
implementations. Each protocol -- Connection, Read, Write, List, Delete,
Metadata, Copy, and Directory -- declares a narrow slice of storage
functionality. Backends implement only the protocols they support, and the
facade dispatches accordingly.

## Concepts Covered

- StorageConnectionProtocol
- StorageReadProtocol
- StorageWriteProtocol
- StorageListProtocol
- StorageDeleteProtocol
- StorageMetadataProtocol
- StorageCopyProtocol
- StorageDirectoryProtocol

## Learning Graph IDs

11, 12, 13, 14, 15, 16, 17, 18

## Prerequisites

- Chapter 1: Foundation Concepts (Python Protocols, Runtime Checkable Protocol, Binary Streams)

---

## Why Eight Protocols Instead of One Interface

A monolithic storage interface that declares every possible operation -- read, write, list, delete, copy, metadata, directory management -- forces every backend to implement methods it may not support. An HTTP backend cannot delete remote files. An S3 backend has no concept of creating directories. A read-only archive backend should not expose write methods at all.

The mountainash-transport library avoids this problem by decomposing storage capabilities into eight narrow protocols. Each protocol declares only the methods for one specific capability. A backend implements whichever subset of protocols matches its actual capabilities, and the StorageFacade checks at runtime which protocols a backend satisfies before dispatching a call.

This fine-grained approach delivers three benefits:

- **Type safety**: static type checkers can verify that code expecting a writable backend actually receives one.
- **Explicit capabilities**: calling code can query `facade.supports(StorageWriteProtocol)` to make runtime decisions.
- **Clean errors**: attempting an unsupported operation raises `UnsupportedOperationError` with a clear message rather than producing a confusing `NotImplementedError` or silent failure.

All eight protocols share a common structure: they are decorated with `@runtime_checkable`, import from `typing.Protocol`, and declare methods with `...` (Ellipsis) bodies. The following sections introduce each protocol from simplest to most complex.

<!-- concept:11 -->
## StorageConnectionProtocol

The **StorageConnectionProtocol** manages the lifecycle of a connection to a storage system. Not all backends require connection management -- the local filesystem is always "connected" -- but remote backends (S3, HTTP, SFTP) need to establish and tear down sessions.

The protocol declares three methods that govern connection state:

```python
@runtime_checkable
class StorageConnectionProtocol(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def is_connected(self) -> bool: ...
```

The `connect()` method establishes a session -- for S3, this means creating a boto3 client; for HTTP, instantiating an httpx client. The `disconnect()` method releases that client. The `is_connected()` method returns the current state, allowing callers to avoid redundant connection attempts.

Backends that need no connection management (like the local filesystem) still implement this protocol with no-op methods. `LocalConnectionMixin.connect()` does nothing, `disconnect()` does nothing, and `is_connected()` always returns `True`. This uniform interface means the facade can always call `connect()` without checking what kind of backend it holds.

<!-- concept:12 -->
## StorageReadProtocol

The **StorageReadProtocol** is the most fundamental data-access protocol. Any backend that can retrieve file contents implements this protocol with two methods -- one returning the entire content as bytes, the other returning a binary stream for lazy consumption.

```python
@runtime_checkable
class StorageReadProtocol(Protocol):
    def read_to_bytes(self, path: str) -> bytes: ...
    def read_to_stream(self, path: str) -> BinaryIO: ...
```

The `read_to_bytes` method loads the entire file into memory and returns it as a `bytes` object. This is convenient for small files but dangerous for large ones -- a 2 GB file would consume 2 GB of RAM.

The `read_to_stream` method returns a `BinaryIO` object (a binary stream) that the caller can read incrementally. For the local backend, this is simply `open(path, "rb")`. For S3, the current implementation downloads the entire object into a `BytesIO` buffer (a known limitation for very large objects). For HTTP, the response body is buffered into `BytesIO` after download.

The distinction between bytes and stream methods exists because different use cases have different needs. Configuration files and small JSON documents are best read as bytes. Large data files, compressed archives, and streaming transforms benefit from the stream interface.

#### Diagram: Read Protocol Data Flow

<iframe src="../../sims/read-protocol-flow/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Read Protocol Data Flow</summary>
Type: workflow
**sim-id:** read-protocol-flow<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Compare the data flow paths for read_to_bytes vs read_to_stream across local, S3, and HTTP backends.

**Components:**

- Three swim lanes (Local, S3, HTTP)
- Two paths per lane: bytes path (full load) and stream path (lazy)
- Nodes showing intermediate buffers: open(), BytesIO, boto3 response body
- Memory usage indicators at each stage

**Interactions:** Click a backend lane to highlight its data flow. Hover over buffer nodes to see memory implications. Toggle between "small file" and "large file" modes to see when each path is preferred.

**Learning Objective:** Evaluate when to use bytes vs stream reads based on file size and backend (Bloom: Evaluate)
</details>

<!-- concept:13 -->
## StorageWriteProtocol

The **StorageWriteProtocol** mirrors the read protocol for output operations. It declares two methods -- one accepting bytes, the other accepting a stream:

```python
@runtime_checkable
class StorageWriteProtocol(Protocol):
    def write_from_bytes(self, path: str, data: bytes) -> None: ...
    def write_from_stream(self, path: str, stream: BinaryIO) -> None: ...
```

The `write_from_bytes` method writes a complete `bytes` payload to the specified path. For local files, this opens the file in binary-write mode and writes the data. For S3, it calls `put_object` with the bytes as the request body.

The `write_from_stream` method accepts a `BinaryIO` and writes its contents to storage. The local backend reads the stream in 64 KiB chunks to avoid loading the entire payload into memory. The S3 backend uses boto3's `upload_fileobj`, which automatically handles multipart uploads for large streams.

Both write methods in the local backend create parent directories automatically using `os.makedirs(exist_ok=True)`. This convention means callers never need to manually ensure directory structures exist before writing -- a significant ergonomic improvement over raw filesystem operations.

<!-- concept:14 -->
## StorageListProtocol

The **StorageListProtocol** provides directory enumeration capabilities. It returns structured metadata about files and discovers subdirectories within a given prefix:

```python
@runtime_checkable
class StorageListProtocol(Protocol):
    def list_files(self, prefix: str) -> list[FileMetadata]: ...
    def list_directories(self, prefix: str) -> list[str]: ...
```

The `list_files` method returns a list of `FileMetadata` Pydantic models (not plain strings) for every file found under the specified prefix. Each `FileMetadata` instance carries the filename, directory, full path, size, and optional fields like `last_modified`, `etag`, and `storage_class`. Returning structured metadata rather than bare filenames saves callers from making follow-up metadata calls.

The `list_directories` method returns path strings for subdirectories. On local filesystems, these are absolute paths from `os.scandir()`. On S3, they are "common prefixes" returned by the `list_objects_v2` API with a `/` delimiter -- the S3-native mechanism for simulating directory listing in a flat keyspace.

| Method | Local Implementation | S3 Implementation |
|---|---|---|
| `list_files` | `os.scandir` + `entry.stat()` | `list_objects_v2` paginator |
| `list_directories` | `os.scandir` filtering dirs | `list_objects_v2` with `Delimiter="/"` |

Both methods are non-recursive in the local backend (only immediate contents). The S3 `list_files` implementation omits the delimiter, returning all objects under the prefix regardless of depth -- this difference reflects the flat-namespace nature of object storage.

<!-- concept:15 -->
## StorageDeleteProtocol

The **StorageDeleteProtocol** is the simplest data-mutation protocol, declaring a single method:

```python
@runtime_checkable
class StorageDeleteProtocol(Protocol):
    def delete_file(self, path: str) -> None: ...
```

The local backend raises `PathNotFoundError` (a library-specific exception inheriting from `StorageError`) when the path does not exist. This behavior differs from S3's `delete_object` API, which returns a 204 success response even when the key does not exist -- a quirk of S3's eventual-consistency model.

The protocol deliberately does not include a `delete_directory` method. Directory deletion is handled separately by the `StorageDirectoryProtocol` because it involves recursive removal semantics that not all backends support (S3 has no directories to delete; you simply delete all objects with a shared prefix).

<!-- concept:16 -->
## StorageMetadataProtocol

The **StorageMetadataProtocol** provides introspection into file state without reading file contents. It declares three methods that progressively reveal more information:

```python
@runtime_checkable
class StorageMetadataProtocol(Protocol):
    def get_metadata(self, path: str) -> FileMetadata: ...
    def path_exists(self, path: str) -> bool: ...
    def get_size(self, path: str) -> int: ...
```

The `path_exists` method is a lightweight existence check. On local filesystems, it wraps `os.path.exists()`. On S3, it issues a `head_object` call and interprets a 404 response as non-existence, with a fallback to `list_objects_v2` for bucket-level checks.

The `get_size` method returns the file size in bytes -- `os.path.getsize()` locally, or the `ContentLength` header from S3's `head_object` response.

The `get_metadata` method returns a full `FileMetadata` instance populated with all available information. For local files, this includes the modification time from `os.stat()`. For S3 objects, it includes the ETag, storage class, and last-modified timestamp from the `head_object` response.

#### Diagram: Metadata Protocol Implementation Comparison

<iframe src="../../sims/metadata-protocol-comparison/main.html" width="100%" height="400px" scrolling="no"></iframe>
<details markdown="1">
<summary>Metadata Protocol Implementation Comparison</summary>
Type: chart
**sim-id:** metadata-protocol-comparison<br/>
**Library:** Chart.js<br/>
**Status:** Specified

**Purpose:** Compare which FileMetadata fields are populated by each backend (local, S3, HTTP) and from which underlying API calls.

**Components:**

- Grouped bar chart or matrix heatmap
- X-axis: FileMetadata fields (filename, directory, full_path, size, last_modified, etag, storage_class, checksum, source)
- Y-axis or groups: Backends (Local, S3, HTTP)
- Color intensity indicates whether the field is always populated, sometimes populated, or never populated

**Interactions:** Hover over a cell to see the exact API call that provides the data (e.g., "os.stat().st_mtime" for local last_modified). Click a backend row to see only its populated fields.

**Learning Objective:** Compare metadata availability across backends (Bloom: Analyze)
</details>

<!-- concept:17 -->
## StorageCopyProtocol

The **StorageCopyProtocol** declares a single method for duplicating files within a storage system:

```python
@runtime_checkable
class StorageCopyProtocol(Protocol):
    def copy(self, source: str, destination: str) -> None: ...
```

The critical design decision here is that `copy` operates *within a single backend*. Copying from S3 to the local filesystem is a *cross-backend transfer*, which is handled by the facade's `copy_between` utility function (covered in Chapter 5) rather than by this protocol.

For the local backend, `copy` uses `shutil.copy2`, which preserves metadata (timestamps and permissions). For S3, it uses `copy_object` -- a server-side copy that never downloads the data to the client, making it extremely efficient for moving objects between keys or buckets within the same region.

The local backend creates destination parent directories automatically before copying, maintaining the library's convention of eliminating manual directory management.

<!-- concept:18 -->
## StorageDirectoryProtocol

The **StorageDirectoryProtocol** manages directory lifecycle operations:

```python
@runtime_checkable
class StorageDirectoryProtocol(Protocol):
    def mkdir(self, path: str, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...
```

The `mkdir` method creates a directory, with the `parents` parameter controlling whether intermediate directories are created (defaulting to `True` for convenience). The local backend delegates to `os.makedirs(exist_ok=True)` when `parents=True` and plain `os.mkdir()` otherwise.

The `rmdir` method removes a directory and all its contents. The local backend uses `shutil.rmtree()` for recursive deletion -- a powerful but dangerous operation that callers should use carefully.

This is the only protocol that the S3 backend does **not** implement. Object storage has no directory concept; there is nothing to create or remove. The facade's protocol-checked dispatch means that calling `facade.mkdir()` on an S3-backed facade raises `UnsupportedOperationError` -- a clear signal that the operation makes no sense for this storage type.

## Protocol Composition in Practice

The power of fine-grained protocols becomes apparent when you examine how different backends compose them. The following table shows which protocols each backend implements:

| Protocol | Local | S3 | HTTP |
|---|---|---|---|
| StorageConnectionProtocol | Yes (no-op) | Yes | Yes |
| StorageReadProtocol | Yes | Yes | Yes |
| StorageWriteProtocol | Yes | Yes | Yes |
| StorageListProtocol | Yes | Yes | No |
| StorageDeleteProtocol | Yes | Yes | No |
| StorageMetadataProtocol | Yes | Yes | Yes |
| StorageCopyProtocol | Yes | Yes | No |
| StorageDirectoryProtocol | Yes | No | No |

The local backend is the only one that implements all eight protocols -- it is the most capable storage system because local filesystems support every operation. The S3 backend implements seven (everything except directory management). The HTTP backend implements only four: connection, read, write, and metadata.

#### Diagram: Protocol Coverage Matrix

<iframe src="../../sims/protocol-coverage-matrix/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Protocol Coverage Matrix</summary>
Type: infographic
**sim-id:** protocol-coverage-matrix<br/>
**Library:** p5.js<br/>
**Status:** Specified

**Purpose:** Interactive matrix showing which protocols each backend implements, with visual indicators of capability level.

**Components:**

- Grid with backends as columns and protocols as rows
- Filled circles for implemented protocols, empty circles for unimplemented
- Color coding: green = full implementation, yellow = partial/limited, red = not implemented
- Summary row showing total protocol count per backend

**Interactions:** Click a protocol row to see the method signatures it requires. Click a backend column to see its full mixin composition. Hover over intersections to see implementation details (e.g., "S3DeleteMixin wraps delete_object").

**Learning Objective:** Evaluate backend capabilities against protocol requirements (Bloom: Evaluate)
</details>

## The Dependency Structure

Each protocol depends on foundational concepts from Chapter 1. All eight protocols depend on `Python Protocols` (they are protocol classes) and `Runtime Checkable Protocol` (they are all decorated with `@runtime_checkable`). The read and write protocols additionally depend on `Binary Streams` because their method signatures reference `BinaryIO`.

The protocols do not depend on each other -- they are independently implementable. A backend can implement `StorageReadProtocol` without implementing `StorageWriteProtocol`, or implement `StorageDeleteProtocol` without implementing `StorageListProtocol`. This independence is by design: it prevents artificial coupling between capabilities that are logically separate.

However, in practice, certain combinations are more useful than others. A backend that implements only `StorageDeleteProtocol` without `StorageMetadataProtocol` would be odd -- you typically want to check if a file exists before deleting it. The protocol system does not enforce these practical dependencies; that responsibility falls to backend authors who choose sensible capability sets.

#### Diagram: Protocol Dependency Graph

<iframe src="../../sims/protocol-dependency-graph/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Protocol Dependency Graph</summary>
Type: graph-model
**sim-id:** protocol-dependency-graph<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show the dependency edges from Chapter 1 foundation concepts into the eight protocols, and forward edges into Chapter 5 (StorageFacade) which consumes all protocols.

**Components:**

- Foundation layer (top): Python Protocols, Runtime Checkable Protocol, Binary Streams nodes
- Protocol layer (middle): 8 protocol nodes arranged horizontally
- Consumer layer (bottom): StorageFacade node
- Directed edges from foundations to protocols, and from all protocols to facade
- Color: foundation nodes in steel blue, protocol nodes in dark slate blue, facade in dark green

**Interactions:** Drag to rearrange. Click a protocol node to highlight its specific dependencies. Hover over edges to see what the dependency provides (e.g., "BinaryIO type used in method signature").

**Learning Objective:** Understand the layered dependency structure of the protocol system (Bloom: Understand)
</details>

## Design Rationale

The protocol decomposition in mountainash-transport follows the **Interface Segregation Principle** from SOLID design -- clients should not be forced to depend on interfaces they do not use. By splitting storage capabilities into eight protocols rather than one monolithic interface, the library achieves:

- **Minimal coupling**: code that only reads does not carry a compile-time or conceptual dependency on write methods.
- **Clear documentation**: each protocol's docstring and type signature fully describe one capability in isolation.
- **Gradual adoption**: new backends can start with just `StorageReadProtocol` and add capabilities over time without breaking existing callers.
- **Testability**: mock objects for testing can implement exactly the protocols the test exercises, making test setup explicit about which capabilities are under scrutiny.

The choice to use structural protocols (PEP 544) rather than abstract base classes means that backends from external packages work without importing or inheriting from mountainash-transport. Any class with the right method signatures satisfies the protocol -- maximum decoupling through duck typing with compile-time verification.

## Key Takeaways

- The library defines **eight independent protocols**, each representing one storage capability: connection, read, write, list, delete, metadata, copy, and directory management.
- All protocols are **`@runtime_checkable`**, enabling the StorageFacade to perform `isinstance` checks before dispatching operations.
- **StorageReadProtocol** and **StorageWriteProtocol** each offer both bytes and stream variants, supporting both convenience (small files) and efficiency (large files).
- **StorageListProtocol** returns structured `FileMetadata` objects rather than bare filenames, eliminating follow-up metadata calls.
- **StorageDeleteProtocol** is deliberately separate from **StorageDirectoryProtocol** because directory semantics differ fundamentally between file systems and object stores.
- **StorageCopyProtocol** handles within-backend copies only; cross-backend transfers use a separate utility function.
- The **local backend** is the only one implementing all eight protocols; S3 omits directories, and HTTP implements only four.
- This fine-grained decomposition follows the Interface Segregation Principle, enabling backends to declare exactly which capabilities they support without implementing unused methods.
