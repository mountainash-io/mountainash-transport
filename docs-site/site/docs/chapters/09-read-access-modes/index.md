---
title: Read access modes
---

# Read access modes

`StorageFacade.read_stream()` can hand back a remote object in three ways: as a forward-only stream fetched on demand, as a seekable handle that fetches byte ranges, or as a seekable buffer holding the whole decoded object in memory. The `access` argument selects which. The choice decides how much is downloaded, how much memory is used and whether the reader can seek, so it matters most for formats such as Parquet that read a footer first and then jump to selected columns.

This page builds on [Streaming reads and writes](../07-file-operations/index.md#streaming-reads-and-writes). The examples use the `local` and `s3` facades, `root` directory and `ENDPOINT` defined at the top of [File operations](../07-file-operations/index.md).

## Choosing an access mode

<!-- concept:159 -->

`read_stream(path, access=...)` accepts `"sequential"` (the default), `"random"` or `"buffered"`:

| `access` | Data fetched | Memory | Seekable | Transforms | Backends |
|---|---|---|---|---|---|
| `"sequential"` | On demand as you read, no whole-object buffer | One read buffer | Remote: no. Local: yes (native handle) | Supported | All |
| `"random"` | Byte ranges, through a configurable cache | Bounded by the cache policy | Yes; `seek()` performs no I/O | Rejected | S3 family, SFTP, HTTP; local returns its native handle |
| `"buffered"` | The whole object, decoded, before returning | Whole decoded object | Yes, in decoded bytes | Supported | All |

`read()` is unaffected by the mode: it always returns the complete content. `copy_between()` always reads sequentially.

Transport does not choose the mode for you, and it does not guess from a file extension. The caller knows the format and how it will be read, so access-mode choice belongs to the consumer, as format handling does ([Formats belong to consumers](../02-mountainash-ecosystem/index.md#formats-belong-to-consumers)). A CSV parser wants sequential access; a Parquet reader wants random access; a library that insists on a seekable in-memory file wants buffered.

The example stores a 1 MB object with an 8-byte header and an 8-byte trailer, then opens it in each mode. Only the seekable modes can jump to the trailer:

```python
import io

path = "s3://reports/2026/data.bin"
s3.write(path, b"HEADER--" + bytes(1_000_000) + b"TRAILER!")

for access in ("sequential", "random", "buffered"):
    with s3.read_stream(path, access=access) as stream:
        if stream.seekable():
            stream.seek(-8, io.SEEK_END)
            print(f"{access}: seekable, last 8 bytes {stream.read(8)!r}")
        else:
            print(f"{access}: forward-only, first 8 bytes {stream.read(8)!r}")

local.write(f"{root}/data.bin", b"HEADER--TRAILER!")
with local.read_stream(f"{root}/data.bin") as stream:
    print("local sequential seekable:", stream.seekable())
```

Output:

```text
sequential: forward-only, first 8 bytes b'HEADER--'
random: seekable, last 8 bytes b'TRAILER!'
buffered: seekable, last 8 bytes b'TRAILER!'
local sequential seekable: True
```

Remote streams used to be downloaded into memory before `read_stream()` returned. They no longer are. Code that seeks on a remote stream must ask for `access="buffered"` to keep the old behaviour, or `access="random"` to seek without downloading the whole object.

<!-- concept:160 -->

### Sequential access

Sequential is the default and suits anything that reads front to back: line-oriented text, CSV, JSON lines, gzip. Remote backends return a forward-only stream that requests more data only as you read, so memory stays flat however large the object is; SFTP also disables unbounded prefetch. On a local store you get the operating system's file handle, which keeps its native seekability. Transforms apply as you read: a `.gz` object is decompressed chunk by chunk. A forward-only remote stream wrapped in gzip remains forward-only. Because data arrives during consumption, so do errors ([Deferred read errors](#deferred-read-errors)).

<!-- concept:161 -->

### Random access

`access="random"` returns a seekable handle over the stored bytes. Opening it learns the object's size; after that, `seek()` only moves a position, and each `read()` fetches whatever byte range is missing from the handle's cache. A reader that needs a Parquet footer and two columns downloads those ranges and little else.

How each backend serves ranges:

- S3 family: a `HEAD` request for the size, then ranged `GET` requests. When the object has a strong ETag, each range request carries `If-Match`, so a replaced object raises `ObjectChangedError` instead of mixing bytes from two versions.
- HTTP: a `bytes=0-0` probe on open, then range requests, each validated before it is read. Strong ETags are pinned the same way.
- SFTP: a native remote file handle without prefetch, and no ETag pinning.
- Local: the native file handle. Local has no ranged-read capability and needs none, so `supports(RangedReadProtocol)` is `False` even though random mode works. `readinto`, `seek`, `tell` and `fileno` behave as on any file.

Random mode reads stored bytes, so it cannot be combined with transforms. A pipeline, or `infer=True` on a path whose suffixes imply one, raises `ValueError`; decompress with sequential or buffered mode instead ([Limits and ownership](../10-stream-transforms/index.md#limits-and-ownership)).

```python
from mountainash_transport import ObjectChangedError, RangePolicy

path = "s3://reports/2026/live.bin"
s3.write(path, b"a" * 4096)
with s3.read_stream(path, access="random", range_policy=RangePolicy("none")) as stream:
    print(stream.read(4))
    s3.write(path, b"b" * 4096)   # another writer replaces the object
    try:
        stream.read(4)
    except ObjectChangedError as error:
        print(type(error).__name__)
```

Output:

```text
b'aaaa'
ObjectChangedError
```

!!! warning "Range support is not negotiable"
    An HTTP server that ignores range requests (answers `200`), does not report a size, or applies a `Content-Encoding` other than identity makes the open raise `RangeNotSupportedError`. There is no silent fallback to downloading the whole object; choose `access="buffered"` if that is what you want. A backend without ranged reads raises `UnsupportedOperationError`. A wrong range interval or a short or oversized body raises `StorageError`. Weak or missing ETags do not prevent opening, but they give no consistency guarantee.

A large `read(n)` allocates `n` bytes whatever the cache settings, and `read()` with no size reads the rest of the object. Random handles are not safe for concurrent `seek()` and `read()` from several threads.

<!-- concept:162 -->

### Buffered access

`access="buffered"` reads the whole object, decodes it through any transforms, and returns a seekable in-memory buffer of the decoded bytes. The source stream and every transform layer are closed before `read_stream()` returns, so the buffer owns its data and stays usable after the facade closes. All transfer and decoding errors are raised inside the `read_stream()` call. Memory use equals the decoded size, so buffered access suits small and medium objects, and libraries that require a seekable file of decoded content. To spill large objects to disk instead of memory, use [`materialize`](#materialize) on a sequential stream.

## Range tuning

<!-- concept:163 -->

A `RangePolicy`, exported from the package root, controls how a random-access handle caches fetched bytes. It is a frozen dataclass with three fields:

| Field | Default | Meaning |
|---|---|---|
| `cache` | `"readahead"` | `"readahead"`: one forward read-ahead window. `"none"`: fetch exactly the requested interval. `"blockcache"`: keep up to `max_blocks` fixed-size blocks across seeks. `"bytes"`: one contiguous cache window. |
| `block_size` | `1048576` (1 MiB) | Window or block size in bytes; must be positive. |
| `max_blocks` | `32` | Blocks kept by `"blockcache"`; must be positive there and is ignored by the other caches. |

The effective policy for a random read is chosen in this order: a `range_policy` passed to `read_stream()` replaces everything else; otherwise the S3, HTTP or SFTP storage profile's `RANGE_CACHE`, `RANGE_BLOCK_SIZE` and `RANGE_MAX_BLOCKS` fields override the library defaults one field at a time. These profile fields are transport settings, not SDK arguments. Passing `range_policy` with any mode other than `"random"` raises `ValueError`.

```python
from mountainash_transport import RangePolicy

print(RangePolicy())
print(RangePolicy.from_profile(
    S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=ENDPOINT, BUCKET="reports",
                     RANGE_CACHE="blockcache", RANGE_MAX_BLOCKS=8)
))
for bad in (dict(block_size=0), dict(cache="lru")):
    try:
        RangePolicy(**bad)
    except ValueError as error:
        print(error)

path = "s3://reports/2026/data.bin"
s3.write(path, bytes(range(256)) * 4096)
policy = RangePolicy("blockcache", block_size=64 * 1024, max_blocks=4)
with s3.read_stream(path, access="random", range_policy=policy) as stream:
    stream.seek(200_000)
    print(stream.read(4), stream.tell())
```

Output:

```text
RangePolicy(cache='readahead', block_size=1048576, max_blocks=32)
RangePolicy(cache='blockcache', block_size=1048576, max_blocks=8)
block_size must be positive
Unknown range cache: 'lru'
b'@ABC' 200004
```

The default suits small forward reads. Format-aware callers, such as `mountainash-files`, are expected to override it per read. Measurements on one local test setup give a starting point, not a guarantee:

| Workload | Suggested policy | Observed tradeoff |
|---|---|---|
| General small forward reads | Default `readahead`, 1 MiB | 2048 reads of 4 KiB took 9 requests, against 122 with a 64 KiB window |
| PyArrow `ParquetFile` schema and projected column reads | `RangePolicy("readahead", block_size=64 * 1024)` | PyArrow requests large column chunks itself; a small window avoids fetching neighbouring bytes |
| PyArrow reads where transferred bytes matter most | `RangePolicy("none")` | No speculative fetching; repeated ranges may cost extra requests |
| Scattered small reads that revisit regions | `RangePolicy("blockcache", block_size=..., max_blocks=...)` | Retains blocks; smaller blocks fetch less but make more requests |

Reading one of twenty columns from a 363 MB Parquet file fetched 18.8 MB with a 64 KiB read-ahead, 18.2 MB with no cache, 26.6 MB with a 1 MiB read-ahead and 57.3 MB with a 4 MiB block cache. ORC, ZIP and Arrow IPC readers were not measured; benchmark their access patterns before choosing a policy. PyArrow is not a dependency of transport, but a random handle is a seekable binary file, so it can be passed straight to PyArrow. Here `path` names a small Parquet file in the bucket:

```python
import pyarrow.parquet as pq

with s3.read_stream(path, access="random",
                    range_policy=RangePolicy("readahead", block_size=64 * 1024)) as handle:
    schema = pq.ParquetFile(handle).schema_arrow
print(schema)
```

Output:

```text
region: string
total: int64
```

The random handle and its cache are implemented in `src/mountainash_transport/_core/ranged_io.py` and described for backend authors in [Read plumbing](../14-backends/index.md#read-plumbing).

## Errors and ownership

<!-- concept:166 -->

### Deferred read errors

A successful `read_stream()` call does not prove that the payload is valid or fully available. Errors can surface at two points:

- When opening: the backend fails to open the object, a random-mode probe, `HEAD` or `stat` fails, or a transform cannot be constructed. In buffered mode every transfer and decoding error also surfaces here, because the whole object is consumed before the call returns. GPG decryption currently buffers internally, so its failures surface when opening too.
- When reading: sequential transfers fail mid-stream, lazy transforms decode as you read (a malformed `.gz` opens cleanly and raises `gzip.BadGzipFile` on `read()`), and random-mode range fetches fail.

HTTP retries and OAuth token refresh happen before a response is handed over; once you have started consuming a body, nothing is replayed. If you want every decoding error raised inside one call, use `read()`.

```python
import gzip

path = f"{root}/bad.csv.gz"
local.write(path, b"this is not gzip data")

try:
    with local.read_stream(path, infer=True) as handle:
        print("opened")
        handle.read()
except gzip.BadGzipFile as error:
    print(f"{type(error).__name__} on read; handle closed: {handle.closed}")

try:
    local.read(path, infer=True)
except gzip.BadGzipFile:
    print("read() raises within the call")
```

Output:

```text
opened
BadGzipFile on read; handle closed: True
read() raises within the call
```

Decoder errors keep their own types; they are not reclassified as storage errors.

<!-- concept:167 -->

### Stream ownership

The stream returned by `read_stream()` belongs to the caller. Closing it, including when the `with` block exits because of an exception, closes every transform layer the facade constructed, in reverse order of construction, and then the backend source. Every close is attempted even if one of them raises; the handle is then marked closed, a second close does nothing, and the last cleanup error propagates. If opening fails part-way, the layers built so far are closed and the original error is raised.

Closing a stream never closes its facade, and the facade must stay open while sequential or random remote streams are in use. A buffered result is independent of both.

```python
from mountainash_transport import Gzip

path = "s3://reports/2026/sales.csv.gz"
s3.write(path, b"region,total\nnorth,120\n", pipeline=Gzip())

with s3.read_stream(path, infer=True) as stream:
    first = stream.readline()
print(first, stream.closed, s3.exists(path))   # facade still usable

buffered = s3.read_stream(path, infer=True, access="buffered")
s3.close()
print(buffered.read())                          # independent of the facade
```

Output:

```text
b'region,total\n' True True
b'region,total\nnorth,120\n'
```

If you apply a pipeline yourself with `Pipeline.apply_read(source)` instead of going through the facade, the returned stream owns only the layers it built, not `source`; close the source separately. Transform ownership in both directions is covered in [Limits and ownership](../10-stream-transforms/index.md#limits-and-ownership).

<!-- concept:168 -->

### `materialize`

`materialize(stream, *, to="memory", memory_cutoff=64 * 1024 * 1024)` drains a stream into a seekable buffer and returns `(buffer, length)`, with the buffer positioned at 0. `to="memory"` uses an `io.BytesIO`. `to="tempfile"` uses a `tempfile.SpooledTemporaryFile` that stays in memory up to `memory_cutoff` bytes and moves to disk beyond it, which makes it safe for objects too large for buffered access. The source stream is exhausted afterwards; close it as usual. Use it when you need a known length or a seekable copy and do not want the whole object in memory.

`materialize` is not exported from the package root. Import it from `mountainash_transport._core.transforms.util`:

```python
from mountainash_transport._core.transforms.util import materialize

path = "s3://reports/2026/big.bin"
s3.write(path, bytes(5_000_000))

with s3.read_stream(path) as stream:
    spooled, length = materialize(stream, to="tempfile", memory_cutoff=1024 * 1024)
with spooled:
    print(type(spooled).__name__, length, spooled.seekable(), spooled.tell())
```

Output:

```text
SpooledTemporaryFile 5000000 True 0
```
