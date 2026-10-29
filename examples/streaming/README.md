# Streaming

How do I process a file without holding it in memory?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/streaming/example.py
```

Expected output:

```text
streamed total: 215
```

`read_stream()` returns a binary stream; close it (a `with` block does) to
release both the decoder and the backend handle. `write_stream()` consumes any
binary stream. Streams have no known length after transforms; buffer
explicitly if a consumer needs one.

Next: [cross-backend copy](../cross_backend_copy/).
