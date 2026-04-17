# path_helpers hygiene pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the eight-file `path_helpers/` package with a single `StoragePath` helper + scheme-metadata registry + S3 free functions, fixing seven latent bugs along the way.

**Architecture:** New modules (`scheme.py`, `storage_path.py`, `s3.py`) built TDD alongside the legacy files; the old files are deleted only after the new API is green. Test tree `tests/path_helpers/` replaces `tests/test_path_utils.py`. No compatibility shim — the module has no external consumers (verified).

**Tech Stack:** Python 3.12, `upath` (universal-pathlib), stdlib `urllib.parse`, `fnmatch`, `dataclasses`. Testing via `pytest` + `hatch run test:test`. Lint via `hatch run ruff:check`.

**Spec:** `docs/superpowers/specs/2026-04-18-path-helpers-hygiene-design.md`

**Branch:** `feat/path-helpers-hygiene` (off `feat/stream-transforms` HEAD; rebases onto `develop` cleanly once PR #39 merges).

---

## File Map

### Create

- `src/mountainash_utils_files/path_helpers/scheme.py` — `SchemeSpec` dataclass + `SCHEMES` registry + `_ALIAS_TO_CANONICAL`.
- `src/mountainash_utils_files/path_helpers/storage_path.py` — `StoragePath` classmethod-only helper.
- `src/mountainash_utils_files/path_helpers/s3.py` — `s3_bucket()`, `s3_key()` free functions.
- `tests/path_helpers/__init__.py` — empty package marker.
- `tests/path_helpers/test_scheme.py` — registry invariants.
- `tests/path_helpers/test_storage_path.py` — all `StoragePath` behavior + bug regressions.
- `tests/path_helpers/test_s3.py` — S3 extractor behavior.

### Modify

- `src/mountainash_utils_files/path_helpers/__init__.py` — new export surface.
- `src/mountainash_utils_files/__init__.py` — swap `PathHelper` re-export for `StoragePath`.
- `tests/test_public_api.py:32–33` — rename `test_path_helper_importable` → `test_storage_path_importable`.
- `CLAUDE.md` — update Package Structure tree.

### Delete

- `src/mountainash_utils_files/path_helpers/base_path_helper.py`
- `src/mountainash_utils_files/path_helpers/path_helper.py`
- `src/mountainash_utils_files/path_helpers/local_path_helper.py`
- `src/mountainash_utils_files/path_helpers/az_path_helper.py`
- `src/mountainash_utils_files/path_helpers/gcs_path_helper.py`
- `src/mountainash_utils_files/path_helpers/sftp_path_helper.py`
- `src/mountainash_utils_files/path_helpers/ssh_path_helper.py`
- `src/mountainash_utils_files/path_helpers/s3_path_helper.py`
- `tests/test_path_utils.py`
- `docs/recommendations/path_helpers_consistency_analysis.md`

---

## Task 1: Scheme registry

**Files:**
- Create: `src/mountainash_utils_files/path_helpers/scheme.py`
- Create: `tests/path_helpers/__init__.py`
- Create: `tests/path_helpers/test_scheme.py`

- [ ] **Step 1.1: Write failing tests for the scheme registry**

Create `tests/path_helpers/__init__.py` as an empty file.

Create `tests/path_helpers/test_scheme.py`:

```python
"""Tests for the scheme registry."""
from __future__ import annotations

import pytest

from mountainash_utils_files.path_helpers.scheme import (
    SCHEMES,
    SchemeSpec,
    _ALIAS_TO_CANONICAL,
)


def test_every_canonical_scheme_is_lowercase():
    for key, spec in SCHEMES.items():
        assert key == spec.scheme, f"key {key!r} must match spec.scheme {spec.scheme!r}"
        assert spec.scheme == spec.scheme.lower()


def test_aliases_are_lowercase_and_unique():
    seen: set[str] = set()
    for spec in SCHEMES.values():
        for alias in spec.aliases:
            assert alias == alias.lower()
            assert alias not in SCHEMES, f"alias {alias!r} collides with a canonical key"
            assert alias not in seen, f"alias {alias!r} repeats across SchemeSpecs"
            seen.add(alias)


def test_alias_to_canonical_covers_every_alias():
    expected = {
        alias: spec.scheme
        for spec in SCHEMES.values()
        for alias in spec.aliases
    }
    assert _ALIAS_TO_CANONICAL == expected


@pytest.mark.parametrize(
    "expected_key",
    [
        "", "file", "s3", "s3u", "gs", "azure", "sftp", "ftp", "ssh", "smb",
        "b2", "github", "dbfs", "hdfs", "webhdfs", "spark", "trino",
        "gdrive", "dropbox", "onedrive", "sharepoint",
    ],
)
def test_expected_schemes_present(expected_key: str):
    assert expected_key in SCHEMES


def test_bare_local_scheme_is_non_strict():
    assert SCHEMES[""].strict is False


def test_gcs_alias_resolves_to_gs():
    assert _ALIAS_TO_CANONICAL["gcs"] == "gs"


def test_az_alias_resolves_to_azure():
    assert _ALIAS_TO_CANONICAL["az"] == "azure"


def test_schemespec_is_frozen():
    spec = SCHEMES["s3"]
    with pytest.raises(Exception):  # dataclasses.FrozenInstanceError subclasses AttributeError
        spec.scheme = "nope"  # type: ignore[misc]
```

- [ ] **Step 1.2: Run tests — expect ImportError**

Run: `hatch run test:test tests/path_helpers/test_scheme.py -v`

Expected: all tests fail with `ModuleNotFoundError: No module named 'mountainash_utils_files.path_helpers.scheme'`.

- [ ] **Step 1.3: Create scheme.py**

Create `src/mountainash_utils_files/path_helpers/scheme.py`:

```python
"""Canonical URL-scheme registry for storage paths.

Parses paths; does not imply a backend exists for the scheme.
Entries here are decoupled from `storage_registry` / `storage_backends`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SchemeSpec:
    """Metadata for a canonical URL scheme.

    Attributes:
        scheme: Canonical lowercase scheme token (e.g. "s3", "gs", "" for local).
        aliases: Alternative lowercase prefixes that resolve to this canonical scheme
            (e.g. "gcs" is an alias of "gs").
        strict: If True (default), mixed-case scheme input is rejected by
            `StoragePath.normalize`. Only the bare-local entry uses strict=False.
    """

    scheme: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    strict: bool = True


SCHEMES: dict[str, SchemeSpec] = {
    "":           SchemeSpec(scheme="",         strict=False),
    "file":       SchemeSpec(scheme="file"),
    "s3":         SchemeSpec(scheme="s3"),
    "s3u":        SchemeSpec(scheme="s3u"),
    "gs":         SchemeSpec(scheme="gs",     aliases=("gcs",)),
    "azure":      SchemeSpec(scheme="azure",  aliases=("az",)),
    "sftp":       SchemeSpec(scheme="sftp"),
    "ftp":        SchemeSpec(scheme="ftp"),
    "ssh":        SchemeSpec(scheme="ssh"),
    "smb":        SchemeSpec(scheme="smb"),
    "b2":         SchemeSpec(scheme="b2"),
    "github":     SchemeSpec(scheme="github"),
    "dbfs":       SchemeSpec(scheme="dbfs"),
    "hdfs":       SchemeSpec(scheme="hdfs"),
    "webhdfs":    SchemeSpec(scheme="webhdfs"),
    "spark":      SchemeSpec(scheme="spark"),
    "trino":      SchemeSpec(scheme="trino"),
    "gdrive":     SchemeSpec(scheme="gdrive"),
    "dropbox":    SchemeSpec(scheme="dropbox"),
    "onedrive":   SchemeSpec(scheme="onedrive"),
    "sharepoint": SchemeSpec(scheme="sharepoint"),
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: spec.scheme for spec in SCHEMES.values() for alias in spec.aliases
}
```

- [ ] **Step 1.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_scheme.py -v`

Expected: all tests pass.

- [ ] **Step 1.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/scheme.py tests/path_helpers/__init__.py tests/path_helpers/test_scheme.py
git commit -m "feat(path_helpers): add canonical scheme registry"
```

---

## Task 2: `StoragePath.identify_scheme`

**Files:**
- Create: `src/mountainash_utils_files/path_helpers/storage_path.py`
- Create: `tests/path_helpers/test_storage_path.py`

Covers bug 5 (unknown-scheme handling) and bug 7 (no silent print).

- [ ] **Step 2.1: Write failing tests for identify_scheme**

Create `tests/path_helpers/test_storage_path.py`:

```python
"""Tests for StoragePath.

Regression tests for bugs documented in the hygiene spec are grouped
under the `test_bug_*` names so coverage maps directly onto the bug list.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from upath import UPath

from mountainash_utils_files.path_helpers.storage_path import StoragePath


@pytest.mark.parametrize(
    "path,expected",
    [
        ("s3://bucket/object", "s3"),
        ("gs://bucket/object", "gs"),
        ("gcs://bucket/object", "gs"),        # alias resolves
        ("azure://container/blob", "azure"),
        ("az://container/blob", "azure"),     # alias resolves
        ("sftp://user@host/p", "sftp"),
        ("ftp://host/p", "ftp"),
        ("ssh://user@host/p", "ssh"),
        ("smb://host/share/p", "smb"),
        ("b2://bucket/key", "b2"),
        ("github://owner/repo/p", "github"),
        ("dbfs:/some/path", "dbfs"),
        ("hdfs://host/path", "hdfs"),
        ("file:///tmp/x", "file"),
        ("SSH://user@host/p", "ssh"),         # forgiving on case
        ("S3://bucket/object", "s3"),         # forgiving on case
    ],
)
def test_identify_scheme_known(path: str, expected: str):
    assert StoragePath.identify_scheme(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/path/to/file",
        "~",
        "~/",
        "~/data/dir/",
        "randomfile.txt",
        "./file.txt",
        "../file.txt",
        "/",
    ],
)
def test_identify_scheme_bare_is_empty_string(path: str):
    assert StoragePath.identify_scheme(path) == ""


def test_identify_scheme_upath_input():
    assert StoragePath.identify_scheme(UPath("s3://bucket/key")) == "s3"


def test_identify_scheme_none_is_empty_string():
    assert StoragePath.identify_scheme(None) == ""


def test_identify_scheme_empty_string_is_empty_string():
    assert StoragePath.identify_scheme("") == ""


def test_bug_5_unknown_backend_scheme_returns_none_not_raises():
    """Bug 5: Old identify_storage_system returned keys without matching helpers.

    New contract: unrecognised scheme → None (not KeyError, not ValueError).
    """
    assert StoragePath.identify_scheme("nonsense://x") is None


def test_bug_7_no_print_on_unknown_scheme():
    """Bug 7: Old code printed a diagnostic on unknown schemes."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        StoragePath.identify_scheme("nonsense://x")
    assert buf.getvalue() == ""
```

- [ ] **Step 2.2: Run tests — expect ImportError**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v`

Expected: all fail with `ModuleNotFoundError: No module named 'mountainash_utils_files.path_helpers.storage_path'`.

- [ ] **Step 2.3: Create minimal storage_path.py with identify_scheme**

Create `src/mountainash_utils_files/path_helpers/storage_path.py`:

```python
"""StoragePath — parse and normalize storage paths.

Classmethod-only facade over upath.UPath + stdlib urlparse/urlunparse.
Does not dispatch to provider backends; callers own the scheme→provider
mapping (a single URL scheme can be served by multiple providers,
e.g. `s3://` → AWS S3 / MinIO / R2 / B2 / S3 Express).
"""
from __future__ import annotations

from typing import Optional, Union
from urllib.parse import urlparse

from upath import UPath

from .scheme import SCHEMES, _ALIAS_TO_CANONICAL


class StoragePath:
    """Stateless helper for parsing and normalizing storage paths."""

    @classmethod
    def identify_scheme(cls, path: Union[str, UPath, None]) -> Optional[str]:
        """Return the canonical scheme token, "" for bare/local, or None for unknown.

        Case-insensitive; aliases resolved. Returns None (not KeyError) for
        schemes not registered in SCHEMES.
        """
        if path is None:
            return ""
        text = str(path)
        if not text:
            return ""
        raw_scheme = urlparse(text).scheme.lower()
        if not raw_scheme:
            return ""
        if raw_scheme in SCHEMES:
            return raw_scheme
        if raw_scheme in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[raw_scheme]
        return None
```

- [ ] **Step 2.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v`

Expected: all 25 tests pass.

- [ ] **Step 2.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/storage_path.py tests/path_helpers/test_storage_path.py
git commit -m "feat(path_helpers): add StoragePath.identify_scheme"
```

---

## Task 3: `StoragePath.to_str` and `StoragePath.matches`

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/storage_path.py`
- Modify: `tests/path_helpers/test_storage_path.py`

- [ ] **Step 3.1: Add failing tests for to_str and matches**

Append to `tests/path_helpers/test_storage_path.py`:

```python
def test_to_str_none_passthrough():
    assert StoragePath.to_str(None) is None


def test_to_str_string_input():
    assert StoragePath.to_str("s3://b/k") == "s3://b/k"


def test_to_str_upath_input():
    assert StoragePath.to_str(UPath("s3://b/k")) == "s3://b/k"


def test_matches_literal():
    assert StoragePath.matches("file.csv", "file.csv") is True


def test_matches_star():
    assert StoragePath.matches("file*.csv", "file1.csv") is True
    assert StoragePath.matches("file*.csv", "file.csv") is True
    assert StoragePath.matches("file*.csv", "nope.csv") is False


def test_matches_question_mark():
    assert StoragePath.matches("f?le.csv", "file.csv") is True
    assert StoragePath.matches("f?le.csv", "fle.csv") is False


def test_matches_no_match():
    assert StoragePath.matches("*.csv", "file.parquet") is False
```

- [ ] **Step 3.2: Run tests — expect new tests fail**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v -k "to_str or matches"`

Expected: 7 failures (`AttributeError: type object 'StoragePath' has no attribute 'to_str'`).

- [ ] **Step 3.3: Implement to_str and matches**

Add imports at top of `storage_path.py`:

```python
import fnmatch
```

Add methods to the `StoragePath` class:

```python
    @classmethod
    def to_str(cls, path: Union[str, UPath, None]) -> Optional[str]:
        """None passthrough; otherwise `str(path)`. No normalization."""
        if path is None:
            return None
        return str(path)

    @classmethod
    def matches(cls, pattern: str, name: str) -> bool:
        """Wildcard match via fnmatch. Supports `*` and `?`."""
        return fnmatch.fnmatch(name, pattern)
```

- [ ] **Step 3.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v`

Expected: all tests pass.

- [ ] **Step 3.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/storage_path.py tests/path_helpers/test_storage_path.py
git commit -m "feat(path_helpers): add StoragePath.to_str and .matches"
```

---

## Task 4: `StoragePath.normalize` — bare/local paths

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/storage_path.py`
- Modify: `tests/path_helpers/test_storage_path.py`

- [ ] **Step 4.1: Add failing tests for bare-path normalize**

Append to `tests/path_helpers/test_storage_path.py`:

```python
@pytest.mark.parametrize(
    "path,expected_str",
    [
        ("/path/to/file", "/path/to/file"),
        ("/path/to/file/", "/path/to/file"),
        ("/", "/"),
        ("randomfile.txt", "randomfile.txt"),
        ("randomfile.txt/", "randomfile.txt"),
        ("./file.txt", "file.txt"),
        ("../file.txt", "../file.txt"),
    ],
)
def test_normalize_bare_paths(path: str, expected_str: str):
    result = StoragePath.normalize(path)
    assert result is not None
    assert str(result) == str(UPath(expected_str))


def test_normalize_none_returns_none():
    assert StoragePath.normalize(None) is None


def test_normalize_empty_string_returns_none():
    assert StoragePath.normalize("") is None


def test_normalize_expands_tilde():
    result = StoragePath.normalize("~")
    assert result is not None
    assert not str(result).startswith("~"), f"~ should expand, got {result}"


def test_normalize_upath_input():
    result = StoragePath.normalize(UPath("/tmp/x"))
    assert str(result) == "/tmp/x"
```

- [ ] **Step 4.2: Run tests — expect failures**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v -k normalize`

Expected: `AttributeError: type object 'StoragePath' has no attribute 'normalize'`.

- [ ] **Step 4.3: Add bare-path normalize**

Add to `StoragePath` class in `storage_path.py`:

```python
    @classmethod
    def normalize(cls, path: Union[str, UPath, None]) -> Optional[UPath]:
        """Normalize a path.

        - None or empty string → None.
        - Bare/local paths: expanduser, strip trailing slash unless length 1.
        - Schemed paths: validated + canonicalised via urlunparse (Task 5).
        - Raises ValueError on invalid schemed input (Task 6).
        """
        if path is None:
            return None
        text = str(path)
        if not text:
            return None
        scheme = cls.identify_scheme(text)
        if scheme == "":
            return cls._normalize_bare(text)
        # Schemed paths handled in later tasks.
        raise NotImplementedError(f"schemed normalization not yet implemented: {scheme}")

    @staticmethod
    def _normalize_bare(text: str) -> UPath:
        stripped = text.rstrip("/\\") if len(text) > 1 else text
        return UPath(stripped).expanduser()
```

- [ ] **Step 4.4: Run tests — bare-path tests PASS**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v -k normalize`

Expected: 11 tests pass (the ones added in 4.1). Any schemed-path normalize tests would fail with NotImplementedError but none exist yet.

- [ ] **Step 4.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/storage_path.py tests/path_helpers/test_storage_path.py
git commit -m "feat(path_helpers): normalize bare/local paths"
```

---

## Task 5: `StoragePath.normalize` — schemed paths + alias resolution

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/storage_path.py`
- Modify: `tests/path_helpers/test_storage_path.py`

Covers bug 2 (explicit returns — the old `_normalize_path_schema` had a silent fall-through to `None`).

- [ ] **Step 5.1: Add failing tests for schemed normalize**

Append to `tests/path_helpers/test_storage_path.py`:

```python
@pytest.mark.parametrize(
    "path,expected",
    [
        ("s3://bucket/object", "s3://bucket/object"),
        ("s3://bucket/object/", "s3://bucket/object"),
        ("s3://bucket", "s3://bucket"),
        ("sftp://user@host/p", "sftp://user@host/p"),
        ("ssh://user@host/p", "ssh://user@host/p"),
        ("github://owner/repo/p", "github://owner/repo/p"),
        ("file:///tmp/x", "file:///tmp/x"),
    ],
)
def test_normalize_schemed_canonical(path: str, expected: str):
    result = StoragePath.normalize(path)
    assert result is not None
    assert str(result) == str(UPath(expected))


def test_normalize_resolves_gcs_alias_to_gs():
    result = StoragePath.normalize("gcs://bucket/key")
    assert result is not None
    assert str(result) == str(UPath("gs://bucket/key"))


def test_normalize_resolves_az_alias_to_azure():
    result = StoragePath.normalize("az://container/blob")
    assert result is not None
    assert str(result) == str(UPath("azure://container/blob"))


def test_bug_2_normalize_always_returns_explicit_value():
    """Bug 2: old `_normalize_path_schema` fell through to None on a valid input branch.

    New contract: every reachable branch returns an explicit value.
    A scheme-valid path is never silently dropped.
    """
    result = StoragePath.normalize("s3://bucket/object")
    assert result is not None, "schemed path must not silently return None"
```

- [ ] **Step 5.2: Run tests — expect failures**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v -k normalize_schemed`

Expected: failures from the `NotImplementedError` placeholder in Task 4.

- [ ] **Step 5.3: Replace NotImplementedError with schemed normalization**

Replace the `raise NotImplementedError(...)` branch in `normalize` with:

```python
        if scheme is None:
            raise ValueError(f"Unknown scheme in path: {text!r}")
        return cls._normalize_schemed(text, scheme)
```

Add `urlunparse` import:

```python
from urllib.parse import urlparse, urlunparse
```

Add helper `_normalize_schemed`:

```python
    @staticmethod
    def _normalize_schemed(text: str, canonical_scheme: str) -> UPath:
        parsed = urlparse(text)
        # Rebuild with the canonical scheme (lowercased/alias-resolved).
        # Preserve netloc, path, params, query, fragment verbatim.
        rebuilt_path = parsed.path.rstrip("/") if len(parsed.path) > 1 else parsed.path
        rebuilt = urlunparse((
            canonical_scheme,
            parsed.netloc,
            rebuilt_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
        return UPath(rebuilt)
```

- [ ] **Step 5.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v`

Expected: all tests pass.

- [ ] **Step 5.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/storage_path.py tests/path_helpers/test_storage_path.py
git commit -m "feat(path_helpers): normalize schemed paths + resolve aliases"
```

---

## Task 6: `StoragePath.normalize` — strict error cases

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/storage_path.py`
- Modify: `tests/path_helpers/test_storage_path.py`

Covers bug 1 (old `__count=1` was a TypeError latent in a dead branch).

- [ ] **Step 6.1: Add failing tests for error cases**

Append to `tests/path_helpers/test_storage_path.py`:

```python
@pytest.mark.parametrize(
    "path",
    [
        "S3://bucket/object",      # mixed-case canonical
        "SSH://host/p",            # mixed-case canonical
        "GCS://bucket/key",        # mixed-case alias
        "AZ://container/blob",     # mixed-case alias
    ],
)
def test_normalize_mixed_case_scheme_raises(path: str):
    with pytest.raises(ValueError, match="mixed-case|case"):
        StoragePath.normalize(path)


@pytest.mark.parametrize(
    "path",
    [
        "nonsense://bucket/key",
        "totallymadeup://x",
    ],
)
def test_normalize_unknown_scheme_raises(path: str):
    with pytest.raises(ValueError, match="[Uu]nknown scheme"):
        StoragePath.normalize(path)


@pytest.mark.parametrize(
    "path",
    [
        "s3:bucket/object",         # missing //
        "s3:bucket/object/",
    ],
)
def test_normalize_malformed_url_raises(path: str):
    with pytest.raises(ValueError, match="[Mm]alformed|missing|//"):
        StoragePath.normalize(path)


def test_bug_1_no_str_replace_count_kwarg():
    """Bug 1: old code called `str.replace(..., __count=1)` which is a TypeError.

    The new path never calls str.replace with a kwarg, so the defect is
    structurally impossible. This test exercises the valid-input branch
    (which in the old code was unreachable past the dead replace call)
    and asserts it produces a clean result.
    """
    # Exercise the path that would have hit the broken branch in old code.
    result = StoragePath.normalize("s3://bucket/object")
    assert result is not None
    assert str(result) == "s3://bucket/object"
```

- [ ] **Step 6.2: Run tests — expect failures**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v -k "mixed_case or unknown_scheme or malformed"`

Expected: tests fail because `normalize` currently accepts mixed-case (urlparse lowercases) and the malformed check is missing.

- [ ] **Step 6.3: Add strictness checks to normalize**

Replace `normalize` in `storage_path.py` with:

```python
    @classmethod
    def normalize(cls, path: Union[str, UPath, None]) -> Optional[UPath]:
        """Normalize a path (see module docstring for contract)."""
        if path is None:
            return None
        text = str(path)
        if not text:
            return None
        scheme = cls.identify_scheme(text)
        if scheme == "":
            return cls._normalize_bare(text)
        if scheme is None:
            raise ValueError(f"Unknown scheme in path: {text!r}")
        cls._check_strict_casing(text, scheme)
        cls._check_url_form(text)
        return cls._normalize_schemed(text, scheme)
```

Add helpers:

```python
    @staticmethod
    def _check_strict_casing(text: str, canonical_scheme: str) -> None:
        """Reject mixed-case schemes when the SchemeSpec is strict.

        Extracts the literal prefix up to the first ':' from `text` and
        compares it to the canonical scheme. Aliases in the input must also
        be lowercase to be accepted.
        """
        raw_prefix = text.split(":", 1)[0]
        spec = SCHEMES[canonical_scheme]
        if not spec.strict:
            return
        # Accept canonical form OR a lowercase alias; reject anything else.
        if raw_prefix == canonical_scheme:
            return
        if raw_prefix in _ALIAS_TO_CANONICAL and raw_prefix == raw_prefix.lower():
            return
        raise ValueError(
            f"mixed-case scheme not accepted: {raw_prefix!r} "
            f"(expected lowercase canonical {canonical_scheme!r})"
        )

    @staticmethod
    def _check_url_form(text: str) -> None:
        """Reject `scheme:x` (missing `//`) — urlparse accepts it but it's ambiguous."""
        colon = text.find(":")
        if colon < 0:
            return
        if text[colon : colon + 3] != "://":
            raise ValueError(
                f"malformed URL — missing '//' after scheme: {text!r}"
            )
```

- [ ] **Step 6.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v`

Expected: all tests pass.

- [ ] **Step 6.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/storage_path.py tests/path_helpers/test_storage_path.py
git commit -m "feat(path_helpers): strict mode rejects mixed-case and malformed URLs"
```

---

## Task 7: `StoragePath.join`

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/storage_path.py`
- Modify: `tests/path_helpers/test_storage_path.py`

Covers bug 6 (old `combine_path_and_filename` was duplicated across subclasses — new design has one implementation).

- [ ] **Step 7.1: Add failing tests for join**

Append to `tests/path_helpers/test_storage_path.py`:

```python
def test_join_local():
    result = StoragePath.join("/tmp", "file.txt")
    assert str(result) == "/tmp/file.txt"


def test_join_s3():
    result = StoragePath.join("s3://bucket", "key.parquet")
    assert result is not None
    assert str(result) == str(UPath("s3://bucket/key.parquet"))


def test_join_strips_leading_slash_from_name():
    result = StoragePath.join("/tmp", "/file.txt")
    assert str(result) == "/tmp/file.txt"


def test_join_strips_trailing_slash_from_name():
    result = StoragePath.join("/tmp", "file.txt/")
    assert str(result) == "/tmp/file.txt"


def test_join_none_path_returns_none():
    assert StoragePath.join(None, "file.txt") is None


def test_join_none_name_returns_none():
    assert StoragePath.join("/tmp", None) is None


def test_join_empty_name_returns_none():
    assert StoragePath.join("/tmp", "") is None


def test_bug_6_single_join_implementation():
    """Bug 6: combine_path_and_filename was duplicated across GCS and SSH subclasses.

    With one StoragePath class there is only one implementation by construction.
    This test asserts the behavior is consistent across schemes.
    """
    local_result = str(StoragePath.join("/a", "b"))
    s3_result = str(StoragePath.join("s3://a", "b"))
    ssh_result = str(StoragePath.join("ssh://host/a", "b"))
    assert local_result.endswith("/a/b")
    assert s3_result.endswith("a/b")
    assert ssh_result.endswith("a/b")
```

- [ ] **Step 7.2: Run tests — expect failures**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v -k join`

Expected: 8 failures (`AttributeError`).

- [ ] **Step 7.3: Implement join**

Add to `StoragePath` class:

```python
    @classmethod
    def join(
        cls,
        path: Union[str, UPath, None],
        name: Optional[str],
    ) -> Optional[UPath]:
        """Return normalize(path) / stripped(name). None if either is falsy."""
        if path is None or name is None:
            return None
        clean_name = name.strip("/\\") if len(name) > 0 else ""
        if not clean_name:
            return None
        base = cls.normalize(path)
        if base is None:
            return None
        return base / clean_name
```

- [ ] **Step 7.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_storage_path.py -v`

Expected: all tests pass.

- [ ] **Step 7.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/storage_path.py tests/path_helpers/test_storage_path.py
git commit -m "feat(path_helpers): add StoragePath.join"
```

---

## Task 8: S3 free functions

**Files:**
- Create: `src/mountainash_utils_files/path_helpers/s3.py`
- Create: `tests/path_helpers/test_s3.py`

Covers bug 3 (old `S3PathHelper.format_namespace` ignored the extracted bucket — deleted outright, callers use `s3_bucket()`).

- [ ] **Step 8.1: Write failing tests for s3_bucket / s3_key**

Create `tests/path_helpers/test_s3.py`:

```python
"""Tests for S3-specific path extractors."""
from __future__ import annotations

import pytest
from upath import UPath

from mountainash_utils_files.path_helpers.s3 import s3_bucket, s3_key


@pytest.mark.parametrize(
    "path,expected_bucket",
    [
        ("s3://my-bucket", "my-bucket"),
        ("s3://my-bucket/key", "my-bucket"),
        ("s3://my-bucket/k/nested/file.parquet", "my-bucket"),
        (UPath("s3://b/k"), "b"),
    ],
)
def test_s3_bucket_happy(path, expected_bucket):
    assert s3_bucket(path) == expected_bucket


@pytest.mark.parametrize(
    "path",
    [
        "/local/path",
        "gs://b/k",
        "",
        None,
    ],
)
def test_s3_bucket_non_s3_returns_none(path):
    assert s3_bucket(path) is None


@pytest.mark.parametrize(
    "path,expected_key",
    [
        ("s3://bucket", ""),
        ("s3://bucket/", ""),
        ("s3://bucket/key", "key"),
        ("s3://bucket/a/b/c.parquet", "a/b/c.parquet"),
    ],
)
def test_s3_key_happy(path: str, expected_key: str):
    assert s3_key(path) == expected_key


@pytest.mark.parametrize(
    "path",
    [
        "/local/path",
        "gs://b/k",
        None,
    ],
)
def test_s3_key_non_s3_returns_none(path):
    assert s3_key(path) is None


def test_bug_3_format_namespace_is_gone():
    """Bug 3: old S3PathHelper.format_namespace returned 's3://' even when a
    bucket was extractable. Function deleted — callers compose the string
    from s3_bucket() instead.
    """
    from mountainash_utils_files.path_helpers import s3

    assert not hasattr(s3, "format_namespace")
```

- [ ] **Step 8.2: Run tests — expect ImportError**

Run: `hatch run test:test tests/path_helpers/test_s3.py -v`

Expected: `ModuleNotFoundError: No module named 'mountainash_utils_files.path_helpers.s3'`.

- [ ] **Step 8.3: Create s3.py**

Create `src/mountainash_utils_files/path_helpers/s3.py`:

```python
"""S3-specific path extractors.

Free functions, not classes. Both return None (not raise) when the
input isn't an S3 path, so callers can branch cheaply.
"""
from __future__ import annotations

from typing import Optional, Union

from upath import UPath

from .storage_path import StoragePath


def s3_bucket(path: Union[str, UPath, None]) -> Optional[str]:
    """Return the bucket name from an S3 path, or None if `path` isn't S3."""
    if path is None:
        return None
    if StoragePath.identify_scheme(path) != "s3":
        return None
    parsed = StoragePath.normalize(path)
    if parsed is None:
        return None
    # UPath parts for "s3://bucket/key/..." → ("s3://", "bucket", "key", ...)
    parts = parsed.parts
    if len(parts) < 2:
        return None
    return parts[1]


def s3_key(path: Union[str, UPath, None]) -> Optional[str]:
    """Return the object key (path after the bucket, no leading slash), or None."""
    if path is None:
        return None
    if StoragePath.identify_scheme(path) != "s3":
        return None
    parsed = StoragePath.normalize(path)
    if parsed is None:
        return None
    parts = parsed.parts
    if len(parts) < 3:
        return ""
    return "/".join(parts[2:])
```

- [ ] **Step 8.4: Run tests — expect PASS**

Run: `hatch run test:test tests/path_helpers/test_s3.py -v`

Expected: all tests pass.

- [ ] **Step 8.5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/s3.py tests/path_helpers/test_s3.py
git commit -m "feat(path_helpers): add s3_bucket and s3_key free functions"
```

---

## Task 9: Package `__init__.py` + top-level re-exports

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/__init__.py`
- Modify: `src/mountainash_utils_files/__init__.py`
- Modify: `tests/test_public_api.py`

- [ ] **Step 9.1: Update test_public_api.py to expect StoragePath**

Read the current `tests/test_public_api.py` to find the `test_path_helper_importable` test (around lines 32-33).

Replace:

```python
    def test_path_helper_importable(self):
        from mountainash_utils_files import PathHelper
```

With:

```python
    def test_storage_path_importable(self):
        from mountainash_utils_files import StoragePath
        assert callable(StoragePath.identify_scheme)
```

- [ ] **Step 9.2: Run the updated test — expect failure**

Run: `hatch run test:test tests/test_public_api.py::TestPublicAPI::test_storage_path_importable -v`

Expected: `ImportError: cannot import name 'StoragePath' from 'mountainash_utils_files'`.

- [ ] **Step 9.3: Rewrite path_helpers/__init__.py**

Replace `src/mountainash_utils_files/path_helpers/__init__.py` entirely with:

```python
"""Path parsing and normalization for storage URLs.

Exports:
    StoragePath — classmethod-only helper (identify_scheme, normalize, join, to_str, matches)
    SchemeSpec  — dataclass describing one canonical scheme
    SCHEMES     — dict of canonical schemes supported by path parsing
    s3          — submodule with s3_bucket(), s3_key()

This module parses paths. It does not imply that a backend exists for
every scheme in SCHEMES; caller is responsible for scheme→provider mapping.
"""
from . import s3
from .scheme import SCHEMES, SchemeSpec
from .storage_path import StoragePath

__all__ = ("StoragePath", "SchemeSpec", "SCHEMES", "s3")
```

- [ ] **Step 9.4: Update top-level mountainash_utils_files/__init__.py**

In `src/mountainash_utils_files/__init__.py`, replace:

```python
# Path utilities
from .path_helpers import PathHelper
```

with:

```python
# Path utilities
from .path_helpers import StoragePath
```

And in the `__all__` list, replace the `"PathHelper",` entry with `"StoragePath",`. (No other legacy class names appear in this file.)

- [ ] **Step 9.5: Run the public-api test — expect PASS**

Run: `hatch run test:test tests/test_public_api.py -v`

Expected: all tests pass, including `test_storage_path_importable`.

- [ ] **Step 9.6: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/__init__.py src/mountainash_utils_files/__init__.py tests/test_public_api.py
git commit -m "feat(api): export StoragePath; drop PathHelper top-level re-export"
```

---

## Task 10: Delete legacy files

**Files:**
- Delete: `src/mountainash_utils_files/path_helpers/base_path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/local_path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/az_path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/gcs_path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/sftp_path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/ssh_path_helper.py`
- Delete: `src/mountainash_utils_files/path_helpers/s3_path_helper.py`
- Delete: `tests/test_path_utils.py`
- Delete: `docs/recommendations/path_helpers_consistency_analysis.md`

- [ ] **Step 10.1: Delete the eight legacy path_helpers files**

Run:

```bash
git rm \
  src/mountainash_utils_files/path_helpers/base_path_helper.py \
  src/mountainash_utils_files/path_helpers/path_helper.py \
  src/mountainash_utils_files/path_helpers/local_path_helper.py \
  src/mountainash_utils_files/path_helpers/az_path_helper.py \
  src/mountainash_utils_files/path_helpers/gcs_path_helper.py \
  src/mountainash_utils_files/path_helpers/sftp_path_helper.py \
  src/mountainash_utils_files/path_helpers/ssh_path_helper.py \
  src/mountainash_utils_files/path_helpers/s3_path_helper.py
```

- [ ] **Step 10.2: Delete the old test file and superseded doc**

Run:

```bash
git rm tests/test_path_utils.py
git rm docs/recommendations/path_helpers_consistency_analysis.md
```

- [ ] **Step 10.3: Run full test suite — expect green**

Run: `hatch run test:test`

Expected: all tests pass. If any test imports a deleted class, the test is on a code path that shouldn't exist; diagnose and fix rather than restore the file.

- [ ] **Step 10.4: Run ruff — expect clean**

Run: `hatch run ruff:check`

Expected: no lint errors.

- [ ] **Step 10.5: Grep invariant — no stray PathHelper references**

Run:

```bash
grep -R "PathHelper\b" src/ tests/ || true
```

Expected: empty output. Any remaining hit must be fixed in this task before committing.

- [ ] **Step 10.6: Commit**

```bash
git commit -m "chore(path_helpers): remove legacy subclass files + old test module"
```

---

## Task 11: Docs refresh

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 11.1: Update the Package Structure tree in CLAUDE.md**

Open `CLAUDE.md`, locate the `### Package Structure` section that lists the `src/mountainash_utils_files/` tree.

Find the existing `path_helpers/` entry (currently unannotated). Replace with:

```
├── path_helpers/                  # Parse + normalize storage paths (scheme-aware)
│   ├── __init__.py                # StoragePath, SchemeSpec, SCHEMES, s3
│   ├── scheme.py                  # SchemeSpec + SCHEMES registry
│   ├── storage_path.py            # StoragePath helper class
│   └── s3.py                      # s3_bucket, s3_key free functions
```

Ensure the tree still renders as a valid ASCII tree (pipes line up; trailing spaces trimmed).

- [ ] **Step 11.2: Commit the docs update**

```bash
git add CLAUDE.md
git commit -m "docs(claude): update path_helpers package structure"
```

---

## Task 12: Final validation

**Files:**
- None (verification only).

- [ ] **Step 12.1: Full test suite**

Run: `hatch run test:test`

Expected: all tests pass (including new `tests/path_helpers/` suite, ~60+ new tests).

- [ ] **Step 12.2: Lint**

Run: `hatch run ruff:check`

Expected: clean.

- [ ] **Step 12.3: Type check (optional but recommended)**

Run: `hatch run mypy:check` if the project includes mypy in CI.

Expected: no new errors in `path_helpers/`. Pre-existing errors elsewhere in the codebase are acceptable.

- [ ] **Step 12.4: Done-criteria grep assertions**

Run all four and verify output:

```bash
# No remaining PathHelper references anywhere in sources or tests.
grep -R "PathHelper\b" src/ tests/ || true

# StoragePath is reachable from src (module def + top-level re-export).
grep -R "StoragePath\b" src/

# No print() calls in path_helpers/.
grep -R "^\s*print(" src/mountainash_utils_files/path_helpers/ || true

# All eight legacy files are gone.
ls src/mountainash_utils_files/path_helpers/
```

Expected:
- `PathHelper` grep: empty.
- `StoragePath` grep: at least two matches (`storage_path.py` and the top-level `__init__.py`).
- `print(` grep: empty.
- `ls` output: `__init__.py`, `scheme.py`, `storage_path.py`, `s3.py` — no other files.

- [ ] **Step 12.5: Push the branch**

```bash
git push -u origin feat/path-helpers-hygiene
```

- [ ] **Step 12.6: Use the superpowers:finishing-a-development-branch skill**

Present the four options and act on the user's choice. The branch's PR should target `develop`, not `main`, per the repo's branch flow.

---

## Notes for the executor

- **TDD discipline:** every task writes tests first, asserts they fail, implements the minimum, asserts they pass. Do not batch implementation commits.
- **Branch state:** the spec commit `8493c4f` is present on both `feat/stream-transforms` (PR #39, still open) and this branch. When PR #39 merges, rebase this branch onto the new `develop`; git will dedupe the identical commit automatically.
- **Bug regression tests:** each bug from the spec §5 is named `test_bug_N_...` so coverage maps onto the bug list. Bugs 4 and 5 are "structural" — the problematic dispatcher simply does not exist in the new design, so their regression tests assert the absence of the failure mode.
- **Do not** re-introduce any of: `PathHelper.path_util_classes`, `format_namespace`, `strip_all_slashes`, `strip_trailing_slashes`, `identify_storage_system`, `wildcard_match` (custom regex), `_normalize_path_schema` with string slicing.
