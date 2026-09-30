# Local files

How do I write, read, inspect and delete a file?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/local_files/example.py
```

Expected output:

```text
sales.csv: 32 bytes written, read back and deleted
```

`StorageFacade.from_path()` picks the backend from the path's scheme; a bare
path selects the local filesystem. The same calls work on any backend that
implements the matching capability; see [capability checks](../capability_checks/).

Next: [directories](../directories/).
