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

facade = StorageFacade.from_path("https://example.org/report.parquet")
with facade.read_stream(
    "https://example.org/report.parquet", access="random",
    range_policy=RangePolicy("readahead", block_size=64 * 1024),
) as stream:
    stream.seek(-8, 2)
    trailer = stream.read(8)
```

Local random reads use a native file handle, not a remote cache. S3 uses HEAD for size and ranged GETs; HTTP probes `bytes=0-0` and validates each response before reading it. SFTP uses a native open handle without prefetch. The default sequential SFTP path also disables unbounded prefetch.

## Cache policy and precedence

A supplied `range_policy` replaces the profile policy. Otherwise the S3, HTTP or SFTP profile's `RANGE_CACHE`, `RANGE_BLOCK_SIZE` and `RANGE_MAX_BLOCKS` fields override library defaults individually. They are transport settings, not SDK client kwargs.

Library defaults are `RangePolicy(cache="readahead", block_size=1024*1024, max_blocks=32)`.

- `readahead`: one forward read-ahead window.
- `none`: fetch the requested interval only.
- `blockcache`: retain up to `max_blocks` fixed-size blocks across seeks.
- `bytes`: a contiguous cache window managed by fsspec.

`block_size` must be positive; `max_blocks` must be positive for `blockcache` and is ignored for other caches. A large caller `read(n)` can allocate `n` bytes; `read()` explicitly consumes the remainder. Cache settings do not cap the caller's requested result size. Handles are not safe for concurrent seek/read operations.

## Format-aware upstream tuning

Transport does **not** infer cache settings from extensions. Format-aware callers, including mountainash-files, may override them per operation.

| Workload | Suggested policy | Evidence / tradeoff |
|---|---|---|
| General use, small forward reads | Default `readahead`, 1 MiB | Disposable loopback spike: 2048 × 4 KiB reads needed 9 requests versus 122 with 64 KiB read-ahead |
| PyArrow `ParquetFile` schema / projected reads | `RangePolicy("readahead", block_size=64*1024)` | PyArrow requests large column chunks itself; smaller read-ahead avoids unnecessary adjacent bytes |
| PyArrow reads where exact transfer matters most | `RangePolicy("none")` | Avoid speculative acquisition; repeated ranges may incur extra requests |
| Scattered small reads with revisits | `RangePolicy("blockcache", block_size=..., max_blocks=...)` | Retain blocks; smaller blocks reduce overfetch but increase request count |

The disposable 363 MB Parquet spike fetched 18.8 MB for one of twenty columns with 64 KiB read-ahead, 18.2 MB with no cache, 26.6 MB with 1 MiB read-ahead and 57.3 MB with 4 MiB block caching. These are workload-specific, not performance guarantees. ORC, ZIP and Arrow IPC readers were not measured: benchmark their access patterns before selecting overrides.

PyArrow is not a transport runtime dependency:

```python
import pyarrow.parquet as pq
from mountainash_transport import RangePolicy

with facade.read_stream(path, access="random",
                        range_policy=RangePolicy("readahead", block_size=64*1024)) as handle:
    schema = pq.ParquetFile(handle).schema_arrow
```

## Errors, consistency and ownership

- Unsupported HTTP ranges, unknown size, ignored ranges (`200`), or non-identity `Content-Encoding`: `RangeNotSupportedError`. No implicit whole-object fallback.
- Backend without ranged capability: `UnsupportedOperationError`.
- Strong ETags are sent as `If-Match`; a failed precondition becomes `ObjectChangedError`. Weak or missing ETags do not prevent opening, but provide no consistency guarantee. SFTP/local handles have no ETag pinning.
- Wrong range interval/total, short or oversized bodies: `StorageError`.
- `range_policy` outside random mode, unknown access modes, or random mode with transforms: `ValueError`.

Random opens can fail during the probe/HEAD/stat, and subsequent reads can fail during range fetches. Sequential errors may occur during consumption. Buffered mode consumes everything before returning, so decode/transfer errors occur within `read_stream`. HTTP retry and OAuth refresh apply before a response is yielded; no body is replayed after consumption starts.

Closing a facade read stream closes every constructed transform layer in reverse
construction order, then the backend source—not just the final decoder.
`read()` uses the same ownership path; buffered mode closes the decoding chain
before returning its independent memory buffer. Cleanup also runs after decoding
or consumer exceptions.

All remaining closes are attempted if a layer's `close()` raises. The returned
handle is still marked closed, and closing it again is a no-op. Cleanup errors
propagate (the last one wins); construction failures
retain their original exception even if cleanup fails.

For direct `Pipeline.apply_read(source)` callers, the returned stream owns the
distinct layers it constructed, **not** the supplied source. Close the source
separately. Empty or identity-only pipelines return the source unchanged.
Transforms should leave borrowed inputs open; layers already closed by a
cascading transform are not explicitly closed again.

Entering a context does not validate the entire payload:

```python
import gzip

try:
    with facade.read_stream("bad.gz", infer=True) as handle:
        handle.read()  # malformed gzip may fail here, not at open
except gzip.BadGzipFile:
    assert handle.closed
```

Consumer exceptions also close handles. To spool explicitly, the existing `materialize(stream, to="tempfile")` utility is available; a facade spooling option remains deferred (backlog #25).
