---
title: References
---

# References

mountainash-transport sits on a small set of third-party libraries, Python standard library modules and storage provider APIs, and it shares configuration and credentials with sibling Mountainash packages. Each entry below links to the project's own documentation, states what transport uses it for, and points to the section of this book where it matters.

## Mountainash packages

The [Mountainash packages](../chapters/02-mountainash-ecosystem/index.md#the-mountainash-packages) section describes how these packages depend on each other.

- [mountainash-transport](https://github.com/mountainash-io/mountainash-transport): source repository for this package, including the tests and protocol classes that the [support matrix](support-matrix.md) is drawn from.
- [mountainash-settings](https://github.com/mountainash-io/mountainash-settings): supplies the settings classes, the `Profile` base class and profile registries behind storage profiles and `resolve_storage`. See [Configuration comes from settings](../chapters/02-mountainash-ecosystem/index.md#configuration-comes-from-settings).
- `mountainash-auth-client` (repository not public): supplies auth profiles, credential rendering and OAuth token lifecycles that transport pairs with storage profiles. See [mountainash-auth-client](../chapters/02-mountainash-ecosystem/index.md#mountainash-auth-client).
- `mountainash-files` (repository not public): reads and writes file formats through transport's public API. See [mountainash-files](../chapters/02-mountainash-ecosystem/index.md#mountainash-files).
- [mountainash](https://github.com/mountainash-io/mountainash): data frame expressions and relations; its readers reach storage through transport. See [mountainash relations readers](../chapters/02-mountainash-ecosystem/index.md#mountainash-relations-readers).

## Libraries transport builds on

### HTTPX

- [Clients](https://www.python-httpx.org/advanced/clients/): `httpx.Client` is the client that `HTTPConnection` builds and that `HttpRequestEngine` sends every request through. See [Making requests](../chapters/12-http-engine/index.md#making-requests) and [HTTPConnection](../chapters/11-connections/index.md#httpconnection).
- [Exceptions](https://www.python-httpx.org/exceptions/): the httpx exception hierarchy (timeouts, network and protocol errors) that the engine and the HTTP backend translate into transport's typed errors. See [Responses and errors](../chapters/12-http-engine/index.md#responses-and-errors).

### fsspec

- [API reference](https://filesystem-spec.readthedocs.io/en/latest/api.html): its read-buffering classes in `fsspec.caching` back the `readahead`, `blockcache` and `bytes` range policies of `RangedReader`. See [RangedReader](../chapters/14-backends/index.md#rangedreader) and [Range tuning](../chapters/09-read-access-modes/index.md#range-tuning).

### universal_pathlib

- [universal_pathlib repository](https://github.com/fsspec/universal_pathlib): the fsspec-based `UPath` type that `StoragePath.normalize` returns for the schemes it supports. See [StoragePath](../chapters/04-paths-and-schemes/index.md#storagepath).

### Pydantic

- [Validation errors](https://pydantic.dev/docs/validation/latest/errors/validation_errors/): storage profiles validate their fields at construction and raise pydantic's `ValidationError` on bad values. See [What a storage profile is](../chapters/05-storage-profiles/index.md#what-a-storage-profile-is).

### boto3

- [S3 client reference](https://docs.aws.amazon.com/boto3/latest/reference/services/s3.html): the S3 client that `S3Connection` creates for every S3 flavour, including `copy_object` for `copy()` and `upload_fileobj` for streamed writes. See [S3Connection](../chapters/11-connections/index.md#s3connection) and [S3 family](../chapters/14-backends/index.md#s3-family).
- [Error handling](https://docs.aws.amazon.com/boto3/latest/guide/error-handling.html): botocore's `ClientError` and its error codes, which the S3 backend maps to transport errors. See [Backend error mapping](../chapters/14-backends/index.md#backend-error-mapping).

### paramiko

- [SSHClient](https://docs.paramiko.org/en/stable/api/client.html): the SSH session that `SSHConnection` opens for SFTP and for bastion hosts. See [SSHConnection](../chapters/11-connections/index.md#sshconnection).
- [SFTPClient](https://docs.paramiko.org/en/stable/api/sftp.html): the client the SFTP backend uses for every remote file operation. See [SFTPConnection](../chapters/11-connections/index.md#sftpconnection) and [SFTP](../chapters/14-backends/index.md#sftp).
- [Transport](https://docs.paramiko.org/en/stable/api/transport.html): `open_channel` with a `direct-tcpip` channel carries each forwarded socket of a bastion tunnel. See [Bastion tunnels](../chapters/11-connections/index.md#bastion-tunnels).

### python-gnupg

- [python-gnupg documentation](https://gnupg.readthedocs.io/en/latest/): the wrapper around the `gpg` binary that the `GPG` transform calls to encrypt and decrypt, including the `recipients`, `armor` and `always_trust` options. See [GPG](../chapters/10-stream-transforms/index.md#gpg).

### Authlib

- [OAuth 1.0 for HTTPX](https://docs.authlib.org/en/latest/oauth1/client/http/httpx.html): Authlib's OAuth 1.0 clients for httpx; the `[oauth1]` extra installs Authlib for OAuth 1.0a request signing. See [Optional extras](../chapters/03-installation/index.md#optional-extras).

## Python standard library and specifications

- [PEP 562](https://peps.python.org/pep-0562/): module-level `__getattr__`, which lets the package root resolve its public names on first use. See [The lazy package root](../chapters/03-installation/index.md#the-lazy-package-root).
- [gzip module](https://docs.python.org/3/library/gzip.html): `GzipFile` decodes gzip data when the `Gzip` transform unwraps a stream. See [Gzip](../chapters/10-stream-transforms/index.md#gzip).
- [zlib module](https://docs.python.org/3/library/zlib.html): a raw deflate `compressobj` and `crc32` produce the body and trailer of the streaming gzip encoder. See [Internals: the streaming gzip encoder](../chapters/10-stream-transforms/index.md#internals-the-streaming-gzip-encoder).
- [RFC 1952, GZIP file format](https://www.rfc-editor.org/rfc/rfc1952): defines the header (including `MTIME`) and the CRC32 and size trailer that the streaming encoder writes. See [Internals: the streaming gzip encoder](../chapters/10-stream-transforms/index.md#internals-the-streaming-gzip-encoder).

## Storage provider documentation

- [Amazon S3 CopyObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html): documents the 5 GB limit for a single-request copy, which bounds the S3 backend's `copy()`. See [Copying](../chapters/07-file-operations/index.md#copying) and [S3 family](../chapters/14-backends/index.md#s3-family).
- [AWS STS AssumeRole](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html): the temporary credentials behind a `ROLE_ARN` on an IAM auth profile. See [S3Connection](../chapters/11-connections/index.md#s3connection) and [How profiles become SDK arguments](../chapters/05-storage-profiles/index.md#how-profiles-become-sdk-arguments).
- [Amazon S3 Express One Zone](https://docs.aws.amazon.com/AmazonS3/latest/userguide/directory-bucket-high-performance.html): directory buckets and Zonal endpoints, served by the `express` flavour. See [S3 flavours](../chapters/05-storage-profiles/index.md#s3-flavours).
- [Cloudflare R2 S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/): the `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` endpoint and the `auto` region used by the `r2` flavour. See [S3 flavours](../chapters/05-storage-profiles/index.md#s3-flavours).
- [Backblaze B2 S3-compatible API endpoints](https://www.backblaze.com/docs/cloud-storage-call-the-s3-compatible-api): the `https://s3.<region>.backblazeb2.com` endpoint format used by the `b2` flavour. See [S3 flavours](../chapters/05-storage-profiles/index.md#s3-flavours).

## Packages installed by each extra

Every third-party package that `pyproject.toml` declares, with its PyPI page. [Base install and extras](../chapters/03-installation/index.md#base-install-and-extras) describes what each extra enables.

| Extra | Package | Version constraint |
|---|---|---|
| base | [typing-extensions](https://pypi.org/project/typing-extensions/) | `>=4.0` |
| `[http]` | `mountainash-settings` (not on PyPI) | `>=0.1.0,<0.2` |
| `[http]` | `mountainash-auth-client` (not on PyPI) | `>=0.1.0,<0.2` |
| `[http]` | [pydantic](https://pypi.org/project/pydantic/) | `>=2.10,<3` |
| `[http]` | [universal-pathlib](https://pypi.org/project/universal-pathlib/) | `==0.2.2` |
| `[http]` | [httpx](https://pypi.org/project/httpx/) | `>=0.27` |
| `[http]` | [fsspec](https://pypi.org/project/fsspec/) | `>=2026.6.0,<2027` |
| `[s3]` | [boto3](https://pypi.org/project/boto3/) | `>=1.29.4` |
| `[s3]` | [s3fs](https://pypi.org/project/s3fs/) | `>=2023.1.0` |
| `[s3]` | [aiobotocore](https://pypi.org/project/aiobotocore/) | `>=2.19.0` |
| `[s3]` | [minio](https://pypi.org/project/minio/) | `>=7.2.7` |
| `[gcs]` | [google-cloud-storage](https://pypi.org/project/google-cloud-storage/) | `>=2.9.0` |
| `[gcs]` | [gcsfs](https://pypi.org/project/gcsfs/) | `>=2023.1.0` |
| `[azure]` | [azure-storage-blob](https://pypi.org/project/azure-storage-blob/) | `>=12.13.0` |
| `[azure]` | [adlfs](https://pypi.org/project/adlfs/) | `>=2023.1.0` |
| `[sftp]` | [paramiko](https://pypi.org/project/paramiko/) | `>=5.0.0` |
| `[sftp]` | [smart-open](https://pypi.org/project/smart-open/) | `>=7.0.4` |
| `[encryption]` | [python-gnupg](https://pypi.org/project/python-gnupg/) | `>=0.5.2` |
| `[oauth1]` | [Authlib](https://pypi.org/project/Authlib/) | `>=1.9.1` |

The `[gcs]` and `[azure]` extras install SDKs only; transport has no GCS or Azure backend yet. See [Settings-only providers](../chapters/05-storage-profiles/index.md#settings-only-providers).
