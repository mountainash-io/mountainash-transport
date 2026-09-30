# Cross-backend copy

How do I copy between two storages and re-encode on the way?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/cross_backend_copy/example.py
```

Expected output:

```text
copied 32 bytes; archived 50 gzip bytes
```

`copy_between()` takes separate facades, so source and destination may be
different backends (for example SFTP to S3) with their own profiles and auth.
With no pipelines and matching backends it delegates to the backend's native
copy; any `source_pipeline=` or `destination_pipeline=` streams the data through
this process. Both local facades here stand in for two different stores.

Next: [path dispatch](../path_dispatch/).
