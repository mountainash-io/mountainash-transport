# Canonical Path Dispatcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `path_helpers.SCHEMES` the single source of truth for scheme→provider dispatch, give callers `StorageFacade.from_path()` and top-level `read_bytes()`, and delete the duplicated scheme ladder in `storage_registry/backend_detection.py`.

**Architecture:** `SchemeSpec` gains an optional `provider` field. `SCHEMES` is annotated in place and gains 5 new entries (`s3express`, `r2`, `minio`, `http`, `https`). `detect_provider_from_path` becomes a thin reader over `SCHEMES` via `StoragePath.identify_scheme`. `StorageFacade.from_path(path)` classmethod and `read_bytes(path)` top-level helper are added. No new backends; no changes to pydata readers (both are follow-up specs).

**Tech Stack:** Python 3.12, hatch, pytest, ruff, pyright. No new deps.

**Spec:** `docs/superpowers/specs/2026-04-18-canonical-path-dispatcher-design.md`

**Branch:** `feat/canonical-path-dispatcher` (already created off `develop`; spec committed at `b363421`)

---

## File Inventory

**Modify:**
- `src/mountainash_utils_files/path_helpers/scheme.py` — extend SchemeSpec; annotate + add SCHEMES entries
- `src/mountainash_utils_files/storage_registry/backend_detection.py` — rewrite as thin reader
- `src/mountainash_utils_files/storage_facade/facade.py` — add `from_path` classmethod
- `src/mountainash_utils_files/storage_facade/__init__.py` — export `read_bytes`
- `src/mountainash_utils_files/__init__.py` — export `read_bytes`
- `tests/path_helpers/test_scheme.py` — extend coverage for provider field
- `CLAUDE.md` — document new APIs

**Create:**
- `src/mountainash_utils_files/storage_facade/read_bytes.py` — new helper
- `tests/storage_registry/__init__.py` — empty
- `tests/storage_registry/test_backend_detection.py` — new test module
- `tests/storage_facade/__init__.py` — empty (if missing)
- `tests/storage_facade/test_from_path.py` — new test module
- `tests/storage_facade/test_read_bytes.py` — new test module

---

## Task 1: Extend `SchemeSpec` with `provider` field

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/scheme.py:7-25`
- Test: `tests/path_helpers/test_scheme.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/path_helpers/test_scheme.py`:

```python
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


def test_schemespec_has_provider_field_defaulting_to_none():
    spec = SchemeSpec(scheme="example")
    assert spec.provider is None


def test_schemespec_accepts_provider():
    spec = SchemeSpec(scheme="s3", provider=CONST_STORAGE_PROVIDER_TYPE.S3)
    assert spec.provider == CONST_STORAGE_PROVIDER_TYPE.S3
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/path_helpers/test_scheme.py::test_schemespec_has_provider_field_defaulting_to_none -v
```

Expected: `FAILED` — `TypeError: SchemeSpec.__init__() got an unexpected keyword argument 'provider'` OR `AttributeError` on `.provider`.

- [ ] **Step 3: Modify `SchemeSpec` to add the field**

In `src/mountainash_utils_files/path_helpers/scheme.py`, at the top of the file, add the import (after the existing `from dataclasses import ...`):

```python
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
```

Replace the `SchemeSpec` dataclass:

```python
@dataclass(frozen=True)
class SchemeSpec:
    """Metadata for a canonical URL scheme.

    Attributes:
        scheme: Canonical lowercase scheme token (e.g. "s3", "gs", "" for local).
        aliases: Alternative lowercase prefixes that resolve to this canonical scheme
            (e.g. "gcs" is an alias of "gs").
        strict: If True (default), mixed-case scheme input is rejected by
            `StoragePath.normalize`. Only the bare-local entry uses strict=False.
        provider: The storage provider enum this scheme routes to, or None for
            schemes described for registry completeness but with no registered
            backend (e.g. hdfs, dbfs, sharepoint).
    """

    scheme: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    strict: bool = True
    provider: CONST_STORAGE_PROVIDER_TYPE | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/path_helpers/test_scheme.py -v
```

Expected: all existing tests still green (provider is additive with default `None`); two new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/scheme.py tests/path_helpers/test_scheme.py
git commit -m "feat(scheme): SchemeSpec gains optional provider field"
```

---

## Task 2: Annotate `SCHEMES` with providers + add 5 new entries

**Files:**
- Modify: `src/mountainash_utils_files/path_helpers/scheme.py:28-50`
- Test: `tests/path_helpers/test_scheme.py`

- [ ] **Step 1: Write failing table-driven tests for the provider annotations**

Append to `tests/path_helpers/test_scheme.py`:

```python
_EXPECTED_PROVIDERS: dict[str, CONST_STORAGE_PROVIDER_TYPE] = {
    "":          CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    "file":      CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    "s3":        CONST_STORAGE_PROVIDER_TYPE.S3,
    "s3express": CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    "gs":        CONST_STORAGE_PROVIDER_TYPE.GCS,
    "azure":     CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "r2":        CONST_STORAGE_PROVIDER_TYPE.R2,
    "minio":     CONST_STORAGE_PROVIDER_TYPE.MINIO,
    "b2":        CONST_STORAGE_PROVIDER_TYPE.B2,
    "sftp":      CONST_STORAGE_PROVIDER_TYPE.SFTP,
    "ssh":       CONST_STORAGE_PROVIDER_TYPE.SSH,
    "ftp":       CONST_STORAGE_PROVIDER_TYPE.FTP,
    "smb":       CONST_STORAGE_PROVIDER_TYPE.SMB,
    "github":    CONST_STORAGE_PROVIDER_TYPE.GITHUB,
}

_DESCRIBE_ONLY_SCHEMES: tuple[str, ...] = (
    "s3u", "http", "https", "dbfs", "hdfs", "webhdfs", "spark", "trino",
    "gdrive", "dropbox", "onedrive", "sharepoint",
)


@pytest.mark.parametrize("scheme,expected", list(_EXPECTED_PROVIDERS.items()))
def test_known_schemes_map_to_expected_providers(
    scheme: str, expected: CONST_STORAGE_PROVIDER_TYPE
):
    assert SCHEMES[scheme].provider == expected


@pytest.mark.parametrize("scheme", _DESCRIBE_ONLY_SCHEMES)
def test_describe_only_schemes_have_none_provider(scheme: str):
    assert SCHEMES[scheme].provider is None


def test_every_spec_has_provider_attribute():
    for spec in SCHEMES.values():
        assert hasattr(spec, "provider")


def test_new_entries_present():
    for key in ("s3express", "r2", "minio", "http", "https"):
        assert key in SCHEMES
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/path_helpers/test_scheme.py -v -k "known_schemes or describe_only or new_entries_present"
```

Expected: failures — provider is `None` for everything so far; `s3express`/`r2`/`minio`/`http`/`https` don't exist as keys.

- [ ] **Step 3: Update `SCHEMES` dict**

In `src/mountainash_utils_files/path_helpers/scheme.py`, replace the `SCHEMES` dict:

```python
SCHEMES: dict[str, SchemeSpec] = {
    "":           SchemeSpec(scheme="",          strict=False, provider=CONST_STORAGE_PROVIDER_TYPE.LOCAL),
    "file":       SchemeSpec(scheme="file",      provider=CONST_STORAGE_PROVIDER_TYPE.LOCAL),
    "s3":         SchemeSpec(scheme="s3",        provider=CONST_STORAGE_PROVIDER_TYPE.S3),
    "s3u":        SchemeSpec(scheme="s3u"),
    "s3express":  SchemeSpec(scheme="s3express", provider=CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS),
    "gs":         SchemeSpec(scheme="gs",        aliases=("gcs",), provider=CONST_STORAGE_PROVIDER_TYPE.GCS),
    "azure":      SchemeSpec(scheme="azure",     aliases=("az",),  provider=CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB),
    "r2":         SchemeSpec(scheme="r2",        provider=CONST_STORAGE_PROVIDER_TYPE.R2),
    "minio":      SchemeSpec(scheme="minio",     provider=CONST_STORAGE_PROVIDER_TYPE.MINIO),
    "b2":         SchemeSpec(scheme="b2",        provider=CONST_STORAGE_PROVIDER_TYPE.B2),
    "sftp":       SchemeSpec(scheme="sftp",      provider=CONST_STORAGE_PROVIDER_TYPE.SFTP),
    "ssh":        SchemeSpec(scheme="ssh",       provider=CONST_STORAGE_PROVIDER_TYPE.SSH),
    "ftp":        SchemeSpec(scheme="ftp",       provider=CONST_STORAGE_PROVIDER_TYPE.FTP),
    "smb":        SchemeSpec(scheme="smb",       provider=CONST_STORAGE_PROVIDER_TYPE.SMB),
    "github":     SchemeSpec(scheme="github",    provider=CONST_STORAGE_PROVIDER_TYPE.GITHUB),
    "http":       SchemeSpec(scheme="http"),
    "https":      SchemeSpec(scheme="https"),
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
```

- [ ] **Step 4: Run full scheme tests**

```bash
pytest tests/path_helpers/test_scheme.py -v
```

Expected: all tests pass (existing + new). Also verify the hygiene-pass parametrised `test_expected_schemes_present` still passes for every scheme it already listed (the 21 original keys remain present).

- [ ] **Step 5: Run full test suite to catch unrelated breakage**

```bash
hatch run test:test
```

Expected: all existing tests still green. In particular, `tests/path_helpers/test_storage_path.py` uses `identify_scheme`, which now has more keys to resolve — verify nothing that scans SCHEMES assumes a 21-entry size.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/path_helpers/scheme.py tests/path_helpers/test_scheme.py
git commit -m "feat(scheme): annotate SCHEMES with providers; add s3express/r2/minio/http/https"
```

---

## Task 3: Rewrite `detect_provider_from_path` to read from `SCHEMES`

**Files:**
- Modify: `src/mountainash_utils_files/storage_registry/backend_detection.py`

Note: tests for the new behavior live in Task 4, which creates the new test directory. This task only replaces the implementation and relies on the existing integration points (nothing else imports `_SCHEME_TO_PROVIDER`).

- [ ] **Step 1: Verify no other in-repo callers depend on `_SCHEME_TO_PROVIDER`**

```bash
grep -rn "_SCHEME_TO_PROVIDER" src tests
```

Expected output: only `src/mountainash_utils_files/storage_registry/backend_detection.py` matches. If anything else matches, update this plan before continuing.

- [ ] **Step 2: Replace the file**

Overwrite `src/mountainash_utils_files/storage_registry/backend_detection.py`:

```python
# storage_registry/backend_detection.py

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.path_helpers.scheme import SCHEMES
from mountainash_utils_files.path_helpers.storage_path import StoragePath


def detect_provider_from_path(path: str) -> CONST_STORAGE_PROVIDER_TYPE:
    """Detect the storage provider from a path string.

    Args:
        path: File path, optionally with a URL scheme (e.g. ``s3://bucket/key``).

    Returns:
        The matching :class:`CONST_STORAGE_PROVIDER_TYPE` enum member.

    Raises:
        ValueError: If the scheme is present but not registered in SCHEMES,
            or if the scheme is registered but has no backend provider.
    """
    scheme = StoragePath.identify_scheme(path)
    if scheme is None:
        raise ValueError(f"Unrecognised scheme in path {path!r}")
    spec = SCHEMES[scheme]
    if spec.provider is None:
        raise ValueError(
            f"Scheme {scheme!r} is recognised but has no registered backend"
        )
    return spec.provider
```

- [ ] **Step 3: Run full test suite**

```bash
hatch run test:test
```

Expected: all existing tests pass. The only existing usage site inside this repo is `storage_facade/facade.py` (not a caller of `detect_provider_from_path` today, but it will be in Task 5). Outside this repo, pydata readers call it through `storage_registry` — not exercised in this repo's tests.

- [ ] **Step 4: Commit**

```bash
git add src/mountainash_utils_files/storage_registry/backend_detection.py
git commit -m "refactor(backend_detection): read provider from SCHEMES; drop literal dict"
```

---

## Task 4: Create `tests/storage_registry/` with behavioral tests

**Files:**
- Create: `tests/storage_registry/__init__.py` (empty)
- Create: `tests/storage_registry/test_backend_detection.py`

- [ ] **Step 1: Create the directory + empty `__init__.py`**

```bash
mkdir -p tests/storage_registry
touch tests/storage_registry/__init__.py
```

- [ ] **Step 2: Write the test module**

Create `tests/storage_registry/test_backend_detection.py`:

```python
"""Tests for storage_registry.backend_detection.detect_provider_from_path."""
from __future__ import annotations

import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_registry.backend_detection import (
    detect_provider_from_path,
)


def test_local_path_returns_local():
    assert detect_provider_from_path("/tmp/foo") == CONST_STORAGE_PROVIDER_TYPE.LOCAL


def test_relative_local_path_returns_local():
    assert detect_provider_from_path("foo/bar.txt") == CONST_STORAGE_PROVIDER_TYPE.LOCAL


def test_empty_path_returns_local():
    assert detect_provider_from_path("") == CONST_STORAGE_PROVIDER_TYPE.LOCAL


def test_s3_scheme_returns_s3():
    assert (
        detect_provider_from_path("s3://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.S3
    )


def test_gs_scheme_returns_gcs():
    assert (
        detect_provider_from_path("gs://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.GCS
    )


def test_gcs_alias_resolves_to_gcs():
    assert (
        detect_provider_from_path("gcs://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.GCS
    )


def test_azure_scheme_returns_azure_blob():
    assert (
        detect_provider_from_path("azure://container/blob")
        == CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB
    )


def test_az_alias_resolves_to_azure_blob():
    assert (
        detect_provider_from_path("az://container/blob")
        == CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB
    )


def test_minio_scheme_now_resolves():
    assert (
        detect_provider_from_path("minio://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.MINIO
    )


def test_r2_scheme_resolves():
    assert (
        detect_provider_from_path("r2://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.R2
    )


def test_ftp_scheme_resolves():
    assert (
        detect_provider_from_path("ftp://host/file")
        == CONST_STORAGE_PROVIDER_TYPE.FTP
    )


def test_github_scheme_resolves():
    assert (
        detect_provider_from_path("github://owner/repo/path")
        == CONST_STORAGE_PROVIDER_TYPE.GITHUB
    )


def test_describe_only_scheme_raises_no_backend():
    with pytest.raises(ValueError, match="has no registered backend"):
        detect_provider_from_path("hdfs://cluster/path")


def test_http_scheme_raises_no_backend():
    # http is registered in SCHEMES but the HTTP backend is a follow-up spec.
    with pytest.raises(ValueError, match="has no registered backend"):
        detect_provider_from_path("http://example.com/file.txt")


def test_https_scheme_raises_no_backend():
    with pytest.raises(ValueError, match="has no registered backend"):
        detect_provider_from_path("https://example.com/file.txt")


def test_unrecognised_scheme_raises():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        detect_provider_from_path("gopher://example.com/")
```

- [ ] **Step 3: Run the new tests**

```bash
pytest tests/storage_registry/test_backend_detection.py -v
```

Expected: all pass.

- [ ] **Step 4: Run full suite**

```bash
hatch run test:test
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add tests/storage_registry/
git commit -m "test(backend_detection): cover widened scheme map and error paths"
```

---

## Task 5: Add `StorageFacade.from_path` classmethod

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/facade.py:78-81` (near `for_local` classmethod)
- Create: `tests/storage_facade/__init__.py` (if missing)
- Create: `tests/storage_facade/test_from_path.py`

- [ ] **Step 1: Verify test directory exists**

```bash
ls tests/storage_facade/__init__.py 2>/dev/null && echo "exists" || echo "missing"
```

If "missing", create it:

```bash
mkdir -p tests/storage_facade
touch tests/storage_facade/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `tests/storage_facade/test_from_path.py`:

```python
"""Tests for StorageFacade.from_path classmethod."""
from __future__ import annotations

import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.storage_facade import StorageFacade


def test_from_path_returns_storagefacade_for_local():
    facade = StorageFacade.from_path("/tmp/foo.txt")
    assert isinstance(facade, StorageFacade)
    # LOCAL backend is always registered, so this must succeed.


def test_from_path_returns_storagefacade_for_s3(monkeypatch):
    """Verify provider routing without requiring real S3 backend construction."""
    captured: dict[str, object] = {}

    class _Dummy:
        pass

    from mountainash_utils_files.storage_facade import facade as facade_mod

    def _fake_get(provider, auth=None):
        captured["provider"] = provider
        captured["auth"] = auth
        return _Dummy()

    # facade.py binds get_storage_backend at module load; patch it there.
    monkeypatch.setattr(facade_mod, "get_storage_backend", _fake_get)

    StorageFacade.from_path("s3://bucket/key")
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.S3
    assert captured["auth"] is None


def test_from_path_passes_auth_params(monkeypatch):
    captured: dict[str, object] = {}

    class _Dummy:
        pass

    def _fake_get(provider, auth=None):
        captured["provider"] = provider
        captured["auth"] = auth
        return _Dummy()

    from mountainash_utils_files.storage_facade import facade as facade_mod

    monkeypatch.setattr(facade_mod, "get_storage_backend", _fake_get)

    sentinel = object()
    StorageFacade.from_path("gs://bucket/key", auth_params=sentinel)  # type: ignore[arg-type]
    assert captured["provider"] == CONST_STORAGE_PROVIDER_TYPE.GCS
    assert captured["auth"] is sentinel


def test_from_path_raises_for_unrecognised_scheme():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        StorageFacade.from_path("gopher://example.com/")


def test_from_path_raises_for_describe_only_scheme():
    with pytest.raises(ValueError, match="has no registered backend"):
        StorageFacade.from_path("hdfs://cluster/file")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/storage_facade/test_from_path.py -v
```

Expected: `AttributeError: type object 'StorageFacade' has no attribute 'from_path'`.

- [ ] **Step 4: Add the classmethod**

In `src/mountainash_utils_files/storage_facade/facade.py`, add the import near the top of the file (alongside the existing `from mountainash_utils_files.storage_registry import get_storage_backend`):

```python
from mountainash_utils_files.storage_registry import (
    detect_provider_from_path,
    get_storage_backend,
)
```

Then, immediately below the existing `for_local` classmethod, add:

```python
    @classmethod
    def from_path(
        cls,
        path: str,
        auth_params: typing.Any = None,
    ) -> StorageFacade:
        """Construct a facade whose provider is inferred from a path's URL scheme.

        Args:
            path: Path string, optionally with a URL scheme.
            auth_params: Optional auth params forwarded to the backend.

        Returns:
            A StorageFacade wired to the provider that matches *path*.

        Raises:
            ValueError: If *path*'s scheme is unrecognised or has no backend.
        """
        provider = detect_provider_from_path(path)
        return cls(provider_type=provider, auth_params=auth_params)
```

- [ ] **Step 5: Run the new tests**

```bash
pytest tests/storage_facade/test_from_path.py -v
```

Expected: all pass.

- [ ] **Step 6: Run full suite**

```bash
hatch run test:test
hatch run ruff:check
```

Expected: both green.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/facade.py tests/storage_facade/
git commit -m "feat(facade): StorageFacade.from_path infers provider from path scheme"
```

---

## Task 6: Add `read_bytes` helper + export

**Files:**
- Create: `src/mountainash_utils_files/storage_facade/read_bytes.py`
- Modify: `src/mountainash_utils_files/storage_facade/__init__.py`
- Modify: `src/mountainash_utils_files/__init__.py`
- Create: `tests/storage_facade/test_read_bytes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/storage_facade/test_read_bytes.py`:

```python
"""Tests for the top-level read_bytes helper."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from mountainash_utils_files import read_bytes


def test_read_bytes_reads_local_file(tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_bytes(b"hello world")
    assert read_bytes(str(target)) == b"hello world"


def test_read_bytes_http_uses_urllib(monkeypatch):
    captured: dict[str, str] = {}

    class _FakeResponse:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return self._payload

    def _fake_urlopen(url):
        captured["url"] = url
        return _FakeResponse(b"http body")

    import mountainash_utils_files.storage_facade.read_bytes as rb_mod

    monkeypatch.setattr(rb_mod.urllib.request, "urlopen", _fake_urlopen)

    assert read_bytes("http://example.com/file") == b"http body"
    assert captured["url"] == "http://example.com/file"


def test_read_bytes_https_uses_urllib(monkeypatch):
    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self) -> bytes:
            return b"https body"

    import mountainash_utils_files.storage_facade.read_bytes as rb_mod

    monkeypatch.setattr(
        rb_mod.urllib.request, "urlopen", lambda url: _FakeResponse()
    )

    assert read_bytes("https://example.com/file") == b"https body"


def test_read_bytes_unrecognised_scheme_raises():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        read_bytes("gopher://example.com/")


def test_read_bytes_describe_only_scheme_raises():
    with pytest.raises(ValueError, match="has no registered backend"):
        read_bytes("hdfs://cluster/file")


def test_read_bytes_routes_s3_through_facade(monkeypatch):
    """s3:// → StorageFacade.from_path(...).read(...) with no urllib involvement."""
    calls: list[str] = []

    class _StreamBackend:
        """Minimal backend implementing StorageReadProtocol via read_to_stream."""

        def read_to_stream(self, path: str):
            calls.append(path)
            return io.BytesIO(b"s3 body")

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, auth=None: _StreamBackend()
    )
    # _require() does an isinstance check against StorageReadProtocol; our
    # stub backend isn't registered with that protocol, so bypass the gate.
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("s3://bucket/key") == b"s3 body"
    assert calls == ["s3://bucket/key"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/storage_facade/test_read_bytes.py -v
```

Expected: `ImportError: cannot import name 'read_bytes' from 'mountainash_utils_files'`.

- [ ] **Step 3: Create the helper module**

Create `src/mountainash_utils_files/storage_facade/read_bytes.py`:

```python
"""Top-level read helper that dispatches by URL scheme.

For http/https, uses urllib directly as a temporary bridge until the HTTP
backend follow-up spec ships.
"""
from __future__ import annotations

import typing
import urllib.request

from mountainash_utils_files.path_helpers.storage_path import StoragePath
from mountainash_utils_files.storage_facade.facade import StorageFacade


def read_bytes(path: str, auth_params: typing.Any = None) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    Local paths and recognised storage schemes route through
    :meth:`StorageFacade.from_path`. ``http://`` and ``https://`` paths use
    ``urllib.request.urlopen`` directly; this branch is removed when the
    HTTP backend follow-up spec ships.

    Args:
        path: Path or URL.
        auth_params: Optional auth params forwarded to the storage facade.

    Returns:
        The full content of *path* as ``bytes``.

    Raises:
        ValueError: If the scheme is unrecognised or describes a backend that
            is not registered.
    """
    scheme = StoragePath.identify_scheme(path)
    if scheme in ("http", "https"):
        with urllib.request.urlopen(path) as response:  # noqa: S310
            return response.read()
    return StorageFacade.from_path(path, auth_params).read(path)
```

- [ ] **Step 4: Export from `storage_facade`**

Replace `src/mountainash_utils_files/storage_facade/__init__.py`:

```python
# storage_facade/__init__.py

from mountainash_utils_files.storage_facade.cross_backend import copy_between
from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_facade.read_bytes import read_bytes

__all__ = ["StorageFacade", "copy_between", "read_bytes"]
```

- [ ] **Step 5: Export from package root**

In `src/mountainash_utils_files/__init__.py`, replace the line:

```python
from .storage_facade import StorageFacade, copy_between
```

with:

```python
from .storage_facade import StorageFacade, copy_between, read_bytes
```

and extend the `__all__` list — find the line:

```python
    "StorageFacade", "copy_between", "storage",
```

and replace with:

```python
    "StorageFacade", "copy_between", "read_bytes", "storage",
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/storage_facade/test_read_bytes.py -v
```

Expected: all pass.

- [ ] **Step 7: Run full suite + lint**

```bash
hatch run test:test
hatch run ruff:check
```

Expected: both green.

- [ ] **Step 8: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/read_bytes.py \
        src/mountainash_utils_files/storage_facade/__init__.py \
        src/mountainash_utils_files/__init__.py \
        tests/storage_facade/test_read_bytes.py
git commit -m "feat(facade): add read_bytes helper with http/https urllib bridge"
```

---

## Task 7: Update CLAUDE.md with new APIs

**Files:**
- Modify: `CLAUDE.md` (Usage Examples section)

- [ ] **Step 1: Read current usage examples**

```bash
grep -n "Storage facade" CLAUDE.md
```

- [ ] **Step 2: Extend the Usage Examples section**

In `CLAUDE.md`, find the "### Storage facade (unchanged public API)" heading. Immediately below the existing `copy_between` example block, add:

````markdown
### Path-driven dispatch (Phase 5, 2026-04-18)

```python
from mountainash_utils_files import StorageFacade, read_bytes

# Facade from a path — provider inferred from the URL scheme.
facade = StorageFacade.from_path("s3://bucket/key")

# One-liner that reads bytes from any recognised scheme (including http/https
# via urllib bridge until the HTTP backend follow-up ships).
payload = read_bytes("s3://bucket/data.parquet")
html = read_bytes("https://example.com/page.html")
local = read_bytes("/tmp/local-file")
```
````

- [ ] **Step 3: Verify lint**

```bash
hatch run ruff:check
```

Expected: clean (markdown only; ruff won't touch it).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): document StorageFacade.from_path and read_bytes"
```

---

## Final verification

- [ ] **Run everything one more time**

```bash
hatch run test:test
hatch run ruff:check
git log --oneline develop..HEAD
```

Expected:
- All tests green (prior 653 + ~25 new = ~678).
- Ruff clean.
- 7 new commits on `feat/canonical-path-dispatcher`.

- [ ] **Confirm spec coverage by reviewing the Done Criteria in the spec**

Every checkbox in `docs/superpowers/specs/2026-04-18-canonical-path-dispatcher-design.md` §9 should be satisfied:

- [ ] `SchemeSpec.provider` field added (Task 1)
- [ ] 21 existing entries annotated; 5 new entries added (Task 2)
- [ ] `backend_detection.py` rewritten; `_SCHEME_TO_PROVIDER` deleted (Task 3)
- [ ] `StorageFacade.from_path` implemented + tested (Task 5)
- [ ] `read_bytes` implemented + exported + tested (Task 6)
- [ ] `tests/storage_registry/` created (Task 4)
- [ ] `tests/storage_facade/test_from_path.py` + `test_read_bytes.py` created (Tasks 5, 6)
- [ ] `hatch run test:test` green, `hatch run ruff:check` clean (final step)
- [ ] `CLAUDE.md` updated (Task 7)

Then hand off to `superpowers:finishing-a-development-branch` (push + PR to `develop`).
