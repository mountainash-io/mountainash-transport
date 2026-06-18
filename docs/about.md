# About

## Who This Is For

This manual is for Python developers who need to read, write, and move files across local disk, S3-compatible object stores (AWS S3, Cloudflare R2, MinIO, Backblaze B2), and HTTP endpoints. You might be building data pipelines, managing an encrypted data lake, or migrating between cloud providers. If you're writing storage code and tired of provider-specific boilerplate, this is for you.

## What You Should Already Know

You should be comfortable with:

- Python 3.10+ (type hints, dataclasses, protocols)
- Basic file I/O in Python (open, read, write)
- What S3 is and how buckets and keys work (you don't need deep AWS experience)
- Environment variables and configuration patterns

No prior experience with mountainash or its other packages is required.

## What You'll Get Out of This

After working through this manual, you'll know how to:

- **Read a file from anywhere with a single call** — local paths, S3 URIs, and HTTP URLs all go through the same `read_bytes()` function
- **Switch cloud providers without changing application code** — swap AWS S3 for Cloudflare R2 or MinIO by changing configuration, not code
- **Apply compression and encryption transparently** — compose gzip and GPG transforms into pipelines that work on reads, writes, and cross-backend transfers
- **Copy files between any two backends** — move data from S3 to local, local to R2, or HTTP to S3 with transforms applied in flight
- **Use suffix-aware path helpers** — let the library infer the right transforms from file extensions like `.csv.gz` or `.csv.gz.gpg`
- **Handle errors at the right level** — catch broad storage failures or narrow provider-specific issues using the exception hierarchy

## How to Navigate

- **Read in order** — chapters are arranged in dependency order, so each one builds on what came before
- **Use search** — the search bar (top right) is the fastest way to find a specific class, function, or concept
- **Try the MicroSims** — when interactive simulations are available, they're the quickest way to build intuition
- **Check the Learning Graph** — the [Learning Graph](learning-graph/index.md) shows how concepts relate, so you can see what to read next
- **Use the API Reference** — the [API Reference](api/index.md) is auto-generated from source and covers every public module

## About mountainash-transport

mountainash-transport is part of the [mountainash](https://github.com/mountainash-io/mountainash) project — a modular Python framework for data engineering. This package handles the file storage abstraction layer: one interface, many backends, transparent transforms.

## Author

Nathaniel Ramm
