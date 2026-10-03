# Gzip pipeline

How do I compress on write and decompress on read?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/gzip_pipeline/example.py
```

Expected output:

```text
stored 50 gzip bytes; decoded 32 bytes; output reproducible
```

One `Pipeline` serves both directions: the facade encodes on `write()` and
decodes on `read()`. Without `pipeline=`, `read()` returns the stored bytes.
`Gzip()` defaults to level 6 and `mtime=0`, so identical input produces identical
output. `GPG(...)` stacks the same way (it needs the `[encryption]` extra and a
GnuPG keyring, so no offline recipe runs it). Order transforms like file
suffixes: `Pipeline(GPG(...), Gzip())` stores `*.gz.gpg`.

Next: [suffix inference](../suffix_inference/).
