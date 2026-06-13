# True Streaming & Backend Coverage Design Spec

> **Date:** 2026-06-11
> **Status:** Draft
> **Packages:** mountainash-utils-files (future: mountainash-transport)
> **Backlog items:** #4 (True Streaming & SDK-Native I/O), #14 (Unimplemented Provider Backends — GCS, Azure, FTP)
> **Prerequisites:** #8 (Provider Registry Honesty) — landed

## Problem

The package advertises "stream-based operations: efficient handling of large
files", and the transforms layer (Gzip, Pipeline) is genuinely lazy. But the
backends underneath materialize almost everything:

| Backend | `read_to_stream` | `write_from_stream` |
|---------|------------------|---------------------|
| **S3**  | ❌ buffers — `read_to_bytes()` then `BytesIO` | ✅ streams via `upload_fileobj` |
| **SFTP** | ❌ buffers — `read_to_bytes()` then `BytesIO` | ❌ buffers — `stream.read()` then `write_from_bytes()` |
| **HTTP** | ❌ buffers — `engine.request()` then `BytesIO` | ❌ buffers — `_resolve_body()` drains stream |
| **Local** | ✅ streams (file handle) | ✅ streams (64 KiB chunks) |

Only 3 of 8 read/write paths actually stream. The fixes are SDK-native — in
several cases the streaming primitive already exists in the codebase and is
simply not called.

Additionally, 3 providers have profiles and specs but no backend: GCS, Azure,
FTP. These should be built streaming-first from day one.

## Scope

### Part A: Streaming fixes for existing backends (backlog #4)

1. S3 `read_to_stream` — return `StreamingBody` via adapter
2. SFTP `read_to_stream` — return paramiko `SFTPFile` with `prefetch()`
3. SFTP `write_from_stream` — use `putfo()`
4. HTTP `read_to_stream` — route through `engine.stream()`
5. HTTP `write_from_stream` — pass stream to httpx, extend retry replayability
6. S3 pagination early-stop
7. S3 `TransferConfig` exposure

### Part B: New backends (backlog #14 — GCS, Azure, FTP)

8. GCS backend (Read, Write, List, Delete, Metadata)
9. Azure Blob backend (Read, Write, List, Delete, Metadata)
10. FTP backend (Read, Write, List, Delete, Metadata)

### Part C: Shared foundation & hygiene

11. Shared `DEFAULT_CHUNK_SIZE` constant
12. Streaming adapters (`StreamingBodyAdapter`, `IterBytesReader`)
13. Remove unused `smart-open` dependency
14. Backlog updates

### Out of scope

- Azure Files (via `SERVICE_TYPE` discriminator — deferred)
- SMB and GitHub backends (remain in backlog #14)
- Async variants (backlog #12 — depends on #2 lifecycle + this work)
- SFTP copy mixin / server-side copy (deferred, documented)
- Seek support on `read_to_stream` (protocol contract is non-seekable)

## Design

### Shared Foundation

#### `DEFAULT_CHUNK_SIZE` (`_core/constants.py`)

```python
DEFAULT_CHUNK_SIZE: int = 65_536  # 64 KiB
```

Three files currently define this independently:
- `storage/backends/local/local_write.py` — `_CHUNK_SIZE = 65_536`
- `_core/transforms/_stream_encoder.py` — `_DEFAULT_CHUNK = 64 * 1024`
- `_core/http/response.py` — `chunk_size: int = 65536` default

All three switch to importing `DEFAULT_CHUNK_SIZE`.

#### Streaming Adapters (`_core/streams.py`)

Two small adapters that bridge SDK stream objects into proper `BinaryIO`:

**`StreamingBodyAdapter(io.RawIOBase)`**

Wraps any object with `read(amt)` and `close()` — like S3's
`botocore.response.StreamingBody` — into a `BinaryIO`-conformant stream.

```python
class StreamingBodyAdapter(io.RawIOBase):
    """Adapts an SDK streaming response to BinaryIO."""

    def __init__(self, body: t.Any) -> None:
        self._body = body

    def readable(self) -> bool:
        return True

    def readinto(self, b: bytearray) -> int:
        data = self._body.read(len(b))
        n = len(data)
        b[:n] = data
        return n

    def close(self) -> None:
        if not self.closed:
            self._body.close()
        super().close()
```

Used by: S3 `read_to_stream`.

**`IterBytesReader(io.RawIOBase)`**

Wraps an `Iterator[bytes]` plus an optional closeable context into a `BinaryIO`.
Pulls from the iterator on demand with internal buffering — never materializes
the full payload.

```python
class IterBytesReader(io.RawIOBase):
    """Adapts an Iterator[bytes] + closeable context to BinaryIO."""

    def __init__(
        self,
        chunks: t.Iterator[bytes],
        context: t.Any = None,
    ) -> None:
        self._chunks = chunks
        self._context = context  # holds httpx stream context or similar
        self._buffer = b""

    def readable(self) -> bool:
        return True

    def readinto(self, b: bytearray) -> int:
        while len(self._buffer) < len(b):
            try:
                self._buffer += next(self._chunks)
            except StopIteration:
                break
        n = min(len(b), len(self._buffer))
        b[:n] = self._buffer[:n]
        self._buffer = self._buffer[n:]
        return n

    def close(self) -> None:
        if not self.closed:
            if hasattr(self._context, "close"):
                self._context.close()
        super().close()
```

Used by: HTTP `read_to_stream`, Azure `read_to_stream`.

### Part A: Streaming Fixes

#### A1. S3 `read_to_stream`

**File:** `storage/backends/s3/s3_read.py`

**Before:** Calls `read_to_bytes()`, wraps result in `io.BytesIO()`.

**After:** Calls `get_object(Bucket=..., Key=...)["Body"]`, wraps the
`StreamingBody` in `StreamingBodyAdapter`, returns it. The `StreamingBody`
already supports `read(amt)` and `close()` — the adapter makes it a proper
`BinaryIO`.

```python
def read_to_stream(self, path: str) -> BinaryIO:
    bucket, key = self._split_path(path)
    response = self._client.get_object(Bucket=bucket, Key=key)
    return StreamingBodyAdapter(response["Body"])
```

#### A2. SFTP `read_to_stream`

**File:** `storage/backends/sftp/sftp_read.py`

**Before:** Calls `read_to_bytes()`, wraps result in `io.BytesIO()`.

**After:** Opens the paramiko `SFTPFile` directly and calls `prefetch()` for
pipelined read-ahead. The paramiko file handle IS the stream — it's already
a file-like object supporting `read(n)` and `close()`.

```python
def read_to_stream(self, path: str) -> BinaryIO:
    fobj = self._sftp_client.open(path, "rb")
    fobj.prefetch()
    return fobj
```

This is the pattern smart_open uses (`ssh.py:304-308`) and what the original
mountainash codebase had (`sftp_file_helper.py` — `getfo` with `prefetch=True`).

#### A3. SFTP `write_from_stream`

**File:** `storage/backends/sftp/sftp_write.py`

**Before:** `stream.read()` to drain entire stream, then `write_from_bytes()`.

**After:** `sftp_client.putfo(stream, path)` — paramiko's native chunked upload.
This is exactly what the original mountainash `_native_put_object_from_stream`
did.

```python
def write_from_stream(self, path: str, stream: BinaryIO) -> None:
    self._sftp_client.putfo(stream, path)
```

#### A4. HTTP `read_to_stream`

**File:** `storage/backends/http/http_read.py`

**Before:** Calls `engine.request("GET", path)`, wraps `response.content` in
`BytesIO`.

**After:** Uses `engine.stream("GET", path)` (already exists, currently unused
by the backend). Returns an `IterBytesReader` wrapping `iter_bytes()`, holding
the stream context open until `close()`.

The key subtlety: `engine.stream()` is a context manager. The `IterBytesReader`
must hold the `__enter__`'d context and call `__exit__` on `close()`. The
adapter's `context` parameter handles this.

```python
def read_to_stream(self, path: str) -> BinaryIO:
    stream_ctx = self._engine.stream("GET", path)
    response = stream_ctx.__enter__()
    return IterBytesReader(
        chunks=response.iter_bytes(DEFAULT_CHUNK_SIZE),
        context=stream_ctx,
    )
```

On `close()`, `IterBytesReader` calls `stream_ctx.close()` which triggers
`__exit__`.

#### A5. HTTP `write_from_stream`

**File:** `_core/http/engine.py` (the `_resolve_body` method)

**Before:** `_resolve_body` drains the stream with `stream.read()`.

**After:** Pass the stream directly to httpx as `content=stream`. httpx accepts
`BinaryIO` for streaming uploads.

**Retry interaction:** A non-seekable stream is not replayable. Extend the
engine's existing body-replayability checks:
- If the stream is seekable: `stream.seek(0)` before retry → retry works.
- If not seekable: single attempt only, no retry for that request.

```python
def _resolve_body(
    self,
    content: bytes | None,
    stream: BinaryIO | None,
) -> bytes | BinaryIO | None:
    if content is not None:
        return content
    if stream is not None:
        return stream  # pass through to httpx
    return None

def _can_retry_body(self, body: bytes | BinaryIO | None) -> bool:
    if body is None or isinstance(body, bytes):
        return True
    if hasattr(body, "seekable") and body.seekable():
        body.seek(0)
        return True
    return False
```

#### A6. S3 Pagination Early-Stop

**File:** `storage/backends/s3/s3_list.py`

**Before:** Fetches all pages from the paginator, then truncates to
`max_results`.

**After:** Pass `PaginationConfig.MaxItems` to the paginator, or break the
loop when accumulated results reach `max_results`.

```python
def list(self, path: str, max_results: int | None = None) -> list[str]:
    bucket, prefix = self._split_path(path)
    paginator = self._client.get_paginator("list_objects_v2")
    config = {"Bucket": bucket, "Prefix": prefix}

    results = []
    for page in paginator.paginate(**config):
        for obj in page.get("Contents", []):
            results.append(obj["Key"])
            if max_results and len(results) >= max_results:
                return results
    return results
```

#### A7. S3 TransferConfig

**File:** `settings/storage/profiles/s3_storage_profile.py`

Add two optional fields to `S3StorageProfile`:

```python
MULTIPART_THRESHOLD: int = 8 * 1024 * 1024    # 8 MB (boto3 default)
MULTIPART_CHUNKSIZE: int = 8 * 1024 * 1024    # 8 MB (boto3 default)
```

These are included in `to_handler_kwargs()` output. The S3 write backend
constructs a `boto3.s3.transfer.TransferConfig` from them:

```python
from boto3.s3.transfer import TransferConfig

config = TransferConfig(
    multipart_threshold=kwargs.get("multipart_threshold", 8 * 1024 * 1024),
    multipart_chunksize=kwargs.get("multipart_chunksize", 8 * 1024 * 1024),
)
self._client.upload_fileobj(stream, bucket, key, Config=config)
```

### Part B: New Backends

#### B1. GCS Backend

**New files:**
- `connections/gcs.py` — `GCSConnection`
- `storage/backends/gcs/__init__.py` — `GCSStorageBackend`
- `storage/backends/gcs/gcs_read.py`
- `storage/backends/gcs/gcs_write.py`
- `storage/backends/gcs/gcs_list.py`
- `storage/backends/gcs/gcs_delete.py`
- `storage/backends/gcs/gcs_metadata.py`

**Connection:**

```python
class GCSConnection:
    def __init__(self, connect_kwargs: dict[str, t.Any], strategy) -> None:
        self._connect_kwargs = connect_kwargs
        self._strategy = strategy
        self._client: google.cloud.storage.Client | None = None

    def connect(self) -> None:
        from google.cloud import storage
        self._client = storage.Client(**self._connect_kwargs)
```

**Streaming patterns:**
- `read_to_stream`: `blob.open('rb')` — SDK returns a streaming file-like
  object. No adapter needed (this is what smart_open's `gcs.py` does).
- `read_to_bytes`: `blob.download_as_bytes()`
- `write_from_stream`: `blob.open('wb')` then chunked copy from input stream
  using `DEFAULT_CHUNK_SIZE`. SDK handles resumable uploads internally.
- `write_from_bytes`: `blob.upload_from_string(data)`
- `list`: `client.list_blobs(bucket, prefix=..., max_results=...)` — SDK
  handles pagination with `max_results`.
- `delete`: `blob.delete()`
- `metadata`: `bucket.get_blob(key)` — returns blob with `size`, `updated`,
  `content_type`.

**Profile update:** Set `implemented=True` on `GCS_SPEC`.

**Auth:** GCS uses `google.auth` default credentials or explicit service
account. The auth strategy passes credentials config through `connect_kwargs`.

**Optional dependency:** `google-cloud-storage` in the `[gcs]` extra (already
declared in `pyproject.toml`).

#### B2. Azure Blob Backend

**New files:**
- `connections/azure.py` — `AzureConnection`
- `storage/backends/azure/__init__.py` — `AzureStorageBackend`
- `storage/backends/azure/azure_read.py`
- `storage/backends/azure/azure_write.py`
- `storage/backends/azure/azure_list.py`
- `storage/backends/azure/azure_delete.py`
- `storage/backends/azure/azure_metadata.py`

**Connection:**

```python
class AzureConnection:
    def __init__(self, connect_kwargs: dict[str, t.Any], strategy) -> None:
        self._connect_kwargs = connect_kwargs
        self._strategy = strategy
        self._client: BlobServiceClient | None = None

    def connect(self) -> None:
        from azure.storage.blob import BlobServiceClient
        conn_str = self._connect_kwargs.get("connection_string")
        if conn_str:
            self._client = BlobServiceClient.from_connection_string(conn_str)
        else:
            self._client = BlobServiceClient(**self._connect_kwargs)
```

**Streaming patterns:**
- `read_to_stream`: `blob_client.download_blob().chunks()` wrapped in
  `IterBytesReader`. The `StorageStreamDownloader` returned by
  `download_blob()` provides a `chunks()` iterator for lazy streaming.
- `read_to_bytes`: `blob_client.download_blob().readall()`
- `write_from_stream`: `blob_client.upload_blob(stream, overwrite=True)` —
  the SDK accepts a stream and handles chunking internally.
- `write_from_bytes`: `blob_client.upload_blob(data, overwrite=True)`
- `list`: `container_client.list_blobs(name_starts_with=prefix)` — SDK
  paginator.
- `delete`: `blob_client.delete_blob()`
- `metadata`: `blob_client.get_blob_properties()` — returns `size`,
  `last_modified`, `content_type`.

**Profile update:** Set `implemented=True` on `AZURE_SPEC`. Only covers
`SERVICE_TYPE="blob"` — Azure Files support is deferred.

**Auth:** Azure uses connection string (via `PasswordAuth` → connection string
in connect_kwargs) or `DefaultAzureCredential` (via `IAMAuth`).

**Optional dependency:** `azure-storage-blob` in the `[azure]` extra (already
declared in `pyproject.toml`).

#### B3. FTP Backend

**New files:**
- `connections/ftp.py` — `FTPConnection`
- `storage/backends/ftp/__init__.py` — `FTPStorageBackend`
- `storage/backends/ftp/ftp_read.py`
- `storage/backends/ftp/ftp_write.py`
- `storage/backends/ftp/ftp_list.py`
- `storage/backends/ftp/ftp_delete.py`
- `storage/backends/ftp/ftp_metadata.py`

**Connection:**

```python
class FTPConnection:
    def __init__(self, connect_kwargs: dict[str, t.Any], strategy) -> None:
        self._connect_kwargs = connect_kwargs
        self._strategy = strategy
        self._client: FTP | FTP_TLS | None = None

    def connect(self) -> None:
        from ftplib import FTP, FTP_TLS
        use_tls = self._connect_kwargs.get("use_tls", False)
        host = self._connect_kwargs["host"]
        port = self._connect_kwargs.get("port", 21)

        if use_tls:
            self._client = FTP_TLS()
        else:
            self._client = FTP()

        self._client.connect(host, port)
        # Auth strategy injects username/password
        self._client.login(
            self._connect_kwargs.get("username", ""),
            self._connect_kwargs.get("password", ""),
        )
        if use_tls:
            self._client.prot_p()
```

**Streaming patterns (from smart_open's `ftp.py`):**
- `read_to_stream`: `ftp.transfercmd("RETR path")` returns a socket →
  `socket.makefile("rb")` gives a file-like object. Patch `close()` to tear
  down socket and call `ftp.voidresp()`. True streaming from the FTP data
  connection.
- `read_to_bytes`: Open stream, `.read()`, close.
- `write_from_stream`: `ftp.storbinary("STOR path", stream)` — FTP's native
  binary upload reads from the stream in chunks (default 8 KiB, configurable
  via `blocksize` parameter).
- `write_from_bytes`: `ftp.storbinary("STOR path", BytesIO(data))`
- `list`: `ftp.mlsd(path)` for machine-readable listings (RFC 3659), fall back
  to `ftp.nlst()` if MLSD isn't supported.
- `delete`: `ftp.delete(path)`
- `metadata`: `ftp.size(path)` for size, `ftp.sendcmd("MDTM path")` for
  modification time.

**FTP read stream close pattern:**

```python
def _make_ftp_read_stream(ftp: FTP, path: str) -> BinaryIO:
    ftp.voidcmd("TYPE I")  # binary mode
    sock = ftp.transfercmd(f"RETR {path}")
    fobj = sock.makefile("rb")

    _orig_close = fobj.close
    def patched_close():
        _orig_close()
        sock.close()
        ftp.voidresp()

    fobj.close = patched_close
    return fobj
```

**Profile update:** Set `implemented=True` on `FTP_SPEC`.

**No optional dependency:** `ftplib` is stdlib.

**Auth:** `PasswordAuth` → username/password injected into connect_kwargs by
the auth resolver. FTP-family dispatch added to `resolve_auth_strategy()`.

### Part C: Hygiene

#### C1. Remove smart-open Dependency

Remove from `pyproject.toml`:
- `"smart-open[ssh]==7.0.4"` from `[sftp]` extras
- `"smart-open[all]==7.0.4"` from `[all]` extras

smart_open was the original streaming layer (used via
`_get_smartopen_stream_generator()` in the old `Base_FileHelper`). The current
architecture replaced it with direct SDK calls but never removed the
dependency declaration.

#### C2. Connection Factory Updates

Add new providers to `_PROVIDER_CONNECTION_MAP` in `connections/__init__.py`:

```python
_PROVIDER_CONNECTION_MAP = {
    "s3": S3Connection,
    "sftp": SSHConnection,
    "http": HTTPConnection,
    "https": HTTPConnection,
    "local": NullConnection,
    "gcs": GCSConnection,
    "azure_blob": AzureConnection,
    "ftp": FTPConnection,
}
```

#### C3. Auth Resolver Updates

Add FTP to the auth resolver dispatch. FTP uses `PasswordAuth` →
username/password in connect_kwargs. No new strategy class needed — the
password is passed directly in connect_kwargs, not via an auth strategy
object. The resolver maps `PasswordAuth` + FTP provider → `NoAuthStrategy`
(credentials are in the connection kwargs, not injected by a strategy).

GCS and Azure auth: For this initial implementation, credentials are passed
through connect_kwargs (service account path for GCS, connection string for
Azure). Full auth strategy integration (IAM, managed identity) is a follow-up.

#### C4. Backlog Updates

- Backlog #4: Mark as **Done**
- Backlog #14: Update to mark GCS, Azure, FTP as done. SMB and GitHub remain
  open.

### Testing Strategy

**Streaming correctness tests:**

A `NoFullReadStream` test stub that raises `AssertionError` if `.read()` is
called without a size argument (or with a size larger than 2× `DEFAULT_CHUNK_SIZE`).
Feed this to `write_from_stream` on each backend; wrap read results in it for
`read_to_stream` consumers. Proves backends consume chunked.

```python
class NoFullReadStream(io.RawIOBase):
    """Test stub that rejects unbounded reads."""
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b: bytearray) -> int:
        if len(b) > 2 * DEFAULT_CHUNK_SIZE:
            raise AssertionError(f"Unbounded read of {len(b)} bytes")
        remaining = self._data[self._pos:self._pos + len(b)]
        n = len(remaining)
        b[:n] = remaining
        self._pos += n
        return n
```

**Per-backend unit tests:**

Each new backend gets tests with mocked SDK clients, following the existing
patterns in `tests/storage/backends/test_s3.py`, `test_sftp.py`, `test_http.py`.

**New test files:**
- `tests/storage/backends/test_gcs.py`
- `tests/storage/backends/test_azure.py`
- `tests/storage/backends/test_ftp.py`
- `tests/_core/test_streams.py` — adapter unit tests
- `tests/storage/backends/test_streaming_correctness.py` — bounded-memory
  assertions across all backends

**Existing tests updated:**
- `tests/storage/protocols/test_backend_conformance.py` — add GCS, Azure, FTP
- `tests/storage/protocols/test_registry_completeness.py` — drift test
  auto-passes when `implemented=True` is set
- S3/SFTP/HTTP backend tests — update to verify streaming behavior

### File Summary

**New files (30):**
```
src/mountainash_transport/_core/streams.py            # StreamingBodyAdapter, IterBytesReader
src/mountainash_transport/connections/gcs.py           # GCSConnection
src/mountainash_transport/connections/azure.py         # AzureConnection
src/mountainash_transport/connections/ftp.py           # FTPConnection
src/mountainash_transport/storage/backends/gcs/__init__.py
src/mountainash_transport/storage/backends/gcs/gcs_read.py
src/mountainash_transport/storage/backends/gcs/gcs_write.py
src/mountainash_transport/storage/backends/gcs/gcs_list.py
src/mountainash_transport/storage/backends/gcs/gcs_delete.py
src/mountainash_transport/storage/backends/gcs/gcs_metadata.py
src/mountainash_transport/storage/backends/azure/__init__.py
src/mountainash_transport/storage/backends/azure/azure_read.py
src/mountainash_transport/storage/backends/azure/azure_write.py
src/mountainash_transport/storage/backends/azure/azure_list.py
src/mountainash_transport/storage/backends/azure/azure_delete.py
src/mountainash_transport/storage/backends/azure/azure_metadata.py
src/mountainash_transport/storage/backends/ftp/__init__.py
src/mountainash_transport/storage/backends/ftp/ftp_read.py
src/mountainash_transport/storage/backends/ftp/ftp_write.py
src/mountainash_transport/storage/backends/ftp/ftp_list.py
src/mountainash_transport/storage/backends/ftp/ftp_delete.py
src/mountainash_transport/storage/backends/ftp/ftp_metadata.py
tests/_core/test_streams.py
tests/storage/backends/test_gcs.py
tests/storage/backends/test_azure.py
tests/storage/backends/test_ftp.py
tests/storage/backends/test_streaming_correctness.py
tests/connections/test_gcs_connection.py
tests/connections/test_azure_connection.py
tests/connections/test_ftp_connection.py
```

**Modified files (15+):**
```
src/mountainash_transport/_core/constants.py           # DEFAULT_CHUNK_SIZE
src/mountainash_transport/storage/backends/s3/s3_read.py
src/mountainash_transport/storage/backends/s3/s3_list.py
src/mountainash_transport/storage/backends/s3/s3_write.py
src/mountainash_transport/storage/backends/sftp/sftp_read.py
src/mountainash_transport/storage/backends/sftp/sftp_write.py
src/mountainash_transport/storage/backends/http/http_read.py
src/mountainash_transport/storage/backends/http/http_write.py
src/mountainash_transport/_core/http/engine.py         # _resolve_body, _can_retry_body
src/mountainash_transport/_core/transforms/_stream_encoder.py  # import DEFAULT_CHUNK_SIZE
src/mountainash_transport/_core/http/response.py       # import DEFAULT_CHUNK_SIZE
src/mountainash_transport/storage/backends/local/local_write.py  # import DEFAULT_CHUNK_SIZE
src/mountainash_transport/settings/storage/profiles/s3_storage_profile.py  # TransferConfig
src/mountainash_transport/settings/storage/profiles/gcs_storage_profile.py  # implemented=True
src/mountainash_transport/settings/storage/profiles/azure_storage_profile.py  # implemented=True
src/mountainash_transport/settings/storage/profiles/ftp_storage_profile.py  # implemented=True
src/mountainash_transport/connections/__init__.py      # factory updates
src/mountainash_transport/_core/auth/resolver.py       # FTP dispatch
src/mountainash_transport/__init__.py                  # exports
pyproject.toml                                         # remove smart-open
```

### Implementation Order

1. Shared chunk constant (`_core/constants.py`, update 3 consumers)
2. Streaming adapters (`_core/streams.py` + tests)
3. S3 streaming fix (`s3_read.py` + test update)
4. SFTP streaming fixes (`sftp_read.py`, `sftp_write.py` + test updates)
5. HTTP streaming fixes (`http_read.py`, `http_write.py`, `engine.py` + tests)
6. S3 hygiene (pagination early-stop, TransferConfig)
7. GCS connection + backend + tests
8. Azure connection + backend + tests
9. FTP connection + backend + tests
10. Remove smart-open dependency
11. Update exports, connection factory, auth resolver
12. Drift test + conformance updates
13. Backlog updates + CLAUDE.md
