# Package Overview

mountainash-transport is a cloud-native storage abstraction library for Python. It provides a single interface for reading, writing, copying, and managing files across local disk, S3-compatible object stores, and HTTP endpoints, with transparent compression and encryption through composable transform pipelines.

## Target Audience

Python developers building data pipelines, ETL processes, or applications that need to work with files across multiple storage backends. Typical readers are data engineers, backend developers, and platform engineers who want a unified file interface instead of provider-specific code.

## Prerequisites

- Python 3.10+ with familiarity in type hints, dataclasses, and protocols
- Basic file I/O in Python
- Conceptual understanding of S3 (buckets, keys, URI schemes)
- Familiarity with environment variables and configuration patterns

## What This Manual Covers

1. Foundation concepts: URL schemes, path dispatch, and the facade pattern
2. Storage protocols: the eight capability protocols (Read, Write, List, Delete, Metadata, Copy, Directory, Connection) and how backends declare what they support
3. Path handling: StoragePath, URL scheme identification, normalisation, and join operations
4. Settings and configuration: typed provider settings for AWS S3, Cloudflare R2, MinIO, Backblaze B2, and S3 Express
5. StorageFacade: the central API for all file operations — read, write, list, delete, copy, and metadata
6. Transforms: Gzip, GPG, and composable pipeline construction for transparent compression and encryption
7. Local backend: local file system operations through the storage protocols
8. S3 backend: connecting to any S3-compatible service with flavour-based configuration
9. HTTP backend: reading from HTTP/HTTPS endpoints through the same interface

## What This Manual Does Not Cover

- Internal implementation details of the settings registry, adapters, or stream encoders
- Other mountainash packages (mountainash-data, mountainash-rules, mountainash-settings)
- General Python programming or cloud infrastructure setup
- Performance benchmarking or production deployment patterns

## Key Capabilities

**Read from anywhere with one call** — `read_bytes()` accepts any supported URL scheme and returns file contents. It dispatches to the correct backend automatically, so code that reads from a local path today can read from S3 or HTTP tomorrow with no changes.

**S3-family unification** — AWS S3, Cloudflare R2, MinIO, Backblaze B2, and S3 Express are all S3-compatible but all slightly different. One settings class with a flavour field handles the variations. Connecting to any S3-compatible service uses the same code path.

**Transparent compression and encryption** — Gzip and GPG transforms compose as pipelines. Attach them to reads, writes, or cross-backend transfers. The `infer_pipeline` helper reads file extensions and applies the right transforms automatically — `.csv.gz` gets decompressed, `.csv.gz.gpg` gets decrypted then decompressed.

**Cross-backend transfers** — Copy from S3 to local, local to another S3 bucket, or HTTP to S3, with transforms applied in flight. The source and destination can be any supported backend.

**Capability-driven backends** — Eight storage protocols, each independently implementable. A backend picks which capabilities it supports, and the facade dispatches based on what's available. Adding a new storage backend means implementing only the protocols that matter for your use case.

## Context

mountainash-transport is part of the [mountainash](https://github.com/mountainash-io/mountainash) project, a modular Python framework for data engineering. It sits at the storage abstraction layer, used by higher-level packages like mountainash-data for file access.
