---
title: Support matrix and known limits
---

# Support matrix and known limits

mountainash-transport has four storage backends: local files, the S3 family, SFTP and HTTP(S). Each one implements the storage protocols that make sense for its storage system. `StorageFacade.supports()` reports the same information at runtime; see [capabilities and supports()](../chapters/06-storage-facade/index.md#capabilities-and-supports).

## Backends and capabilities

| Backend | Provider types | Extra | Read | Write | Enumerate | Delete | Metadata | Copy | Directory | Ranged read |
|---|---|---|---|---|---|---|---|---|---|---|
| Local | `local` | none (base install) | yes | yes | yes | yes | yes | yes | yes | no |
| S3 family | `s3`, `s3express`, `r2`, `minio`, `b2` | `[s3]` | yes | yes | yes | yes | yes | yes | no | yes |
| SFTP | `sftp` | `[sftp]` | yes | yes | yes | yes | yes | no | yes | yes |
| HTTP(S) | `http` | `[http]` | yes | yes | no | no | yes | no | no | yes |

One `S3StorageBackend` class is registered for all five S3-family provider types. The flavour on the storage profile selects endpoint and region handling. Local files support random access through the native file handle rather than the ranged-read protocol. See [read access modes](../chapters/09-read-access-modes/index.md#choosing-an-access-mode).

The table was produced from `get_registered_backends()` and the protocol classes in `src/mountainash_transport/storage/protocols/`. `tests/storage/protocols/test_backend_conformance.py` asserts the first seven capability columns. Ranged read is satisfied structurally by an `open_ranged` method.

## Settings-only providers

GCS, Azure (Blob and Files), FTP/FTPS, SMB and GitHub repositories have storage profile classes but no backend. A path-only facade such as `StorageFacade.from_path("gs://...")`, or a backend lookup, raises `BackendNotImplementedError`. A facade built with one of these profiles fails earlier, during connection setup, with `TransportConnectionError`, because `create_connection` falls back to an HTTP connection for these providers. See [specs, the registry and settings-only providers](../chapters/05-storage-profiles/index.md#specs-the-registry-and-settings-only-providers).

## Known limits

These behaviours are current and affect correct use. Each one is also noted where it matters in the chapters.

| Area | Behaviour | Where it is explained |
|---|---|---|
| Location policy | An empty host set in `allowed_remote` (for example `{"https": frozenset()}`) allows any host for that scheme. To allow no remote hosts for a scheme, leave the scheme out. | [Allowing remote hosts](../chapters/08-location-policy/index.md#allowing-remote-hosts) |
| Tunnels | A tunnelled connection rewrites `base_url` and `endpoint_url` to `http://127.0.0.1:<port>`. The SSH hop is encrypted, but an HTTPS-only target receives plain HTTP and the request fails; any path prefix on the URL is dropped. | [Decorator connections](../chapters/11-connections/index.md#decorator-connections) |
| Tunnels (bypass) | An `aws` flavour S3 profile (no `endpoint_url`) used through a tunnelled connection connects directly to AWS without error, bypassing the bastion. | [Decorator connections](../chapters/11-connections/index.md#decorator-connections) |
| Unknown schemes | Without an active location policy, the `ValueError` for an unrecognised scheme quotes the path, including any `user:password`. | [Policy on the facade](../chapters/08-location-policy/index.md#policy-on-the-facade) |
| Path normalisation | `StoragePath.normalize` drops the host of `sftp://` and `ftp://` URLs, and `join` inherits this. | [StoragePath](../chapters/04-paths-and-schemes/index.md#storagepath) |
| HTTP retries | A 429 is retried for any method and any body. Transport errors and other retryable statuses are not retried when the body was passed as a non-seekable stream. | [Retries](../chapters/12-http-engine/index.md#retries) |
| Directories | `rmdir` on a local directory removes the whole tree. On SFTP it removes only an empty directory. | [Deleting, directories and parent creation](../chapters/07-file-operations/index.md#deleting-directories-and-parent-creation) |
| SFTP writes | `write_stream` to SFTP reads the whole source stream into memory before uploading, including during `copy_between` into SFTP. | [Where backends differ](../chapters/14-backends/index.md#where-backends-differ) |
| S3 copy | A same-store S3 copy is a single `copy_object` request with no multipart fallback, so it is bounded by the provider's single-request copy limit ([5 GB on Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html)). | [Where backends differ](../chapters/14-backends/index.md#where-backends-differ) |
| S3 stream uploads | `write_stream` to an S3-family store closes the caller's source stream after a small single-request upload, and leaves it open after a multipart upload. | [Reading and writing](../chapters/07-file-operations/index.md#reading-and-writing) |
| S3 listing | Enumeration with a result limit lists every page before truncating. | [Where backends differ](../chapters/14-backends/index.md#where-backends-differ) |
| Missing extras | `MissingExtraError` names the missing extra only for the `[http]` stack. A missing boto3, paramiko or python-gnupg surfaces as a plain import or connection error. | [Errors](../chapters/03-installation/index.md#errors) |
| Transforms on write | The gzip compressor closes the stream it wraps when it is closed. | [Limits and ownership](../chapters/10-stream-transforms/index.md#limits-and-ownership) |
| Native copy | `copy_between` uses a backend's native copy only when both facades share the same profile object; equal but separate profiles download and re-upload. | [Copying between backends](../chapters/10-stream-transforms/index.md#copying-between-backends) |
| Connections | `create_connection` uses `HTTPConnection` for a provider type it has no connection class for, so a settings-only profile fails with a `TransportConnectionError` about unexpected client arguments. | [create_connection](../chapters/11-connections/index.md#create_connection) |
