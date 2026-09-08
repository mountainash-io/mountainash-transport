---
title: 'Package Overview'
description: 'Course-style overview of Mountainash Utils Files: audience, prerequisites, learning outcomes, and chapter-by-chapter syllabus for mountainash-transport.'
---

# Course Description

Mountainash Utils Files is structured like a short course on cloud-native storage abstraction in Python: it takes you from the problem (provider-specific file I/O boilerplate) through the design (protocols, dispatch, pipelines) to hands-on familiarity with every backend the library ships. This page describes the course in those terms — who it's for, what it assumes, what you'll walk away able to do, and how the nine chapters are sequenced. For the narrative introduction and a full breakdown of the library's design philosophy, start at [Home](index.md); for a distilled who/what-you'll-get summary, see [About](about.md).

## Audience

This course is aimed at Python developers who work with files across more than one storage backend — data engineers, backend developers, and platform engineers building data pipelines, ETL processes, encrypted data lakes, or applications that need to move data between local disk, S3-compatible object stores, and HTTP sources without hand-rolling provider-specific code for each one.

## Prerequisites

Readers should be comfortable with:

- Python 3.10+, including type hints, dataclasses, and protocols
- Basic file I/O in Python (`open`, `read`, `write`)
- The conceptual shape of S3 (buckets, keys, URI schemes) — deep AWS experience is not required
- Environment variables and typical configuration patterns

No prior exposure to mountainash or its other packages is assumed.

## Learning Outcomes

By the end of the course, you will be able to:

1. **Read from any supported backend with one call** — use `read_bytes()` against local paths, S3 URIs, and HTTP URLs interchangeably.
2. **Swap storage providers without touching application code** — move between AWS S3, Cloudflare R2, MinIO, Backblaze B2, and S3 Express by changing configuration, not call sites.
3. **Apply compression and encryption transparently** — compose Gzip and GPG transforms into pipelines that operate on reads, writes, and cross-backend copies.
4. **Copy files between arbitrary backend pairs** — transfer data from S3 to local disk, local to another bucket, or HTTP to S3, with transforms applied in flight.
5. **Use suffix-aware path helpers** — let the library infer the correct transform pipeline from extensions like `.csv.gz` or `.csv.gz.gpg`.
6. **Handle storage errors at the right granularity** — catch broad storage failures or narrow provider-specific exceptions using the library's exception hierarchy.

## Syllabus

The course is delivered as nine chapters, each building on concepts introduced earlier (see [Chapters](chapters/index.md) for the full list with concept counts):

1. **Foundation Concepts** — URL schemes, path dispatch, and the facade pattern that ties the library together.
2. **Storage Protocols** — the eight capability protocols (Read, Write, List, Delete, Metadata, Copy, Directory, Connection) and how a backend declares what it supports.
3. **Path Handling** — `StoragePath`, URL scheme identification, normalisation, and join operations.
4. **Settings and Configuration** — typed provider settings for AWS S3, Cloudflare R2, MinIO, Backblaze B2, and S3 Express.
5. **StorageFacade** — the central API for reading, writing, listing, deleting, copying, and inspecting metadata across every backend.
6. **Transforms** — Gzip, GPG, and how they compose into pipelines for transparent compression and encryption.
7. **Local Backend** — local file system operations implemented through the storage protocols.
8. **S3 Backend** — connecting to any S3-compatible service through flavour-based configuration.
9. **HTTP Backend** — reading from HTTP/HTTPS endpoints through the same unified interface.

## Out of Scope

This course does not cover the internal implementation details of the settings registry, adapters, or stream encoders; other mountainash packages (mountainash-data, mountainash-rules, mountainash-settings); general Python programming or cloud infrastructure setup; or performance benchmarking and production deployment patterns. These are deliberately left out so the course stays focused on using and reasoning about the public `mountainash-transport` API.
