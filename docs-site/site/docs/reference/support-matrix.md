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

The table was produced from `get_registered_backends()` and the protocol classes in `src/mountainash_transport/storage/protocols/`. `tests/storage/protocols/test_backend_conformance.py` asserts every capability column, including ranged read, for each registered provider, and checks the root README's support table against the same backends. Ranged read is satisfied structurally by an `open_ranged` method.

## Settings-only providers

GCS, Azure (Blob and Files), FTP/FTPS, SMB and GitHub repositories have storage profile classes but no backend. A path-only facade such as `StorageFacade.from_path("gs://...")`, a facade built with one of these profiles, `create_connection` and a backend lookup all raise `BackendNotImplementedError`. See [specs, the registry and settings-only providers](../chapters/05-storage-profiles/index.md#specs-the-registry-and-settings-only-providers).

## Known limits

These behaviours are current and affect correct use. Each one is also noted where it matters in the chapters.

| Area | Behaviour | Where it is explained |
|---|---|---|
| Tunnels (SDK-resolved endpoints) | An `aws` or `express` flavour S3 profile without `ENDPOINT_URL`, or an S3 target that assumes a role (`ROLE_ARN`, or a `PROFILE_NAME` whose AWS config sets `role_arn`), cannot be routed through a tunnel; `connect()` raises `TunnelEndpointError` instead of connecting directly to AWS or AWS STS. | [Decorator connections](../chapters/11-connections/index.md#decorator-connections) |
| Native copy | `copy_between` uses a backend's native copy only when both facades share the same profile object; equal but separate profiles download and re-upload. | [Copying between backends](../chapters/10-stream-transforms/index.md#copying-between-backends) |
