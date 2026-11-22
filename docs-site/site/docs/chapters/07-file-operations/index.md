---
title: File operations
---

# File operations

A `StorageFacade` reads and writes files, streams them, lists and inspects them, deletes them, manages directories and copies within one store. Each operation has one signature for every backend that supports it, so code written against a local directory runs unchanged against an S3 bucket or an SFTP server, apart from operations whose behaviour differs by backend, such as SFTP having no `copy()` ([known limits](../../reference/support-matrix.md#known-limits)). Each difference is noted beside the operation.

Creating, checking and closing facades is described in [Opening storage with StorageFacade](../06-storage-facade/index.md). The examples on this page share one setup: a local facade, an S3 facade on a bucket named `reports`, and a temporary directory `root`. `ENDPOINT` is the URL of a local S3-compatible server; the examples were run in page order against moto's server. Each example writes under its own paths, so its output does not depend on the examples before it.

```python
import tempfile
from pathlib import Path

from mountainash_auth_client import IAMAuthProfile
from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles import S3StorageProfile

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
| `write(path, data)` | `StorageEntry` | `pipeline`, `create_parents=True` |

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
| SFTP | Forward-only, no unbounded prefetch | Uploaded with paramiko's `putfo` in 32 KiB chunks |
| HTTP | Forward-only, fetched on demand | Streamed as the body of a `PUT` |

`write_stream()` reads the source in chunks on every backend, so memory use does not grow with the payload. This also holds when `copy_between()` copies into any of them. A `GPG` transform is the exception: python-gnupg holds the whole payload while it encrypts or decrypts.

`write_stream()` never closes the stream you pass it: after a single-request or a multipart S3 upload, a local write or an HTTP `PUT`, the source is still open and yours to close.

A stream returned by `read_stream()` must stay open for the whole read, and its facade must stay open until the stream is closed. Closing the stream also closes every transform layer stacked on it. Errors from lazy decoding appear when you read, not when you open. These rules are covered in [Errors and ownership](../09-read-access-modes/index.md#errors-and-ownership).

## Listing and metadata

<!-- concept:150 -->

`list_objects(prefix, *, delimiter="/", max_results=None)` returns an `EnumerateResult` with two tuples of `StorageEntry`: `objects` (files or objects) and `common_prefixes` (groups). The prefix means slightly different things on different stores, because filesystems have directories and object stores do not:

- On local and SFTP stores, `prefix` is an exact path. A file path selects that file; a directory path selects the files beneath it. `reports` never matches a sibling called `reports-old`. A missing path returns an empty result.
- On S3 the prefix is a literal key prefix. `2026/` selects every key that starts with `2026/`; `2026/q1.csv` would also match `2026/q1.csv.bak`.

With the default `delimiter="/"` you get one level: immediate files in `objects` and immediate subdirectories or key groups in `common_prefixes`, as entries of type `EntryType.PREFIX`. With `delimiter=None` the listing recurses and returns every file below the prefix. `max_results` caps the combined count of both tuples. The facade default of `"/"` differs from the backend protocol default of `None`, so code that calls a backend directly gets a recursive listing.

Given the same three files in a local directory and under a key prefix in the bucket, both stores list them the same way:

```python
for key in ("2026/q1.csv", "2026/q2.csv", "2026/archive/q4.csv"):
    local.write(f"{root}/inventory/{key}", b"region,total\n")
    s3.write(f"s3://reports/inventory/{key}", b"region,total\n")

for storage, prefix in ((local, f"{root}/inventory/2026"), (s3, "s3://reports/inventory/2026/")):
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
    On the S3 family, a listing with `max_results` asks for pages of at most that many keys and stops fetching once it has enough entries, so a small limit on a large prefix costs one request. `max_results=0` makes no request.

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

### What a write returns

`write`, `write_stream`, `copy`, `move` and `copy_between` return the `StorageEntry` of what they created. The type is the same on every backend; what differs is which fields the store reports. An empty field (`""` or `None`) means the store did not report it. A write never spends an extra request to fill one in, so a result can say less than a later `metadata()` call on the same path.

`size` is the number of bytes stored. With a pipeline that is the encoded size, for example the compressed length, not the length of the data you passed.

| Backend | Operation | Always filled | Also filled when the store reports it |
|---|---|---|---|
| local | write | path, name, size, last_modified | — |
| local | copy | path, name, size, last_modified | — |
| local | move | path, name, size, last_modified | — |
| sftp | write | path, name, size, last_modified | — |
| sftp | move | path, name, size, last_modified | — |
| s3 | write | path, name, size, etag | version_id (versioned buckets), checksum |
| s3 | copy | path, name, etag | last_modified, version_id (versioned buckets), checksum |
| http | write | path, name, size | etag, last_modified, content_type, checksum |

Where a result reports less than `metadata()`:

- An S3 write reports no `last_modified`, because S3's upload responses do not carry it.
- An S3 copy reports no `size`, because S3's copy responses do not carry it.
- An HTTP write reports only the validators the server sends back with the `PUT` response.

On S3 the ETag and version come from the upload's or copy's own response, never from a later lookup, so on a versioned bucket they identify the version this call wrote even if another writer replaces the object straight afterwards. A large upload or copy runs as several requests on boto3's worker threads; the package captures the final response from the client. If another write to the same key runs through the same facade at the same moment, the two responses cannot be told apart, and `etag`, `version_id` and `checksum` are left empty rather than risk describing the other write.

SFTP results come from the size check paramiko already makes after an upload and, for `move`, one `lstat` after the rename. A moved symbolic link is described as the link itself.

```python
entry = s3.write("s3://reports/2026/sales.csv", b"region,total\nnorth,120\n")
print(entry.size, entry.etag != "", entry.last_modified)
```

Output:

```text
23 True None
```

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

### Deleting many paths

`delete_many(paths)` deletes every path in an iterable and attempts all of them, even after a failure. Unlike `delete()`, a path that is already gone counts as deleted on every store, so the same cleanup code behaves the same on local disk, SFTP and S3.

- On S3 the paths are grouped by bucket and deleted with `DeleteObjects`, one request per 1,000 keys. A key repeated in the input is sent once.
- Local and SFTP have no batch delete, so they delete one path at a time; SFTP retries each delete as it would a single `delete()`.
- Every path is checked against the location policy before anything is deleted. A path outside the allowed root raises at once, and nothing is removed.

If any path cannot be deleted, `delete_many` raises one `BulkDeleteError` at the end. Its `failures` attribute lists, in input order, each path that remains with the storage error it raised (for example `PermissionDeniedError`); every other path is gone. A directory is not a file, so a directory path fails here as it does with `delete()`.

```python
from mountainash_transport import BulkDeleteError

for name in ("a.csv", "b.csv"):
    local.write(f"{root}/old/{name}", b"x")
local.mkdir(f"{root}/old/keep")
try:
    local.delete_many(f"{root}/old/{name}" for name in ("a.csv", "missing.csv", "keep", "b.csv"))
except BulkDeleteError as error:
    print(error.failures[0][0].rsplit("/", 1)[-1], type(error.failures[0][1]).__name__)
print(sorted(entry.name for entry in local.list_dir(f"{root}/old")))
```

Output:

```text
keep StorageError
['keep']
```

<!-- concept:154 -->

### Directory operations

Local and SFTP stores have real directories and support three directory methods. Object stores have only key prefixes, so the S3 family and HTTP raise `UnsupportedOperationError`; check with `supports(StorageDirectoryProtocol)` if your code must work with both.

- `list_dir(path)` returns a list of `StorageEntry`, one per immediate child, with `entry_type` set to `FILE` or `DIRECTORY`. A missing path raises `PathNotFoundError`, and a path that is a file raises a storage error rather than returning an empty list.
- `mkdir(path, parents=True)` creates the directory and any missing ancestors, and accepts a directory that already exists. With `parents=False`, only the final directory is created, and a missing parent or an existing destination raises. Recursive creation is not atomic: ancestors created before a failure remain.
- `rmdir(path)` removes an empty directory; a non-empty one raises `StorageError` and is left untouched. `rmdir(path, recursive=True)` removes the directory and everything inside it, removing symbolic links rather than following them. A missing path raises `PathNotFoundError`, and a file or a link to a directory is refused in both modes. Local and SFTP behave the same.

```python
from mountainash_transport import PathNotFoundError, StorageError

folder = f"{root}/projects/2026"
local.mkdir(folder)                           # parents=True by default
local.write(f"{folder}/q1.csv", b"region,total\n")
local.mkdir(f"{folder}/archive")

for entry in sorted(local.list_dir(folder), key=lambda e: e.name):
    print(entry.name, entry.entry_type.value, entry.size)

try:
    local.mkdir(f"{root}/missing/child", parents=False)
except PathNotFoundError as error:
    print("parents=False:", type(error).__name__)

try:
    local.rmdir(f"{root}/projects")          # not empty: refused
except StorageError as error:
    print("rmdir:", type(error).__name__)
local.rmdir(f"{root}/projects", recursive=True)
print(local.exists(f"{root}/projects"))
```

Output:

```text
archive directory None
q1.csv file 13
parents=False: PathNotFoundError
rmdir: StorageError
False
```

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

`copy(source, destination)` copies one file to another path in the same store and returns the copy's `StorageEntry` ([What a write returns](#what-a-write-returns)). Both paths go through the same facade.

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

An S3-family `copy()` stays server side at any size: objects under 4 GiB are copied with one `CopyObject` request, larger ones with multipart `UploadPartCopy`, below every provider's [single-request copy limit](../14-backends/index.md#where-backends-differ).

To copy between two different stores, for example from SFTP to S3, or to copy within SFTP, use `copy_between()`, which streams from one facade into another and can apply transforms on the way ([Copying between backends](../10-stream-transforms/index.md#copying-between-backends)).

## Moving

`move(source, destination, *, create_parents=True)` renames a file in the same store with the store's own rename, so it is atomic where the store's rename is: `os.replace` on local disk (within one filesystem) and the OpenSSH `posix-rename@openssh.com` extension on SFTP. An existing destination is replaced. Missing parent directories are created unless `create_parents=False`, in which case the missing parent raises `PathNotFoundError`. A missing source raises `PathNotFoundError`, and both paths are checked against the location policy. It returns the moved entry's `StorageEntry`.

```python
for folder in (root, f"{root}/outbox"):
    local.write(f"{folder}/draft.csv", b"region,total\n")
local.move(f"{root}/draft.csv", f"{root}/outbox/draft.csv")   # replaces the existing file
print(local.exists(f"{root}/draft.csv"), local.read(f"{root}/outbox/draft.csv"))
```

Output:

```text
False b'region,total\n'
```

The S3 family and HTTP have no rename and raise `UnsupportedOperationError`; on S3, copy and then delete if a non-atomic move is acceptable. A local move to another filesystem raises `StorageError` and leaves the source in place. SFTP servers without the OpenSSH extension raise `StorageError` as well, because plain SFTP rename refuses an existing destination.

## Presigned URLs

`presign(path, *, method="GET", expires_in=3600, content_type=None)` returns a URL that lets anyone who has it read (`GET`) or upload (`PUT`) one object for a limited time, without credentials, for example a browser or another service. Only the S3 family signs URLs; local, SFTP and HTTP stores raise `UnsupportedOperationError`. The path is checked against the location policy like any other.

```python
url = s3.presign("s3://reports/2026/sales.csv", expires_in=900)
upload = s3.presign("s3://reports/incoming/sales.csv", method="PUT", content_type="text/csv")
```

- **Signing.** URLs are signed with AWS Signature Version 4 against the client's own endpoint, so R2, MinIO, B2 and S3 Express URLs point at their own hosts. Signing happens locally, without a request, except on S3 Express (below).
- **`content_type`.** Allowed only with `PUT`. It is signed into the URL, so the uploader must send exactly that `Content-Type` header or the store rejects the upload. An empty string is a value to sign, not "no content type".
- **Credential lifetime.** The URL is only as long-lived as the credentials that signed it. With temporary credentials (assume-role, SSO, session tokens) it stops working when they expire, whatever `expires_in` says.
- **S3 Express.** Directory buckets sign with a session from `CreateSession`. That may be a request, needs the `s3express:CreateSession` permission, and limits the URL to the session's lifetime, which is minutes. A denied session raises `PermissionDeniedError`.

These calls raise `ValueError` before anything is signed:

| Call | Reason |
|---|---|
| `presign(path, method="DELETE")` | Only `GET` and `PUT` are supported |
| `presign(path, expires_in=0)` or `expires_in=604801` | The range is 1 second to 604,800 seconds (7 days), the Signature Version 4 maximum |
| `presign(path, content_type="text/csv")` | `content_type` applies to `PUT` only |
| `presign(path, method="PUT", content_type="application/x-www-form-urlencoded; charset=utf-8")` | botocore leaves exactly this value out of the signature, so the URL could not enforce it |
