---
title: "Chapter 5: StorageFacade"
description: "The unified user-facing API that dispatches storage operations through protocol-checked backends"
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 5: StorageFacade

## Summary

This chapter introduces the StorageFacade class -- the unified, user-facing API
through which all storage operations flow. The facade accepts any backend,
detects which protocols it supports via runtime checking, and dispatches method
calls accordingly. Readers learn about protocol-checked dispatch, the
UnsupportedOperationError raised when a backend lacks a capability, and the full
set of facade methods: read bytes, read stream, write bytes, write stream, list
files, delete, exists, get metadata, and copy.

## Concepts Covered

- StorageFacade Class
- Protocol Checked Dispatch
- UnsupportedOperationError
- Read Bytes Method
- Read Stream Method
- Write Bytes Method
- Write Stream Method
- List Files Method
- Delete Method
- Exists Method
- Get Metadata Method
- Copy Method

## Learning Graph IDs

19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30

## Prerequisites

- Chapter 2: Storage Protocols (all eight protocols)
- Chapter 3: Path Handling (Detect Provider From Path)

---

## The Facade Pattern in Storage

The **StorageFacade** is the single class that application code interacts with for all storage operations. Rather than importing backend-specific classes and managing connection logic directly, callers construct a facade and use its uniform method set. The facade hides the complexity of backend selection, protocol checking, and transform pipeline integration behind a clean, predictable API.

The facade design follows the classic Facade pattern: it provides a simplified interface to a complex subsystem. In this case, the subsystem includes the backend registry, eight storage protocols, the path resolution chain, and the transform pipeline. The caller sees only `facade.read(path)`, `facade.write(path, data)`, and similar methods.

<!-- concept:19 -->
## StorageFacade Class

The `StorageFacade` class is constructed with a provider type and optional auth parameters. It looks up the corresponding backend in the registry and holds a reference to the instantiated backend:

```python
class StorageFacade:
    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        auth_params: Any = None,
    ) -> None:
        self._backend = get_storage_backend(provider_type, auth_params)
```

The constructor delegates entirely to `get_storage_backend`, which performs the registry lookup and instantiation. The backend instance is stored privately (`_backend`) because callers should never interact with it directly -- all access flows through the facade's methods.

Two convenience factory methods provide ergonomic construction without requiring callers to know provider types:

```python
# Construct from a provider type explicitly
facade = StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, auth_params=settings)

# Construct for local filesystem (no auth needed)
facade = StorageFacade.for_local()

# Construct by inferring provider from a path's URL scheme
facade = StorageFacade.from_path("s3://bucket/key", auth_params=settings)
```

The `from_path` factory uses the `detect_provider_from_path` function (covered in Chapter 3) to resolve the path's URL scheme to a provider type, then constructs the facade normally. This enables a common pattern where callers pass any path string and the library figures out which backend to use.

#### Diagram: StorageFacade Construction Paths

<iframe src="../../sims/facade-construction-paths/main.html" width="100%" height="400px" scrolling="no"></iframe>
<details markdown="1">
<summary>StorageFacade Construction Paths</summary>
Type: workflow
**sim-id:** facade-construction-paths<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show the three construction paths (direct provider type, for_local, from_path) converging on the same internal backend instantiation.

**Components:**

- Three entry nodes: "StorageFacade(provider_type)", "StorageFacade.for_local()", "StorageFacade.from_path(path)"
- from_path node connects through detect_provider_from_path
- All three converge on get_storage_backend(provider_type, auth_params)
- Output: StorageFacade instance with _backend reference
- Color: entry nodes in different blues, convergence point in green

**Interactions:** Click each entry node to see a code example. Hover over the convergence point to see what get_storage_backend does internally. Click the output to see the facade's available methods.

**Learning Objective:** Understand the three facade construction patterns and their common backend resolution (Bloom: Understand)
</details>

<!-- concept:20 -->
## Protocol Checked Dispatch

The core mechanism that makes the facade safe is **protocol-checked dispatch**. Before delegating any operation to the backend, the facade checks whether the backend implements the required protocol. This check happens through the `_require` helper method:

```python
def _require(self, protocol: type, operation: str) -> None:
    if not isinstance(self._backend, protocol):
        raise UnsupportedOperationError(
            f"{type(self._backend).__name__} does not support '{operation}'"
        )
```

Every public method on the facade calls `_require` as its first action. For example, `read()` calls `self._require(StorageReadProtocol, "read")`, and `delete()` calls `self._require(StorageDeleteProtocol, "delete")`. If the check passes, the method proceeds to delegate to the backend. If it fails, the caller receives a clear error.

The facade also exposes a public `supports` method for proactive capability checking:

```python
if facade.supports(StorageWriteProtocol):
    facade.write(path, data)
else:
    # Handle read-only backend gracefully
    logger.warning("Backend does not support writes")
```

This pattern lets application code make decisions based on backend capabilities without catching exceptions. It is particularly useful when the same code path might run against different backends (e.g., a data pipeline that can write to S3 or read-only from HTTP).

<!-- concept:21 -->
## UnsupportedOperationError

**`UnsupportedOperationError`** is a custom exception (inheriting from `StorageError`) raised when a facade method is called on a backend that does not implement the required protocol. The error message identifies both the backend class name and the operation that was attempted:

```
UnsupportedOperationError: HTTPStorageBackend does not support 'delete'
```

This exception is part of the library's exception hierarchy:

- `StorageError` -- base for all storage exceptions
    - `UnsupportedOperationError` -- backend lacks a protocol
    - `StorageConnectionError` -- connection failure
    - `PathNotFoundError` -- file does not exist
    - `AuthenticationError` -- credential failure
    - `TransformError` -- compression/encryption failure

The hierarchy enables callers to catch specific errors or broad categories depending on their error-handling strategy. Catching `StorageError` handles everything; catching `UnsupportedOperationError` specifically handles only capability mismatches.

<!-- concept:22 -->
## Read Bytes Method

The **`read`** method downloads file contents and returns them as `bytes`. It is the simplest and most commonly used read operation:

```python
data = facade.read("s3://bucket/reports/q1.csv")
```

Behind the scenes, the method performs several steps. It checks that the backend implements `StorageReadProtocol`. It resolves the transform pipeline (either explicitly provided or inferred from the path's suffix chain). It calls `backend.read_to_stream()` to get a source stream, applies the pipeline's `apply_read` method to strip transform layers, reads the resulting stream to completion, and returns the bytes.

The method signature includes optional transform parameters:

```python
def read(
    self,
    path: str,
    *,
    pipeline: Pipeline | StreamTransform | None = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
```

When `infer=True`, the facade inspects the path's suffix chain (e.g., `.gz` or `.gpg`) and automatically constructs the appropriate pipeline. When `pipeline` is provided explicitly, that pipeline is used directly. Providing both `infer=True` and an explicit `pipeline` raises a `ValueError` to prevent ambiguity.

<!-- concept:23 -->
## Read Stream Method

The **`read_stream`** method returns a `BinaryIO` object for lazy consumption instead of buffering the entire file in memory:

```python
stream = facade.read_stream("s3://bucket/large-dataset.csv.gz", infer=True)
try:
    for line in stream:
        process(line)
finally:
    stream.close()
```

The returned stream is a `_PairedStream` instance -- a custom `io.RawIOBase` subclass that wraps both the pipeline-transformed stream and the underlying source stream. When closed, it propagates the close to both, ensuring no file descriptors leak. This is important because the pipeline may create intermediate wrapper streams that each hold resources.

The distinction between `read` (bytes) and `read_stream` (BinaryIO) maps to two use cases. Small files like configuration, metadata, and templates are best read with `read()` for simplicity. Large files like datasets, archives, and media are best read with `read_stream()` to avoid memory pressure.

| Method | Returns | Memory | Best For |
|---|---|---|---|
| `read()` | `bytes` | Entire file in RAM | Small files (< 100 MB) |
| `read_stream()` | `BinaryIO` | Streaming chunks | Large files, transforms |

<!-- concept:24 -->
## Write Bytes Method

The **`write`** method uploads a `bytes` payload to a path, optionally applying a transform pipeline:

```python
facade.write("s3://bucket/reports/q1.csv", csv_bytes)
facade.write("s3://bucket/reports/q1.csv.gz", csv_bytes, pipeline=Gzip())
```

Without a pipeline, the method calls `backend.write_from_bytes(path, data)` directly -- the simplest path. With a pipeline, it wraps the bytes in a `BytesIO` stream, applies `pipeline.apply_write()` to encode (compress, encrypt), and calls `backend.write_from_stream()` with the encoded stream.

The write method does not support `infer=True` for suffix-based pipeline inference. This is intentional -- inferring transforms on write is dangerous because it could silently double-compress data that is already compressed. Write-side transform inference requires explicit opt-in through a future API.

<!-- concept:25 -->
## Write Stream Method

The **`write_stream`** method accepts a `BinaryIO` source and writes its contents to storage:

```python
with open("local-report.csv", "rb") as f:
    facade.write_stream("s3://bucket/reports/q1.csv", f)
```

Like `write`, it supports an optional pipeline parameter for encoding the stream before upload. The method applies `pipeline.apply_write()` to the input stream and passes the result to `backend.write_from_stream()`. The S3 backend's `write_from_stream` uses boto3's `upload_fileobj`, which handles multipart uploads automatically for large streams.

<!-- concept:26 -->
## List Files Method

The **`list_files`** method returns structured metadata for files under a given prefix:

```python
files = facade.list_files("s3://bucket/data/2026/")
for f in files:
    print(f"{f.filename}: {f.size} bytes, modified {f.last_modified}")
```

The return type is `list[FileMetadata]` -- the Pydantic model introduced in Chapter 1. Each entry carries filename, directory, full path, size, and backend-specific fields like etag and storage class. The facade also exposes `list_directories` through the same protocol check.

!!! tip "Prefix vs Directory Semantics"
    On S3, `list_files("s3://bucket/data/")` returns all objects with the `data/` prefix at any depth. On local filesystems, `list_files("/data/")` returns only immediate children (non-recursive). Be aware of this behavioral difference when writing backend-agnostic code.

<!-- concept:27 -->
## Delete Method

The **`delete`** method removes a file at the specified path:

```python
facade.delete("s3://bucket/reports/old-report.csv")
```

The method checks for `StorageDeleteProtocol` support and delegates to `backend.delete_file(path)`. On local filesystems, deleting a non-existent file raises `PathNotFoundError`. On S3, the delete operation succeeds silently even if the key does not exist (S3's native behavior).

<!-- concept:28 -->
## Exists Method

The **`exists`** method checks whether a path exists on the backend:

```python
if facade.exists("s3://bucket/reports/q1.csv"):
    data = facade.read("s3://bucket/reports/q1.csv")
```

This method requires `StorageMetadataProtocol` support and delegates to `backend.path_exists(path)`. The local backend uses `os.path.exists()`. The S3 backend uses `head_object` with a 404-check fallback to `list_objects_v2` for bucket-level paths.

<!-- concept:29 -->
## Get Metadata Method

The **`metadata`** method retrieves full file metadata without reading the file contents:

```python
meta = facade.metadata("s3://bucket/reports/q1.csv")
print(f"Size: {meta.size}, Last modified: {meta.last_modified}")
print(f"ETag: {meta.etag}, Storage class: {meta.storage_class}")
```

The facade also provides `get_size(path)` as a shortcut when only the byte count is needed, avoiding the overhead of constructing a full `FileMetadata` object on backends where size retrieval is cheaper than full metadata.

#### Diagram: Facade Method-to-Protocol Mapping

<iframe src="../../sims/facade-method-protocol-map/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Facade Method-to-Protocol Mapping</summary>
Type: infographic
**sim-id:** facade-method-protocol-map<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show every public facade method connected to the protocol it requires, grouped by operation category.

**Components:**

- Left column: Facade methods grouped by category (Read, Write, List, Delete, Metadata, Copy, Directory)
- Right column: Protocol classes
- Directed edges from each method to its required protocol
- Color coding by category: read=blue, write=green, list=teal, delete=red, metadata=purple, copy=orange, directory=brown
- Backend support indicators on each protocol node

**Interactions:** Click a protocol node to highlight all methods that require it. Click a method to see its signature and a code example. Hover over edges to see the _require() call.

**Learning Objective:** Map facade methods to their protocol requirements (Bloom: Apply)
</details>

<!-- concept:30 -->
## Copy Method

The **`copy`** method duplicates a file from one path to another within the same backend:

```python
facade.copy("s3://bucket/data/v1.csv", "s3://bucket/archive/v1.csv")
```

This delegates to `backend.copy(source, destination)`, which on S3 performs a server-side copy (no data downloads to the client). On local filesystems, it uses `shutil.copy2` to preserve metadata.

For **cross-backend** copies (e.g., S3 to local), the library provides the `copy_between` utility function in `storage_facade/cross_backend.py`. This function accepts two facades and handles the transfer:

```python
from mountainash_utils_files.storage_facade.cross_backend import copy_between

copy_between(
    source_path="s3://bucket/data.csv",
    destination_path="/local/data.csv",
    source_facade=s3_facade,
    destination_facade=local_facade,
)
```

The `copy_between` function attempts an optimized native copy when both facades share the same backend type and no pipelines are specified. Otherwise, it falls back to a stream-through copy: `read_stream` from the source, `write_stream` to the destination. This ensures any backend combination works, at the cost of the data flowing through the client.

#### Diagram: Copy Strategy Decision Tree

<iframe src="../../sims/copy-strategy-decision/main.html" width="100%" height="400px" scrolling="no"></iframe>
<details markdown="1">
<summary>Copy Strategy Decision Tree</summary>
Type: workflow
**sim-id:** copy-strategy-decision<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show the decision logic in copy_between: same-backend native copy vs stream-through copy.

**Components:**

- Decision nodes: "Same backend type?", "Pipelines specified?", "Backend supports StorageCopyProtocol?"
- Leaf nodes: "Native server-side copy (fast)" and "Stream-through copy (universal)"
- Performance indicators: server-side copy shows "0 bytes transferred through client", stream-through shows "full file transferred"

**Interactions:** Click decision nodes to toggle their answers and see the path update. Hover over leaf nodes to see performance characteristics.

**Learning Objective:** Evaluate when native copy vs stream-through copy is used (Bloom: Evaluate)
</details>

## Transform Pipeline Integration

The facade integrates tightly with the transform pipeline system (covered in Chapter 6). The `_resolve_pipeline` internal method handles the decision between explicit and inferred pipelines:

```python
def _resolve_pipeline(self, path, *, pipeline, infer, gpg, gzip) -> Pipeline:
    if infer and pipeline is not None:
        raise ValueError("Cannot pass both infer=True and an explicit pipeline")
    if infer:
        inferred, _ = _infer_pipeline(path, gpg=gpg, gzip=gzip)
        if inferred is not None:
            return inferred
    return self._coerce_pipeline(pipeline)
```

The `_coerce_pipeline` helper normalizes the pipeline argument: `None` becomes an empty `Pipeline()`, a single `StreamTransform` is wrapped in a `Pipeline`, and an existing `Pipeline` is returned as-is. This normalization means every code path can call `pipeline.apply_read()` or `pipeline.apply_write()` without checking for `None`.

## The Top-Level read_bytes Helper

For the most common use case -- "read a file by path, auto-detecting the backend" -- the library provides a module-level `read_bytes` function that combines facade construction with a read operation:

```python
from mountainash_utils_files.storage_facade import read_bytes

data = read_bytes("s3://bucket/report.csv.gz", infer=True)
```

This function constructs a `StorageFacade.from_path()`, calls `facade.read()` with the provided arguments, and returns the bytes. It is a convenience wrapper for scripts and notebooks where constructing a facade explicitly feels like unnecessary ceremony.

## Key Takeaways

- **StorageFacade** is the single user-facing class for all storage operations, constructed from a provider type or inferred from a path's URL scheme.
- **Protocol-checked dispatch** via `_require()` ensures operations fail fast with clear errors when a backend lacks the required capability.
- **`UnsupportedOperationError`** provides explicit, descriptive error messages identifying both the backend class and the unsupported operation.
- The facade offers **bytes and stream variants** for both reads and writes, matching small-file convenience with large-file efficiency.
- **`read`** and **`read_stream`** support both explicit pipeline parameters and suffix-based inference (`infer=True`) for automatic decompression/decryption.
- **`write`** and **`write_stream`** support explicit pipelines but not inference, preventing accidental double-encoding.
- **`list_files`** returns structured `FileMetadata` objects; behavior differs between local (non-recursive) and S3 (prefix scan) backends.
- **`copy`** handles within-backend copies; **`copy_between`** handles cross-backend transfers with automatic fallback from native to stream-through strategy.
- The **`from_path`** factory and **`read_bytes`** helper provide ergonomic one-liner access for common operations.
- All facade methods delegate to backend protocol methods without adding logic beyond dispatch and pipeline integration, keeping the facade thin and predictable.
