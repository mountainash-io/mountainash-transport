---
title: 'About'
description: 'Why mountainash-transport exists, the design ideas behind it, where it fits in Mountainash, who maintains it and how it is licensed.'
---

[← Back to Home](index.md)

# About mountainash-transport

**boto3, paramiko and httpx each talk to one kind of store. mountainash-transport decides which one a path needs and puts the same file API in front of all of them.**

## Why it exists

Python already has a good client for every common store: `open()` and `pathlib` for local disk, `boto3` for S3-compatible object stores, `paramiko` for SFTP and `httpx` for HTTP. While a program talks to one store, that is all it needs.

Trouble starts when the same code has to work against several. Something has to look at each path and pick a client, and that `if path.startswith("s3://")` ladder gets copied into every package that reads files. Error handling grows one `except` clause per client library. Connection settings and credentials end up in the same dictionary. Code asks a web server to list a folder, or an object store to create a directory, and finds out halfway through a job that the store cannot do it.

mountainash-transport answers all of these with one idea: the path names the store, and everything else about the store is described separately. You open a `StorageFacade` from a path. A storage profile says how to reach the store, an auth profile supplies the credentials, and the backend behind the facade declares which operations its store supports.

## What it adds to the client libraries

The client libraries speak each store's protocol. Transport adds the layer that lets one piece of code use any of them.

| Area | What you get |
|---|---|
| Path dispatch | `StorageFacade.from_path` picks the backend from the path's scheme: local disk, the S3 family, SFTP or HTTP(S) |
| One file API | The same calls to read, write, stream, list, inspect, copy and delete on every backend |
| Capability checks | `supports()` reports what a store can do; an unsupported call raises `UnsupportedOperationError` before any I/O |
| Profiles and credentials | Storage profiles describe stores, auth profiles from `mountainash-auth-client` supply credentials, and `resolve_storage` loads named profiles from configuration |
| Stream transforms | `Gzip` and `GPG` applied on read, write and cross-store copy, with opt-in decoding from the file suffix |
| Location policy | `LocationPolicy` confines local paths to a root and remote access to listed hosts and buckets |
| Typed errors | `PathNotFoundError`, `AuthenticationError`, `StorageConnectionError` and the rest of the `StorageError` family, whichever library failed |

## Design ideas

The path picks the backend. The main entry points take a path and read its scheme, so callers do not name a provider that the path already implies. Moving data from local disk to `s3://` changes the path and adds a storage profile and an auth profile; the calls stay the same.

Capabilities are checked, not assumed. Each capability (read, write, enumerate, delete, metadata, copy, directories, ranged reads) is a separate protocol, and a backend implements only the ones its store supports. Code that accepts any store can ask `supports()` first, and code that skips the check gets `UnsupportedOperationError` instead of a half-finished operation.

A profile describes the store; credentials come separately. A storage profile holds the region, bucket, endpoint, host and timeouts, and never a password or key. The same auth profile can be paired with different stores, and the pairing is validated before a connection opens.

Copies between stores name both stores. `copy_between` is a top-level function that takes the source and destination facades explicitly, so the call site shows which two stores are involved and which pipeline applies on each side.

Decoding by suffix is opt in, and only on read. `read(path, infer=True)` decompresses or decrypts according to suffixes such as `.gz` and `.gpg`; decryption also needs a `GPG` instance that holds the keys. Writes never guess from the file name: you pass `pipeline=` explicitly, so bytes that are already compressed are not compressed twice.

Transport moves bytes; formats belong to the caller. Transport returns bytes and streams and has no dependency on any format or data frame library. The caller chooses how to read (sequential, random or buffered) and does all the parsing.

## Where it fits

mountainash-transport is the storage layer of the [Mountainash packages](https://github.com/mountainash-io). Below it, `mountainash-settings` loads configuration and resolves secret references, and `mountainash-auth-client` owns credential types and OAuth flows; transport uses both through its `[http]` extra. Above it, `mountainash-files` parses file formats and `mountainash` builds data frame expressions and relations. Both depend on transport, and `mountainash-files` reaches all storage through transport's public API, so profiles, credentials, transforms and location policy apply to every file it reads.

Credential models and OAuth token handling live in `mountainash-auth-client`, configuration loading in `mountainash-settings`, and file formats in `mountainash-files`. [Transport in the Mountainash ecosystem](chapters/02-mountainash-ecosystem/index.md) describes each boundary in detail.

## Who maintains it

mountainash-transport is written and maintained by Nathaniel Ramm. The code is at [github.com/mountainash-io/mountainash-transport](https://github.com/mountainash-io/mountainash-transport), and runnable recipes that work offline are in its [examples folder](https://github.com/mountainash-io/mountainash-transport/tree/develop/examples).

Every page of this documentation has an edit button that opens its source on GitHub. Corrections and contributions arrive as pull requests against the `develop` branch, as described in [CONTRIBUTING.md](https://github.com/mountainash-io/mountainash-transport/blob/develop/CONTRIBUTING.md). For questions and feedback, see the [Contact](contact.md) page.

## License

The code is licensed under the [Apache License, Version 2.0](https://github.com/mountainash-io/mountainash-transport/blob/develop/LICENSE), copyright 2024 to 2026 Mountain Ash Solutions Pty. Ltd., as stated in the repository's `NOTICE` file.

This documentation is Copyright &copy; 2026 Nathaniel Ramm and licensed under [CC BY-NC-SA 4.0](license.md) (Attribution-NonCommercial-ShareAlike 4.0 International) for non-commercial use. The [License](license.md) page has the full terms and how to ask about commercial use.
