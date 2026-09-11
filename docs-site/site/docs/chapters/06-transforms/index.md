---
title: "Chapter 6: Transforms"
description: "The stream transform pipeline for transparent compression and encryption during storage operations"
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 6: Transforms

## Summary

This chapter explains the transform pipeline system that lets callers compress,
encrypt, or otherwise process data transparently during read and write
operations. It covers the StreamTransform protocol with its wrap and unwrap
methods, the Pipeline class that chains transforms in order, and the built-in
Gzip and GPG transforms. Readers also learn about suffix-based transform
inference, the materialize utility for converting streams to bytes, and the
PairedStream helper that ties read and write streams together.

## Concepts Covered

- StreamTransform Protocol
- Wrap Method
- Unwrap Method
- Pipeline Class
- Apply Read Direction
- Apply Write Direction
- Gzip Transform
- GPG Transform
- Suffix Transforms Map
- Infer Pipeline Function
- Materialize Utility
- PairedStream Helper

## Learning Graph IDs

41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52

## Prerequisites

- Chapter 1: Foundation Concepts (Python Protocols, Runtime Checkable Protocol, Binary Streams, URL Schemes)
- Chapter 5: StorageFacade (Read Stream Method -- required by PairedStream Helper)

---

## The Need for Stream Transforms

Data at rest is rarely stored in its raw form. Compression reduces storage costs and transfer times. Encryption protects sensitive data from unauthorized access. Some systems layer both -- a file stored as `report.csv.gz.gpg` is first encrypted with GPG, then gzip-compressed (or rather, when reading, the outer gzip layer is stripped first, then the GPG layer is decrypted).

Without a transform system, callers would need to manually decompress and decrypt before reading, and encrypt and compress before writing. This clutters application code with I/O plumbing that obscures the actual business logic. The mountainash-transport transform pipeline makes these operations transparent -- callers specify *what* transforms to apply (or let the library infer them from file suffixes), and the pipeline handles the mechanics.

<!-- concept:41 -->
## StreamTransform Protocol

The **`StreamTransform`** protocol defines the contract that any transform must satisfy. It declares exactly two methods:

```python
@runtime_checkable
class StreamTransform(Protocol):
    def wrap(self, stream: BinaryIO) -> BinaryIO: ...
    def unwrap(self, stream: BinaryIO) -> BinaryIO: ...
```

Both methods take a readable binary stream as input and return a new readable binary stream as output. The transform does not consume the input eagerly (in general) -- it wraps it so that reads from the output stream trigger processing of the input stream on demand.

The naming reflects the layering metaphor: transforms are layers wrapped around data. Writing adds layers (wrapping); reading removes layers (unwrapping). This metaphor makes multi-transform pipelines intuitive -- you wrap layers on during write and unwrap them in reverse during read.

<!-- concept:42 -->
## Wrap Method

The **`wrap`** method encodes data: it takes a plaintext stream and returns an encoded stream. "Encoded" means whatever the transform does -- compression, encryption, base64 encoding, or any other reversible transformation.

When you call `gzip_transform.wrap(plaintext_stream)`, the returned stream yields gzip-compressed bytes when read. The original `plaintext_stream` is consumed lazily as the caller reads from the wrapped stream. This lazy behavior is critical for memory efficiency with large files.

The wrap direction is used during **write operations**. When the facade writes data through a pipeline, it applies `wrap` to encode the data before sending it to the backend. The data stored on disk or in object storage is in its encoded (compressed, encrypted) form.

<!-- concept:43 -->
## Unwrap Method

The **`unwrap`** method decodes data: it takes an encoded stream and returns a plaintext stream. It is the logical inverse of `wrap`.

When you call `gzip_transform.unwrap(compressed_stream)`, the returned stream yields decompressed plaintext bytes. The `compressed_stream` is consumed as reads occur on the unwrapped stream.

The unwrap direction is used during **read operations**. When the facade reads data through a pipeline, it applies `unwrap` to decode the data after receiving it from the backend. The caller receives plaintext regardless of how the data is stored.

| Direction | Method | When Used | Data Flow |
|---|---|---|---|
| Encode | `wrap` | Writing to storage | plaintext -> encoded |
| Decode | `unwrap` | Reading from storage | encoded -> plaintext |

<!-- concept:44 -->
## Pipeline Class

The **`Pipeline`** class chains multiple transforms in a defined order. It represents the layering as stored on disk, with transforms listed outermost-first:

```python
class Pipeline:
    def __init__(self, *transforms: StreamTransform) -> None:
        self._outer_to_inner: tuple[StreamTransform, ...] = transforms
```

The outermost-first ordering means that for a file stored as `data.csv.gz.gpg`, the pipeline is `Pipeline(Gzip(), GPG(...))` -- Gzip is the outer layer (applied last during write, stripped first during read), and GPG is the inner layer.

A pipeline with no transforms (`Pipeline()`) acts as a pass-through -- it returns the input stream unchanged. This identity behavior simplifies the facade code, which can always call `pipeline.apply_read()` without checking for empty pipelines.

#### Diagram: Pipeline Layer Model

<iframe src="../../sims/pipeline-layer-model/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Pipeline Layer Model</summary>
Type: diagram
**sim-id:** pipeline-layer-model<br/>
**Library:** p5.js<br/>
**Status:** Specified

**Purpose:** Visualize the onion-layer model of a pipeline: plaintext at the center, inner transforms as inner rings, outer transforms as outer rings. Show how read peels from outside in and write wraps from inside out.

**Components:**

- Concentric rings representing layers: center = plaintext, ring 1 = GPG (inner), ring 2 = Gzip (outer)
- Two animated arrows: "Read direction" peeling rings outward-to-inward, "Write direction" adding rings inward-to-outward
- Labels on each ring showing the transform name and its wrap/unwrap operation
- File suffix annotation showing how `.csv.gz.gpg` maps to the layers

**Interactions:** Click "Read" or "Write" button to animate the corresponding direction. Drag to rotate the visualization. Click a ring to see the transform's parameters.

**Learning Objective:** Visualize the relationship between transform ordering and read/write directions (Bloom: Understand)
</details>

<!-- concept:45 -->
## Apply Read Direction

The **`apply_read`** method processes a stream through the pipeline in read direction -- stripping layers outermost to innermost by calling `unwrap` on each transform in list order:

```python
def apply_read(self, stream: BinaryIO) -> BinaryIO:
    for t in self._outer_to_inner:
        stream = t.unwrap(stream)
    return stream
```

For `Pipeline(Gzip(), GPG(passphrase="secret"))` reading a `.csv.gz.gpg` file:

1. Backend returns a stream of encrypted-then-compressed bytes.
2. `Gzip().unwrap(stream)` strips the outer gzip layer, yielding GPG-encrypted bytes.
3. `GPG().unwrap(stream)` strips the inner GPG layer, yielding plaintext CSV.

The final stream returned to the caller contains the original plaintext data.

<!-- concept:46 -->
## Apply Write Direction

The **`apply_write`** method processes a stream in write direction -- adding layers innermost to outermost by calling `wrap` on each transform in **reverse** list order:

```python
def apply_write(self, stream: BinaryIO) -> BinaryIO:
    for t in reversed(self._outer_to_inner):
        stream = t.wrap(stream)
    return stream
```

For the same pipeline writing plaintext CSV to `data.csv.gz.gpg`:

1. Caller provides a stream of plaintext CSV bytes.
2. `GPG().wrap(stream)` adds the inner GPG encryption layer.
3. `Gzip().wrap(stream)` adds the outer gzip compression layer.

The final stream sent to the backend contains compressed-then-encrypted bytes, ready for storage.

The reversed iteration in `apply_write` is the key insight: the pipeline stores transforms in the order they appear on disk (outer-first), but writing applies them in reverse (inner-first) because you build layers from the inside out.

<!-- concept:47 -->
## Gzip Transform

The **`Gzip`** transform provides gzip compression and decompression using Python's standard library. It requires no external dependencies:

```python
class Gzip:
    def __init__(self, level: int = 6, mtime: int | None = 0) -> None:
        self.level = level
        self.mtime = mtime

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        return GzipCompressingReader(stream, level=self.level, mtime=self.mtime)

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        return gzip.GzipFile(fileobj=stream, mode="rb")
```

The constructor accepts two optional parameters. The `level` parameter controls compression effort (1 = fastest/least compression, 9 = slowest/best compression, default 6). The `mtime` parameter sets the modification time in the gzip header -- defaulting to 0 for reproducible output (different runs produce identical bytes), which is important for content-addressable storage and caching.

The `wrap` method uses a custom `GzipCompressingReader` class that streams gzip-encoded bytes lazily -- unlike the stdlib `gzip.GzipFile` in write mode, which requires a writable target. The `unwrap` method uses the standard `gzip.GzipFile` in read mode, which lazily decompresses as the caller reads.

<!-- concept:48 -->
## GPG Transform

The **`GPG`** transform provides GPG encryption and decryption using the `python-gnupg` package (an optional dependency installed via the `[encryption]` extra):

```python
class GPG:
    def __init__(
        self,
        recipients: list[str] | None = None,
        gnupghome: str | None = None,
        passphrase: str | None = None,
        armor: bool = False,
        always_trust: bool = False,
    ) -> None: ...
```

Unlike the Gzip transform, GPG does **not** stream lazily. The `python-gnupg` library requires the entire payload to be available for encryption or decryption. Both `wrap` and `unwrap` materialize the full stream into memory and return a `BytesIO` buffer. For very large files, callers should use the `materialize` utility to spill to a temporary file before applying GPG transforms.

The `wrap` method requires `recipients` to be set (encryption needs to know who can decrypt). It calls `gpg.encrypt_file()` and raises `TransformError` if encryption fails. The `unwrap` method uses `gpg.decrypt_file()` with an optional passphrase and similarly raises `TransformError` on failure.

!!! warning "GPG Memory Usage"
    The GPG transform buffers the entire file in memory. For files larger than available RAM, consider streaming the file to a temporary location, applying GPG via the command-line tool, and then uploading the result. The transform is designed for moderate-sized files (configuration, keys, credentials, small datasets) rather than multi-gigabyte archives.

<!-- concept:49 -->
## Suffix Transforms Map

The **`SUFFIX_TRANSFORMS`** dictionary maps file suffixes to transform type identifiers:

```python
SUFFIX_TRANSFORMS: dict[str, str] = {
    ".gz":   "gzip",
    ".gzip": "gzip",
    ".gpg":  "gpg",
    ".asc":  "gpg",
    ".pgp":  "gpg",
}
```

This map is the foundation of suffix-based transform inference. When the library encounters a path ending in `.gz`, it knows to apply a Gzip transform. When it encounters `.gpg`, `.asc`, or `.pgp`, it knows to apply a GPG transform.

The map uses lowercase suffixes exclusively -- the inference function normalizes suffixes to lowercase before lookup. The map is intentionally simple and does not include every possible compression format (no `.bz2`, `.zstd`, `.lz4`). Additional transforms can be registered in future versions by extending this dictionary.

<!-- concept:50 -->
## Infer Pipeline Function

The **`infer_pipeline`** function parses a path's suffix chain right-to-left and constructs a `Pipeline` from the recognized suffixes:

```python
def infer_pipeline(
    path: str,
    *,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> tuple[Pipeline | None, str]:
```

The function returns a tuple of `(pipeline, stripped_path)`. The `stripped_path` has all recognized suffixes removed -- useful for determining the underlying file type. If no recognized suffixes are found, `pipeline` is `None` and `stripped_path` equals the original path.

The right-to-left parsing order matters. For `report.csv.gz.gpg`:

1. Rightmost suffix: `.gpg` maps to `"gpg"` -- add GPG to the list.
2. Next suffix: `.gz` maps to `"gzip"` -- add Gzip to the list.
3. Next suffix: `.csv` -- not in `SUFFIX_TRANSFORMS`, stop parsing.

The resulting list `[GPG, Gzip]` is in outermost-first order, which is exactly what `Pipeline.__init__` expects. The stripped path is `report.csv`.

```python
pipeline, stripped = infer_pipeline("data/report.csv.gz.gpg", gpg=GPG(passphrase="x"))
# pipeline = Pipeline(GPG(...), Gzip())
# stripped = "data/report.csv"
```

If a GPG-family suffix is found but `gpg=None`, the function raises `ValueError` -- the caller must provide key material for decryption. The `gzip` parameter is optional; if omitted, a default `Gzip()` instance is used.

#### Diagram: Suffix Inference Pipeline Construction

<iframe src="../../sims/suffix-inference-pipeline/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Suffix Inference Pipeline Construction</summary>
Type: workflow
**sim-id:** suffix-inference-pipeline<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Animate the right-to-left suffix parsing process, showing how each suffix is consumed, mapped to a transform, and added to the pipeline.

**Components:**

- Input: editable path string (e.g., "s3://bucket/data.csv.gz.gpg")
- Suffix chain displayed as segments that are consumed one at a time
- SUFFIX_TRANSFORMS lookup table shown as a reference panel
- Growing pipeline visualization as transforms are added
- Output: final Pipeline object and stripped path

**Interactions:** Edit the path string to see different suffix chains parsed. Step through the parsing with next/prev buttons. Click a suffix to see its lookup in SUFFIX_TRANSFORMS.

**Learning Objective:** Apply the right-to-left suffix parsing algorithm to construct pipelines (Bloom: Apply)
</details>

<!-- concept:51 -->
## Materialize Utility

The **`materialize`** function drains a stream into a seekable buffer, returning both the buffer and its byte length:

```python
def materialize(
    stream: BinaryIO,
    *,
    to: Literal["memory", "tempfile"] = "memory",
    memory_cutoff: int = 64 * 1024 * 1024,
) -> tuple[BinaryIO, int]:
```

Two modes are available. The `"memory"` mode creates a `BytesIO` buffer -- simple and fast, but bounded by available RAM. The `"tempfile"` mode uses `tempfile.SpooledTemporaryFile`, which starts in memory but automatically rolls to disk when the content exceeds `memory_cutoff` (default 64 MB).

After materialization, the returned buffer is positioned at byte 0 and the original stream is exhausted. The length is provided because some operations (like S3's `put_object` with content-length headers) need to know the payload size before writing.

Common use cases for `materialize` include:

- Converting a stream to bytes when the `read()` method is not available or when the length is needed.
- Buffering data before applying the GPG transform (which cannot stream).
- Re-reading a stream multiple times (streams are normally consumed once).

<!-- concept:52 -->
## PairedStream Helper

The **`_PairedStream`** class (internal to the facade module) solves a resource management problem. When a pipeline wraps a source stream, the caller receives the outermost wrapper. Closing that wrapper may not propagate to the original source stream, leading to file descriptor leaks.

`_PairedStream` wraps both the transformed stream and the source stream, ensuring both are closed when the caller closes the returned stream:

```python
class _PairedStream(io.RawIOBase):
    def __init__(self, wrapped: BinaryIO, source: BinaryIO) -> None:
        self._wrapped = wrapped
        self._source = source

    def close(self) -> None:
        try:
            if self._wrapped is not self._source:
                self._wrapped.close()
        finally:
            self._source.close()
            super().close()
```

The `read_stream` method on `StorageFacade` returns a `_PairedStream` that pairs the pipeline-transformed stream with the backend's raw stream. This guarantees that `stream.close()` (or exiting a `with` block) releases all underlying resources regardless of how many transform layers are active.

The class also implements `readable()`, `readinto()`, and `read()` to satisfy the `BinaryIO` interface, delegating all reads to the wrapped (transformed) stream.

#### Diagram: PairedStream Resource Chain

<iframe src="../../sims/paired-stream-chain/main.html" width="100%" height="350px" scrolling="no"></iframe>
<details markdown="1">
<summary>PairedStream Resource Chain</summary>
Type: diagram
**sim-id:** paired-stream-chain<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show the chain of stream objects from backend source through pipeline transforms to the PairedStream wrapper, with close propagation arrows.

**Components:**

- Linear chain: Backend source stream -> Gzip unwrap stream -> GPG unwrap stream -> PairedStream (returned to caller)
- Close propagation arrows showing how PairedStream.close() reaches back to both the outermost transform and the source
- Resource leak scenario (without PairedStream) shown in a dimmed alternative path

**Interactions:** Click "close()" on the PairedStream to animate close propagation. Toggle "without PairedStream" to see the resource leak scenario. Hover over streams to see their type and state.

**Learning Objective:** Understand why PairedStream is necessary for resource safety in multi-transform pipelines (Bloom: Understand)
</details>

## Writing Custom Transforms

Because `StreamTransform` is a protocol (not an abstract base class), writing a custom transform requires only implementing `wrap` and `unwrap` with the correct signatures. Here is a conceptual example of a base64 transform:

```python
import base64
import io
from typing import BinaryIO

class Base64Transform:
    def wrap(self, stream: BinaryIO) -> BinaryIO:
        data = stream.read()
        encoded = base64.b64encode(data)
        return io.BytesIO(encoded)

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        data = stream.read()
        decoded = base64.b64decode(data)
        return io.BytesIO(decoded)
```

This transform satisfies `StreamTransform` without importing it or inheriting from it -- structural subtyping at work. It can be used in a pipeline alongside the built-in transforms:

```python
pipeline = Pipeline(Base64Transform(), Gzip())
facade.write("s3://bucket/data.csv.gz.b64", content, pipeline=pipeline)
```

The main constraint is that `wrap` and `unwrap` must be true inverses: `unwrap(wrap(stream))` must produce the original data. If this invariant is violated, data corruption results.

## Key Takeaways

- **`StreamTransform`** is a runtime-checkable protocol with two methods: `wrap` (encode for writing) and `unwrap` (decode for reading).
- **`Pipeline`** chains transforms in outermost-first order; `apply_read` unwraps in list order, `apply_write` wraps in reverse order.
- The **Gzip transform** streams lazily and uses Python's stdlib -- no external dependencies. Default `mtime=0` produces reproducible output.
- The **GPG transform** buffers the entire payload in memory (python-gnupg limitation) and requires the `[encryption]` extra.
- **`SUFFIX_TRANSFORMS`** maps five file suffixes (`.gz`, `.gzip`, `.gpg`, `.asc`, `.pgp`) to their transform types.
- **`infer_pipeline`** parses suffixes right-to-left to automatically construct pipelines from file paths, stopping at the first unrecognized suffix.
- **`materialize`** converts a stream to a seekable buffer (memory or tempfile) when length is needed or when a transform requires random access.
- **`_PairedStream`** ensures that closing the caller's stream propagates to both the transform wrapper and the underlying backend source stream.
- Custom transforms can be written by implementing the `wrap`/`unwrap` protocol -- no inheritance required.
- The transform system is transparent to callers: `facade.read(path, infer=True)` handles all decompression/decryption automatically based on the file's suffix chain.
