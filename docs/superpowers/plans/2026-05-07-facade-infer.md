# Facade-Level Suffix Inference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `infer`/`gpg`/`gzip` kwargs to `StorageFacade.read()` and `read_stream()`, and simplify `read_bytes()` to delegate inference to the facade.

**Architecture:** A new private method `_resolve_pipeline()` on `StorageFacade` handles the `infer=True` → `infer_pipeline()` dispatch and the `infer + pipeline` conflict check. `read()` and `read_stream()` call it instead of `_coerce_pipeline()` directly. `read_bytes()` delegates to `facade.read()`.

**Tech Stack:** Existing `infer_pipeline` from `path_helpers/suffixes.py`, `Pipeline`/`GPG`/`Gzip` from `storage_transforms`.

**Spec:** `docs/superpowers/specs/2026-05-07-facade-infer-design.md`

---

## File Structure

### Modified files

| File | Change |
|------|--------|
| `src/mountainash_utils_files/storage_facade/facade.py` | Add `_resolve_pipeline()`, add `infer`/`gpg`/`gzip` kwargs to `read()` and `read_stream()` |
| `src/mountainash_utils_files/storage_facade/read_bytes.py` | Simplify body to delegate `infer` to facade |

### New files

| File | Purpose |
|------|---------|
| `tests/facade/test_facade_infer.py` | Facade-level inference tests (gzip, conflict, stream, gpg round-trip) |

---

## Task 1: Add `_resolve_pipeline()` and update `read()` with inference

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/facade.py:27,122-153`
- Create: `tests/facade/test_facade_infer.py`

- [ ] **Step 1: Write failing tests for facade.read() with infer**

Create `tests/facade/test_facade_infer.py`:

```python
"""Tests for StorageFacade.read() and read_stream() with infer=True."""
from __future__ import annotations

import gzip as gzlib
from pathlib import Path

import pytest

import mountainash_utils_files.storage_backends  # noqa: F401
from mountainash_utils_files.storage_facade import StorageFacade
from mountainash_utils_files.storage_transforms import Gzip


class TestReadInfer:
    def test_read_infer_false_returns_raw_bytes(self, tmp_path: Path):
        payload = b"hello world"
        compressed = gzlib.compress(payload)
        target = tmp_path / "data.gz"
        target.write_bytes(compressed)

        facade = StorageFacade.for_local()
        result = facade.read(str(target))
        assert result == compressed

    def test_read_infer_true_decompresses_gz(self, tmp_path: Path):
        payload = b"hello world"
        target = tmp_path / "data.gz"
        target.write_bytes(gzlib.compress(payload))

        facade = StorageFacade.for_local()
        result = facade.read(str(target), infer=True)
        assert result == payload

    def test_read_infer_true_no_known_suffix_returns_raw(self, tmp_path: Path):
        payload = b"raw parquet bytes"
        target = tmp_path / "data.parquet"
        target.write_bytes(payload)

        facade = StorageFacade.for_local()
        result = facade.read(str(target), infer=True)
        assert result == payload

    def test_read_infer_true_with_pipeline_raises(self, tmp_path: Path):
        target = tmp_path / "data.gz"
        target.write_bytes(b"irrelevant")

        facade = StorageFacade.for_local()
        with pytest.raises(ValueError, match="Cannot pass both"):
            facade.read(str(target), infer=True, pipeline=Gzip())

    def test_read_infer_gpg_suffix_without_gpg_raises(self, tmp_path: Path):
        target = tmp_path / "data.gpg"
        target.write_bytes(b"irrelevant")

        facade = StorageFacade.for_local()
        with pytest.raises(ValueError, match=r"\.gpg suffix"):
            facade.read(str(target), infer=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/facade/test_facade_infer.py -v`
Expected: `TypeError` — `read()` does not accept `infer` kwarg.

- [ ] **Step 3: Add `_resolve_pipeline()` and update `read()`**

In `src/mountainash_utils_files/storage_facade/facade.py`:

First, add the import after the existing `storage_transforms` import (line 27):

```python
from mountainash_utils_files.path_helpers.suffixes import infer_pipeline as _infer_pipeline
from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline, StreamTransform
```

(Replace the existing `from mountainash_utils_files.storage_transforms import Pipeline, StreamTransform` line.)

Then, add `_resolve_pipeline` after `_coerce_pipeline` (after line 130):

```python
    def _resolve_pipeline(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None,
        infer: bool,
        gpg: GPG | None,
        gzip: Gzip | None,
    ) -> Pipeline:
        """Resolve the effective pipeline from explicit or inferred sources."""
        if infer and pipeline is not None:
            raise ValueError(
                "Cannot pass both infer=True and an explicit pipeline"
            )
        if infer:
            inferred, _ = _infer_pipeline(path, gpg=gpg, gzip=gzip)
            if inferred is not None:
                return inferred
        return self._coerce_pipeline(pipeline)
```

Then, update `read()` — replace the current method (lines 136–153) with:

```python
    def read(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        infer: bool = False,
        gpg: GPG | None = None,
        gzip: Gzip | None = None,
    ) -> bytes:
        """Read file contents and return as bytes, optionally through *pipeline*.

        When *infer* is True, the path's suffix chain is parsed into a
        pipeline via :func:`infer_pipeline`. Raises ``ValueError`` if both
        *infer* and *pipeline* are provided.
        """
        self._require(StorageReadProtocol, "read")
        effective = self._resolve_pipeline(
            path, pipeline=pipeline, infer=infer, gpg=gpg, gzip=gzip,
        )
        source_stream = self._backend.read_to_stream(path)
        try:
            wrapped_stream = effective.apply_read(source_stream)
            try:
                return wrapped_stream.read()
            finally:
                if wrapped_stream is not source_stream:
                    wrapped_stream.close()
        finally:
            source_stream.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/facade/test_facade_infer.py -v`
Expected: All 5 pass.

- [ ] **Step 5: Run existing facade tests for regressions**

Run: `pytest tests/facade/ tests/storage_facade/ -v --tb=short`
Expected: All pass — no existing behavior changed.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/facade.py \
        tests/facade/test_facade_infer.py
git commit -m "feat(facade): add infer/gpg/gzip kwargs to read() with _resolve_pipeline"
```

---

## Task 2: Update `read_stream()` with inference

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/facade.py:155-170`
- Modify: `tests/facade/test_facade_infer.py`

- [ ] **Step 1: Write failing tests for read_stream() with infer**

Add to `tests/facade/test_facade_infer.py`:

```python
class TestReadStreamInfer:
    def test_read_stream_infer_true_decompresses_gz(self, tmp_path: Path):
        payload = b"streamed decompression test"
        target = tmp_path / "data.gz"
        target.write_bytes(gzlib.compress(payload))

        facade = StorageFacade.for_local()
        stream = facade.read_stream(str(target), infer=True)
        assert stream.read() == payload
        stream.close()

    def test_read_stream_infer_true_with_pipeline_raises(self, tmp_path: Path):
        target = tmp_path / "data.gz"
        target.write_bytes(b"irrelevant")

        facade = StorageFacade.for_local()
        with pytest.raises(ValueError, match="Cannot pass both"):
            facade.read_stream(str(target), infer=True, pipeline=Gzip())

    def test_read_stream_infer_true_no_known_suffix_returns_raw(
        self, tmp_path: Path,
    ):
        payload = b"raw stream bytes"
        target = tmp_path / "data.parquet"
        target.write_bytes(payload)

        facade = StorageFacade.for_local()
        stream = facade.read_stream(str(target), infer=True)
        assert stream.read() == payload
        stream.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/facade/test_facade_infer.py::TestReadStreamInfer -v`
Expected: `TypeError` — `read_stream()` does not accept `infer` kwarg.

- [ ] **Step 3: Update `read_stream()` with inference kwargs**

In `src/mountainash_utils_files/storage_facade/facade.py`, replace the current
`read_stream()` method with:

```python
    def read_stream(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        infer: bool = False,
        gpg: GPG | None = None,
        gzip: Gzip | None = None,
    ) -> BinaryIO:
        """Read file contents and return as a binary stream, optionally through *pipeline*.

        When *infer* is True, the path's suffix chain is parsed into a
        pipeline via :func:`infer_pipeline`. Raises ``ValueError`` if both
        *infer* and *pipeline* are provided.

        The returned stream should be closed by the caller (context manager
        recommended). Closing propagates to both the pipeline wrapper and the
        underlying backend stream so file descriptors are not leaked.
        """
        self._require(StorageReadProtocol, "read_stream")
        effective = self._resolve_pipeline(
            path, pipeline=pipeline, infer=infer, gpg=gpg, gzip=gzip,
        )
        source_stream = self._backend.read_to_stream(path)
        wrapped_stream = effective.apply_read(source_stream)
        return _PairedStream(wrapped_stream, source_stream)  # type: ignore[return-value]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/facade/test_facade_infer.py -v`
Expected: All 8 pass (5 from Task 1 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/facade.py \
        tests/facade/test_facade_infer.py
git commit -m "feat(facade): add infer/gpg/gzip kwargs to read_stream()"
```

---

## Task 3: GPG round-trip tests at facade level

**Files:**
- Modify: `tests/facade/test_facade_infer.py`

- [ ] **Step 1: Add GPG round-trip tests**

Add to `tests/facade/test_facade_infer.py` (after the existing imports, add):

```python
import io
import shutil
import subprocess

from mountainash_utils_files.storage_transforms import GPG, Pipeline
```

Then add the test class:

```python
_RECIPIENT = "test@mountainash.example"
_FIXTURE_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "fixtures" / "gpg" / "generate_test_key.sh"
)


@pytest.mark.integration
class TestReadInferGPG:
    @pytest.fixture
    def gpg_home(self, tmp_path: Path) -> Path:
        if shutil.which("gpg") is None:
            pytest.skip("gpg binary not available on PATH")
        home = tmp_path / "gnupg"
        subprocess.run([str(_FIXTURE_SCRIPT), str(home)], check=True)
        return home

    def test_read_infer_true_decompresses_gz_gpg(
        self, tmp_path: Path, gpg_home: Path,
    ):
        payload = b"encrypted and compressed payload" * 50
        encoded = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
            Gzip(),
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.parquet.gz.gpg"
        target.write_bytes(encoded)

        facade = StorageFacade.for_local()
        gpg = GPG(gnupghome=str(gpg_home))
        result = facade.read(str(target), infer=True, gpg=gpg)
        assert result == payload

    def test_read_stream_infer_true_decompresses_gz_gpg(
        self, tmp_path: Path, gpg_home: Path,
    ):
        payload = b"streamed encrypted compressed" * 50
        encoded = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
            Gzip(),
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.parquet.gz.gpg"
        target.write_bytes(encoded)

        facade = StorageFacade.for_local()
        gpg = GPG(gnupghome=str(gpg_home))
        stream = facade.read_stream(str(target), infer=True, gpg=gpg)
        assert stream.read() == payload
        stream.close()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/facade/test_facade_infer.py -v`
Expected: 8 unit tests pass, 2 integration tests pass (or skip if no gpg).

- [ ] **Step 3: Commit**

```bash
git add tests/facade/test_facade_infer.py
git commit -m "test(facade): add GPG round-trip tests for facade-level inference"
```

---

## Task 4: Simplify `read_bytes()` to delegate to facade

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/read_bytes.py`

- [ ] **Step 1: Run existing read_bytes tests to establish baseline**

Run: `pytest tests/storage_facade/test_read_bytes.py tests/storage_facade/test_read_bytes_infer.py -v`
Expected: All pass.

- [ ] **Step 2: Simplify `read_bytes()`**

Replace the entire content of `src/mountainash_utils_files/storage_facade/read_bytes.py`:

```python
"""Top-level read helper that dispatches by URL scheme.

All schemes — including http/https — route through StorageFacade.from_path().
Suffix-driven transform inference delegates to the facade's read() method.
"""
from __future__ import annotations

import typing

from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_transforms import GPG, Gzip


def read_bytes(
    path: str,
    *,
    auth_params: typing.Any = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    All recognised schemes route through :meth:`StorageFacade.from_path`.
    When *infer* is True, the facade applies suffix-driven transform
    inference via :func:`infer_pipeline`.

    Args:
        path: Path or URL.
        auth_params: Optional auth params forwarded to the storage facade.
        infer: When True, inspect *path*'s suffix chain and auto-apply a
            read-side ``Pipeline`` for known suffixes (``.gz``, ``.gzip``,
            ``.gpg``, ``.asc``, ``.pgp``). Default False preserves
            byte-for-byte current behaviour.
        gpg: Required when *infer* is True and the suffix chain contains a
            gpg-family suffix. Supplies key material. Ignored when *infer*
            is False.
        gzip: Optional; defaults to ``Gzip()`` when a gzip suffix is seen.
            Ignored when *infer* is False.

    Returns:
        The full content of *path* as ``bytes``, optionally transform-decoded.

    Raises:
        ValueError: If the scheme is unrecognised, describes a backend that
            is not registered, or *infer* is True and a gpg-family suffix
            was seen without a *gpg* instance.
    """
    facade = StorageFacade.from_path(path, auth_params)
    return facade.read(path, infer=infer, gpg=gpg, gzip=gzip)
```

- [ ] **Step 3: Run read_bytes tests to verify no regressions**

Run: `pytest tests/storage_facade/test_read_bytes.py tests/storage_facade/test_read_bytes_infer.py -v`
Expected: All pass — behavior is identical, just delegated differently.

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/read_bytes.py
git commit -m "refactor(read_bytes): delegate infer to facade.read()"
```

---

## Task 5: Final verification

**Files:** None new — verification only.

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All pass.

- [ ] **Step 2: Run linting**

Run: `hatch run ruff:check`
Expected: Clean.

- [ ] **Step 3: Verify `infer_pipeline` import removed from read_bytes.py**

Run: `grep -n "infer_pipeline" src/mountainash_utils_files/storage_facade/read_bytes.py`
Expected: No matches — the import moved to facade.py.

- [ ] **Step 4: Verify facade.py has the new import**

Run: `grep -n "infer_pipeline" src/mountainash_utils_files/storage_facade/facade.py`
Expected: One match — the import line.

- [ ] **Step 5: Commit any cleanup**

If lint/type fixes were needed:

```bash
git add -u
git commit -m "chore: lint fixes for facade-level inference"
```
