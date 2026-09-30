# Capability checks

How do I find out what a backend supports before calling it?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/capability_checks/example.py
```

Expected output:

```text
local: read, write, metadata, directory
https: read, write, metadata; list_dir refused
```

Backends implement capability protocols à la carte. `supports()` is an
`isinstance` check against the backend; every facade method checks its protocol
first and raises `UnsupportedOperationError` instead of failing inside an SDK.
Constructing either facade here opens no connection and sends no request.

Next: [gzip pipeline](../gzip_pipeline/).
