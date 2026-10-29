---
title: File operations
---

# File operations

A `StorageFacade` reads and writes files, streams them, lists and inspects them, deletes them, manages directories and copies within one store. Each operation has one signature for every backend that supports it, so code written against a local directory runs unchanged against an S3 bucket or an SFTP server. Where backends genuinely differ, the difference is noted beside the operation.

Creating, checking and closing facades is described in [Opening storage with StorageFacade](../06-storage-facade/index.md). The examples on this page share one setup: a local facade, an S3 facade on a bucket named `reports`, and a temporary directory `root`. `ENDPOINT` is the URL of a local S3-compatible server; the examples were run against moto's server.

```python
import tempfile
from pathlib import Path

from mountainash_auth_client import IAMAuthProfile
from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL=ENDPOINT, BUCKET="reports")
auth = IAMAuthProfile(ACCESS_KEY_ID="example-access-key", SECRET_ACCESS_KEY="example-secret")
root = tempfile.mkdtemp()
local = StorageFacade.for_local()
s3 = StorageFacade.from_path("s3://reports/", profile, auth_profile=auth)
```

## Reading and writing

<!-- concept:148 -->

`read(path)` returns the whole content as `bytes`. `write(path, data)` stores `bytes`, replacing anything already at `path`. Both accept a stream transform so that the stored form can differ from the bytes your code sees: compressed or encrypted on the store, plain in memory.

| Method | Returns | Keyword arguments |
|---|---|---|
| `read(path)` | `bytes` | `pipeline`, `infer`, `gpg`, `gzip` |
| `write(path, data)` | `None` | `pipeline`, `create_parents=True` |

The keywords work the same way on every backend:

- `pipeline` takes a `Gzip()`, a `GPG(...)` or a `Pipeline` of several. On write it encodes the data before storing it; on read it decodes what was stored.
- `infer=True` (read only) builds the pipeline from the path's suffixes, so `sales.csv.gz` is decompressed. Passing both `infer=True` and `pipeline` raises `ValueError`. `gpg` and `gzip` supply the configured transform instances that inference should use, for example a `GPG` with your key settings.
- `create_parents` controls whether missing parent directories are created; see [Parent creation](#parent-creation).

The transforms themselves, the order of a pipeline and the gzip size bound are described in [Stream transforms](../10-stream-transforms/index.md#transforms-and-pipelines). The package treats the bytes as opaque: it does not parse CSV, Parquet or any other format, which is the job of consumer packages ([Formats belong to consumers](../02-mountainash-ecosystem/index.md#formats-belong-to-consumers)).

The same loop writes gzip-compressed data to both stores and reads it back twice, once as stored and once decoded:

```python
from mountainash_transport import Gzip

SALES = b"region,total\nnorth,120\nsouth,95\n"

for storage, path in ((local, f"{root}/sales.csv.gz"), (s3, "s3://reports/2026/sales.csv.gz")):
    storage.write(path, SALES, pipeline=Gzip())
    stored = storage.read(path)               # raw stored bytes
    decoded = storage.read(path, infer=True)  # .gz suffix selects Gzip
    print(f"{path.rsplit('/', 1)[-1]}: stored {len(stored)}, decoded {len(decoded)}, "
          f"match={decoded == SALES}")
```

Output:

```text
sales.csv.gz: stored 50, decoded 32, match=True
sales.csv.gz: stored 50, decoded 32, match=True
```

`read()` consumes the stream completely before returning, so any transfer or decoding error is raised inside the call. A write is not atomic: if it fails part-way, the destination may hold partial data, and the package adds no rollback or retry. Failures are raised as the storage errors described in [Errors](../03-installation/index.md#errors): `PathNotFoundError` for a missing resource, `PermissionDeniedError` for denied access, `AuthenticationError` for bad credentials, `StorageConnectionError` for connection and timeout failures, and `StorageError` for other backend failures.

<!-- concept:149 -->

### Streaming reads and writes

`read()` and `write()` hold the whole object in memory. For large objects, use the streaming forms:

- `read_stream(path)` returns a binary file object that you read from and must close, ideally with `with`. It takes the same `pipeline`, `infer`, `gpg` and `gzip` keywords as `read()`, plus `access` and `range_policy`.
- `write_stream(path, stream)` reads from any binary file object you supply and stores its content. It takes `pipeline` and `create_parents` like `write()`.

By default `read_stream()` uses sequential access. From a remote store you get a forward-only stream that fetches data as you read it rather than downloading the whole object first. Local files return a native file handle, which is also seekable. Random access by byte range, and full in-memory buffering, are selected with `access`; see [Read access modes](../09-read-access-modes/index.md#choosing-an-access-mode).

This example uploads a 950 KB local file to S3 from an open file handle, then totals the second column while streaming the object back one line at a time:

```python
import io

source = Path(root) / "big.csv"
source.write_bytes(b"region,total\n" + b"north,120\nsouth,95\n" * 50_000)

path = "s3://reports/2026/big.csv"
with source.open("rb") as upload:
    s3.write_stream(path, upload)

total = 0
with s3.read_stream(path) as stream:
    print("seekable:", stream.seekable())
    lines = io.TextIOWrapper(stream, encoding="utf-8")
    next(lines)  # header
    for line in lines:
        total += int(line.rsplit(",", 1)[1])
print("total:", total)
```

Output:

```text
seekable: False
total: 10750000
```

How much of the payload each backend holds in memory differs:

| Backend | `read_stream()` (sequential) | `write_stream()` |
|---|---|---|
| Local | Native file handle, seekable | Copied to the file in 64 KiB chunks |
| S3 family | Forward-only, fetched on demand | boto3 managed upload; large uploads become multipart |
| SFTP | Forward-only, no unbounded prefetch | Whole source read into memory, then written |
| HTTP | Forward-only, fetched on demand | Streamed as the body of a `PUT` |

!!! warning "SFTP buffers stream writes"
    On SFTP, `write_stream()` reads the entire source stream into memory and then writes it in one call. Memory use grows with the payload size, and this also applies when `copy_between()` copies into SFTP. Writing a multi-gigabyte stream to SFTP needs that much free memory. See the [support matrix and known limits](../../reference/support-matrix.md).

!!! note "S3 uploads may close your stream"
    `write_stream()` to an S3-family store hands the stream to boto3's managed upload. After a small upload, sent as a single request, the source stream is closed; after a larger multipart upload it is left open. In a local run, a 100-byte `BytesIO` and file handle were both closed afterwards, and 20 MiB ones were not. Do not rely on the source stream's state after `write_stream()` returns. See the [support matrix and known limits](../../reference/support-matrix.md#known-limits).

A stream returned by `read_stream()` must stay open for the whole read, and its facade must stay open until the stream is closed. Closing the stream also closes every transform layer stacked on it. Errors from lazy decoding appear when you read, not when you open. These rules are covered in [Errors and ownership](../09-read-access-modes/index.md#errors-and-ownership).

## Listing and metadata

<!-- concept:150 -->

`list_objects(prefix, *, delimiter="/", max_results=None)` returns an `EnumerateResult` with two tuples of `StorageEntry`: `objects` (files or objects) and `common_prefixes` (groups). The prefix means slightly different things on different stores, because filesystems have directories and object stores do not:

- On local and SFTP stores, `prefix` is an exact path. A file path selects that file; a directory path selects the files beneath it. `reports` never matches a sibling called `reports-old`. A missing path returns an empty result.
- On S3 the prefix is a literal key prefix. `2026/` selects every key that starts with `2026/`; `2026/q1.csv` would also match `2026/q1.csv.bak`.

With the default `delimiter="/"` you get one level: immediate files in `objects` and immediate subdirectories or key groups in `common_prefixes`, as entries of type `EntryType.PREFIX`. With `delimiter=None` the listing recurses and returns every file below the prefix. `max_results` caps the combined count of both tuples. The facade default of `"/"` differs from the backend protocol default of `None`, so code that calls a backend directly gets a recursive listing.

Given the same three files in a local directory and in the bucket, both stores list them the same way:

```python
for key in ("2026/q1.csv", "2026/q2.csv", "2026/archive/q4.csv"):
    local.write(f"{root}/reports/{key}", b"region,total\n")
    s3.write(f"s3://reports/{key}", b"region,total\n")

for storage, prefix in ((local, f"{root}/reports/2026"), (s3, "s3://reports/2026/")):
    grouped = storage.list_objects(prefix)                  # delimiter="/"
    flat = storage.list_objects(prefix, delimiter=None)     # recursive
    print(sorted(e.name for e in grouped.objects),
          [e.entry_type.value + ":" + e.name for e in grouped.common_prefixes],
          len(flat.objects))
```

Output:

```text
['q1.csv', 'q2.csv'] ['prefix:archive'] 3
['q1.csv', 'q2.csv'] ['prefix:archive'] 3
```

The S3 prefix ends with `/` so that it selects the folder's keys only. HTTP stores cannot list. For a plain directory listing with directory entries rather than prefix groups, local and SFTP also offer `list_dir()` ([Directory operations](#directory-operations)).

!!! note "S3 listings with a limit"
    On the S3 family, `max_results` is applied after every page of the listing has been fetched, so a small limit on a large prefix still lists the whole prefix. See the [support matrix and known limits](../../reference/support-matrix.md).

<!-- concept:151 -->

### `StorageEntry`

Listings and metadata queries describe each resource with a `StorageEntry`, a frozen dataclass exported from the package root. Backends fill the fields they know and leave the rest at their defaults:

| Field | Type | Meaning |
|---|---|---|
| `path` | `str` | Full path, in the store's own form (`s3://bucket/key` for S3) |
| `name` | `str` | Final path component |
| `size` | `int \| None` | Size in bytes; `None` for directories and prefixes |
| `last_modified` | `datetime \| None` | Timezone-aware timestamp (UTC on local and SFTP) |
| `entry_type` | `EntryType` | `FILE`, `DIRECTORY` or `PREFIX` |
| `etag`, `content_type`, `storage_class` | `str` | Object-store and HTTP details; empty when unknown |
| `version_id`, `checksum`, `checksum_algorithm` | `str` | S3 version and checksum; empty when unknown |
| `source` | `str` | Backend that produced the entry: `local`, `s3`, `sftp` or `http` |

<!-- concept:152 -->

### Metadata queries

Three methods answer questions about one path without reading it:

- `exists(path)` returns `False` only when the store establishes that the resource is absent. Denied access or an operational failure raises the matching storage error instead of returning `False`, so a `False` answer can be trusted.
- `get_size(path)` returns the size in bytes, `0` included. It returns `None` only when the resource exists but the store does not report a size, for example an HTTP response without `Content-Length`. A missing resource raises `PathNotFoundError`.
- `metadata(path)` returns a `StorageEntry` for the resource.

```python
from mountainash_transport import PathNotFoundError

path = "s3://reports/2026/sales.csv"
s3.write(path, b"region,total\nnorth,120\n")

entry = s3.metadata(path)
print(entry.name, entry.size, entry.entry_type.value, entry.etag[:8], entry.source)
print(s3.exists(path), s3.get_size(path))

missing = "s3://reports/2026/missing.csv"
print(s3.exists(missing))
try:
    s3.get_size(missing)
except PathNotFoundError as error:
    print(f"{type(error).__name__}: {error}")
```

Output:

```text
sales.csv 23 file ec35683e s3
True 23
False
PathNotFoundError: s3://reports/2026/missing.csv
```

S3 object queries use a `HEAD` request. A denied `HEAD` raises `PermissionDeniedError` and does not prove that the object is absent. HTTP stores answer all three queries with `HEAD` as well. On local and SFTP stores, directories report `EntryType.DIRECTORY`.

## Deleting, directories and parent creation

<!-- concept:153 -->

`delete(path)` removes one file or object. It does not remove directories; use `rmdir()` for those. HTTP stores do not support deletion.

What happens when the path is already gone depends on the store. Local and SFTP stores raise `PathNotFoundError`. S3 deletion is idempotent: deleting a key that does not exist succeeds silently, because that is how the S3 `DeleteObject` call behaves. If your code needs to know whether something was deleted, check `exists()` first.

```python
from mountainash_transport import PathNotFoundError

for storage, path in ((local, f"{root}/sales.csv"), (s3, "s3://reports/sales.csv")):
    storage.write(path, b"region,total\n")
    storage.delete(path)
    print(path.rsplit("/", 1)[-1], "exists after delete:", storage.exists(path))
    try:
        storage.delete(path)
        print("  second delete: no error")
    except PathNotFoundError as error:
        print(f"  second delete: {type(error).__name__}")
```

Output:

```text
sales.csv exists after delete: False
  second delete: PathNotFoundError
sales.csv exists after delete: False
  second delete: no error
```

The first pair of lines is the local store and the second is S3.

<!-- concept:154 -->

### Directory operations

Local and SFTP stores have real directories and support three directory methods. Object stores have only key prefixes, so the S3 family and HTTP raise `UnsupportedOperationError`; check with `supports(StorageDirectoryProtocol)` if your code must work with both.

- `list_dir(path)` returns a list of `StorageEntry`, one per immediate child, with `entry_type` set to `FILE` or `DIRECTORY`. A missing path raises `PathNotFoundError`, and a path that is a file raises a storage error rather than returning an empty list.
- `mkdir(path, parents=True)` creates the directory and any missing ancestors, and accepts a directory that already exists. With `parents=False`, only the final directory is created, and a missing parent or an existing destination raises. Recursive creation is not atomic: ancestors created before a failure remain.
- `rmdir(path)` removes a directory.

```python
from mountainash_transport import PathNotFoundError

reports = f"{root}/reports/2026"
local.mkdir(reports)                          # parents=True by default
local.write(f"{reports}/q1.csv", b"region,total\n")
local.mkdir(f"{reports}/archive")

for entry in sorted(local.list_dir(reports), key=lambda e: e.name):
    print(entry.name, entry.entry_type.value, entry.size)

try:
    local.mkdir(f"{root}/missing/child", parents=False)
except PathNotFoundError as error:
    print("parents=False:", type(error).__name__)

local.rmdir(f"{root}/reports")               # local removes the whole tree
print(local.exists(f"{root}/reports"))
```

Output:

```text
archive directory None
q1.csv file 13
parents=False: PathNotFoundError
False
```

!!! warning "`rmdir` is recursive on local stores and empty-only on SFTP"
    On a local store, `rmdir()` removes the directory and everything inside it, using `shutil.rmtree`. On SFTP, `rmdir()` issues the protocol's remove-directory request, which succeeds only for an empty directory; the server refuses a non-empty directory and the call raises. Code that must behave the same on both should delete the contents first, then call `rmdir()` on the empty directory. See the [support matrix and known limits](../../reference/support-matrix.md).

<!-- concept:155 -->

### Parent creation

`write()` and `write_stream()` create missing parent directories by default, so writing `a/b/c.csv` into an empty directory creates `a` and `a/b`. Pass `create_parents=False` to turn that off. Local and SFTP then open the destination without creating or checking parents, and a missing parent raises `PathNotFoundError`. The S3 family and HTTP accept the keyword and ignore it, because object keys and URLs have no parent directories to create. The option controls directory creation only; it does not make a write atomic.

```python
from mountainash_transport import PathNotFoundError

local.write(f"{root}/a/b/c.csv", b"x")        # creates a/ and a/b/
print(local.exists(f"{root}/a/b"))

try:
    local.write(f"{root}/new/c.csv", b"x", create_parents=False)
except PathNotFoundError as error:
    print("local:", type(error).__name__)

s3.write("s3://reports/new/c.csv", b"x", create_parents=False)  # ignored for keys
print("s3:", s3.exists("s3://reports/new/c.csv"))
```

Output:

```text
True
local: PathNotFoundError
s3: True
```

## Copying

<!-- concept:156 -->

`copy(source, destination)` copies one file to another path in the same store. Both paths go through the same facade.

- Local stores copy with `shutil.copy2`, which keeps the modification time, and create the destination's parent directories.
- S3-family stores ask the service to copy the object server side, so no data is downloaded. Source and destination may be in different buckets reachable with the same credentials.
- SFTP and HTTP do not support `copy()` and raise `UnsupportedOperationError`.

```python
for storage, folder in ((local, root), (s3, "s3://reports")):
    storage.write(f"{folder}/2026/sales.csv", b"region,total\nnorth,120\n")
    storage.copy(f"{folder}/2026/sales.csv", f"{folder}/backup/2026/sales.csv")
    print(storage.read(f"{folder}/backup/2026/sales.csv") == storage.read(f"{folder}/2026/sales.csv"))
```

Output:

```text
True
True
```

!!! warning "S3 copies use a single request"
    An S3-family `copy()` is one `CopyObject` request with no multipart fallback. It is bounded by the provider's single-request copy limit, which is [5 GB on Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html); copying a larger object fails. See the [support matrix and known limits](../../reference/support-matrix.md).

To copy between two different stores, for example from SFTP to S3, or to copy within SFTP, use `copy_between()`, which streams from one facade into another and can apply transforms on the way ([Copying between backends](../10-stream-transforms/index.md#copying-between-backends)).
