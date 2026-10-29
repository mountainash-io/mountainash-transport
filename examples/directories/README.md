# Directories

How do I create, list, copy within and remove a directory?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/directories/example.py
```

Expected output:

```text
listed sales-backup.csv, sales.csv; directory removed
```

`list_dir()` returns `StorageEntry` records for a filesystem-style directory.
`copy()` is a same-backend copy; to move data between backends, see
[cross-backend copy](../cross_backend_copy/). Bucket stores expose prefix
listing through `list_objects()` instead.

Next: [capability checks](../capability_checks/).
