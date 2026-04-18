# Stream Transforms — Restoring Compression & Encryption

**Date:** 2026-04-17
**Status:** Approved
**Approach:** Facade-level stream decorators (Approach B from brainstorm)
**Reference architecture:** 2026-04-03 protocol-driven architecture design (Sections 5 and 8.4)

---

## 1. Problem Statement

The 2026-04-03 protocol-driven refactor deleted the old `Base_FileHelper` and, with it, three capability groups that were never rebuilt:

- **Compression** — `gzip`-based byte and stream helpers (`compress_data`, `compress_stream`, `decompress_*`).
- **Encryption** — GPG-based byte and stream helpers (`encrypt_data`, `encrypt_stream`, `decrypt_*`).
- **Composite stream operations** — cross-backend `put_object_from_stream` / `get_object_to_stream` accepting `encrypt=/compress=` flags applied inline.

The 2026-04-03 spec's §5.1 listed `StorageCompressionProtocol` and `StorageEncryptionProtocol`, and §8.4 committed to building compression/encryption as "composable at facade level — stream decorators." Neither protocol nor the decorator layer were implemented. The `storage_transforms/` subpackage does not exist. Nothing in the runtime code imports `gzip`, `python-gnupg`, or `mountainash-utils-gpg`.

This spec restores those capabilities using facade-level stream decorators, as the prior spec intended.

## 2. Goals

1. Restore gzip compression and GPG encryption as streaming transforms that work on both read and write paths.
2. Make transforms composable (gzip + GPG together, in either order) without combinatorial API growth.
3. Keep backends unaware of transforms — pure facade-layer composition above `StorageReadProtocol` / `StorageWriteProtocol`.
4. Avoid the old footgun of 48 boolean `supports_*` flags: capability = transform class exists; ordering = a single `Pipeline` object.
5. Ensure the design extends naturally to additional transforms (zstd, age, chunked hashing, …) without reworking the API.

## 3. Non-Goals

- Restoring additional transforms beyond gzip and GPG (parity only).
- Text-mode stream helpers (`open_read_textstream`) — callers use `io.TextIOWrapper` directly.
- Server-side encryption (S3 SSE-KMS, Azure encryption scopes, GCS CSEK) — those belong in backend settings if/when added.
- New storage backends (gcs/azure/sftp/ssh/ftp/smb/github) — tracked separately.
- Reviving `mountainash-utils-gpg` as a dependency — confirmed orphaned, no consumers. `GPG` transform depends on `python-gnupg` directly.
- Length-known upload paths (`ContentLength`-required PUT) — superseded by mandatory streaming upload APIs on backends (§7).

## 4. Architecture Overview

Four layers, strict dependency direction:

```
Transforms → Pipeline → Facade → Backends
    ↑           ↑          ↑        ↑
    |           |          |        |
  (stdlib +  (imports   (imports  (unchanged —
   gnupg)    transforms) pipeline)  transforms invisible
                                    to backends)
```

- **Transforms** — single-responsibility stream encoders/decoders (`Gzip`, `GPG`). Implement `StreamTransform` protocol.
- **Pipeline** — ordered stack of transforms. Direction-agnostic at call time; the facade decides read-vs-write direction.
- **Facade** — `StorageFacade` gains an optional `pipeline=` keyword-only argument on read/write operations. Delegates transform wrapping before/after calling the backend.
- **Backends** — no changes beyond the write-API audit in §7.2. Backends never see a transform.

## 5. Transform Layer

### 5.1 Protocol

```python
# storage_transforms/base.py
from typing import BinaryIO, Protocol, runtime_checkable

@runtime_checkable
class StreamTransform(Protocol):
    """A reversible encoder/decoder operating on binary streams.

    Both methods take a readable binary stream and return a new readable
    binary stream. The returned stream yields encoded bytes on wrap() and
    decoded bytes on unwrap(). Both methods must stream lazily — no
    eager draining of the input.
    """

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        """Encode: plaintext → encoded (add a layer, for writing outward)."""
        ...

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Decode: encoded → plaintext (strip a layer, for reading inward)."""
        ...
```

### 5.2 Design decisions

- **One class per scheme.** `Gzip` handles both compression and decompression; `GPG` handles both encryption and decryption. The direction is chosen by which method the Pipeline calls. Avoids the `Gzip`/`Gunzip` class-pair duplication and makes the Pipeline's "layer stack" model cleaner.
- **Config on the instance.** Compression level, GPG recipients, gnupghome, etc. are constructor arguments. Captured at construction, treated as immutable.
- **Lazy streaming.** `wrap`/`unwrap` must not drain the input eagerly. The returned stream encodes/decodes incrementally on each `.read()`. This is non-negotiable — eager materialization would break large-file use cases.
- **Reusable instances.** Each call to `wrap`/`unwrap` returns an independent fresh stream wrapper. Transforms are safe to construct once and reuse across many calls, sequentially.
- **Not thread-safe per-instance.** Concurrent `wrap`/`unwrap` from multiple threads on the same transform instance is not supported. Construct per-thread if needed.

## 6. Pipeline

### 6.1 Definition

```python
# storage_transforms/pipeline.py

class Pipeline:
    """Ordered stack of transforms representing the layering on disk.

    Transforms are listed OUTERMOST-FIRST — the order a reader would
    peel them off. For a file stored as gzip-of(gpg-of(plaintext)):

        Pipeline(Gzip(), GPG(recipients=["alice"]))
                 ^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^^^
               outer     inner (closest to plaintext)

    One pipeline is used on both read and write paths. The facade applies
    transforms in the correct direction automatically:
        - read:  outer → inner (unwrap in list order)
        - write: inner → outer (wrap in reverse list order)
    """

    def __init__(self, *transforms: StreamTransform) -> None:
        self._outer_to_inner = transforms

    def apply_read(self, stream: BinaryIO) -> BinaryIO:
        for t in self._outer_to_inner:
            stream = t.unwrap(stream)
        return stream

    def apply_write(self, stream: BinaryIO) -> BinaryIO:
        for t in reversed(self._outer_to_inner):
            stream = t.wrap(stream)
        return stream
```

### 6.2 Ordering convention

The `Pipeline(outer, ..., inner)` order mirrors file-extension order: the last-applied layer is the outermost.

| On-disk shape | Pipeline |
|---|---|
| Plaintext | `None` |
| `file.gz` — gzipped plaintext | `Pipeline(Gzip())` |
| `file.gpg` — GPG-encrypted plaintext | `Pipeline(GPG(...))` |
| `file.gpg.gz` — gzip of GPG-encrypted plaintext | `Pipeline(Gzip(), GPG(...))` |
| `file.gz.gpg` — GPG of gzipped plaintext | `Pipeline(GPG(...), Gzip())` |

### 6.3 Why one object, not two lists

A previous iteration of this design had `through=[...]` kwargs on read and write, with inverse list ordering between the two. That is a footgun: one caller mistake per round-trip. `Pipeline` fixes this by picking a single canonical direction (outermost-first) and having the facade handle direction at dispatch time. The same `Pipeline` instance is passed to both `read` and `write` calls. Round-trips are symmetric at the call site.

## 7. Facade Integration

### 7.1 Signatures

All signatures gain one keyword-only argument. Default `None` preserves today's behavior exactly.

```python
StorageFacade.read(
    self,
    path: str,
    *,
    pipeline: Pipeline | StreamTransform | None = None,
) -> bytes

StorageFacade.read_stream(
    self,
    path: str,
    *,
    pipeline: Pipeline | StreamTransform | None = None,
) -> BinaryIO

StorageFacade.write(
    self,
    path: str,
    data: bytes,
    *,
    pipeline: Pipeline | StreamTransform | None = None,
) -> None

StorageFacade.write_stream(
    self,
    path: str,
    stream: BinaryIO,
    *,
    pipeline: Pipeline | StreamTransform | None = None,
) -> None
```

A bare `StreamTransform` is accepted as sugar for `Pipeline(transform)` — e.g. `facade.read(path, pipeline=Gzip())`.

### 7.2 Backend write-path contract

Backends must use streaming upload APIs so that writes never require a known `ContentLength`:

| Backend | Required API |
|---|---|
| Local | `shutil.copyfileobj` or equivalent incremental write |
| S3 (boto3) | `client.upload_fileobj(stream, Bucket, Key)` — auto-multiparts; **not** `put_object(Body=..., ContentLength=N)` |
| GCS | `blob.upload_from_file(stream)` |
| Azure Blob | `container_client.upload_blob(data=stream)` |
| SFTP | `sftp.putfo(stream, remote_path)` |
| FTP | `ftp.storbinary("STOR ...", stream)` |
| SMB | streaming write |

This contract is a prerequisite of the design: transforms change length in ways that can't be pre-computed without draining the stream, so the write path must tolerate unknown length. An audit of `storage_backends/s3/s3_write.py` to verify `upload_fileobj` usage is step 1 of the implementation plan.

### 7.3 Cross-backend copy

```python
def copy_between(
    source_path: str,
    destination_path: str,
    source_auth: Any,
    destination_auth: Any,
    *,
    source_pipeline: Pipeline | StreamTransform | None = None,
    destination_pipeline: Pipeline | StreamTransform | None = None,
) -> None
```

Separate source and destination pipelines, because source-format and destination-format are often asymmetric (e.g. decrypt at source, re-encrypt at destination under different recipients). Both default to `None` — pass `None` for both for a pure byte-for-byte copy.

**Native same-backend copy fast-path** (existing `StorageCopyProtocol`) is taken only when *both* pipelines are `None`. Any transform forces a stream-through copy because the SDK-level native copy operation (e.g. S3 `CopyObject`) doesn't know about client-side transforms.

### 7.4 Protocol checks

No new protocols at the backend layer. `read`/`read_stream` still require `StorageReadProtocol`; `write`/`write_stream` still require `StorageWriteProtocol`. Transforms operate above the backend layer, so no `supports(StorageCompressionProtocol)` check is needed.

## 8. Built-in Transforms

### 8.1 Gzip

```python
# storage_transforms/compression.py

class Gzip:
    """Gzip compression / decompression transform.

    Uses stdlib gzip/zlib — no external dependency. Lazy streaming.
    """
    def __init__(self, level: int = 6, mtime: int | None = 0) -> None: ...
    def wrap(self, stream: BinaryIO) -> BinaryIO: ...    # plaintext → gzip
    def unwrap(self, stream: BinaryIO) -> BinaryIO: ...  # gzip → plaintext
```

- `level=6` — stdlib default. Previous `Base_FileHelper` used `9`, but that was not measured. Stay with the default unless benchmarks show otherwise.
- `mtime=0` — fixed so identical input always yields byte-identical output. Pass `mtime=None` for stdlib's default (current time). Reproducible output is useful for content-addressed storage, test fixtures, and diff-friendly backups.

### 8.2 GPG

```python
# storage_transforms/encryption.py

class GPG:
    """GPG encryption / decryption transform.

    Requires the [encryption] optional dependency (python-gnupg).
    """
    def __init__(
        self,
        recipients: list[str] | None = None,  # required for wrap() only
        gnupghome: str | None = None,
        key_file: str | None = None,          # auto-imported on first use
        passphrase: str | None = None,        # for unwrap() if key requires
        armor: bool = False,                  # default binary output
        always_trust: bool = False,
    ) -> None: ...
    def wrap(self, stream: BinaryIO) -> BinaryIO: ...    # plaintext → ciphertext
    def unwrap(self, stream: BinaryIO) -> BinaryIO: ...  # ciphertext → plaintext
```

- **Keyring warm-up is lazy and cached.** The first call to `wrap`/`unwrap` opens the keyring and (if `key_file` is set) imports it. Subsequent calls on the same instance reuse the loaded keyring.
- **`recipients` is required for `wrap()`**, not for `unwrap()`. Calling `GPG().wrap(...)` with no recipients raises `TransformError` at wrap time with a clear message.
- **No config is pulled from env/globals.** All configuration is explicit constructor args. Callers wire up their own secret management.

### 8.3 Dependency strategy

- `Gzip` — stdlib only, no extra dependency.
- `GPG` — depends on `python-gnupg` via an optional extra:

```toml
[project.optional-dependencies]
encryption = ["python-gnupg>=0.5.2"]
```

`python-gnupg` is imported lazily inside `encryption.py` so that `from mountainash_utils_files import GPG` works without the extra installed — construction or first `wrap`/`unwrap` raises `ImportError` with the install hint if the extra is missing.

The existing `[encryption]` entry in `pyproject.toml` currently lists both `gnupg==2.3.1` (a separate, unrelated package) and `python-gnupg==0.5.2`. The `gnupg` entry is incorrect and should be removed; only `python-gnupg` is needed.

### 8.4 Implementation notes (non-API)

These are implementation concerns, included here so implementers have the plan; they are not part of the public contract.

- **Gzip `wrap` (compress while being read)** cannot use stdlib `gzip.GzipFile(mode='wb')` directly — that API expects a writable sink. Implementation uses `zlib.compressobj()` inside a `BinaryIO`-compatible reader adapter (`_stream_encoder.py`) that pulls from the source and yields compressed chunks on each `read()`.
- **Gzip `unwrap`** uses stdlib `gzip.GzipFile(mode='rb', fileobj=inner)` directly.
- **GPG `wrap` and `unwrap`** bridge python-gnupg's "take `data`, write to `output`" API to our "wrap readable, return readable" contract via a background thread: the thread pumps source bytes into gpg's stdin, and our returned stream reads gpg's stdout. Errors on the background side surface on the next `.read()` of the returned stream as `TransformError`.
- **No server-side encryption.** SSE-KMS, CSEK, Azure encryption scopes are backend-settings-layer concerns, not transforms.

## 9. Write-Path Length Handling

### 9.1 Rule

Backends never require a known length (§7.2). Transforms therefore never have to predict or surface length. `Pipeline.apply_write(source) -> BinaryIO` is a pure readable; the backend drains it to EOF.

### 9.2 Opt-in length utility

For the occasional caller that *wants* a length (progress bars, quota pre-checks, content-addressed storage):

```python
# storage_transforms/util.py

def materialize(
    stream: BinaryIO,
    *,
    to: Literal["memory", "tempfile"] = "memory",
    memory_cutoff: int = 64 * 1024 * 1024,  # 64 MiB
) -> tuple[BinaryIO, int]:
    """Drain stream into a seekable buffer; return (buffer, length).

    - to="memory": io.BytesIO. RAM-bounded; use for known-small streams.
    - to="tempfile": tempfile.SpooledTemporaryFile that rolls to disk
      past memory_cutoff. Safe for arbitrarily large streams.

    After return, the original stream is exhausted. The returned buffer
    is positioned at 0 and is seekable.
    """
```

This is deliberately **not** a transform — it's a buffering utility, not a layer. It lives in `util.py`, not in the pipeline API.

## 10. Package Layout & Public API

### 10.1 New subpackage

```
src/mountainash_utils_files/
└── storage_transforms/
    ├── __init__.py          # Re-exports Pipeline, Gzip, GPG, StreamTransform
    ├── base.py              # StreamTransform protocol
    ├── pipeline.py          # Pipeline
    ├── compression.py       # Gzip
    ├── encryption.py        # GPG (lazy-imports python-gnupg)
    ├── _stream_encoder.py   # Internal: zlib chunked encoder, gpg subprocess bridge
    └── util.py              # materialize()
```

### 10.2 Top-level exports

```python
# src/mountainash_utils_files/__init__.py — additions
from mountainash_utils_files.storage_transforms import (
    Pipeline,
    StreamTransform,
    Gzip,
    GPG,
)
from mountainash_utils_files.exceptions import TransformError
```

`materialize` stays one level deeper (`from mountainash_utils_files.storage_transforms.util import materialize`) — uncommon enough not to warrant a top-level export.

## 11. Exceptions

One new class, added to the existing hierarchy:

```python
# exceptions.py — addition
class TransformError(StorageError):
    """A stream transform encoding or decoding failure."""
```

Raised by `Gzip`, `GPG`, and future transforms. Preserves the root cause via `__cause__`. No further subclassing — one class is enough for the failure modes in scope.

## 12. Testing Strategy

### 12.1 Test structure

```
tests/
└── storage_transforms/
    ├── test_pipeline.py                # Ordering, direction, empty, reuse
    ├── test_gzip.py                    # Round-trip sizes, level, mtime, laziness
    ├── test_gpg.py                     # Round-trip via fixture keyring (integration)
    ├── test_materialize.py             # Memory vs tempfile, spool crossover
    └── test_facade_integration.py      # pipeline= kwarg, copy_between
```

### 12.2 Key assertions

- `Pipeline()` with zero transforms is the identity on both read and write paths.
- `Pipeline(Gzip(), GPG(...))` round-trips to input bytes exactly.
- `Pipeline(GPG(...), Gzip())` produces on-disk bytes that differ from `Pipeline(Gzip(), GPG(...))` — ordering is demonstrably observable.
- `Gzip(mtime=0)` produces byte-identical output for identical input.
- `Gzip().wrap(src)` does not drain `src` until the consumer calls `.read()` on the returned stream (verify with a counter-wrapped source).
- `GPG()` constructed without `recipients` raises `TransformError` on `wrap()`.
- `GPG()` decryption with wrong passphrase surfaces `TransformError` on the first `.read()` of the unwrap result.
- `materialize(stream, to="tempfile", memory_cutoff=N)` stays in memory for small streams and rolls to disk past `N`.
- `facade.read(path, pipeline=Gzip())` round-trips with `facade.write(path, data, pipeline=Gzip())`.
- `facade.copy_between(src, dst, source_pipeline=Gzip())` reads a gzipped source and writes a plaintext destination.

### 12.3 GPG fixtures

A test keyring lives under `tests/fixtures/gpg/` with a throwaway private key for the placeholder recipient `test@mountainash.example`. Per-test, `gnupghome` is copied into `tmp_path` to avoid pollution. GPG tests are marked `@pytest.mark.integration` and excluded from the default unit lane.

### 12.4 Protocol conformance in CI

Extend the existing `test_protocol_conformance.py` suite to assert `isinstance(Gzip(), StreamTransform)` and `isinstance(GPG(...), StreamTransform)`. CI then enforces that all built-in transforms conform to the protocol.

## 13. Out of Scope

- New transforms beyond Gzip and GPG (zstd, age, bz2, lz4, chunked hashing).
- Symmetric-key encryption (AES-GCM) as a transform.
- Server-side encryption (SSE-KMS, CSEK, Azure encryption scopes).
- Auto-detection of on-disk format (e.g. magic-byte sniffing to auto-select `Gzip().unwrap`).
- Text-mode stream helpers — callers wrap with `io.TextIOWrapper`.
- Restoring `mountainash-utils-gpg` as a dependency (orphaned package, archival tracked separately).
- Content-Length-required write paths on backends — forbidden by §7.2.
- Backends other than `local` and `s3` — tracked in a separate spec.

## 14. Implementation Plan Overview

Ordered prerequisites for the implementation plan (details in the subsequent plan document):

1. **Audit** `storage_backends/s3/s3_write.py` for `upload_fileobj` usage; fix to streaming upload if currently using `put_object(ContentLength=...)`.
2. **Add** `StreamTransform` protocol and `Pipeline` class.
3. **Add** `Gzip` transform + tests.
4. **Add** `GPG` transform + tests (gated behind `[encryption]` extra).
5. **Add** `materialize()` utility + tests.
6. **Extend** `StorageFacade.read`/`read_stream`/`write`/`write_stream` with the `pipeline=` keyword-only argument.
7. **Extend** `copy_between` with `source_pipeline=` and `destination_pipeline=` arguments.
8. **Add** `TransformError` to the exceptions module.
9. **Wire** protocol conformance checks into the existing CI suite.
10. **Update** top-level `__init__.py` re-exports and the Architecture section of `CLAUDE.md`.
