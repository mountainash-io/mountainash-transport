# Concept Taxonomy

This taxonomy organizes the 90 mountainash-utils-files concepts into 9 categories.

## Categories

### FOUND — Foundation Concepts
Prerequisites: file systems, cloud storage, URL schemes, binary streams, Python protocols, mixins, Pydantic, decorators, registry pattern.

### PROTO — Storage Protocols
8 runtime-checkable protocols defining fine-grained storage capabilities (Connection, Read, Write, List, Delete, Metadata, Copy, Directory).

### FACADE — StorageFacade
Unified user-facing API that dispatches to protocol-checked backends with bytes, stream, and transform pipeline support.

### PATH — Path Handling
StoragePath for scheme detection and normalization, SchemeSpec registry, alias resolution, UPath integration, path-driven provider detection.

### TRANS — Transforms
StreamTransform protocol, Pipeline class for ordered transform stacks, Gzip compression, GPG encryption, suffix-aware inference, materialize utility.

### LOCAL — Local Backend
Full 8-protocol implementation via 8 mixins composing LocalStorageBackend — the only backend implementing StorageDirectoryProtocol.

### S3 — S3 Backend
Unified S3-family handler for AWS S3, S3 Express One Zone, Cloudflare R2, MinIO, and Backblaze B2 via boto3 with flavor dispatch. 7 of 8 protocols (no Directory).

### HTTP — HTTP Backend
Read-only backend for HTTP/HTTPS URLs implementing 3 of 8 protocols (Connection, Read, Metadata) via httpx.

### SETT — Settings & Configuration
StorageAuthBase, provider/auth/access enums, per-provider settings classes, descriptors, profiles, and adapters.

## Taxonomy Summary Table

| TaxonomyID | Category Name | Concept Range | Count |
|------------|---------------|---------------|-------|
| FOUND | Foundation Concepts | 1-10 | 10 |
| PROTO | Storage Protocols | 11-18 | 8 |
| FACADE | StorageFacade | 19-30 | 12 |
| PATH | Path Handling | 31-40 | 10 |
| TRANS | Transforms | 41-52 | 12 |
| LOCAL | Local Backend | 53-62 | 10 |
| S3 | S3 Backend | 63-76 | 14 |
| HTTP | HTTP Backend | 77-82 | 6 |
| SETT | Settings & Configuration | 83-90 | 8 |
