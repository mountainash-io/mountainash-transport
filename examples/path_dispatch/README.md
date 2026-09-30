# Path dispatch

Which backend does a path select, and how are paths normalised?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/path_dispatch/example.py
```

Expected output:

```text
(bare) -> local
s3 -> s3
r2 -> r2
gs -> gcs
sftp -> sftp
https -> http
```

Detection reads only the scheme; it opens nothing. A scheme may be recognised
before its backend exists: facades for providers without a backend raise
`BackendNotImplementedError` (see the support matrix in the root README).
`StoragePath` helpers accept strings or `UPath` objects and resolve scheme
aliases such as `gcs` to their canonical token.

Next: [storage profiles](../storage_profiles/).
