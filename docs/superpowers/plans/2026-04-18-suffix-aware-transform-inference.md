# Suffix-Aware Transform Inference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Infer a `Pipeline` of stream transforms from a path's suffix chain, so callers can read encrypted-compressed files with a single `read_bytes(path, infer=True, gpg=..., gzip=...)` call.

**Architecture:** A pure suffix-parser (`path_helpers/suffixes.py`) walks a path's suffixes right-to-left, mapping each known suffix to a `StreamTransform` instance and assembling them into a `Pipeline` in outermost-first order. `read_bytes` gains three keyword-only kwargs — `infer`, `gpg`, `gzip` — that route through this parser and the facade's existing `pipeline=` parameter. Default `infer=False` preserves current behaviour byte-for-byte.

**Tech Stack:** Python 3.12, `pathlib.PurePosixPath` (stdlib) for suffix extraction, existing `Pipeline` / `Gzip` / `GPG` from `storage_transforms/`, pytest with `@pytest.mark.integration` for GPG tests.

**Spec:** `docs/superpowers/specs/2026-04-18-suffix-aware-transform-inference-design.md`

---

## File Structure

| File | Role |
|---|---|
| **`src/mountainash_utils_files/path_helpers/suffixes.py`** (new) | `SUFFIX_TRANSFORMS` dict + `infer_pipeline()` pure function. No I/O. |
| **`src/mountainash_utils_files/path_helpers/__init__.py`** (modify) | Re-export `infer_pipeline`, `SUFFIX_TRANSFORMS`. |
| **`src/mountainash_utils_files/__init__.py`** (modify) | Add `infer_pipeline` to top-level imports + `__all__`. |
| **`src/mountainash_utils_files/storage_facade/read_bytes.py`** (modify) | Add `infer` / `gpg` / `gzip` keyword-only kwargs; tighten `auth_params` to keyword-only; extract private `_apply_pipeline_to_bytes` helper for the http bridge. |
| **`tests/path_helpers/test_suffixes.py`** (new) | 12 parametrised cases covering `infer_pipeline`. |
| **`tests/storage_facade/test_read_bytes.py`** (modify) | Add unit tests for the new kwargs (monkeypatched facade); leave existing tests untouched. |
| **`tests/storage_facade/test_read_bytes_infer.py`** (new) | Integration tests using real files + `gpg_home` fixture from `tests/storage_transforms/`. |
| **`CLAUDE.md`** (modify) | Add usage example under the Stream Transforms section. |

---

## Task 1: `infer_pipeline` pure function

**Files:**
- Create: `src/mountainash_utils_files/path_helpers/suffixes.py`
- Test: `tests/path_helpers/test_suffixes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/path_helpers/test_suffixes.py`:

```python
"""Tests for infer_pipeline — suffix-driven Pipeline construction."""
from __future__ import annotations

import pytest

from mountainash_utils_files.path_helpers.suffixes import infer_pipeline, SUFFIX_TRANSFORMS
from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline


def _kinds(pipeline: Pipeline) -> list[str]:
    """Return the transform class names in outer-to-inner order."""
    return [type(t).__name__ for t in pipeline._outer_to_inner]


def test_suffix_map_covers_spec_baseline():
    assert SUFFIX_TRANSFORMS == {
        ".gz": "gzip",
        ".gzip": "gzip",
        ".gpg": "gpg",
        ".asc": "gpg",
        ".pgp": "gpg",
    }


def test_no_known_suffix_returns_none_and_original_path():
    assert infer_pipeline("data.parquet") == (None, "data.parquet")


def test_bare_stem_returns_none():
    assert infer_pipeline("data") == (None, "data")


@pytest.mark.parametrize("path", ["data.gz", "data.gzip", "data.GZ", "data.Gzip"])
def test_gzip_suffix_default_instance(path: str):
    pipeline, stripped = infer_pipeline(path)
    assert isinstance(pipeline, Pipeline)
    assert _kinds(pipeline) == ["Gzip"]
    assert stripped == "data"


def test_gzip_custom_instance_threaded_through():
    custom = Gzip(level=9)
    pipeline, _ = infer_pipeline("data.gz", gzip=custom)
    assert pipeline is not None
    assert pipeline._outer_to_inner == (custom,)


@pytest.mark.parametrize("suffix", [".gpg", ".asc", ".pgp"])
def test_gpg_suffix_requires_instance(suffix: str):
    gpg = GPG()
    pipeline, stripped = infer_pipeline(f"data{suffix}", gpg=gpg)
    assert pipeline is not None
    assert pipeline._outer_to_inner == (gpg,)
    assert stripped == "data"


@pytest.mark.parametrize("suffix", [".gpg", ".asc", ".pgp"])
def test_gpg_suffix_without_instance_raises(suffix: str):
    with pytest.raises(ValueError, match=f"{suffix} suffix"):
        infer_pipeline(f"data{suffix}")


def test_combined_gz_gpg_outer_is_gpg():
    gpg = GPG()
    pipeline, stripped = infer_pipeline("data.parquet.gz.gpg", gpg=gpg)
    assert pipeline is not None
    # Right-most suffix (.gpg) is the outermost layer.
    assert _kinds(pipeline) == ["GPG", "Gzip"]
    assert stripped == "data.parquet"


def test_repeated_gzip_suffix():
    pipeline, stripped = infer_pipeline("data.gz.gz")
    assert pipeline is not None
    assert _kinds(pipeline) == ["Gzip", "Gzip"]
    assert stripped == "data"


def test_unknown_suffix_mid_chain_halts_parsing():
    pipeline, stripped = infer_pipeline("data.txt.gz")
    assert pipeline is not None
    assert _kinds(pipeline) == ["Gzip"]
    assert stripped == "data.txt"


def test_url_path_is_handled():
    pipeline, stripped = infer_pipeline("s3://bucket/path/to/data.parquet.gz")
    assert pipeline is not None
    assert _kinds(pipeline) == ["Gzip"]
    assert stripped == "s3://bucket/path/to/data.parquet"


def test_no_splitting_on_dot_in_directory_segment():
    # Dots in directory components must not be consumed.
    pipeline, stripped = infer_pipeline("/some.dir/data")
    assert pipeline is None
    assert stripped == "/some.dir/data"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/path_helpers/test_suffixes.py -v`
Expected: `ModuleNotFoundError: No module named 'mountainash_utils_files.path_helpers.suffixes'` (or `ImportError` naming `infer_pipeline`).

- [ ] **Step 3: Write the implementation**

Create `src/mountainash_utils_files/path_helpers/suffixes.py`:

```python
"""Suffix-aware transform inference.

Parses a path's suffix chain right-to-left into a Pipeline of stream
transforms. See docs/superpowers/specs/2026-04-18-suffix-aware-transform-inference-design.md.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Optional, Tuple

from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline
from mountainash_utils_files.storage_transforms.base import StreamTransform

SUFFIX_TRANSFORMS: dict[str, str] = {
    ".gz":   "gzip",
    ".gzip": "gzip",
    ".gpg":  "gpg",
    ".asc":  "gpg",
    ".pgp":  "gpg",
}


def _split_final_suffix(path: str) -> Tuple[str, str]:
    """Return (stem, suffix) using posix-path rules.

    ``suffix`` is the lowercased final suffix including the dot, or the
    empty string if the final segment has no dot. ``stem`` is ``path``
    with that suffix removed.
    """
    pp = PurePosixPath(path)
    suffix = pp.suffix.lower()
    if not suffix:
        return path, ""
    # Strip only the trailing suffix length — preserves scheme, netloc,
    # and any dots in directory components because pp.suffix is defined
    # against the final name only.
    return path[: -len(suffix)], suffix


def infer_pipeline(
    path: str,
    *,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> Tuple[Optional[Pipeline], str]:
    """Parse the suffix chain of *path* right-to-left into a Pipeline.

    Stops at the first suffix not in :data:`SUFFIX_TRANSFORMS`. Comparison
    on the suffix is case-insensitive.

    Args:
        path: Any path-like string (local, ``s3://...``, etc). Only the
            suffix portion of the final segment is inspected; no scheme
            validation is performed.
        gpg: Required if the suffix chain contains any of ``.gpg``,
            ``.asc``, ``.pgp``. Supplies key material.
        gzip: Optional; defaults to ``Gzip()`` when a gzip suffix is seen.

    Returns:
        ``(pipeline, stripped_path)``.
          - ``pipeline`` is ``None`` when no known suffixes were found.
          - ``stripped_path`` is *path* with every stripped suffix removed.

    Raises:
        ValueError: A gpg-family suffix was found but ``gpg`` is ``None``.
    """
    outer_to_inner: list[StreamTransform] = []
    current = path
    while True:
        stem, suffix = _split_final_suffix(current)
        if not suffix:
            break
        kind = SUFFIX_TRANSFORMS.get(suffix)
        if kind is None:
            break
        if kind == "gzip":
            outer_to_inner.append(gzip if gzip is not None else Gzip())
        elif kind == "gpg":
            if gpg is None:
                raise ValueError(
                    f"path {path!r} has a {suffix} suffix; "
                    f"pass gpg=GPG(...) to infer"
                )
            outer_to_inner.append(gpg)
        current = stem

    if not outer_to_inner:
        return None, path
    # Walking right-to-left produces outermost-first order, matching
    # Pipeline.__init__'s contract.
    return Pipeline(*outer_to_inner), current
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/path_helpers/test_suffixes.py -v`
Expected: 15 passed (the parametrised `.gpg`/`.asc`/`.pgp` case yields 3 per marker + 4 gzip variants).

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/suffixes.py tests/path_helpers/test_suffixes.py
git commit -m "feat(path_helpers): add infer_pipeline for suffix-driven transforms"
```

---

## Task 2: Export `infer_pipeline` from the package

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/__init__.py`
- Modify: `src/mountainash_utils_files/__init__.py`
- Test: `tests/path_helpers/test_suffixes.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/path_helpers/test_suffixes.py`:

```python
def test_infer_pipeline_exported_from_path_helpers():
    from mountainash_utils_files.path_helpers import infer_pipeline as from_subpkg
    from mountainash_utils_files.path_helpers.suffixes import infer_pipeline as from_mod
    assert from_subpkg is from_mod


def test_infer_pipeline_exported_at_top_level():
    from mountainash_utils_files import infer_pipeline as from_top
    from mountainash_utils_files.path_helpers.suffixes import infer_pipeline as from_mod
    assert from_top is from_mod


def test_suffix_transforms_exported_from_path_helpers():
    from mountainash_utils_files.path_helpers import SUFFIX_TRANSFORMS as from_subpkg
    from mountainash_utils_files.path_helpers.suffixes import SUFFIX_TRANSFORMS as from_mod
    assert from_subpkg is from_mod
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/path_helpers/test_suffixes.py -v -k exported`
Expected: `ImportError: cannot import name 'infer_pipeline' from 'mountainash_utils_files.path_helpers'`.

- [ ] **Step 3: Add re-export from the `path_helpers` subpackage**

Current `src/mountainash_utils_files/path_helpers/__init__.py` ends with:

```python
from . import s3
from .scheme import SCHEMES, SchemeSpec
from .storage_path import StoragePath

__all__ = ("StoragePath", "SchemeSpec", "SCHEMES", "s3")
```

Replace that final block with:

```python
from . import s3
from .scheme import SCHEMES, SchemeSpec
from .storage_path import StoragePath
from .suffixes import SUFFIX_TRANSFORMS, infer_pipeline

__all__ = ("StoragePath", "SchemeSpec", "SCHEMES", "s3", "SUFFIX_TRANSFORMS", "infer_pipeline")
```

- [ ] **Step 4: Add the top-level export**

Modify `src/mountainash_utils_files/__init__.py`. In the "Path utilities" section, change:

```python
# Path utilities
from .path_helpers import StoragePath
```

to:

```python
# Path utilities
from .path_helpers import StoragePath, infer_pipeline
```

And in the `__all__` list, in the line containing `"StoragePath",`, replace:

```python
    "StoragePath",
```

with:

```python
    "StoragePath", "infer_pipeline",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `hatch run test:test tests/path_helpers/test_suffixes.py -v`
Expected: all tests pass (previous 15 + 3 new export tests).

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/__init__.py src/mountainash_utils_files/__init__.py tests/path_helpers/test_suffixes.py
git commit -m "feat(api): export infer_pipeline + SUFFIX_TRANSFORMS"
```

---

## Task 3: Wire `infer` kwargs into `read_bytes`

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/read_bytes.py`
- Modify: `tests/storage_facade/test_read_bytes.py`

- [ ] **Step 1: Write failing unit tests**

Append to `tests/storage_facade/test_read_bytes.py`:

```python
def test_read_bytes_infer_false_preserves_existing_behaviour(tmp_path: Path):
    target = tmp_path / "data.gz"
    target.write_bytes(b"\x1f\x8braw-gz-bytes")  # not valid gzip, but that's the point
    # infer=False must NOT touch the bytes.
    assert read_bytes(str(target)) == b"\x1f\x8braw-gz-bytes"
    assert read_bytes(str(target), infer=False) == b"\x1f\x8braw-gz-bytes"


def test_read_bytes_infer_true_no_known_suffix_falls_through(tmp_path: Path):
    target = tmp_path / "plain.txt"
    target.write_bytes(b"plain bytes")
    assert read_bytes(str(target), infer=True) == b"plain bytes"


def test_read_bytes_infer_gpg_suffix_without_gpg_raises(tmp_path: Path):
    target = tmp_path / "data.gpg"
    target.write_bytes(b"irrelevant")
    with pytest.raises(ValueError, match=".gpg suffix"):
        read_bytes(str(target), infer=True)


def test_read_bytes_http_infer_applies_pipeline_to_bytes(monkeypatch):
    """http body with a .gz suffix + infer=True must be gunzipped in-process."""
    import gzip as gzlib
    payload = gzlib.compress(b"plain text from web")

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return payload

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda url: _FakeResponse())

    assert read_bytes("https://example.com/file.gz", infer=True) == b"plain text from web"


def test_read_bytes_auth_params_still_accepted_as_keyword(tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_bytes(b"hello")
    # auth_params is now keyword-only — passing by keyword must still work.
    assert read_bytes(str(target), auth_params=None) == b"hello"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `hatch run test:test tests/storage_facade/test_read_bytes.py -v`
Expected: The 5 new tests fail with `TypeError: read_bytes() got an unexpected keyword argument 'infer'` (first four) and `test_read_bytes_infer_false_preserves_existing_behaviour` passes by luck only on the `read_bytes(str(target))` line — it fails on `infer=False`. The existing 6 tests continue to pass.

- [ ] **Step 3: Rewrite `read_bytes`**

Replace the contents of `src/mountainash_utils_files/storage_facade/read_bytes.py` with:

```python
"""Top-level read helper that dispatches by URL scheme.

For http/https, uses urllib directly as a temporary bridge until the HTTP
backend follow-up spec ships.
"""
from __future__ import annotations

import io
import typing
import urllib.request

from mountainash_utils_files.path_helpers.storage_path import StoragePath
from mountainash_utils_files.path_helpers.suffixes import infer_pipeline
from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline


def _apply_pipeline_to_bytes(pipeline: Pipeline, raw: bytes) -> bytes:
    """Run *pipeline*'s read-side over *raw* and return the decoded bytes."""
    return pipeline.apply_read(io.BytesIO(raw)).read()


def read_bytes(
    path: str,
    *,
    auth_params: typing.Any = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    Local paths and recognised storage schemes route through
    :meth:`StorageFacade.from_path`. ``http://`` and ``https://`` paths use
    ``urllib.request.urlopen`` directly; this branch is removed when the
    HTTP backend follow-up spec ships.

    Args:
        path: Path or URL.
        auth_params: Optional auth params forwarded to the storage facade.
        infer: When True, inspect *path*'s suffix chain and auto-apply a
            read-side ``Pipeline`` for known suffixes (``.gz``, ``.gzip``,
            ``.gpg``, ``.asc``, ``.pgp``). Default False preserves
            byte-for-byte current behaviour.
        gpg: Required when *infer* is True and the suffix chain contains a
            gpg-family suffix. Supplies key material.
        gzip: Optional; defaults to ``Gzip()`` when a gzip suffix is seen.

    Returns:
        The full content of *path* as ``bytes``, optionally transform-decoded.

    Raises:
        ValueError: If the scheme is unrecognised, describes a backend that
            is not registered, or *infer* is True and a gpg-family suffix
            was seen without a *gpg* instance.
    """
    scheme = StoragePath.identify_scheme(path)

    if scheme in ("http", "https"):
        with urllib.request.urlopen(path) as response:  # noqa: S310
            raw = response.read()
        if not infer:
            return raw
        pipeline, _ = infer_pipeline(path, gpg=gpg, gzip=gzip)
        return _apply_pipeline_to_bytes(pipeline, raw) if pipeline else raw

    facade = StorageFacade.from_path(path, auth_params)
    if not infer:
        return facade.read(path)

    pipeline, _stripped = infer_pipeline(path, gpg=gpg, gzip=gzip)
    if pipeline is None:
        return facade.read(path)
    return facade.read(path, pipeline=pipeline)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `hatch run test:test tests/storage_facade/test_read_bytes.py -v`
Expected: all 11 tests pass (6 existing + 5 new).

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `hatch run test:test -v --no-header`
Expected: all previously-passing tests still pass. No tests newly failing.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/read_bytes.py tests/storage_facade/test_read_bytes.py
git commit -m "feat(read_bytes): add infer/gpg/gzip kwargs for suffix-driven pipelines"
```

---

## Task 4: Integration tests for `read_bytes(infer=True)`

**Files:**
- Create: `tests/storage_facade/test_read_bytes_infer.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/storage_facade/test_read_bytes_infer.py`:

```python
"""Integration tests for read_bytes with infer=True.

Local-filesystem fixtures only — no network. The GPG-backed tests reuse
the throwaway-keyring fixture pattern from tests/storage_transforms/test_gpg.py.
"""
from __future__ import annotations

import gzip as gzlib
import io
import shutil
import subprocess
from pathlib import Path

import pytest

from mountainash_utils_files import read_bytes
from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline

_RECIPIENT = "test@mountainash.example"
_FIXTURE_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "fixtures" / "gpg" / "generate_test_key.sh"
)


def test_read_bytes_infer_gzip_local_round_trip(tmp_path: Path):
    payload = b"the quick brown fox jumps over the lazy dog" * 20
    target = tmp_path / "data.gz"
    target.write_bytes(gzlib.compress(payload))

    assert read_bytes(str(target), infer=True) == payload


def test_read_bytes_infer_gzip_custom_instance_threaded(tmp_path: Path):
    payload = b"hello"
    target = tmp_path / "data.gz"
    target.write_bytes(gzlib.compress(payload, compresslevel=9))

    # Custom Gzip() on the read side — level is irrelevant for decode, but
    # threading a caller-supplied instance must not break the round trip.
    assert read_bytes(str(target), infer=True, gzip=Gzip(level=9)) == payload


def test_read_bytes_infer_preserves_plain_read_when_no_suffix(tmp_path: Path):
    target = tmp_path / "plain"
    target.write_bytes(b"not-encoded")
    assert read_bytes(str(target), infer=True) == b"not-encoded"


@pytest.mark.integration
class TestReadBytesInferGPG:
    @pytest.fixture
    def gpg_home(self, tmp_path: Path) -> Path:
        if shutil.which("gpg") is None:
            pytest.skip("gpg binary not available on PATH")
        home = tmp_path / "gnupg"
        subprocess.run([str(_FIXTURE_SCRIPT), str(home)], check=True)
        return home

    def test_read_bytes_infer_gpg_round_trip(self, tmp_path: Path, gpg_home: Path):
        payload = b"secret payload" * 20
        encrypted = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True)
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.gpg"
        target.write_bytes(encrypted)

        gpg = GPG(gnupghome=str(gpg_home))
        assert read_bytes(str(target), infer=True, gpg=gpg) == payload

    def test_read_bytes_infer_gz_gpg_combined_round_trip(
        self, tmp_path: Path, gpg_home: Path,
    ):
        payload = b"combined encoding" * 50
        # Pipeline(GPG, Gzip) = write gzip inside, gpg outside.
        encoded = Pipeline(
            GPG(recipients=[_RECIPIENT], gnupghome=str(gpg_home), always_trust=True),
            Gzip(),
        ).apply_write(io.BytesIO(payload)).read()

        target = tmp_path / "data.parquet.gz.gpg"
        target.write_bytes(encoded)

        gpg = GPG(gnupghome=str(gpg_home))
        assert read_bytes(str(target), infer=True, gpg=gpg) == payload
```

- [ ] **Step 2: Run tests to verify they pass**

Run the non-integration cases first:
`hatch run test:test tests/storage_facade/test_read_bytes_infer.py -v -m "not integration"`
Expected: 3 passed.

Then the integration cases (skipped if `gpg` is not on PATH — that's fine):
`hatch run test:test tests/storage_facade/test_read_bytes_infer.py -v -m integration`
Expected: 2 passed or 2 skipped.

- [ ] **Step 3: Run the full suite**

Run: `hatch run test:test`
Expected: all tests pass; no regressions.

- [ ] **Step 4: Run ruff**

Run: `hatch run ruff:check`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add tests/storage_facade/test_read_bytes_infer.py
git commit -m "test(read_bytes): integration tests for suffix-driven inference"
```

---

## Task 5: Document usage in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Locate the Stream Transforms section**

Open `CLAUDE.md` and find the `### Stream Transforms` heading (under `## Architecture`). It currently ends with the line:

```
The same `Pipeline` instance is used on both read and write paths; the facade applies transforms in the correct direction automatically.
```

- [ ] **Step 2: Add the usage example**

Immediately after that line, insert:

```markdown

### Suffix-Aware Transform Inference (Phase 6, 2026-04-18)

`infer_pipeline(path, gpg=..., gzip=...)` parses a path's suffix chain
right-to-left into a `Pipeline`. `read_bytes` accepts an opt-in `infer=True`
flag that routes through this inference.

```python
from mountainash_utils_files import read_bytes, GPG

# Auto-decompress a gzip-encoded file.
plaintext = read_bytes("s3://bucket/data.parquet.gz", infer=True)

# Auto-decrypt-then-decompress. gpg= supplies key material — a .gpg-family
# suffix without an instance raises ValueError.
plaintext = read_bytes(
    "s3://bucket/data.parquet.gz.gpg",
    infer=True,
    gpg=GPG(gnupghome="/path/to/keyring"),
)
```

Baseline suffix map: `.gz`/`.gzip` → `Gzip`, `.gpg`/`.asc`/`.pgp` → `GPG`.
Parsing stops at the first unknown suffix, so `data.parquet.gz.gpg` yields
`Pipeline(GPG, Gzip)` and a stripped path of `data.parquet`. Write-side
inference is intentionally not provided — writes take an explicit
`pipeline=` argument.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document read_bytes infer=True and infer_pipeline"
```

---

## Done criteria (mirror spec §9)

- [ ] `infer_pipeline` exported from `mountainash_utils_files.path_helpers` and top-level `mountainash_utils_files`.
- [ ] `read_bytes(path, infer=True, gpg=..., gzip=...)` routes through `infer_pipeline` and the facade's existing `pipeline=` parameter.
- [ ] Default `infer=False` preserves current `read_bytes` behaviour byte-for-byte (existing tests unchanged and passing).
- [ ] All new tests in Tasks 1, 2, 3, 4 pass under `hatch run test:test`.
- [ ] `hatch run ruff:check` clean.
- [ ] CLAUDE.md updated with a usage example under Stream Transforms.
- [ ] No new runtime dependency added; `[encryption]` extra still gates GPG.
