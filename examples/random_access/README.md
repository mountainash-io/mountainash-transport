# Random access

How do I seek within a large file without reading all of it?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/random_access/example.py
```

Expected output:

```text
local: last 4 bytes fcfdfeff
http none: 8 bytes read in 3 request(s), 9 bytes transferred
http readahead: 8 bytes read in 2 request(s), 65541 bytes transferred
```

`read_stream(path, access="random")` returns a seekable handle. A local file
uses its native handle. Over HTTP, S3 and SFTP each read becomes a byte-range
request; the recipe answers them with a small in-process web server, so nothing
leaves the machine.

`RangePolicy` decides what each request fetches. Both runs start with a 1-byte
probe that checks the server honours ranges. `"none"` then fetches exactly
what each `read` asks for, one request per read. `"readahead"` fetches a window
(here 64 KiB) and serves the next read from it. Pick by access pattern: see
[read access modes](../../docs/read-access-modes.md).

Next: [streaming](../streaming/).
