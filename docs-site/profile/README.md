# mountainash-transport

**Cloud-native storage abstraction -- one interface for local files, S3, HTTP, and more.**

## Vision

Data lives everywhere -- local disks, S3 buckets, HTTP endpoints, Cloudflare R2, MinIO,
Backblaze B2, and eventually GCS, Azure, and SFTP. The access patterns are the same but
every backend demands its own code. mountainash-transport provides a single interface
where backends declare their capabilities through protocols, compression and encryption
compose as transform pipelines, and path-driven dispatch routes to the right backend
automatically.

The practical effect is that `read_bytes('s3://bucket/file.gz')`,
`read_bytes('https://api.example.com/data.csv')`, and
`read_bytes('/tmp/local.parquet')` are the same function call with the same interface.
URL scheme detection routes to the right backend. Transform pipelines decompress and
decrypt transparently. Switching from AWS S3 to Cloudflare R2 is a configuration change,
not a code change.

Cross-backend transfers complete the picture. Copy from S3 to local, local to another S3
bucket, HTTP to S3 -- with compression and encryption transforms applied in flight. The
source and destination can be any supported backend, and the application code stays the
same regardless of where data lives or moves.

## Installation

```bash
pip install mountainash-transport
```

## Use Cases

### The Multi-Cloud Data Pipeline

A pipeline reads compressed data from S3, processes it, and writes results to a different
cloud provider. The storage facade handles both ends -- the pipeline calls `read_bytes()`
on the source and writes through `StorageFacade` on the destination. Transforms decompress
on read and compress on write. The pipeline code does not know or care which cloud the
data lives on. When the infrastructure team migrates to a different provider, the pipeline
code does not change.

### The Encrypted Data Lake

Sensitive data lands GPG-encrypted in S3. Analytics pipelines read it through the storage
facade with automatic decryption -- the `infer_pipeline` helper sees the `.gpg` extension
and applies the GPG transform transparently. Processed results write back encrypted.
The encryption is a transform pipeline, not application code -- it composes with any read
or write operation. Layered formats work naturally: a file named `data.csv.gz.gpg` is
decrypted, then decompressed, and the application receives clean CSV bytes.

### The Migration That Does Not Touch Application Code

An organisation migrates from AWS S3 to Cloudflare R2. The application code calls the
same storage facade methods -- `read_bytes()`, `StorageFacade.write()`,
`copy_between()`. The settings class changes its flavour field from `aws` to `r2`. The
migration is a configuration change. Under the hood, a single S3 backend class serves
both providers, with flavour-specific endpoint and region handling managed in the
connection layer.

### Suffix-Aware Transform Inference

A data engineering team works with files across multiple compression and encryption
formats. Rather than manually constructing transform pipelines for each file type, the
`infer_pipeline` helper examines file extensions and builds the appropriate pipeline
automatically. A file ending in `.csv.gz` gets a gzip decompression transform on read.
A file ending in `.csv.gz.gpg` gets decrypted then decompressed, in that order. Writes
apply the inverse transforms: compress then encrypt. The ordering stays consistent with
how file extensions are stacked, and no manual pipeline construction is needed.

## Key Capabilities

### One-Liner File Reading

`read_bytes()` accepts any supported URL scheme and returns file contents in a single
call. It dispatches to the correct backend automatically based on the URL scheme, so
reading from local paths, S3 URIs, and HTTP URLs uses exactly the same function. This is
the fastest way to get started -- one import, one function call, and you have your data
regardless of where it lives.

For applications that need the full set of file operations, `StorageFacade` provides the
complete interface: read, write, list, delete, copy, and metadata retrieval. Use
`from_path()` to create a facade instance for any supported storage location. The facade
checks backend capabilities at runtime via the `supports()` method, so you can query
what operations are available before invoking them.

### S3-Family Unification

AWS S3, Cloudflare R2, MinIO, Backblaze B2, and S3 Express are all S3-compatible but all
slightly different in their endpoint conventions, region handling, and authentication
details. One settings class with a flavour field handles these variations. A single
backend class serves all five providers, with flavour-specific configuration handled in
the connection layer.

Connecting to any S3-compatible service uses the same code. Each provider has a dedicated
settings class with typed fields for authentication, endpoints, and provider-specific
options. Configuration is explicit and discoverable, with clear required and optional
parameters. When a new S3-compatible service emerges, adding support means defining the
provider's flavour-specific settings and adding a registration decorator.

### Transparent Compression and Encryption

Gzip and GPG transforms compose as declarative pipelines. The `Pipeline` class manages
ordered transform application, applying transforms in the correct direction for both
reads and writes. On read, transforms strip outward-in: decompress then decrypt,
matching the order you would apply manually. On write, transforms wrap inward-out:
encrypt then compress.

Transforms attach to reads, writes, and cross-backend transfers alike. The pipeline
handles the encoding details, keeping application logic focused on data rather than
format concerns. Streams flow through the transforms, so large files do not need to
be buffered entirely in memory.

### Cross-Backend File Transfers

`copy_between()` moves files across different storage backends in a single call. You can
apply transform pipelines during the copy, enabling workflows like compressing a local
file while uploading it to S3, or decrypting data from one bucket while writing it
unencrypted to another. The source and destination can be any combination of supported
backends -- the function handles the dispatch on both ends.

### Storage Path Utilities

`StoragePath` provides URL scheme identification, path normalisation, and join operations
across all supported backends. It gives you a consistent way to construct and manipulate
paths regardless of the underlying storage system. The `SCHEMES` registry maps URL schemes
to provider types, supporting aliases and placeholder schemes for future backends. This
registry is the entry point for all path-driven dispatch.

### Error Handling

A clear exception hierarchy lets you catch storage errors at the right level of
specificity, from broad storage failures down to provider-specific issues. Each exception
carries context about what went wrong and where, making it straightforward to diagnose
problems that span multiple backends or involve transform pipeline failures.

## Architecture

mountainash-transport is built on a protocol-driven, registry-dispatched architecture.
Eight runtime-checkable protocols -- Read, Write, List, Delete, Metadata, Copy, Directory,
and Connection -- define the storage contract, with each protocol independently
implementable. Backends opt into whichever protocols they support, and the facade
dispatches operations through runtime `isinstance` checks. The `_require()` method gates
access to unsupported operations, while `supports()` lets callers check capabilities
before invoking them.

Settings flow through a spec-driven profile pattern. `StorageProfile` holds typed
configuration fields, and a provider-specific adapter module translates profile values
into the exact kwargs the underlying SDK expects. This pipeline keeps provider settings
declarative while giving each SDK precisely the parameters it needs. The local backend
implements all eight protocols, the S3 backend covers seven, and the HTTP backend focuses
on read, write, and metadata -- each implementing exactly the capabilities that make
sense for its storage system.

## Contributing

Contributions welcome. The protocol-driven architecture means adding a new storage
backend involves implementing the relevant protocol interfaces, writing an adapter for
the settings pipeline, registering the backend via the `@register_storage_backend`
decorator, and adding a settings class with a `StorageDescriptor` for provider metadata.
Automated protocol conformance tests verify alignment, so new backends get structural
validation for free. The local and S3 backends use mixin composition with one mixin per
protocol, providing a clear pattern to follow.

## Maintaining

The eight storage protocols are the primary design invariant for the entire storage layer.
When modifying protocol signatures, the automated conformance and completeness tests are
the safety net -- run them after any protocol change to verify all backends remain aligned.
The local and S3 backends use mixin composition, making it straightforward to modify
individual capabilities in isolation without affecting others.

The S3 flavour dispatch is the mechanism that unifies multiple S3-compatible providers
under one backend class. Five stacked `@register_storage_backend` decorators map each
provider type to the same class, with flavour-specific configuration handled in the
connection layer. As new S3-compatible services emerge, adding support means defining a
new provider type, writing a settings class with the appropriate flavour, and adding
another decorator.

The settings pipeline -- from `StorageProfile` through adapters to SDK kwargs -- is where
provider-specific complexity is contained. Each provider gets one adapter function that
translates profile fields into SDK-ready keyword arguments. The `settings.utils` module
contains partially commented-out code, and `settings.templates` may be eligible for
inlining -- these are candidates for future cleanup to reduce the maintenance surface.
