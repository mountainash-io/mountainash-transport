# Storage Protocol Redesign

## Context

mountainash-transport's storage backends implement granular protocols à la
carte (Read, Write, Delete, Copy, Metadata, List, Directory). The current
`StorageListProtocol` conflates bucket/object-store semantics (prefix
enumeration) with filesystem semantics (directory listing) — `list_files`
does a flat prefix match while `list_directories` uses a delimiter, but
both live on the same protocol. HTTP backends implement neither but the
protocol doesn't model that cleanly.

The return type `FileMetadata` is a Pydantic BaseModel that's too heavy for
listing thousands of entries and can't distinguish files from directories.

## Problem

**Three storage models, one protocol:**
1. **Bucket/object stores** (S3, GCS, Azure Blob) — flat namespace, prefix
   matching, virtual directories via delimiter. No real directories.
2. **Filesystem stores** (local, SFTP, SMB, FTP) — real directory hierarchy,
   `stat()`/`scandir()` semantics, directories must be created and removed.
3. **HTTP endpoints** — single-resource operations (GET, PUT, HEAD). No
   listing capability at all.

`StorageListProtocol` tries to serve all three, serving none well.

**`FileMetadata` limitations:**
- Pydantic BaseModel — validation overhead on construction, wasteful for
  bulk listing results.
- No `entry_type` field — can't distinguish files from directories.
- Redundant fields — `filename` is derivable from `full_path`, `directory`
  is derivable from `full_path`.
- Name implies files only — misleading for directory entries.

## Design

### StorageEntry (replaces FileMetadata)

A single frozen dataclass representing any storage resource — file,
directory, or object-store prefix.

```python
class EntryType(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    PREFIX = "prefix"

@dataclass(frozen=True, slots=True)
class StorageEntry:
    path: str
    name: str
    size: int | None = None
    last_modified: datetime | None = None
    etag: str = ""
    content_type: str = ""
    entry_type: EntryType = EntryType.FILE
    storage_class: str = ""
    source: str = ""
    version_id: str = ""
    checksum: str = ""
    checksum_algorithm: str = ""
```

Every method that returns "information about a resource" returns
`StorageEntry`. Listing, stat, HEAD — same shape. `entry_type`
distinguishes what the entry represents.

**Field semantics:**
- `path` — fully-qualified identifier (`s3://bucket/key`,
  `/home/user/file.txt`, `https://example.com/resource`).
- `name` — last path segment. For `PREFIX` entries, no trailing slash
  (e.g., `data` not `data/`). For `DIRECTORY` entries, no trailing
  slash. For `FILE` entries, the filename.
- `size` — `None` means unknown (HTTP without Content-Length, directories,
  prefixes). `0` means genuinely zero bytes.
- `content_type` — populated from HTTP `Content-Type` header or
  filesystem MIME detection. Empty string when unavailable.
- `version_id` — provider-specific version identifier. S3: `VersionId`.
  Azure: `x-ms-version-id`. GCS: `generation` (as string). Empty for
  unversioned objects and filesystem entries. Populated from
  `head_object` and `list_object_versions` responses; standard
  `list_objects_v2` does not return version IDs.
- `checksum` — base64-encoded checksum value, normalised from whatever
  encoding the SDK returns. Populated from the strongest available
  algorithm in the SDK response (preference order:
  SHA256 > CRC32C > CRC32 > SHA1 > MD5). Empty when unavailable.
  Single-value by design — callers needing all checksums access the
  backend directly.
- `checksum_algorithm` — algorithm name (e.g., `"SHA256"`, `"CRC32C"`,
  `"MD5"`). Tells the consumer how to interpret `checksum`. Empty when
  `checksum` is empty. Values are normalised to uppercase, no hyphens.

**Checksum population by backend:**
- **S3** — `head_object` returns `ChecksumSHA256`, `ChecksumCRC32C`,
  `ChecksumCRC32`, `ChecksumSHA1`. Pick strongest available
  (SHA256 > CRC32C > CRC32 > SHA1). Values are already base64.
  `list_objects_v2` returns `ChecksumAlgorithm` (list of enabled
  algorithms) but not values — checksum is empty in list results.
- **Azure Blob** — `Content-MD5` header → `checksum="...", algorithm="MD5"`.
- **GCS** — `crc32c` and `md5Hash` properties. Prefer CRC32C.
- **HTTP** — `Content-MD5` header when present.
- **Local / SFTP** — empty (no native checksum).

**Changes from FileMetadata:**
- Dropped: `filename` (redundant with `name`), `directory` (derivable
  from `path`)
- Added: `entry_type`, `content_type`, `version_id`, `checksum`,
  `checksum_algorithm`
- Changed: `size` from `int` to `int | None`, `checksum` from
  `List[str]` to single `str` value with separate `checksum_algorithm`
- Renamed: `full_path` → `path`
- Base: Pydantic `BaseModel` → `@dataclass(frozen=True, slots=True)`

`FileMetadata` is deleted. No compatibility shim.

### EnumerateResult

Structured return type for object-store listings.

```python
@dataclass(frozen=True, slots=True)
class EnumerateResult:
    objects: tuple[StorageEntry, ...]
    common_prefixes: tuple[StorageEntry, ...]
```

Uses `tuple` rather than `list` so the frozen dataclass is deeply
immutable — callers cannot accidentally mutate the result.

- `objects` — entries with `entry_type=FILE`. Real zero-byte objects
  whose keys end in the delimiter (e.g., `data/`) appear here as
  `entry_type=FILE` with `size=0` — they are real objects, not virtual
  prefixes, even though their key looks like a prefix.
- `common_prefixes` — entries with `entry_type=PREFIX`. The backend
  populates `path`, `name`, `source`, and `entry_type`. Size and
  timestamps are `None`/empty (prefixes are virtual).

Common prefixes are `StorageEntry` rather than plain strings so the
backend can normalize names and set the source field. The facade does
not need to synthesize `PREFIX` entries — they come from the backend
directly.

`list_objects` fully materializes the result — pagination is hidden
internally via the SDK paginator. `max_results` caps the total number
of entries returned (objects + common prefixes combined). For extremely
large buckets, streaming/paged iteration is a future concern.

### Protocol Set (7 protocols)

**Unchanged (5):**

| Protocol | Methods |
|----------|---------|
| `StorageReadProtocol` | `read_to_bytes(path) -> bytes`, `read_to_stream(path) -> BinaryIO` |
| `StorageWriteProtocol` | `write_from_bytes(path, data)`, `write_from_stream(path, stream)` |
| `StorageDeleteProtocol` | `delete_file(path)` |
| `StorageCopyProtocol` | `copy(source, destination)` |
| `StorageMetadataProtocol` | `get_metadata(path) -> StorageEntry`, `path_exists(path) -> bool`, `get_size(path) -> int | None` |

`StorageMetadataProtocol.get_metadata()` return type changes from
`FileMetadata` to `StorageEntry`. `get_size()` return type changes
from `int` to `int | None` to align with `StorageEntry.size` — HTTP
resources without `Content-Length` and directories return `None`.

**Replaced (2):**

#### StorageEnumerateProtocol (replaces StorageListProtocol)

Native bucket/object-store semantics. Prefix matching with optional
delimiter for virtual directory grouping.

```python
@runtime_checkable
class StorageEnumerateProtocol(Protocol):
    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult: ...
```

- No delimiter → flat prefix match, all objects recursively.
  `common_prefixes` is empty.
- `delimiter="/"` → immediate objects in `.objects` + virtual directory
  entries in `.common_prefixes`.
- `max_results` caps the total number of entries returned (objects +
  common prefixes combined). `None` means no limit. Backends apply
  the cap after materializing all pages — SDK pagination is hidden
  internally.
- Implemented by: S3, GCS, Azure Blob, R2, MinIO, B2.

#### StorageDirectoryProtocol (reworked)

Native filesystem semantics. Real directories with immediate children.

```python
@runtime_checkable
class StorageDirectoryProtocol(Protocol):
    def list_dir(self, path: str) -> list[StorageEntry]: ...
    def mkdir(self, path: str, *, parents: bool = True) -> None: ...
    def rmdir(self, path: str) -> None: ...
```

- `list_dir` returns immediate children with `entry_type` set to
  `FILE` or `DIRECTORY`.
- **Symlink policy:** symlinks are resolved via `stat()` (not
  `lstat()`). A symlink to a directory appears as `DIRECTORY`, a
  symlink to a file appears as `FILE`. Broken symlinks (dangling
  targets) are skipped — they do not appear in the result. Symlinks
  pointing outside the backend's `ROOT_PATH` are skipped silently
  (containment rule — see Root Path Normalization). No
  `EntryType.SYMLINK` — consumers see resolved targets only.
- `mkdir` creates a directory, optionally with parents.
- `rmdir` removes an empty directory.
- Implemented by: Local, SFTP, SMB, FTP, Azure Files.

### Backend Protocol Composition

| Backend | Read | Write | Delete | Copy | Metadata | Enumerate | Directory |
|---------|------|-------|--------|------|----------|-----------|-----------|
| **S3** | Y | Y | Y | Y | Y | Y | — |
| **Local** | Y | Y | Y | Y | Y | — | Y |
| **SFTP** | Y | Y | Y | — | Y | — | Y |
| **HTTP** | Y | Y | — | — | Y | — | — |
| *GCS* | Y | Y | Y | Y | Y | Y | — |
| *Azure Blob* | Y | Y | Y | Y | Y | Y | — |
| *Azure Files* | Y | Y | Y | — | Y | — | Y |
| *FTP* | Y | Y | Y | — | Y | — | Y |
| *SMB* | Y | Y | Y | — | Y | — | Y |

Most backends implement one listing protocol, not both. Azure is split
by `SERVICE_TYPE` — Blob gets Enumerate, Files gets Directory.

A future backend (e.g., ADLS Gen2 with hierarchical namespace) may
implement both protocols. The protocol system is additive — this is
supported. The facade exposes both `list_objects()` and `list_dir()`
independently, so backends implementing both protocols make both
methods available.

### Root Path Normalization

Each storage model interprets "root" differently. The protocol methods
receive paths after the facade/caller has resolved the scheme:

- **Bucket stores** — prefix is the key prefix within the bucket
  (e.g., `"data/"`, `""`). The bucket is resolved from the connection
  profile, not from the prefix string.
- **Filesystem stores** — path is an absolute filesystem path
  (e.g., `"/home/user"`, `"/"`). The backend's root may be scoped
  by the profile's `ROOT_PATH`.
- **HTTP** — path is a full URL. Not applicable to listing.

`StorageEntry.path` is always fully qualified — `s3://bucket/key`,
`/absolute/path`, `https://host/resource`. The backend constructs
this from its context (bucket name, root path, base URL) so the
consumer never sees a relative path.

**Filesystem path containment:** When a backend has a configured
`ROOT_PATH`, all operations are confined to that subtree. Paths are
resolved to their real path (`os.path.realpath()`) before use.
Operations on paths that resolve outside `ROOT_PATH` raise
`PathNotFoundError` — the backend treats them as non-existent rather
than leaking information about the host filesystem. `../` sequences,
absolute paths outside the root, and symlinks pointing outside the
root are all caught by this check. SFTP backends apply the same
containment logic using SFTP `stat()` + prefix check.

### Facade Listing API

No unified `list()` method. The two storage models have fundamentally
different semantics — prefix enumeration vs directory hierarchy — and
a unified method either loses information or becomes complex enough to
negate the abstraction. Consumers know which storage model they
configured and call the matching method.

```python
class StorageFacade:
    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = "/",
        max_results: int | None = None,
    ) -> EnumerateResult:
        """Bucket-store listing. Requires StorageEnumerateProtocol."""
        ...

    def list_dir(self, path: str) -> list[StorageEntry]:
        """Filesystem listing. Requires StorageDirectoryProtocol."""
        ...
```

Both methods are 1:1 pass-throughs to the corresponding protocol —
no translation layer, no information loss.

- `list_objects()` delegates to `StorageEnumerateProtocol.list_objects()`.
  Raises `UnsupportedOperationError` on filesystem/HTTP backends.
- `list_dir()` delegates to `StorageDirectoryProtocol.list_dir()`.
  Raises `UnsupportedOperationError` on bucket-store/HTTP backends.

For truly backend-agnostic code, consumers can branch on
`facade.supports(StorageEnumerateProtocol)` vs
`facade.supports(StorageDirectoryProtocol)`.

**`facade.mkdir()` / `facade.rmdir()`** delegate to
`StorageDirectoryProtocol` if available, raise
`UnsupportedOperationError` otherwise.

### Error Contract

All protocol methods raise exceptions from the existing `StorageError`
hierarchy. Backends wrap provider-specific exceptions into these types
so consumers can write portable error handling.

| Condition | Exception | Notes |
|-----------|-----------|-------|
| Resource not found | `PathNotFoundError` | `get_metadata`, `read_*`, `delete_file`, `list_dir` on missing path |
| Permission denied | `AuthenticationError` | S3 403, SFTP permission error, filesystem `PermissionError` |
| Backend unreachable | `StorageConnectionError` | Network errors, timeout, connection refused |
| Operation not supported | `UnsupportedOperationError` | Protocol not implemented by backend |
| Transform failure | `TransformError` | Pipeline encode/decode errors |
| Path escapes root | `PathNotFoundError` | Containment violation treated as not-found (no info leak) |

`list_objects()` and `list_dir()` do not return partial results — if
pagination fails mid-way, the backend raises `StorageError` rather
than returning what it has so far. Partial-result semantics are a
future concern alongside streaming/paged iteration.

No new exception types are introduced. The existing hierarchy is
sufficient.

### Backend Changes

**S3StorageBackend:**
- `S3ListMixin` → `S3EnumerateMixin` implementing
  `list_objects(prefix, *, delimiter, max_results) -> EnumerateResult`.
- Populates `StorageEntry` from `list_objects_v2` response fields
  (`Key`, `Size`, `LastModified`, `ETag`, `StorageClass`).
- `common_prefixes` populated as `StorageEntry(entry_type=PREFIX)`
  from `CommonPrefixes[].Prefix`.
- `get_metadata()` returns `StorageEntry` instead of `FileMetadata`.
  Populates `version_id` from `head_object` `VersionId` field.
  Populates `checksum` + `checksum_algorithm` from the strongest
  available `Checksum*` field (SHA256 > CRC32C > CRC32 > SHA1 > MD5).

**LocalStorageBackend:**
- Replaces current list methods with `list_dir(path)` using
  `os.scandir()`.
- Each `DirEntry` from scandir maps to `StorageEntry` with
  `entry_type=FILE` or `DIRECTORY` based on `entry.is_dir()`
  (follows symlinks).
- `mkdir`/`rmdir` already exist, signatures unchanged.
- `get_metadata()` returns `StorageEntry`.

**SFTPStorageBackend:**
- `list_paths()` → `list_dir(path)` returning `StorageEntry` items.
  Uses `sftp.listdir_attr()`, sets `entry_type` from
  `stat.st_mode & S_ISDIR`.
- Gains `mkdir(path)` → `sftp.mkdir()` and `rmdir(path)` →
  `sftp.rmdir()`.
- `get_metadata()` returns `StorageEntry`.

**HTTPStorageBackend:**
- No listing changes (implements neither protocol).
- `get_metadata()` returns `StorageEntry` with `content_type`
  populated from the `Content-Type` response header. `checksum`
  populated from `Content-MD5` header when present.

## Migration Impact

**Deleted:**
- `FileMetadata` class
- `StorageListProtocol`
- `S3ListMixin.list_files()` / `list_directories()`

**Modified:**
- `StorageMetadataProtocol` return type
- `StorageDirectoryProtocol` gains `list_dir()`
- All four backends' `get_metadata()` methods
- S3/Local/SFTP listing implementations
- `StorageFacade` replaces `list_files()`/`list_directories()` with
  `list_objects()` and `list_dir()`
- Top-level `__init__.py` exports

**Test impact:**
- All tests referencing `FileMetadata` update to `StorageEntry`
- S3 list tests rewritten for `list_objects()` + `EnumerateResult`
- Local/SFTP list tests rewritten for `list_dir()` + `StorageEntry`
- Facade `list_objects()` and `list_dir()` tests added
- S3 `get_metadata()` tests verify `version_id`, `checksum`,
  `checksum_algorithm` population
- HTTP `get_metadata()` tests verify `content_type` and `Content-MD5`
  checksum population
- Protocol conformance tests updated

## Verification

After implementation:
1. `hatch run test:test-quick` — all tests pass
2. `hatch run ruff:check` — lint clean
3. `StorageEntry` used everywhere `FileMetadata` was
4. Facade `list_objects()` works for S3 backend
5. Facade `list_dir()` works for Local and SFTP backends
6. S3 `get_metadata()` populates checksum and version_id fields
