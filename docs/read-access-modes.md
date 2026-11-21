# Read access modes

`StorageFacade.read_stream` supports three explicit access patterns. Always close the returned handle, preferably with a context manager.

| `access` | Remote acquisition | Seekability | Transforms |
|---|---|---|---|
| `"sequential"` (default) | Demand-driven streaming; no whole-object buffer | Remote handles are forward-only; local handles remain natively seekable | Supported; gzip over forward-only input is forward-only |
| `"random"` | Fetch byte ranges, with configurable caching | Seekable; `seek` itself performs no I/O | Rejected if the resolved pipeline is non-empty |
| `"buffered"` | Read and decode the entire object into memory before returning | Seekable in decoded bytes | Supported |

`read()` still returns fully consumed bytes. Cross-backend copies use sequential reads. GPG currently buffers internally, independent of the access mode.

## Migration

Previously HTTP, S3 and SFTP downloaded whole objects into `BytesIO` before returning streams. They no longer do so by default. Existing callers that seek on remote streams must select `access="buffered"` to retain that behavior, or `access="random"` to avoid whole-object acquisition. Writes are unchanged.

```python
from mountainash_transport import StorageFacade, RangePolicy

with StorageFacade.from_path("https://example.org/report.parquet") as facade:
    with facade.read_stream(
        "https://example.org/report.parquet", access="random",
        range_policy=RangePolicy("readahead", block_size=64 * 1024),
    ) as stream:
        stream.seek(-8, 2)
        trailer = stream.read(8)
```

Local random reads use a native-backed seekable handle, not a remote cache or a guaranteed concrete Python file class. Supported binary operations (including `readinto`, `seek`, `tell` and native `fileno` in random mode) remain available. Local backend I/O errors are translated when opening, consuming or closing the handle; caller argument errors remain native. Local `exists()` returns `False` only for absence, and missing `get_size()` raises `PathNotFoundError`; denied access raises `PermissionDeniedError`, including on queries. S3 uses HEAD for size and ranged GETs; HTTP probes `bytes=0-0` and validates each response before reading it. SFTP uses a native open handle without prefetch. The default sequential SFTP path also disables unbounded prefetch.

## Cache policy and precedence

A supplied `range_policy` replaces the profile policy. Otherwise the S3, HTTP or SFTP profile's `RANGE_CACHE`, `RANGE_BLOCK_SIZE` and `RANGE_MAX_BLOCKS` fields override library defaults individually. They are transport settings, not SDK client kwargs.

Library defaults are `RangePolicy(cache="readahead", block_size=1024*1024, max_blocks=32)`.

- `readahead`: one forward read-ahead window.
- `none`: fetch the requested interval only.
- `blockcache`: retain up to `max_blocks` fixed-size blocks across seeks.
- `bytes`: a contiguous cache window managed by fsspec.

`block_size` must be positive; `max_blocks` must be positive for `blockcache` and is ignored for other caches. A large caller `read(n)` can allocate `n` bytes; `read()` explicitly consumes the remainder. Cache settings do not cap the caller's requested result size. Handles are not safe for concurrent seek/read operations.

## Choosing a cache policy

Transport does **not** infer cache settings from extensions. Format-aware callers, including mountainash-files, choose a policy per operation; library-specific usage belongs in their documentation.

| Access pattern | Suggested policy | Evidence / tradeoff |
|---|---|---|
| Small forward reads | Default `readahead`, 1 MiB | Disposable loopback spike: 2048 × 4 KiB reads needed 9 requests versus 122 with 64 KiB read-ahead |
| A reader that already requests large chunks itself | `RangePolicy("readahead", block_size=64*1024)` or `RangePolicy("none")` | A large window fetches neighbouring bytes the reader never asks for; `"none"` fetches exactly the requested intervals, so repeated ranges cost extra requests |
| Scattered small reads with revisits | `RangePolicy("blockcache", block_size=..., max_blocks=...)` | Retains blocks; smaller blocks reduce overfetch but increase request count |

One consumer measurement, reading one of twenty columns of a 363 MB file whose reader requests large chunks: 18.8 MB fetched with a 64 KiB read-ahead, 18.2 MB with no cache, 26.6 MB with a 1 MiB read-ahead and 57.3 MB with a 4 MiB block cache. These are workload-specific, not guarantees; measure your reader's access pattern before choosing.

## Handle lifetime and threads

A handle returned by `read_stream` is a Python file object owned by the caller. It is not safe for concurrent `seek`/`read` from several threads, and it must not outlive its use: close it (or leave its `with` block) before the facade closes and before the interpreter exits.

Libraries that read on native worker threads need particular care. If a worker thread holds the last reference to a handle when the interpreter shuts down, releasing it there can abort the process. Give such libraries a handle only for the duration of the call, make sure their threads have released it before you close it, or let them read from a copy they own (for example an in-memory buffer from `access="buffered"` or `materialize`). How a particular library achieves this is documented by the consumer that uses it.

## Errors, consistency and ownership

- Unsupported HTTP ranges, unknown size, ignored ranges (`200`), or non-identity `Content-Encoding`: `RangeNotSupportedError`. No implicit whole-object fallback.
- Backend without ranged capability: `UnsupportedOperationError`.
- Strong ETags are sent as `If-Match`; a failed precondition becomes `ObjectChangedError`. Weak or missing ETags do not prevent opening, but provide no consistency guarantee. SFTP/local handles have no ETag pinning.
- Wrong range interval/total, short or oversized bodies: `StorageError`.
- Random mode with transforms, passed or inferred: `RandomAccessUnavailableError` (exported from the package root; subclasses `ValueError`). Catch it to fall back to `access="buffered"`.
- `range_policy` outside random mode or an unknown access mode: plain `ValueError`.

Random opens can fail during the probe/HEAD/stat, and subsequent reads can fail during range fetches. Sequential errors may occur during consumption. Buffered mode consumes everything before returning, so decode/transfer errors occur within `read_stream`. HTTP retry and OAuth refresh apply before a response is yielded; no body is replayed after consumption starts.

Closing a facade read stream closes every constructed transform layer in reverse
construction order, then the backend source—not just the final decoder.
`read()` uses the same ownership path; buffered mode closes the decoding chain
before returning its independent memory buffer. Cleanup also runs after decoding
or consumer exceptions.

Keep the facade open until sequential/random remote streams are closed. Closing
a stream does not close the facade. Fully buffered results own their bytes and
remain usable after facade close. Facade close itself is terminal: further
storage operations raise `StorageConnectionError`, while repeated close is a no-op.

All remaining closes are attempted if a layer's `close()` raises. The returned
handle is still marked closed, and closing it again is a no-op. Cleanup errors
propagate (the last one wins); construction failures
retain their original exception even if cleanup fails.

For direct `Pipeline.apply_read(source)` and `Pipeline.apply_write(source)`
callers, the returned stream owns the distinct layers it constructed, **not** the
supplied source. Close the source separately. Empty or identity-only pipelines
return the source unchanged. Transforms leave borrowed inputs open (on both the
read and write paths); layers already closed by a cascading transform are not
explicitly closed again. `StorageFacade.write`/`write_stream` close the layers
they build after the backend consumes them and never close the caller's stream.

Entering a context does not validate the entire payload:

```python
import gzip

try:
    with facade.read_stream("bad.gz", infer=True) as handle:
        handle.read()  # malformed gzip may fail here, not at open
except gzip.BadGzipFile:
    assert handle.closed
```

Consumer exceptions also close handles. To spool explicitly, use `materialize(stream, to="tempfile")` (`from mountainash_transport import materialize`); a facade spooling option remains deferred (backlog #25).
