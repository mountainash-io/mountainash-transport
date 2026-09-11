---
title: "Chapter 8: S3 Backend"
description: "The unified S3-family backend handling AWS S3, S3 Express, Cloudflare R2, MinIO, and B2 through flavor dispatch"
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 8: S3 Backend

## Summary

This chapter covers the S3-family storage backend that handles AWS S3, S3
Express One Zone, Cloudflare R2, MinIO, and other S3-compatible services through
a unified interface. It introduces the S3StorageBackend class, the Boto3 client
wrapper, and the seven protocol mixins (Connection, Read, Write, List, Delete,
Metadata, Copy). Readers learn how the S3 Flavor Dispatch mechanism uses the
Provider Type enum to select provider-specific behavior for each of the four
supported flavors.

## Concepts Covered

- S3StorageBackend Class
- S3ConnectionMixin
- S3ReadMixin
- S3WriteMixin
- S3ListMixin
- S3DeleteMixin
- S3MetadataMixin
- S3CopyMixin
- Boto3 Client
- S3 Flavor Dispatch
- AWS S3 Flavor
- S3 Express One Zone Flavor
- Cloudflare R2 Flavor
- MinIO Flavor

## Learning Graph IDs

63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76

## Prerequisites

- Chapter 1: Foundation Concepts (Cloud Object Storage, Mixin Pattern, Registry Pattern)
- Chapter 2: Storage Protocols (StorageConnectionProtocol through StorageCopyProtocol)
- Chapter 4: Settings and Configuration (Provider Type Enum)

---

## One Backend, Five Providers

Amazon S3's API has become the de facto standard for object storage. Cloudflare R2, MinIO, Backblaze B2, and AWS's own S3 Express One Zone all implement the S3 API with minor variations. Rather than maintaining five separate backends with largely duplicated code, mountainash-transport consolidates them into a single `S3StorageBackend` class that dispatches provider-specific behavior through a flavor mechanism.

The key insight is that these services differ primarily in how they *connect* (endpoint URL, region handling, addressing style) but share the same *operations* (get_object, put_object, list_objects_v2, delete_object, copy_object). The mixin architecture places all connection-time flavor logic in `S3ConnectionMixin` while the operation mixins remain provider-agnostic.

<!-- concept:63 -->
## S3StorageBackend Class

The `S3StorageBackend` class is registered against five provider types using stacked decorators:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.R2)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.MINIO)
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.B2)
class S3StorageBackend(
    S3ConnectionMixin,
    S3ReadMixin,
    S3WriteMixin,
    S3ListMixin,
    S3DeleteMixin,
    S3MetadataMixin,
    S3CopyMixin,
):
    def __init__(self, auth_params: Any) -> None:
        self.auth_params = auth_params
        self._client: Any = None
```

Five decorator invocations register the same class for five different enum values. When `StorageFacade(CONST_STORAGE_PROVIDER_TYPE.R2, auth_params)` is called, the registry returns `S3StorageBackend` -- the same class that handles `S3`, `S3EXPRESS`, `MINIO`, and `B2`.

The class composes seven mixins (not eight -- there is no directory mixin). This reflects the fundamental nature of object storage: S3-compatible services do not have real directories. The `StorageDirectoryProtocol` is intentionally unimplemented, so calling `facade.mkdir()` on an S3-backed facade raises `UnsupportedOperationError`.

Backwards-compatible aliases (`R2StorageBackend`, `S3ExpressStorageBackend`, `MinIOStorageBackend`, `B2StorageBackend`) are exported for legacy code that imported per-flavor backend classes.

<!-- concept:71 -->
## Boto3 Client

**Boto3** is the AWS SDK for Python and the underlying library that all S3 operations use. The `S3StorageBackend` wraps a `boto3.client("s3", ...)` instance, stored as `self._client`. All seven mixins access this client to make API calls.

The boto3 client is created lazily -- `self._client` starts as `None` and is populated when `connect()` is called. This allows the backend to be instantiated without immediately requiring network access. The client creation call looks like:

```python
self._client = boto3.client("s3", **kwargs)
```

The `kwargs` dictionary contains endpoint URL, region, credentials, SSL settings, and botocore configuration -- all resolved by the flavor dispatch mechanism in `S3ConnectionMixin`.

Key boto3 client methods used by the mixins:

| boto3 Method | Storage Protocol | Purpose |
|---|---|---|
| `get_object` | StorageReadProtocol | Download object body |
| `put_object` | StorageWriteProtocol | Upload bytes |
| `upload_fileobj` | StorageWriteProtocol | Stream upload (multipart) |
| `list_objects_v2` | StorageListProtocol | List objects by prefix |
| `delete_object` | StorageDeleteProtocol | Remove an object |
| `head_object` | StorageMetadataProtocol | Get object metadata |
| `copy_object` | StorageCopyProtocol | Server-side copy |

<!-- concept:64 -->
## S3ConnectionMixin

The **`S3ConnectionMixin`** handles boto3 client creation with flavor-aware configuration. It accepts three shapes of `auth_params` for backwards compatibility:

1. **S3Settings profile** (preferred): a descriptor-driven settings object with `to_handler_kwargs()` that returns a ready-made kwargs dict.
2. **Legacy `.settings` wrapper**: an older-style object exposing `ENDPOINT_URL`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, `REGION`, and optional `FLAVOR` attributes.
3. **None**: the backend is instantiated without credentials (test fixture scenario where `_client` is set manually).

The `connect()` method resolves kwargs and creates the client:

```python
def connect(self) -> None:
    try:
        import boto3
        kwargs = self._resolve_kwargs()
        kwargs.pop("service_name", None)
        self._client = boto3.client("s3", **kwargs)
    except Exception as exc:
        raise StorageConnectionError(f"Failed to create S3 client: {exc}")
```

The `disconnect()` method sets `self._client = None`, and `is_connected()` returns `self._client is not None`. This simple state model means reconnection is achieved by calling `connect()` again.

<!-- concept:72 -->
## S3 Flavor Dispatch

**Flavor dispatch** is the mechanism by which the single `S3StorageBackend` adapts its connection behavior for different S3-compatible providers. The `FLAVOR` field (defaulting to `"aws"`) determines how the endpoint URL, region, and addressing style are resolved.

The dispatch happens inside `_resolve_kwargs()` for legacy settings, or in the settings adapter (`adapters/s3.py`) for the preferred profile path. The five supported flavors produce different connection configurations:

#### Diagram: S3 Flavor Dispatch

<iframe src="../../sims/s3-flavor-dispatch/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>S3 Flavor Dispatch</summary>
Type: diagram
**sim-id:** s3-flavor-dispatch<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show how the FLAVOR field routes through the connection mixin to produce different boto3 client configurations for each provider.

**Components:**

- Central decision node: "FLAVOR value"
- Five branches: aws, express, r2, minio, b2
- Each branch shows: endpoint_url, region_name, addressing_style, special settings
- Color coding: AWS blue, R2 orange, MinIO dark green, B2 red, Express teal

**Interactions:** Click a flavor to see its full configuration details. Hover over configuration values to see why they differ from the default. Toggle between "Settings profile" and "Legacy settings" to see both resolution paths.

**Learning Objective:** Compare how flavor dispatch produces different boto3 configurations (Bloom: Analyze)
</details>

<!-- concept:73 -->
## AWS S3 Flavor

The **AWS S3 flavor** (`FLAVOR="aws"`) is the default and most straightforward configuration:

- **Endpoint URL**: `None` -- boto3's default resolver handles region-based endpoint selection.
- **Region**: the configured `REGION` value (default `"us-east-1"`).
- **Addressing style**: configurable (`"auto"`, `"path"`, or `"virtual"`); defaults to `"auto"`.
- **Special features**: supports Transfer Acceleration (`ACCELERATE_ENDPOINT=True`) and dual-stack IPv6 endpoints (`DUALSTACK_ENDPOINT=True`).

Standard AWS S3 uses virtual-hosted addressing by default (`bucket.s3.region.amazonaws.com`) and supports the full S3 API without restrictions.

<!-- concept:74 -->
## S3 Express One Zone Flavor

The **S3 Express One Zone flavor** (`FLAVOR="express"`) targets AWS's single-AZ, low-latency storage tier:

- **Endpoint URL**: `None` -- the SDK auto-detects the endpoint from the bucket name (Express One Zone buckets have a distinctive naming convention).
- **Region**: the configured `REGION` value.
- **Addressing style**: forced to `"virtual"` regardless of configuration -- S3 Express requires virtual-hosted addressing.
- **Special features**: none (acceleration and dualstack are not supported).

S3 Express One Zone is designed for latency-sensitive workloads that do not require multi-AZ durability. The backend treats it identically to standard S3 for all operations; only the connection parameters differ.

<!-- concept:75 -->
## Cloudflare R2 Flavor

The **Cloudflare R2 flavor** (`FLAVOR="r2"`) targets Cloudflare's S3-compatible storage with zero egress fees:

- **Endpoint URL**: `https://{ACCOUNT_ID}.r2.cloudflarestorage.com` (auto-derived from `ACCOUNT_ID`, or explicit `ENDPOINT_URL`).
- **Region**: always `"auto"` -- R2 requires this specific value.
- **Addressing style**: configurable (defaults to `"auto"`).
- **Required**: either `ACCOUNT_ID` or `ENDPOINT_URL` must be provided; the adapter raises `ValueError` if both are missing.

R2's `region_name="auto"` requirement is the most notable flavor-specific behavior. Standard boto3 defaults to `"us-east-1"`, which would cause authentication failures against R2's endpoint.

<!-- concept:76 -->
## MinIO Flavor

The **MinIO flavor** (`FLAVOR="minio"`) targets self-hosted MinIO instances:

- **Endpoint URL**: must be provided explicitly (e.g., `http://minio.local:9000`). The adapter raises `ValueError` if not set.
- **Region**: the configured `REGION` value (may be arbitrary for self-hosted instances).
- **Addressing style**: configurable; often set to `"path"` for MinIO deployments behind reverse proxies.
- **SSL**: often disabled (`USE_SSL=False`) for local development instances.

MinIO is the most common choice for local S3-compatible development environments. Its flavor requires explicit endpoint configuration because there is no standard URL template to derive from.

The library also supports **Backblaze B2** (`FLAVOR="b2"`) with endpoint URL template `https://s3.{REGION}.backblazeb2.com`.

<!-- concept:65 -->
## S3ReadMixin

The **`S3ReadMixin`** downloads objects using boto3's `get_object` API:

```python
class S3ReadMixin:
    def read_to_bytes(self, path: str) -> bytes:
        bucket, key = parse_s3_path(path)
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def read_to_stream(self, path: str) -> BinaryIO:
        data = self.read_to_bytes(path)
        return io.BytesIO(data)
```

All S3 paths are parsed by the `parse_s3_path` utility, which accepts both `s3://bucket/key` and `bucket/key` formats and returns a `(bucket, key)` tuple. This normalization is shared across all S3 mixins.

The current `read_to_stream` implementation buffers the entire object in memory (`BytesIO`). This is a known limitation for very large objects -- a streaming implementation using boto3's `StreamingBody` directly would avoid this buffer but introduces complexity around connection lifecycle management.

<!-- concept:66 -->
## S3WriteMixin

The **`S3WriteMixin`** uploads objects using two different boto3 APIs depending on the input type:

```python
class S3WriteMixin:
    def write_from_bytes(self, path: str, data: bytes) -> None:
        bucket, key = parse_s3_path(path)
        self._client.put_object(Bucket=bucket, Key=key, Body=data)

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        bucket, key = parse_s3_path(path)
        self._client.upload_fileobj(stream, bucket, key)
```

The `write_from_bytes` method uses `put_object` -- a single HTTP PUT request suitable for objects up to 5 GB. The `write_from_stream` method uses `upload_fileobj`, which automatically uses multipart upload for large objects (splitting them into parts and uploading in parallel) while using a single PUT for small ones. This means callers do not need to manage multipart upload logic themselves.

<!-- concept:67 -->
## S3ListMixin

The **`S3ListMixin`** uses the `list_objects_v2` paginator to handle buckets with thousands of objects:

```python
class S3ListMixin:
    def list_files(self, prefix: str) -> list[FileMetadata]:
        bucket, key_prefix = parse_s3_path(prefix)
        results = []
        paginator = self._client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=key_prefix)
        for page in pages:
            for obj in page.get("Contents", []):
                # ... build FileMetadata
        return results

    def list_directories(self, prefix: str) -> list[str]:
        # Uses Delimiter="/" to get CommonPrefixes
        ...
```

The `list_files` method omits the `Delimiter` parameter, returning all objects under the prefix regardless of depth. The `list_directories` method uses `Delimiter="/"` to get only the immediate "directory" level -- the `CommonPrefixes` in S3 terminology.

Both methods use boto3's paginator, which automatically handles the 1,000-object-per-response limit by issuing multiple API calls transparently. The results include S3-specific metadata fields: `etag` (content hash) and `storage_class` (STANDARD, GLACIER, etc.).

<!-- concept:68 -->
## S3DeleteMixin

The **`S3DeleteMixin`** removes objects using `delete_object`:

```python
class S3DeleteMixin:
    def delete_file(self, path: str) -> None:
        bucket, key = parse_s3_path(path)
        self._client.delete_object(Bucket=bucket, Key=key)
```

S3's `delete_object` returns a 204 success response regardless of whether the key exists. This differs from the local backend which raises `PathNotFoundError`. The behavior is intentionally preserved (not normalized) because it reflects S3's eventual-consistency model -- an object might appear to exist or not depending on timing.

<!-- concept:69 -->
## S3MetadataMixin

The **`S3MetadataMixin`** retrieves object metadata using `head_object`:

```python
class S3MetadataMixin:
    def get_metadata(self, path: str) -> FileMetadata:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)
        return FileMetadata(
            filename=key.split("/")[-1],
            directory=f"s3://{bucket}/{'/'.join(key.split('/')[:-1])}",
            full_path=f"s3://{bucket}/{key}",
            size=response.get("ContentLength", 0),
            last_modified=response.get("LastModified"),
            etag=response.get("ETag", "").strip('"'),
            storage_class=response.get("StorageClass", ""),
            source="s3",
        )

    def path_exists(self, path: str) -> bool:
        # head_object with 404 fallback to list_objects_v2
        ...

    def get_size(self, path: str) -> int:
        # ContentLength from head_object
        ...
```

The `path_exists` method uses a two-step check: first `head_object` (which raises a `ClientError` with code `"404"` for missing keys), then falls back to `list_objects_v2` with `MaxKeys=1` to handle bucket-level or prefix-level existence checks.

!!! note "ETag Stripping"
    S3 returns ETags wrapped in double quotes (e.g., `"d41d8cd98f00b204e9800998ecf8427e"`). The mixin strips these quotes before storing in `FileMetadata`, so callers receive a clean hash string.

<!-- concept:70 -->
## S3CopyMixin

The **`S3CopyMixin`** performs server-side copies using `copy_object`:

```python
class S3CopyMixin:
    def copy(self, source: str, destination: str) -> None:
        src_bucket, src_key = parse_s3_path(source)
        dst_bucket, dst_key = parse_s3_path(destination)
        self._client.copy_object(
            Bucket=dst_bucket,
            Key=dst_key,
            CopySource={"Bucket": src_bucket, "Key": src_key},
        )
```

Server-side copy means the data never leaves the S3 infrastructure -- no bytes are downloaded to the client and re-uploaded. This makes intra-S3 copies extremely fast regardless of object size. Cross-bucket copies within the same region are also server-side.

The `CopySource` parameter uses a dictionary format rather than the older string format (`bucket/key`), which is more explicit and avoids issues with key names containing special characters.

#### Diagram: S3 Backend Operation Flow

<iframe src="../../sims/s3-operation-flow/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>S3 Backend Operation Flow</summary>
Type: workflow
**sim-id:** s3-operation-flow<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Trace a complete operation from facade method call through S3 mixin to boto3 API call, showing path parsing, client method selection, and response handling.

**Components:**

- Entry: facade.read("s3://my-bucket/data/file.csv")
- parse_s3_path node: splits into bucket="my-bucket", key="data/file.csv"
- boto3 method selection: get_object
- Response handling: extract Body, read bytes
- Return: bytes to caller
- Side panel showing the actual boto3 API request/response structure

**Interactions:** Select different operations (read, write, list, delete, copy) to see their flow. Hover over boto3 API calls to see the full request parameters.

**Learning Objective:** Trace operations from facade to boto3 API calls (Bloom: Apply)
</details>

## The parse_s3_path Utility

All S3 mixins share a common path-parsing utility that normalizes S3 path formats:

```python
def parse_s3_path(path: str) -> tuple[str, str]:
    if path.startswith("s3://"):
        path = path[5:]
    parts = path.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    return bucket, key
```

This simple function strips the `s3://` prefix (if present), splits on the first `/`, and returns `(bucket, key)`. The key is empty string for bucket-root references. It accepts both `s3://bucket/key` and bare `bucket/key` formats for flexibility.

## Key Takeaways

- **`S3StorageBackend`** is a single class registered for five provider types (S3, S3Express, R2, MinIO, B2) using stacked `@register_storage_backend` decorators.
- **Boto3** is the underlying SDK; the backend wraps a `boto3.client("s3", ...)` instance created lazily on `connect()`.
- **S3 Flavor Dispatch** adapts connection parameters (endpoint URL, region, addressing style) based on the `FLAVOR` field without changing operation logic.
- **AWS S3** uses default boto3 resolver with optional acceleration and dualstack; **S3 Express** forces virtual addressing; **R2** requires `region_name="auto"` and account-derived endpoints; **MinIO** requires explicit endpoints.
- **`S3ReadMixin`** downloads via `get_object`; the stream variant currently buffers in `BytesIO` (known limitation for very large objects).
- **`S3WriteMixin`** uses `put_object` for bytes and `upload_fileobj` for streams, with automatic multipart handling for large uploads.
- **`S3ListMixin`** uses paginated `list_objects_v2` to handle arbitrarily large buckets transparently.
- **`S3CopyMixin`** performs server-side copies via `copy_object` -- no data transits through the client.
- The backend does **not** implement `StorageDirectoryProtocol` because S3 has no real directory concept.
- All mixins share `parse_s3_path` for normalizing `s3://bucket/key` and `bucket/key` formats.
