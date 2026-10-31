---
title: mountainash-transport
description: One file API for Python across local disk, S3-compatible stores, SFTP servers and HTTP(S) endpoints. The path picks the backend.
---

[← Back to Ecosystem](https://docs.mountainash.io/)

# mountainash-transport

**One file API for Python, from a folder on your laptop to S3-compatible buckets, SFTP servers and HTTP(S) endpoints.**

!!! warning "Experimental"
    mountainash-transport 0.1.0 is experimental and not yet ready for production use. Its APIs can change between versions, and it is not yet published on PyPI.

A data job usually starts with a file on local disk. Then the input moves to an S3 bucket, a partner starts dropping files on an SFTP server, and a reference table turns up behind an HTTPS URL. Each store brings its own client library, credentials, error types and idea of what a directory is. Before long the code branches on `if path.startswith("s3://")`, and every package that reads files carries its own copy of those branches.

mountainash-transport gives that code one set of calls. You open storage from a path, and the path's scheme picks the backend: local disk, the S3 family (AWS S3, S3 Express, Cloudflare R2, MinIO and Backblaze B2), SFTP or HTTP(S). The same methods read, write, stream, list, copy and delete on each of them. A storage profile describes the store, credentials arrive separately, and gzip or GPG can be applied to the bytes on their way in or out.

## Who it's for

<div class="grid cards" markdown>

-   **Application developers**

    ---

    Read, write, stream, list and delete files through one `StorageFacade`, whatever the path points at. Ask a store what it supports before calling, and catch one family of storage errors instead of one per client library.

    [Install and open a store](chapters/03-installation/index.md)

-   **Teams working across several stores**

    ---

    Moving between AWS S3, R2, MinIO and B2 is a change of storage profile, not of code. `copy_between` copies a file from one store to another and can compress or encrypt it on the way. Named profiles keep stores and secret references in configuration.

    [Describe your stores](chapters/05-storage-profiles/index.md)

-   **Platform and security engineers**

    ---

    Confine what a piece of code may touch with a location policy: a local root it cannot leave, and an allow list of remote hosts and buckets. Reach a plain-HTTP service on a private network through an SSH bastion; HTTPS targets do not work through a tunnel.

    [Set a location policy](chapters/08-location-policy/index.md)

-   **Packages built on Mountainash**

    ---

    Get bytes, streams and typed errors from one public API and keep format handling in your own package. Credentials come from `mountainash-auth-client` and configuration from `mountainash-settings`.

    [See where transport fits](chapters/02-mountainash-ecosystem/index.md)

-   **Backend contributors**

    ---

    Each capability is a small protocol, each backend implements the ones its store supports, and conformance tests hold every backend to its contract.

    [Read the architecture](chapters/13-architecture/index.md)

</div>

## See it work

The script stores a gzip-compressed CSV on local disk, reads it back with the compression removed and lists its folder. It then opens a facade for an HTTPS URL and asks whether that store can delete files.

```python
import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageDeleteProtocol, StorageFacade

with tempfile.TemporaryDirectory() as root:
    path = str(Path(root) / "reports" / "sales.csv.gz")

    with StorageFacade.from_path(path) as storage:  # a bare path selects local disk
        storage.write(path, b"region,total\nnorth,120\nsouth,95\n", pipeline=Gzip())
        print("stored:", storage.get_size(path), "bytes")
        print("read back:", storage.read(path, infer=True).decode().splitlines())
        listing = storage.list_objects(str(Path(root) / "reports"))
        print("listed:", [Path(entry.path).name for entry in listing.objects])

url = "https://files.example.com/reports/sales.csv.gz"
with StorageFacade.from_path(url) as web:  # an https:// URL selects the HTTP backend
    print("https can delete:", web.supports(StorageDeleteProtocol))
```

Output:

```text
stored: 50 bytes
read back: ['region,total', 'north,120', 'south,95']
listed: ['sales.csv.gz']
https can delete: False
```

The path chose the backend both times, the `.gz` suffix told the read to decompress, and the HTTP facade answered the capability question without sending a request. The local part runs on the base install; the HTTPS facade needs the `[http]` extra.

## Where to go next

- New to the package? Start with [What transport does](chapters/01-what-transport-does/index.md). It assumes Python 3.12 or later, context managers and binary I/O with `bytes` and file objects.
- The [chapter list](chapters/index.md) shows everything the documentation covers.
- The [support matrix and known limits](reference/support-matrix.md) shows what each backend can do.
- [About](about.md) has the design ideas, authorship, the licenses and the link to the code repository.

!!! note "Development baseline"
    This documentation describes version 0.1.0, the development baseline. Until the sibling Mountainash packages are published, install development checkouts side by side, as described in [Optional extras](chapters/03-installation/index.md#optional-extras).
