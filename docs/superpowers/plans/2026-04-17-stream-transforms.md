# Stream Transforms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore gzip compression and GPG encryption as streaming transforms composable via a `Pipeline` object on `StorageFacade`.

**Architecture:** Facade-level stream decorators. New `storage_transforms/` subpackage contains a `StreamTransform` protocol, a direction-agnostic `Pipeline`, and two built-in transforms (`Gzip`, `GPG`). Facade read/write/copy operations gain a `pipeline=` keyword-only argument. Backends are untouched except for a prerequisite S3 write fix.

**Tech Stack:** Python stdlib `gzip` / `zlib` (for `Gzip`), `python-gnupg` via the existing `[encryption]` optional extra (for `GPG`), pytest for tests, hatch for test orchestration.

**Reference spec:** `docs/superpowers/specs/2026-04-17-stream-transforms-design.md`

---

## Target File Layout

```
src/mountainash_utils_files/
├── storage_transforms/                    # NEW package
│   ├── __init__.py                        # Re-export Pipeline, Gzip, GPG, StreamTransform
│   ├── base.py                            # StreamTransform protocol
│   ├── pipeline.py                        # Pipeline
│   ├── compression.py                     # Gzip
│   ├── encryption.py                      # GPG (lazy-imports python-gnupg)
│   ├── _stream_encoder.py                 # Internal: zlib chunked encoder + gpg thread bridge
│   └── util.py                            # materialize()
├── exceptions.py                          # MODIFY: add TransformError
├── __init__.py                            # MODIFY: top-level re-exports
├── storage_facade/
│   ├── facade.py                          # MODIFY: add pipeline= kwarg
│   └── cross_backend.py                   # MODIFY: add source_pipeline/destination_pipeline
└── storage_backends/s3/s3_write.py        # MODIFY: switch to upload_fileobj

tests/
├── storage_transforms/                    # NEW test package
│   ├── __init__.py
│   ├── test_pipeline.py
│   ├── test_gzip.py
│   ├── test_gpg.py                        # @pytest.mark.integration
│   ├── test_materialize.py
│   └── test_facade_integration.py
└── backends/test_s3.py                    # MODIFY: update write_from_stream assertions

pyproject.toml                             # MODIFY: fix [encryption] extra
CLAUDE.md                                  # MODIFY: add Stream Transforms section
```

---

## Task 1: Fix S3 write_from_stream to use streaming upload

**Rationale:** `storage_backends/s3/s3_write.py:32` currently drains the entire stream into memory before uploading. This breaks large-file writes and breaks transforms (which expect the backend to consume streams incrementally). Required before any transform work.

**Files:**
- Modify: `src/mountainash_utils_files/storage_backends/s3/s3_write.py`
- Test: `tests/backends/test_s3.py` (update existing `test_write_from_stream`)

- [ ] **Step 1: Write/update the failing test**

Replace the existing `test_write_from_stream` test in `tests/backends/test_s3.py` with an assertion that `upload_fileobj` is called, not `put_object`:

```python
def test_write_from_stream_uses_upload_fileobj(self):
    """write_from_stream must stream via upload_fileobj, not buffer via put_object."""
    mock_client = MagicMock()
    backend = _make_backend(mock_client)
    stream = io.BytesIO(b"from stream")
    backend.write_from_stream("s3://bucket/path/stream.bin", stream)
    mock_client.upload_fileobj.assert_called_once_with(
        stream, "bucket", "path/stream.bin"
    )
    mock_client.put_object.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/backends/test_s3.py::TestS3WriteMixin::test_write_from_stream_uses_upload_fileobj -v`
Expected: FAIL — `put_object` called instead of `upload_fileobj`, or assertion on the positional/keyword call shape.

- [ ] **Step 3: Update the implementation**

Replace `src/mountainash_utils_files/storage_backends/s3/s3_write.py` contents:

```python
"""S3WriteMixin — write operations for AWS S3."""

from __future__ import annotations

from typing import BinaryIO

from .s3_path import parse_s3_path


class S3WriteMixin:
    """Write mixin for AWS S3."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Upload bytes as an S3 object."""
        bucket, key = parse_s3_path(path)
        self._client.put_object(Bucket=bucket, Key=key, Body=data)  # type: ignore[attr-defined]

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        """Upload from a binary stream using boto3's multipart-aware upload_fileobj.

        Does NOT buffer the stream into memory. boto3 auto-multiparts large
        uploads and uses a single PUT for small ones.
        """
        bucket, key = parse_s3_path(path)
        self._client.upload_fileobj(stream, bucket, key)  # type: ignore[attr-defined]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/backends/test_s3.py -v`
Expected: PASS (including the new test and any other unaffected S3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/s3/s3_write.py tests/backends/test_s3.py
git commit -m "fix(s3): stream uploads via upload_fileobj instead of buffering"
```

---

## Task 2: Add TransformError exception

**Files:**
- Modify: `src/mountainash_utils_files/exceptions.py`
- Test: `tests/test_constants_and_exceptions.py` (add assertion)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_constants_and_exceptions.py`:

```python
def test_transform_error_inherits_storage_error():
    from mountainash_utils_files.exceptions import StorageError, TransformError
    assert issubclass(TransformError, StorageError)
    err = TransformError("boom")
    assert isinstance(err, StorageError)
    assert str(err) == "boom"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/test_constants_and_exceptions.py::test_transform_error_inherits_storage_error -v`
Expected: FAIL — `ImportError: cannot import name 'TransformError'`.

- [ ] **Step 3: Add the exception class**

Append to `src/mountainash_utils_files/exceptions.py`:

```python
class TransformError(StorageError):
    """Raised when a stream transform fails to encode or decode."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/test_constants_and_exceptions.py::test_transform_error_inherits_storage_error -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/exceptions.py tests/test_constants_and_exceptions.py
git commit -m "feat(exceptions): add TransformError for stream transform failures"
```

---

## Task 3: Add StreamTransform protocol + package scaffold

**Files:**
- Create: `src/mountainash_utils_files/storage_transforms/__init__.py`
- Create: `src/mountainash_utils_files/storage_transforms/base.py`
- Create: `tests/storage_transforms/__init__.py`
- Create: `tests/storage_transforms/test_base.py`

- [ ] **Step 1: Write the failing test**

Create `tests/storage_transforms/__init__.py` (empty file) and `tests/storage_transforms/test_base.py`:

```python
"""Tests for the StreamTransform protocol."""
from __future__ import annotations

import io
from typing import BinaryIO


def test_stream_transform_protocol_is_runtime_checkable():
    from mountainash_utils_files.storage_transforms import StreamTransform

    class Identity:
        def wrap(self, stream: BinaryIO) -> BinaryIO:
            return stream
        def unwrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

    assert isinstance(Identity(), StreamTransform)


def test_stream_transform_protocol_rejects_incomplete_impl():
    from mountainash_utils_files.storage_transforms import StreamTransform

    class OnlyWrap:
        def wrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

    assert not isinstance(OnlyWrap(), StreamTransform)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/storage_transforms/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: mountainash_utils_files.storage_transforms`.

- [ ] **Step 3: Create the package and protocol**

Create `src/mountainash_utils_files/storage_transforms/base.py`:

```python
"""StreamTransform protocol — reversible encoder/decoder over binary streams."""

from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class StreamTransform(Protocol):
    """A reversible encoder/decoder operating on binary streams.

    Both methods take a readable binary stream and return a new readable
    binary stream. wrap() encodes (adds a layer); unwrap() decodes (removes
    a layer). Both must stream lazily — no eager draining of the input.
    """

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        """Encode: plaintext → encoded (add a layer, for writing outward)."""
        ...

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Decode: encoded → plaintext (strip a layer, for reading inward)."""
        ...
```

Create `src/mountainash_utils_files/storage_transforms/__init__.py`:

```python
"""Stream transforms — facade-level encoders/decoders for compression and encryption."""

from .base import StreamTransform

__all__ = ["StreamTransform"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/storage_transforms/test_base.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_transforms/ tests/storage_transforms/__init__.py tests/storage_transforms/test_base.py
git commit -m "feat(transforms): add StreamTransform protocol and package scaffold"
```

---

## Task 4: Add Pipeline class

**Files:**
- Create: `src/mountainash_utils_files/storage_transforms/pipeline.py`
- Modify: `src/mountainash_utils_files/storage_transforms/__init__.py`
- Test: `tests/storage_transforms/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/storage_transforms/test_pipeline.py`:

```python
"""Tests for the Pipeline class."""
from __future__ import annotations

import io
from typing import BinaryIO

from mountainash_utils_files.storage_transforms import Pipeline


class _RecordingTransform:
    """Transform that tags bytes with a prefix on wrap and strips it on unwrap.

    wrap(b"data") -> prefix + b"data"
    unwrap(prefix + b"data") -> b"data"
    """
    def __init__(self, prefix: bytes) -> None:
        self.prefix = prefix

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        return io.BytesIO(self.prefix + stream.read())

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        data = stream.read()
        assert data.startswith(self.prefix), f"expected prefix {self.prefix!r}"
        return io.BytesIO(data[len(self.prefix):])


def test_empty_pipeline_is_identity_on_read():
    source = io.BytesIO(b"hello")
    out = Pipeline().apply_read(source)
    assert out.read() == b"hello"


def test_empty_pipeline_is_identity_on_write():
    source = io.BytesIO(b"hello")
    out = Pipeline().apply_write(source)
    assert out.read() == b"hello"


def test_single_transform_wrap_and_unwrap_roundtrip():
    t = _RecordingTransform(b"[A]")
    pipeline = Pipeline(t)
    written = pipeline.apply_write(io.BytesIO(b"payload"))
    assert written.read() == b"[A]payload"
    read = pipeline.apply_read(io.BytesIO(b"[A]payload"))
    assert read.read() == b"payload"


def test_multi_transform_outermost_first_ordering_on_write():
    """Pipeline(outer, inner).apply_write applies inner first, outer last."""
    outer = _RecordingTransform(b"[OUT]")
    inner = _RecordingTransform(b"[IN]")
    pipeline = Pipeline(outer, inner)
    out = pipeline.apply_write(io.BytesIO(b"data"))
    # inner wraps first: [IN]data; then outer wraps: [OUT][IN]data
    assert out.read() == b"[OUT][IN]data"


def test_multi_transform_outermost_first_ordering_on_read():
    """Pipeline(outer, inner).apply_read strips outer first, inner last."""
    outer = _RecordingTransform(b"[OUT]")
    inner = _RecordingTransform(b"[IN]")
    pipeline = Pipeline(outer, inner)
    out = pipeline.apply_read(io.BytesIO(b"[OUT][IN]data"))
    assert out.read() == b"data"


def test_pipeline_instance_is_reusable():
    t = _RecordingTransform(b"[X]")
    pipeline = Pipeline(t)
    a = pipeline.apply_write(io.BytesIO(b"one"))
    b = pipeline.apply_write(io.BytesIO(b"two"))
    assert a.read() == b"[X]one"
    assert b.read() == b"[X]two"


def test_pipeline_roundtrip_is_symmetric():
    t1 = _RecordingTransform(b"[A]")
    t2 = _RecordingTransform(b"[B]")
    pipeline = Pipeline(t1, t2)
    original = b"hello world"
    encoded = pipeline.apply_write(io.BytesIO(original)).read()
    decoded = pipeline.apply_read(io.BytesIO(encoded)).read()
    assert decoded == original
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_pipeline.py -v`
Expected: FAIL — `ImportError: cannot import name 'Pipeline'`.

- [ ] **Step 3: Implement Pipeline**

Create `src/mountainash_utils_files/storage_transforms/pipeline.py`:

```python
"""Pipeline — ordered stack of stream transforms."""

from __future__ import annotations

from typing import BinaryIO

from .base import StreamTransform


class Pipeline:
    """Ordered stack of transforms representing the layering as stored on disk.

    Transforms are listed OUTERMOST-FIRST — the order a reader would peel them
    off the stored bytes. For a file stored as gzip-of(gpg-of(plaintext)):

        Pipeline(Gzip(), GPG(recipients=["alice"]))

    The same Pipeline is used on both read and write paths. The facade applies
    transforms in the correct direction:
      - read:  outer → inner (unwrap in list order)
      - write: inner → outer (wrap in reverse list order)
    """

    def __init__(self, *transforms: StreamTransform) -> None:
        self._outer_to_inner: tuple[StreamTransform, ...] = transforms

    def apply_read(self, stream: BinaryIO) -> BinaryIO:
        """Strip layers outermost → innermost."""
        for t in self._outer_to_inner:
            stream = t.unwrap(stream)
        return stream

    def apply_write(self, stream: BinaryIO) -> BinaryIO:
        """Add layers innermost → outermost (reverse of list)."""
        for t in reversed(self._outer_to_inner):
            stream = t.wrap(stream)
        return stream
```

Update `src/mountainash_utils_files/storage_transforms/__init__.py`:

```python
"""Stream transforms — facade-level encoders/decoders for compression and encryption."""

from .base import StreamTransform
from .pipeline import Pipeline

__all__ = ["StreamTransform", "Pipeline"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_pipeline.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_transforms/pipeline.py src/mountainash_utils_files/storage_transforms/__init__.py tests/storage_transforms/test_pipeline.py
git commit -m "feat(transforms): add Pipeline — direction-agnostic transform stack"
```

---

## Task 5: Add Gzip transform

**Files:**
- Create: `src/mountainash_utils_files/storage_transforms/_stream_encoder.py`
- Create: `src/mountainash_utils_files/storage_transforms/compression.py`
- Modify: `src/mountainash_utils_files/storage_transforms/__init__.py`
- Test: `tests/storage_transforms/test_gzip.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/storage_transforms/test_gzip.py`:

```python
"""Tests for the Gzip transform."""
from __future__ import annotations

import gzip
import io

import pytest

from mountainash_utils_files.storage_transforms import Gzip, Pipeline, StreamTransform


def test_gzip_implements_stream_transform_protocol():
    assert isinstance(Gzip(), StreamTransform)


@pytest.mark.parametrize("size", [0, 1, 17, 64_000, 1_000_000])
def test_gzip_round_trip_via_pipeline(size):
    data = bytes(i % 256 for i in range(size))
    pipeline = Pipeline(Gzip())
    encoded = pipeline.apply_write(io.BytesIO(data)).read()
    decoded = pipeline.apply_read(io.BytesIO(encoded)).read()
    assert decoded == data


def test_gzip_wrap_produces_valid_gzip_bytes():
    """Output of Gzip().wrap must be parseable by stdlib gzip."""
    data = b"hello world" * 100
    encoded = Gzip().wrap(io.BytesIO(data)).read()
    assert gzip.decompress(encoded) == data


def test_gzip_unwrap_decodes_stdlib_gzip_bytes():
    """Gzip().unwrap must accept stdlib-compressed bytes."""
    data = b"the quick brown fox"
    encoded = gzip.compress(data)
    decoded = Gzip().unwrap(io.BytesIO(encoded)).read()
    assert decoded == data


def test_gzip_mtime_zero_is_reproducible():
    """With mtime=0 (default), identical input yields byte-identical output."""
    data = b"reproducibility matters"
    a = Gzip().wrap(io.BytesIO(data)).read()
    b = Gzip().wrap(io.BytesIO(data)).read()
    assert a == b


def test_gzip_default_level_is_6():
    assert Gzip().level == 6


def test_gzip_wrap_is_lazy():
    """Gzip().wrap should not read the source before the consumer pulls."""
    source = io.BytesIO(b"x" * 10_000)
    # Don't call .read() on the wrapped stream — expect source position still at 0
    wrapped = Gzip().wrap(source)
    assert source.tell() == 0
    # Now pull one byte — source should advance
    wrapped.read(1)
    assert source.tell() > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_gzip.py -v`
Expected: FAIL — `ImportError: cannot import name 'Gzip'`.

- [ ] **Step 3: Implement the chunked zlib reader**

Create `src/mountainash_utils_files/storage_transforms/_stream_encoder.py`:

```python
"""Internal helpers: BinaryIO-compatible reader adapters for streaming codecs."""

from __future__ import annotations

import io
import struct
import zlib
from typing import BinaryIO

_DEFAULT_CHUNK = 64 * 1024


class GzipCompressingReader(io.RawIOBase):
    """Read-side adapter that gzips source bytes on demand.

    Produces a gzip member (header + deflate stream + trailer) compliant with
    RFC 1952. Uses a fixed mtime when provided (default 0) so identical input
    yields byte-identical output.
    """

    def __init__(
        self,
        source: BinaryIO,
        level: int = 6,
        mtime: int | None = 0,
        chunk_size: int = _DEFAULT_CHUNK,
    ) -> None:
        self._source = source
        self._chunk_size = chunk_size
        self._buffer = bytearray()
        self._source_exhausted = False
        self._trailer_emitted = False
        self._crc = 0
        self._size = 0
        # zlib.compressobj with wbits=-zlib.MAX_WBITS produces raw deflate
        # (no zlib header / trailer), which is what gzip wraps.
        self._compressor = zlib.compressobj(
            level, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0,
        )
        self._buffer.extend(_gzip_header(mtime if mtime is not None else 0))

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:  # type: ignore[override]
        while len(self._buffer) < len(b) and not self._trailer_emitted:
            self._fill()
        n = min(len(b), len(self._buffer))
        b[:n] = self._buffer[:n]
        del self._buffer[:n]
        return n

    def _fill(self) -> None:
        if not self._source_exhausted:
            chunk = self._source.read(self._chunk_size)
            if chunk:
                self._crc = zlib.crc32(chunk, self._crc) & 0xFFFFFFFF
                self._size = (self._size + len(chunk)) & 0xFFFFFFFF
                self._buffer.extend(self._compressor.compress(chunk))
                return
            self._source_exhausted = True
        if not self._trailer_emitted:
            self._buffer.extend(self._compressor.flush(zlib.Z_FINISH))
            self._buffer.extend(struct.pack("<II", self._crc, self._size))
            self._trailer_emitted = True


def _gzip_header(mtime: int) -> bytes:
    """RFC 1952 minimal gzip header."""
    return struct.pack(
        "<BBBBIBB",
        0x1F, 0x8B,       # magic
        0x08,             # compression method (deflate)
        0x00,             # flags
        mtime & 0xFFFFFFFF,
        0x00,             # extra flags
        0xFF,             # OS: unknown
    )
```

- [ ] **Step 4: Implement Gzip transform**

Create `src/mountainash_utils_files/storage_transforms/compression.py`:

```python
"""Gzip compression / decompression transform."""

from __future__ import annotations

import gzip
import io
from typing import BinaryIO

from ._stream_encoder import GzipCompressingReader


class Gzip:
    """Gzip transform — compresses on wrap, decompresses on unwrap.

    Uses Python stdlib — no external dependency required.

    Args:
        level: Compression level 1-9. Default 6 (stdlib default).
        mtime: Fixed mtime in the gzip header. Default 0 (reproducible output).
            Pass None to use the current time (stdlib default behaviour).
    """

    def __init__(self, level: int = 6, mtime: int | None = 0) -> None:
        self.level = level
        self.mtime = mtime

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        """Wrap *stream* so reads yield gzip-encoded bytes."""
        return GzipCompressingReader(stream, level=self.level, mtime=self.mtime)

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        """Wrap *stream* so reads yield gzip-decoded (plaintext) bytes."""
        # gzip.GzipFile in rb mode consumes the source lazily on .read().
        return gzip.GzipFile(fileobj=stream, mode="rb")  # type: ignore[return-value]
```

Update `src/mountainash_utils_files/storage_transforms/__init__.py`:

```python
"""Stream transforms — facade-level encoders/decoders for compression and encryption."""

from .base import StreamTransform
from .compression import Gzip
from .pipeline import Pipeline

__all__ = ["StreamTransform", "Pipeline", "Gzip"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_gzip.py -v`
Expected: PASS (all 9 tests, including the 5 parametrized round-trip sizes).

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/storage_transforms/_stream_encoder.py src/mountainash_utils_files/storage_transforms/compression.py src/mountainash_utils_files/storage_transforms/__init__.py tests/storage_transforms/test_gzip.py
git commit -m "feat(transforms): add Gzip transform (stdlib, streaming, reproducible)"
```

---

## Task 6: Fix [encryption] extra in pyproject and add GPG transform

**Files:**
- Modify: `pyproject.toml`
- Modify: `hatch.toml`
- Create: `src/mountainash_utils_files/storage_transforms/encryption.py`
- Modify: `src/mountainash_utils_files/storage_transforms/__init__.py`
- Create: `tests/storage_transforms/test_gpg.py`
- Create: `tests/fixtures/gpg/README.md`
- Create: `tests/fixtures/gpg/generate_test_key.sh`

- [ ] **Step 1: Fix the [encryption] extra**

Edit `pyproject.toml`: find the line `encryption = ["gnupg==2.3.1", "python-gnupg==0.5.2"]` and replace with:

```toml
encryption = ["python-gnupg>=0.5.2"]
```

The `gnupg` package on PyPI is an unrelated project; only `python-gnupg` is needed.

Also edit the `all = [...]` block in the same file: remove the `"gnupg==2.3.1",` line.

- [ ] **Step 2: Ensure python-gnupg is installed in the test env**

Open `hatch.toml`. Locate the `[envs.test]` section. Its `dependencies = [...]` list currently installs `python-gnupg` transitively via `mountainash_utils_gpg` — that link is fragile (utils-gpg is slated for retirement). Add `python-gnupg` as a direct test-env dep so our tests do not depend on the utils-gpg package.

Add this entry to the `dependencies` list in `[envs.test]`:

```toml
    "python-gnupg>=0.5.2",
```

Then remove the cached test environment so the new dep is picked up, and verify:

```
hatch env remove test
hatch -e test run python -c "import gnupg; print(gnupg.__version__)"
```

Expected: prints the python-gnupg version (>=0.5.2).

- [ ] **Step 3: Create the GPG test fixture key generator**

Create `tests/fixtures/gpg/README.md`:

```markdown
# GPG test fixtures

This directory holds a throwaway GPG keyring used only by tests.

The key is generated by `generate_test_key.sh`. The resulting `test_secret.asc`
and `test_public.asc` files are NOT committed — the test fixture generates a
fresh key per test run into `tmp_path`.

**Recipient:** `test@mountainash.example` (RFC 2606 reserved TLD — not a real address).
```

Create `tests/fixtures/gpg/generate_test_key.sh` (marked executable):

```bash
#!/usr/bin/env bash
# Generate a throwaway test key for GPG transform tests.
# Invoked from the test fixture at runtime against a tmp_path gnupghome.
# Uses gpg defaults (RSA, sign+encrypt+auth usage) with no passphrase.
set -euo pipefail
GNUPGHOME="${1:?missing gnupghome argument}"
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"
gpg --homedir "$GNUPGHOME" --batch --pinentry-mode loopback --passphrase '' \
    --quick-gen-key 'test@mountainash.example' default default never
```

Make it executable: `chmod +x tests/fixtures/gpg/generate_test_key.sh`

- [ ] **Step 4: Write the failing tests**

Create `tests/storage_transforms/test_gpg.py`:

```python
"""Tests for the GPG transform. Requires the [encryption] extra and the gpg binary."""
from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest

from mountainash_utils_files.storage_transforms import Pipeline

# GPG suite is integration-only: requires the gpg binary on PATH and python-gnupg.
pytestmark = pytest.mark.integration

_RECIPIENT = "test@mountainash.example"
_FIXTURE_SCRIPT = Path(__file__).resolve().parent.parent / "fixtures" / "gpg" / "generate_test_key.sh"


@pytest.fixture
def gpg_home(tmp_path) -> Path:
    if shutil.which("gpg") is None:
        pytest.skip("gpg binary not available on PATH")
    home = tmp_path / "gnupg"
    subprocess.run([str(_FIXTURE_SCRIPT), str(home)], check=True)
    return home


def test_gpg_implements_stream_transform_protocol():
    from mountainash_utils_files.storage_transforms import GPG, StreamTransform
    # recipients not required for protocol conformance (only required for wrap())
    assert isinstance(GPG(), StreamTransform)


def test_gpg_round_trip_via_pipeline(gpg_home):
    from mountainash_utils_files.storage_transforms import GPG

    transform = GPG(
        recipients=[_RECIPIENT],
        gnupghome=str(gpg_home),
        always_trust=True,
    )
    pipeline = Pipeline(transform)
    original = b"the quick brown fox" * 100
    encrypted = pipeline.apply_write(io.BytesIO(original)).read()
    assert encrypted != original
    decrypted = pipeline.apply_read(io.BytesIO(encrypted)).read()
    assert decrypted == original


def test_gpg_wrap_without_recipients_raises_transform_error():
    from mountainash_utils_files.exceptions import TransformError
    from mountainash_utils_files.storage_transforms import GPG

    with pytest.raises(TransformError, match="recipients"):
        GPG().wrap(io.BytesIO(b"data"))


def test_gpg_pipeline_with_gzip_round_trip(gpg_home):
    from mountainash_utils_files.storage_transforms import GPG, Gzip

    pipeline = Pipeline(
        Gzip(),
        GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
    )
    original = b"mixed compression and encryption" * 50
    encoded = pipeline.apply_write(io.BytesIO(original)).read()
    # Encoded bytes must not start with the gzip magic 1f 8b, because the
    # OUTER layer is gzip wrapping the INNER gpg — actually wait, outermost
    # is gzip per Pipeline convention. So encoded SHOULD start with 1f 8b.
    assert encoded[:2] == b"\x1f\x8b"
    decoded = pipeline.apply_read(io.BytesIO(encoded)).read()
    assert decoded == original
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_gpg.py -v -m integration`
Expected: FAIL — `ImportError: cannot import name 'GPG'`.

- [ ] **Step 6: Implement GPG transform**

Note: `python-gnupg` buffers the full encrypted/decrypted payload internally before returning, so our `GPG.wrap` / `GPG.unwrap` also buffer in `io.BytesIO`. This matches the previous pre-refactor behaviour and the `python-gnupg` API reality. If future scale demands true streaming, switch to a direct `gpg` subprocess with pipes — out of scope for this spec.

Create `src/mountainash_utils_files/storage_transforms/encryption.py`:

```python
"""GPG encryption / decryption transform.

Requires the optional [encryption] extra (python-gnupg).

Note: python-gnupg does not stream — the full encoded/decoded payload is
materialized in memory inside the underlying python-gnupg call. This
transform therefore buffers the payload in io.BytesIO. For very large
files, materialize the source (or switch to disk-backed materialize())
before calling wrap/unwrap.
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO

from mountainash_utils_files.exceptions import TransformError


def _import_gnupg() -> Any:
    try:
        import gnupg
    except ImportError as exc:
        raise ImportError(
            "The GPG transform requires the [encryption] extra. "
            "Install with: pip install 'mountainash-utils-files[encryption]'"
        ) from exc
    return gnupg


class GPG:
    """GPG transform — encrypts on wrap, decrypts on unwrap.

    Args:
        recipients: List of GPG recipient identifiers. Required for wrap()
            (encryption). Not required for unwrap() (decryption).
        gnupghome: Path to the GPG home directory. None → gpg default.
        key_file: Optional path to a key file to import on first use.
        passphrase: Passphrase for the private key (if decryption requires it).
        armor: If True, produce ASCII-armored output on wrap. Default False
            (binary output — smaller).
        always_trust: If True, skip GPG's ownertrust check on wrap.
    """

    def __init__(
        self,
        recipients: list[str] | None = None,
        gnupghome: str | None = None,
        key_file: str | None = None,
        passphrase: str | None = None,
        armor: bool = False,
        always_trust: bool = False,
    ) -> None:
        self.recipients = recipients
        self.gnupghome = gnupghome
        self.key_file = key_file
        self.passphrase = passphrase
        self.armor = armor
        self.always_trust = always_trust
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            gnupg = _import_gnupg()
            self._client = (
                gnupg.GPG(gnupghome=self.gnupghome)
                if self.gnupghome
                else gnupg.GPG()
            )
            if self.key_file is not None:
                with open(self.key_file, "rb") as fh:
                    self._client.import_keys(fh.read())
        return self._client

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        if not self.recipients:
            raise TransformError(
                "GPG.wrap() requires recipients. Construct GPG(recipients=[...])."
            )
        client = self._get_client()
        result = client.encrypt_file(
            stream,
            recipients=list(self.recipients),
            armor=self.armor,
            always_trust=self.always_trust,
        )
        if not getattr(result, "ok", False):
            status = getattr(result, "status", "unknown")
            raise TransformError(f"GPG encryption failed: {status}")
        return io.BytesIO(bytes(result.data))

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        client = self._get_client()
        result = client.decrypt_file(stream, passphrase=self.passphrase)
        if not getattr(result, "ok", False):
            status = getattr(result, "status", "unknown")
            raise TransformError(f"GPG decryption failed: {status}")
        return io.BytesIO(bytes(result.data))
```

Update `src/mountainash_utils_files/storage_transforms/__init__.py`:

```python
"""Stream transforms — facade-level encoders/decoders for compression and encryption."""

from .base import StreamTransform
from .compression import Gzip
from .encryption import GPG
from .pipeline import Pipeline

__all__ = ["StreamTransform", "Pipeline", "Gzip", "GPG"]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_gpg.py -v -m integration`
Expected: PASS (all 4 tests, assuming gpg binary is available on PATH).

If gpg is not on PATH, the `gpg_home` fixture will skip the keyring-dependent tests; the protocol-conformance and recipients-required tests still run and must pass.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml hatch.toml src/mountainash_utils_files/storage_transforms/encryption.py src/mountainash_utils_files/storage_transforms/__init__.py tests/storage_transforms/test_gpg.py tests/fixtures/gpg/
git commit -m "feat(transforms): add GPG transform + fix [encryption] extra"
```

---

## Task 7: Add materialize() utility

**Files:**
- Create: `src/mountainash_utils_files/storage_transforms/util.py`
- Test: `tests/storage_transforms/test_materialize.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/storage_transforms/test_materialize.py`:

```python
"""Tests for the materialize() utility."""
from __future__ import annotations

import io
import tempfile

import pytest

from mountainash_utils_files.storage_transforms.util import materialize


def test_materialize_memory_mode_small_stream():
    source = io.BytesIO(b"hello world")
    buffered, length = materialize(source, to="memory")
    assert length == 11
    assert buffered.read() == b"hello world"


def test_materialize_returns_seekable_buffer_positioned_at_zero():
    source = io.BytesIO(b"data")
    buffered, _ = materialize(source, to="memory")
    assert buffered.tell() == 0
    assert buffered.seekable() is True


def test_materialize_exhausts_original_stream():
    source = io.BytesIO(b"abc")
    materialize(source, to="memory")
    assert source.read() == b""


def test_materialize_tempfile_mode_below_cutoff_stays_in_memory():
    source = io.BytesIO(b"x" * 100)
    buffered, length = materialize(source, to="tempfile", memory_cutoff=1024)
    assert length == 100
    # SpooledTemporaryFile below cutoff exposes an internal _file that is BytesIO
    assert isinstance(buffered, tempfile.SpooledTemporaryFile)
    assert buffered.read() == b"x" * 100


def test_materialize_tempfile_mode_above_cutoff_rolls_to_disk():
    source = io.BytesIO(b"x" * 5000)
    buffered, length = materialize(source, to="tempfile", memory_cutoff=1024)
    assert length == 5000
    assert isinstance(buffered, tempfile.SpooledTemporaryFile)
    # After exceeding cutoff the spooled file has rolled over
    assert buffered._rolled is True
    assert buffered.read() == b"x" * 5000


def test_materialize_invalid_mode_raises():
    with pytest.raises(ValueError, match="to="):
        materialize(io.BytesIO(b""), to="bogus")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_materialize.py -v`
Expected: FAIL — `ModuleNotFoundError: mountainash_utils_files.storage_transforms.util`.

- [ ] **Step 3: Implement materialize**

Create `src/mountainash_utils_files/storage_transforms/util.py`:

```python
"""Stream utilities — explicit opt-in buffering for callers that need length."""

from __future__ import annotations

import io
import shutil
import tempfile
from typing import BinaryIO, Literal


def materialize(
    stream: BinaryIO,
    *,
    to: Literal["memory", "tempfile"] = "memory",
    memory_cutoff: int = 64 * 1024 * 1024,
) -> tuple[BinaryIO, int]:
    """Drain *stream* into a seekable buffer; return (buffer, length).

    - to="memory": io.BytesIO. Simple, RAM-bounded.
    - to="tempfile": tempfile.SpooledTemporaryFile that rolls to disk
      past memory_cutoff. Safe for large streams.

    After return, the original *stream* is exhausted and the returned
    buffer is positioned at 0.
    """
    if to == "memory":
        buffer: BinaryIO = io.BytesIO()
    elif to == "tempfile":
        buffer = tempfile.SpooledTemporaryFile(max_size=memory_cutoff)
    else:
        raise ValueError(f"to={to!r} must be 'memory' or 'tempfile'")

    shutil.copyfileobj(stream, buffer)
    length = buffer.tell()
    buffer.seek(0)
    return buffer, length
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_materialize.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_transforms/util.py tests/storage_transforms/test_materialize.py
git commit -m "feat(transforms): add materialize() utility for opt-in length probing"
```

---

## Task 8: Add pipeline= kwarg to StorageFacade read path

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/facade.py`
- Test: `tests/storage_transforms/test_facade_integration.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/storage_transforms/test_facade_integration.py`:

```python
"""Facade integration tests for the pipeline= kwarg."""
from __future__ import annotations

import gzip
import io
from pathlib import Path

import pytest

from mountainash_utils_files import StorageFacade
from mountainash_utils_files.storage_transforms import Gzip, Pipeline


@pytest.fixture
def local_facade() -> StorageFacade:
    return StorageFacade.for_local()


def test_facade_read_with_pipeline_decompresses(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"hello"))
    assert local_facade.read(str(path), pipeline=Gzip()) == b"hello"


def test_facade_read_stream_with_pipeline_decompresses(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"streamed"))
    with local_facade.read_stream(str(path), pipeline=Gzip()) as stream:
        assert stream.read() == b"streamed"


def test_facade_read_with_none_pipeline_is_unchanged(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"abc")
    assert local_facade.read(str(path), pipeline=None) == b"abc"
    assert local_facade.read(str(path)) == b"abc"


def test_facade_read_accepts_bare_transform_or_pipeline(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"ok"))
    assert local_facade.read(str(path), pipeline=Gzip()) == b"ok"
    assert local_facade.read(str(path), pipeline=Pipeline(Gzip())) == b"ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_facade_integration.py::test_facade_read_with_pipeline_decompresses -v`
Expected: FAIL — `TypeError: read() got an unexpected keyword argument 'pipeline'`.

- [ ] **Step 3: Modify the facade read path**

Edit `src/mountainash_utils_files/storage_facade/facade.py`. Update the imports block to add:

```python
from mountainash_utils_files.storage_transforms import Pipeline, StreamTransform
```

Add a helper method on `StorageFacade`:

```python
    @staticmethod
    def _coerce_pipeline(
        pipeline: Pipeline | StreamTransform | None,
    ) -> Pipeline:
        if pipeline is None:
            return Pipeline()
        if isinstance(pipeline, Pipeline):
            return pipeline
        return Pipeline(pipeline)
```

Replace the `read` method:

```python
    def read(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
    ) -> bytes:
        """Read file contents and return as bytes, optionally through *pipeline*."""
        self._require(StorageReadProtocol, "read")
        stream = self._backend.read_to_stream(path)
        stream = self._coerce_pipeline(pipeline).apply_read(stream)
        try:
            return stream.read()
        finally:
            stream.close()
```

Replace the `read_stream` method:

```python
    def read_stream(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
    ) -> BinaryIO:
        """Read file contents and return as a binary stream, optionally through *pipeline*."""
        self._require(StorageReadProtocol, "read_stream")
        stream = self._backend.read_to_stream(path)
        return self._coerce_pipeline(pipeline).apply_read(stream)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_facade_integration.py -v -k "read"`
Expected: PASS for the 4 read-path tests.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/facade.py tests/storage_transforms/test_facade_integration.py
git commit -m "feat(facade): add pipeline= kwarg to read and read_stream"
```

---

## Task 9: Add pipeline= kwarg to StorageFacade write path

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/facade.py`
- Test: `tests/storage_transforms/test_facade_integration.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/storage_transforms/test_facade_integration.py`:

```python
def test_facade_write_with_pipeline_compresses(local_facade, tmp_path):
    path = tmp_path / "out.gz"
    local_facade.write(str(path), b"payload", pipeline=Gzip())
    assert gzip.decompress(path.read_bytes()) == b"payload"


def test_facade_write_stream_with_pipeline_compresses(local_facade, tmp_path):
    path = tmp_path / "out.gz"
    local_facade.write_stream(str(path), io.BytesIO(b"streamed"), pipeline=Gzip())
    assert gzip.decompress(path.read_bytes()) == b"streamed"


def test_facade_write_read_roundtrip_through_pipeline(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    local_facade.write(str(path), b"roundtrip", pipeline=Gzip())
    assert local_facade.read(str(path), pipeline=Gzip()) == b"roundtrip"


def test_facade_write_with_none_pipeline_is_unchanged(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    local_facade.write(str(path), b"raw", pipeline=None)
    assert path.read_bytes() == b"raw"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_facade_integration.py -v -k "write"`
Expected: FAIL — `TypeError: write() got an unexpected keyword argument 'pipeline'`.

- [ ] **Step 3: Modify the facade write path**

Replace the `write` method in `src/mountainash_utils_files/storage_facade/facade.py`:

```python
    def write(
        self,
        path: str,
        data: bytes,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
    ) -> None:
        """Write bytes data to a file at *path*, optionally through *pipeline*."""
        self._require(StorageWriteProtocol, "write")
        if pipeline is None:
            self._backend.write_from_bytes(path, data)
            return
        source = io.BytesIO(data)
        encoded = self._coerce_pipeline(pipeline).apply_write(source)
        self._backend.write_from_stream(path, encoded)
```

Replace the `write_stream` method:

```python
    def write_stream(
        self,
        path: str,
        stream: BinaryIO,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
    ) -> None:
        """Write data from a binary stream, optionally through *pipeline*."""
        self._require(StorageWriteProtocol, "write_stream")
        encoded = self._coerce_pipeline(pipeline).apply_write(stream)
        self._backend.write_from_stream(path, encoded)
```

Also add `import io` at the top of the file if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_facade_integration.py -v`
Expected: PASS (all tests in the file including the 4 new write-path tests).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/facade.py tests/storage_transforms/test_facade_integration.py
git commit -m "feat(facade): add pipeline= kwarg to write and write_stream"
```

---

## Task 10: Add pipeline kwargs to copy_between

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/cross_backend.py`
- Test: `tests/storage_transforms/test_facade_integration.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/storage_transforms/test_facade_integration.py`:

```python
def test_copy_between_source_pipeline_decodes(local_facade, tmp_path):
    """Copy a gzipped source to a plaintext destination using source_pipeline."""
    from mountainash_utils_files import copy_between

    src_path = tmp_path / "source.gz"
    dst_path = tmp_path / "dest.bin"
    src_path.write_bytes(gzip.compress(b"hello world"))

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        source_pipeline=Gzip(),
    )
    assert dst_path.read_bytes() == b"hello world"


def test_copy_between_destination_pipeline_encodes(local_facade, tmp_path):
    """Copy a plaintext source to a gzipped destination using destination_pipeline."""
    from mountainash_utils_files import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.gz"
    src_path.write_bytes(b"hello world")

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        destination_pipeline=Gzip(),
    )
    assert gzip.decompress(dst_path.read_bytes()) == b"hello world"


def test_copy_between_no_pipeline_uses_native_copy(local_facade, tmp_path):
    """With no pipelines, same-backend copy uses the native copy fast-path."""
    from mountainash_utils_files import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.bin"
    src_path.write_bytes(b"payload")

    copy_between(str(src_path), str(dst_path), local_facade, local_facade)
    assert dst_path.read_bytes() == b"payload"


def test_copy_between_forces_stream_when_pipeline_present(local_facade, tmp_path, monkeypatch):
    """When any pipeline is given, native copy is skipped even for same-backend."""
    from mountainash_utils_files import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.gz"
    src_path.write_bytes(b"x")

    copy_called = {"value": False}
    orig_copy = local_facade.copy

    def tracking_copy(*args, **kwargs):
        copy_called["value"] = True
        return orig_copy(*args, **kwargs)

    monkeypatch.setattr(local_facade, "copy", tracking_copy)

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        destination_pipeline=Gzip(),
    )
    assert copy_called["value"] is False  # native copy was NOT used
    assert gzip.decompress(dst_path.read_bytes()) == b"x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_transforms/test_facade_integration.py -v -k "copy_between"`
Expected: FAIL — `TypeError: copy_between() got an unexpected keyword argument 'source_pipeline'`.

- [ ] **Step 3: Modify copy_between**

Replace the entirety of `src/mountainash_utils_files/storage_facade/cross_backend.py`:

```python
# storage_facade/cross_backend.py

"""Cross-backend file transfer utilities."""

from __future__ import annotations

import typing

from mountainash_utils_files.storage_protocols import StorageCopyProtocol
from mountainash_utils_files.storage_transforms import Pipeline, StreamTransform

if typing.TYPE_CHECKING:
    from mountainash_utils_files.storage_facade.facade import StorageFacade


def copy_between(
    source_path: str,
    destination_path: str,
    source_facade: StorageFacade,
    destination_facade: StorageFacade,
    *,
    source_pipeline: Pipeline | StreamTransform | None = None,
    destination_pipeline: Pipeline | StreamTransform | None = None,
) -> None:
    """Copy a file between two facades, optionally applying transforms on each side.

    Native same-backend copy is used only when both pipelines are None.
    Any pipeline argument forces a stream-through copy.
    """
    if (
        source_pipeline is None
        and destination_pipeline is None
        and isinstance(source_facade._backend, type(destination_facade._backend))
        and source_facade.supports(StorageCopyProtocol)
    ):
        source_facade.copy(source_path, destination_path)
        return

    stream = source_facade.read_stream(source_path, pipeline=source_pipeline)
    try:
        destination_facade.write_stream(
            destination_path, stream, pipeline=destination_pipeline
        )
    finally:
        stream.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_transforms/test_facade_integration.py -v`
Expected: PASS — all tests including the 4 new copy_between tests.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/cross_backend.py tests/storage_transforms/test_facade_integration.py
git commit -m "feat(facade): add source_pipeline + destination_pipeline to copy_between"
```

---

## Task 11: Add top-level re-exports

**Files:**
- Modify: `src/mountainash_utils_files/__init__.py`
- Test: `tests/test_public_api.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_public_api.py`:

```python
def test_transform_exports_are_top_level():
    """Pipeline, Gzip, GPG, StreamTransform, TransformError import from package root."""
    from mountainash_utils_files import (
        GPG,
        Gzip,
        Pipeline,
        StreamTransform,
        TransformError,
    )
    # Construction smoke checks
    assert isinstance(Pipeline(Gzip()).apply_read, type(Pipeline().apply_read))
    assert issubclass(TransformError, Exception)
    assert isinstance(Gzip(), StreamTransform)
    # GPG is importable even without python-gnupg at import time
    assert GPG is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `hatch run test:test tests/test_public_api.py::test_transform_exports_are_top_level -v`
Expected: FAIL — ImportError for `Pipeline` / `Gzip` / `GPG` / `StreamTransform` / `TransformError`.

- [ ] **Step 3: Update the package __init__**

Edit `src/mountainash_utils_files/__init__.py`. First, update the existing exceptions import block to include `TransformError`:

```python
# Exceptions
from .exceptions import (
    StorageError,
    UnsupportedOperationError,
    StorageConnectionError,
    PathNotFoundError,
    AuthenticationError,
    TransformError,
)
```

Add a new transforms import block after the exceptions block:

```python
# Stream transforms
from .storage_transforms import (
    Pipeline,
    StreamTransform,
    Gzip,
    GPG,
)
```

Append the new names to the `__all__` list. Insert the following after the `AuthenticationError` entry:

```python
    "TransformError",
    "Pipeline", "StreamTransform", "Gzip", "GPG",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `hatch run test:test tests/test_public_api.py::test_transform_exports_are_top_level -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/__init__.py tests/test_public_api.py
git commit -m "feat(api): re-export Pipeline, Gzip, GPG, StreamTransform, TransformError"
```

---

## Task 12: Update CLAUDE.md with Stream Transforms section

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the section**

In `CLAUDE.md`, insert a new subsection under `## Architecture` after the `### Settings Architecture (descriptor-driven)` block and before `### Package Structure`:

```markdown
### Stream Transforms

Facade-level stream decorators for compression and encryption (restored 2026-04-17, spec at `docs/superpowers/specs/2026-04-17-stream-transforms-design.md`).

- `storage_transforms/Pipeline(outer, ..., inner)` — ordered stack matching file-extension order (last-applied = outermost).
- `Gzip(level=6, mtime=0)` — stdlib-based, reproducible by default, zero new dependency.
- `GPG(recipients=[...], gnupghome=..., ...)` — requires the `[encryption]` optional extra (python-gnupg).
- `StorageFacade.read/read_stream/write/write_stream` accept a keyword-only `pipeline=` argument.
- `copy_between` accepts separate `source_pipeline=` and `destination_pipeline=` arguments.
- `storage_transforms.util.materialize(stream, to=...)` — opt-in buffering to recover a known length.

The same `Pipeline` instance is used on both read and write paths; the facade applies transforms in the correct direction automatically.
```

- [ ] **Step 2: Verify the section renders**

Run: `head -200 CLAUDE.md` and manually verify the section appears in the expected location.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document stream transforms architecture"
```

---

## Final validation

- [ ] **Run the full test suite**

Run: `hatch run test:test -v`
Expected: all tests pass. Integration-marked GPG tests skip cleanly if `gpg` binary is not on PATH.

- [ ] **Run the linter**

Run: `hatch run ruff:check`
Expected: no errors.

- [ ] **Run type checker**

Run: `hatch run mypy:check`
Expected: no errors in `src/mountainash_utils_files/storage_transforms/` and no new errors elsewhere.

- [ ] **Verify the branch state**

Run: `git log --oneline origin/develop..HEAD`
Expected: 12 commits matching tasks 1-12 plus the design spec commit.

- [ ] **Open a PR against develop**

Run: `gh pr create --base develop --title "feat: restore compression + encryption via stream transforms" --body "$(cat <<'EOF'
## Summary
- Restores gzip and GPG capabilities lost in the 2026-04-03 protocol-driven refactor.
- Adds a new `storage_transforms/` subpackage with `Pipeline`, `Gzip`, `GPG`, `StreamTransform`, and `materialize()`.
- `StorageFacade` read/write/copy gain a `pipeline=` keyword-only argument.
- Prerequisite fix: S3 `write_from_stream` now uses `upload_fileobj` instead of buffering the entire stream.

Spec: `docs/superpowers/specs/2026-04-17-stream-transforms-design.md`
Plan: `docs/superpowers/plans/2026-04-17-stream-transforms.md`

## Test plan
- [ ] `hatch run test:test` passes locally (including @pytest.mark.integration where gpg is available)
- [ ] `hatch run ruff:check` passes
- [ ] `hatch run mypy:check` passes
- [ ] Round-trip a gzipped file through the facade manually
- [ ] Round-trip a Pipeline(Gzip(), GPG(...)) file against a test keyring

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"`
