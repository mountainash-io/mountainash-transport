# Canonical Path Dispatcher — Design

**Date:** 2026-04-18
**Target branch:** `feat/canonical-path-dispatcher` (from `develop`)
**Supersedes part of:** `docs/path_helpers_full_scope.md` (Concern 2)
**Follows:** `2026-04-18-path-helpers-hygiene-design.md` (merged PR #40)

## 1. Problem

After the hygiene pass landed, `path_helpers.SCHEMES` owns 21 canonical URL schemes
but carries no dispatch information. Three callers today each maintain their own
scheme-ladder to answer "what provider is this path?":

1. `storage_registry/backend_detection._SCHEME_TO_PROVIDER` — 7 entries
   (`s3`, `gs`, `az`, `sftp`, `ssh`, `r2`, `b2`). Missing `minio`, `azure_files`,
   `ftp`, `smb`, `github`, `s3express`, `nfs`.
2. `mountainash/relations/dag/readers/parquet.py:12-46` — a `_REMOTE_SCHEMES`
   tuple and an inline `_facade_read_bytes` function with a
   `startswith("s3://") / startswith("r2://") / startswith("minio://")` ladder.
3. `mountainash/relations/dag/readers/csv.py:12-49` — near-identical copy of the
   parquet reader's ladder.

These three ladders disagree (the backend_detection map doesn't know about `minio`;
the pydata readers don't know about `b2` or `ssh`). Adding a new backend means
editing three files.

## 2. Goals

1. **SCHEMES becomes the single source of truth for `scheme → provider`.**
2. **`detect_provider_from_path` becomes a thin reader over `SCHEMES`.**
3. **Callers get a path-driven facade constructor:** `StorageFacade.from_path(...)`.
4. **Callers get a one-line read helper:** `read_bytes(path, auth_params=None)`.
5. **pydata reader dedup is documented as a follow-up** (different repo; not in
   this spec's PR).
6. **HTTP/HTTPS as real schemes + read-only backend is documented as a follow-up.**

## 3. Non-Goals

- No new storage backends land in this spec. HTTP/HTTPS backend is a separate
  follow-up spec.
- No suffix-aware transform inference (that is Concern 3 — separate follow-up).
- No changes to `StorageFacade.__init__`, existing protocols, or the settings
  architecture.
- No changes to `mountainash/relations/dag/readers/*` in this PR. Those are
  listed as Follow-Up A and ship separately in the `mountainash` repo.

## 4. Component Specs

### 4.1 `SchemeSpec` extension

Add an optional `provider` field. Schemes described for registry completeness
but without a backend carry `provider=None`.

```python
# src/mountainash_utils_files/path_helpers/scheme.py

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

@dataclass(frozen=True)
class SchemeSpec:
    scheme: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    strict: bool = True
    provider: CONST_STORAGE_PROVIDER_TYPE | None = None
```

**Import-cycle verification:** `constants.py` has no project-internal imports
(it imports only `enum` and `typing`). `path_helpers` already sits above
`storage_registry` and `storage_backends` in the layering; importing
`constants` from `path_helpers/scheme.py` does not introduce a cycle.

### 4.2 `SCHEMES` annotation + new entries

Existing 21 entries annotated; 5 new entries added (`r2`, `minio`, `s3express`,
`http`, `https`) so the registry matches the full provider enum plus web
schemes pydata cares about.

| Scheme key    | Aliases    | Provider (enum)          | Notes                                   |
|---------------|------------|--------------------------|-----------------------------------------|
| `""` (bare)   | —          | `LOCAL`                  | Local path with no URL scheme           |
| `file`        | —          | `LOCAL`                  | RFC 8089 file URL                       |
| `s3`          | —          | `S3`                     | AWS + MinIO-via-s3-endpoint             |
| `s3u`         | —          | `None`                   | Rare variant; no backend                |
| `s3express`   | —          | `S3EXPRESS`              | NEW entry                               |
| `gs`          | `gcs`      | `GCS`                    |                                         |
| `azure`       | `az`       | `AZURE_BLOB`             | Callers wanting Files pass explicitly   |
| `r2`          | —          | `R2`                     | NEW entry                               |
| `minio`       | —          | `MINIO`                  | NEW entry                               |
| `b2`          | —          | `B2`                     |                                         |
| `sftp`        | —          | `SFTP`                   |                                         |
| `ssh`         | —          | `SSH`                    |                                         |
| `ftp`         | —          | `FTP`                    |                                         |
| `smb`         | —          | `SMB`                    |                                         |
| `github`      | —          | `GITHUB`                 |                                         |
| `http`        | —          | `None`                   | NEW entry; backend is Follow-Up B       |
| `https`       | —          | `None`                   | NEW entry; backend is Follow-Up B       |
| `dbfs`        | —          | `None`                   | Described only                          |
| `hdfs`        | —          | `None`                   | Described only                          |
| `webhdfs`     | —          | `None`                   | Described only                          |
| `spark`       | —          | `None`                   | Described only                          |
| `trino`       | —          | `None`                   | Described only                          |
| `gdrive`      | —          | `None`                   | Described only                          |
| `dropbox`     | —          | `None`                   | Described only                          |
| `onedrive`    | —          | `None`                   | Described only                          |
| `sharepoint`  | —          | `None`                   | Described only                          |

**Azure discriminator:** `azure://` maps to `AZURE_BLOB` by default. Callers who
need `AZURE_FILES` pass the enum to `StorageFacade(...)` directly, or supply a
hint param (out of scope for this spec). We document this as a known limitation.

**NFS:** No URL scheme entry. NFS is handled via `LocalSettings(MOUNT_SPEC=...)`
in the settings layer — there is no `nfs://foo` path form. The `NFS` enum
member exists for settings but has no scheme counterpart, and
`detect_provider_from_path` will never return it. This is correct and
intentional.

### 4.3 `detect_provider_from_path` rewrite

```python
# src/mountainash_utils_files/storage_registry/backend_detection.py

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
        ValueError: If the scheme is present but not recognised, or is a
            described-only scheme with no registered backend.
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

The 7-entry `_SCHEME_TO_PROVIDER` literal dict is deleted.

`StoragePath.identify_scheme` returns `""` for local paths (no scheme) and `None`
for truly unknown schemes. The `""` entry's provider is `LOCAL`, so local paths
fall through the normal lookup — no special casing.

### 4.4 `StorageFacade.from_path` classmethod

```python
# src/mountainash_utils_files/storage_facade/facade.py

@classmethod
def from_path(
    cls,
    path: str,
    auth_params: StorageAuthBase | None = None,
) -> "StorageFacade":
    """Construct a facade whose provider is inferred from a path's URL scheme."""
    provider = detect_provider_from_path(path)
    return cls(provider_type=provider, auth_params=auth_params)
```

Existing `__init__(provider_type, auth_params=None)` is untouched. Callers who
already know the provider continue to use `StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, ...)`.

### 4.5 `read_bytes` top-level helper

```python
# src/mountainash_utils_files/storage_facade/read_bytes.py  (new file)

from __future__ import annotations

import urllib.request

from mountainash_utils_files.path_helpers.storage_path import StoragePath
from mountainash_utils_files.settings.base import StorageAuthBase
from mountainash_utils_files.storage_facade.facade import StorageFacade


def read_bytes(path: str, auth_params: StorageAuthBase | None = None) -> bytes:
    """Read the full contents of `path` as bytes, dispatching by URL scheme.

    For `http://` and `https://` paths, this uses ``urllib.request.urlopen``
    directly. This is a temporary bridge; once the HTTP backend spec
    (Follow-Up B) ships, this branch is removed and the scheme entries gain a
    real provider.
    """
    scheme = StoragePath.identify_scheme(path)
    if scheme in ("http", "https"):
        with urllib.request.urlopen(path) as response:  # noqa: S310
            return response.read()
    return StorageFacade.from_path(path, auth_params).read(path)
```

Exported from the package root:

```python
# src/mountainash_utils_files/__init__.py
from .storage_facade import StorageFacade, copy_between, read_bytes
# __all__ += ["read_bytes"]
```

### 4.6 Public API diff

Additions (all backward-compatible):

- `path_helpers.scheme.SchemeSpec.provider` (new optional field).
- `SCHEMES` gains 5 new entries (`s3express`, `r2`, `minio`, `http`, `https`).
- `StorageFacade.from_path(path, auth_params=None)` classmethod.
- `mountainash_utils_files.read_bytes(path, auth_params=None)` function.

Behavior change (semver-minor, not a break):

- `detect_provider_from_path("minio://bucket/k")` previously raised
  `ValueError("Unknown scheme: 'minio' …")`; now returns
  `CONST_STORAGE_PROVIDER_TYPE.MINIO`. Same widening for `ftp`, `smb`,
  `github`, `s3express`, `azure`.
- `detect_provider_from_path("hdfs://…")` previously raised; still raises, but
  with a different message ("no registered backend" instead of "Unknown scheme").

No removals.

## 5. Testing

### 5.1 New tests

- `tests/path_helpers/test_scheme.py`
  - `test_every_spec_has_provider_field` — property inspection.
  - `test_known_schemes_map_to_expected_providers` — table-driven over the
    provider-populated rows.
  - `test_describe_only_schemes_have_none_provider` — table-driven over the
    `None` rows (hdfs, dbfs, webhdfs, spark, trino, gdrive, dropbox, onedrive,
    sharepoint, http, https, s3u).
  - `test_aliases_resolve_to_provider_of_canonical` — `gcs` and `az` aliases.

- `tests/storage_registry/test_backend_detection.py` (new directory)
  - Port existing behavioral tests (local path, s3://, unknown scheme).
  - `test_minio_scheme_now_resolves` — regression for the widened map.
  - `test_describe_only_scheme_raises_no_backend` — e.g. `hdfs://…`.
  - `test_unparsable_scheme_raises_unrecognised` — e.g. `not a url`.

- `tests/storage_facade/test_from_path.py` (new)
  - `test_from_path_returns_facade_with_correct_provider` — for local, s3,
    gs, azure, ftp, smb, github.
  - `test_from_path_without_auth_params` — defaults to `None`.
  - `test_from_path_raises_for_unknown_scheme`.

- `tests/storage_facade/test_read_bytes.py` (new)
  - `test_read_bytes_local_roundtrip` — `tmp_path` fixture.
  - `test_read_bytes_s3_via_moto` — matches existing s3 test pattern.
  - `test_read_bytes_http_via_urlopen_monkeypatch` — mock `urllib.request.urlopen`
    to avoid real network.
  - `test_read_bytes_https_via_urlopen_monkeypatch`.
  - `test_read_bytes_unknown_scheme_raises`.

### 5.2 Existing tests

- `tests/path_helpers/test_scheme.py` existing cases continue to pass (frozen
  dataclass, aliases, strict flag) because `provider` is additive with a
  default of `None`.
- `storage_registry` tests: none exist today (the module had no test module).
  The new directory holds the migrated behavioral tests.

### 5.3 Test commands

```bash
hatch run test:test                                         # all tests
pytest tests/path_helpers/test_scheme.py -v                 # scheme registry
pytest tests/storage_registry/test_backend_detection.py -v  # dispatcher
pytest tests/storage_facade/ -v                             # facade + read_bytes
hatch run ruff:check
```

All existing tests (653 from hygiene pass + stream transforms) must continue
to pass unchanged.

## 6. Migration

No breaking changes for in-tree callers. One external behavior change for
out-of-tree callers: `detect_provider_from_path` now accepts `minio`, `ftp`,
`smb`, `github`, `s3express`, `azure` schemes where it previously raised. This
is strictly a widening.

Downstream `mountainash/relations/dag/readers/*.py` cleanup is **Follow-Up A**,
not this spec. Those readers will switch to:

```python
from mountainash_utils_files import read_bytes

def _scan_one(path: str, kwargs: dict[str, Any]) -> pl.LazyFrame:
    if _is_remote(path):
        return pl.read_parquet(io.BytesIO(read_bytes(path)), **kwargs).lazy()
    return pl.scan_parquet(path, **kwargs)
```

and drop their local `_facade_read_bytes` and `_REMOTE_SCHEMES`.

## 7. Risks

| Risk                                   | Mitigation                                          |
|----------------------------------------|-----------------------------------------------------|
| Import cycle (scheme ↔ constants)      | Verified: `constants.py` has no project imports.    |
| Azure blob vs files ambiguity          | Default to blob; document; allow explicit override via direct `StorageFacade()` call. |
| `http`/`https` bridge becomes permanent | Explicitly documented as bridge; Follow-Up B deletes the `urlopen` branch. |
| Widened `detect_provider_from_path` surprises downstream | Behavior change documented; previously-raising calls now succeed — strictly looser. |

## 8. Follow-Up Items (not this spec)

**Follow-Up A — pydata reader dedup** (mountainash repo)
- File paths: `mountainash/relations/dag/readers/{parquet,csv,json}.py`
- Replace each `_facade_read_bytes` with `from mountainash_utils_files import read_bytes`.
- Drop `_REMOTE_SCHEMES` tuples; decide `_is_remote` based on whether
  `StoragePath.identify_scheme(path)` returns a non-empty scheme (i.e. the
  path has a URL scheme at all).
- Verify existing CSV/Parquet/JSON reader tests pass.

**Follow-Up B — HTTP/HTTPS read-only backend** (this repo)
- Add `CONST_STORAGE_PROVIDER_TYPE.HTTP` (single enum member covers both
  `http://` and `https://`; TLS is a transport detail, not a provider).
- Add `storage_backends/http/backend.py` implementing `StorageReadProtocol`
  (GET) and `StorageMetadataProtocol` (HEAD); no list/write/delete.
- Update `SCHEMES["http"].provider` and `SCHEMES["https"].provider` to
  `CONST_STORAGE_PROVIDER_TYPE.HTTP`.
- Delete the urllib branch in `read_bytes`.
- Decide fsspec vs `httpx` vs `urllib` as the implementation in its own spec.

**Follow-Up C — Suffix-aware transform inference** (Concern 3)
- Inspect `UPath(path).suffixes` to build `Pipeline(GPG, Gzip)` inverses from
  suffix chains like `.parquet.gz.gpg`. Own design conversation; own spec.

## 9. Done Criteria

- [ ] `SchemeSpec.provider` field added; 21 existing entries annotated;
      5 new entries (`s3express`, `r2`, `minio`, `http`, `https`) added.
- [ ] `storage_registry/backend_detection.py` rewritten as a thin
      `SCHEMES`-reader; `_SCHEME_TO_PROVIDER` dict deleted.
- [ ] `StorageFacade.from_path` classmethod implemented + tested.
- [ ] `read_bytes` helper implemented + exported + tested (local, s3, http mock).
- [ ] `tests/storage_registry/` directory created with migrated + new tests.
- [ ] `tests/storage_facade/` directory created with `test_from_path.py` +
      `test_read_bytes.py`.
- [ ] `hatch run test:test` all green.
- [ ] `hatch run ruff:check` clean.
- [ ] CLAUDE.md updated if any top-level export or import path changed
      (add `read_bytes` and `StorageFacade.from_path` to the usage examples).
