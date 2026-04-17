# path_helpers hygiene pass — design

**Status:** draft → approved 2026-04-18
**Scope:** Concern 1 (hygiene) only. Concerns 2 (facade/pydata wiring) and 3 (suffix-driven transform inference) are out of scope.

## 1. Problem statement

`src/mountainash_utils_files/path_helpers/` is a thin wrapper over `universal-pathlib.UPath` that has accumulated:

- Real bugs that only don't fire because no code reaches them.
- Duplicated methods across sibling subclasses.
- A scheme-to-provider coupling that doesn't hold (`s3://` is served by five different providers).
- A custom wildcard matcher that reimplements `fnmatch`.
- Silent `print()` warnings on unknown input.

None of the package's load-bearing code (facade, backends, transforms) consults `path_helpers`. External callers are the package's own `__init__.py` re-export, two test files, and `deprecated/` modules in `mountainash-utils-gpg`. That gives us a free hand: the module can be rewritten in-place without a compatibility shim.

The hygiene pass removes the bugs, drops the string-hacking, collapses the six near-identical subclasses into one helper driven by a scheme-metadata table, and restates the module's job as: parse paths, not route providers.

## 2. Goals & non-goals

**Goals**
- Delete every bug listed in §5.
- One entry-point class (`StoragePath`) + a scheme table (`SCHEMES`) + a small S3-specific module.
- `identify_scheme` returns a URL-scheme token, not a provider; callers own scheme→provider mapping.
- Every behavior has a test; every bug has a regression test.
- Remove silent `print()`-based diagnostics.

**Non-goals**
- Wiring `StoragePath` into `storage_facade`, `storage_registry`, or the `mountainash.pydata` readers. Those call sites keep their current ad-hoc `startswith("s3://")` ladders; replacing them is a separate spec.
- Suffix-driven transform inference (e.g. `data.parquet.gz.gpg` → `Pipeline(GPG, Gzip)`).
- Windows drive-letter local-path detection.
- Adding a provider resolver on top of `identify_scheme`.
- Deprecation windows or compatibility shims — there are no external consumers.

## 3. Package layout

```
src/mountainash_utils_files/path_helpers/
├── __init__.py        # exports: StoragePath, SchemeSpec, SCHEMES, s3
├── scheme.py          # SchemeSpec, SCHEMES, _ALIAS_TO_CANONICAL
├── storage_path.py    # StoragePath class
└── s3.py              # s3_bucket(), s3_key() free functions
```

Deleted files:
- `base_path_helper.py`, `path_helper.py`
- `local_path_helper.py`, `az_path_helper.py`, `gcs_path_helper.py`
- `sftp_path_helper.py`, `ssh_path_helper.py`, `s3_path_helper.py`

## 4. Components

### 4.1 `scheme.py` — canonical scheme registry

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SchemeSpec:
    scheme: str                    # canonical scheme token, lowercase
    aliases: tuple[str, ...] = ()  # alt prefixes that resolve to this scheme
    strict: bool = True            # if True, mixed-case rejected by normalize()

SCHEMES: dict[str, SchemeSpec] = {
    "":         SchemeSpec(scheme="",       strict=False),  # bare local
    "file":     SchemeSpec(scheme="file"),
    "s3":       SchemeSpec(scheme="s3"),
    "s3u":      SchemeSpec(scheme="s3u"),
    "gs":       SchemeSpec(scheme="gs",    aliases=("gcs",)),
    "azure":    SchemeSpec(scheme="azure", aliases=("az",)),
    "sftp":     SchemeSpec(scheme="sftp"),
    "ftp":      SchemeSpec(scheme="ftp"),
    "ssh":      SchemeSpec(scheme="ssh"),
    "smb":      SchemeSpec(scheme="smb"),
    "b2":       SchemeSpec(scheme="b2"),
    "github":   SchemeSpec(scheme="github"),
    "dbfs":     SchemeSpec(scheme="dbfs"),
    "hdfs":     SchemeSpec(scheme="hdfs"),
    "webhdfs":  SchemeSpec(scheme="webhdfs"),
    "spark":    SchemeSpec(scheme="spark"),
    "trino":    SchemeSpec(scheme="trino"),
    "gdrive":   SchemeSpec(scheme="gdrive"),
    "dropbox":  SchemeSpec(scheme="dropbox"),
    "onedrive": SchemeSpec(scheme="onedrive"),
    "sharepoint": SchemeSpec(scheme="sharepoint"),
}

# Built at import time from SCHEMES.
_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: spec.scheme for spec in SCHEMES.values() for alias in spec.aliases
}
```

Rules:
- Entries in `SCHEMES` do **not** imply a backend exists for the scheme. `identify_scheme("dbfs://x")` returns `"dbfs"` even though no `DBFS` backend is implemented. Registry-vs-backend is decoupled from path parsing.
- Aliases are asymmetric: `"gcs"` resolves to `"gs"` in `identify_scheme`, but `normalize("gcs://x")` rewrites to `"gs://x"`.
- Unknown schemes (e.g. `nonsense://x`) are not added here and are rejected by `normalize`.

### 4.2 `storage_path.py` — `StoragePath`

Single class, classmethods only. No `__init__`. Wraps `upath.UPath` with a thin parsing/normalising layer.

```python
class StoragePath:
    @classmethod
    def identify_scheme(cls, path: str | UPath | None) -> str | None:
        """Return the canonical scheme token from SCHEMES, or None.

        - "" for bare/relative/home paths with no URL scheme.
        - Canonical scheme for known schemes (aliases resolved).
        - None for unrecognised schemes (e.g. "nonsense://x").
        Case-insensitive — forgiving on input.
        """

    @classmethod
    def normalize(cls, path: str | UPath | None) -> UPath | None:
        """Normalise and validate a path.

        Returns None if path is None or empty.
        Raises ValueError on:
        - unknown scheme
        - mixed-case scheme (e.g. "S3://x") when the SchemeSpec is strict=True
        - malformed URL (e.g. "s3:bucket" — missing "//")
        """

    @classmethod
    def join(cls, path: str | UPath | None, name: str | None) -> UPath | None:
        """Return `normalize(path) / stripped(name)`, or None if either is falsy."""

    @classmethod
    def to_str(cls, path: str | UPath | None) -> str | None:
        """`None` passthrough, else `str(path)`. No normalisation."""

    @classmethod
    def matches(cls, pattern: str, name: str) -> bool:
        """`fnmatch.fnmatch(name, pattern)`. No regex reimplementation."""
```

Implementation notes:

- `identify_scheme` uses `urlparse(str(path)).scheme.lower()`, then consults `SCHEMES` / `_ALIAS_TO_CANONICAL`. Paths with no scheme (`/foo`, `~`, `randomfile.txt`) return `""`.
- `normalize` rebuilds schemed URLs via `urlunparse` — no string slicing, no `.replace()` tricks. For bare paths it uses `UPath(...).expanduser()`.
- Trailing slash is stripped **unless** the path is exactly `scheme://` or `/`.
- `normalize` distinguishes three failure modes: `None` (null input), `ValueError` (invalid input), `UPath` (valid).

### 4.3 `s3.py` — S3-specific extractors

Two free functions, nothing else:

```python
def s3_bucket(path: str | UPath | None) -> str | None:
    """Return the bucket name from `s3://bucket/key/...`, or None if not S3."""

def s3_key(path: str | UPath | None) -> str | None:
    """Return the object key (path after bucket, no leading slash), or None."""
```

Both delegate to `StoragePath.normalize` first; both return `None` (not raise) if the scheme isn't `s3`.

### 4.4 `__init__.py`

```python
from . import s3
from .scheme import SCHEMES, SchemeSpec
from .storage_path import StoragePath

__all__ = ("StoragePath", "SchemeSpec", "SCHEMES", "s3")
```

The top-level `mountainash_utils_files.__init__` re-export changes from `PathHelper` to `StoragePath`.

## 5. Bugs fixed (each gets a regression test)

1. **`base_path_helper.py:178` — `str.replace(..., __count=1)` is a `TypeError`.**
   `str.replace` takes positional `count`; `__count` isn't a kwarg, and the result isn't assigned back. Dead on arrival. Replaced with `urlunparse` rebuild.

2. **`_normalize_path_schema` silent fall-through to `None`.**
   The "already good" branch after a `.replace()` has no `return`, so valid uppercase scheme input quietly returns `None` instead of the normalised string. New `normalize` has explicit returns on every branch.

3. **`S3PathHelper.format_namespace` ignores extracted bucket.**
   When called with `path=<s3-url>` and `bucket_name=None`, the method extracts a bucket via `get_path_bucketname(u_path)` but the final `f"s3://{str_bucket_name}" if bucket_name else "s3://"` keys on the original (falsy) arg. Deleted — callers use `s3_bucket(path)` directly.

4. **`PathHelper.path_util_classes` keys on legacy strings.**
   Uses `"LOCAL_DISK"`, `"AZ"` etc. that don't match `CONST_STORAGE_PROVIDER_TYPE`. Whole dispatcher deleted; scheme-driven logic lives in `StoragePath`.

5. **`identify_storage_system` returns keys with no matching helper.**
   Returns `"B2"`, `"FTP"`, `"GITHUB"` for their schemes, but no subclass is registered for those keys in `path_util_classes`, so `_get_util_class` raises `ValueError`. Eliminated — one class, one code path.

6. **`combine_path_and_filename` duplicated verbatim.**
   The base implementation is copy-pasted into `GCSPathHelper` and `SSHPathHelper` with no behavioral difference. Collapsed into one method.

7. **Silent `print` on unknown scheme.**
   `base_path_helper.py:142` prints a diagnostic and assumes `"LOCAL_DISK"`. New `identify_scheme` returns `None`; `normalize` raises `ValueError`. No print statements.

## 6. Case-handling contract

- `identify_scheme("SSH://host/p")` → `"ssh"` (forgiving: urlparse lowercases).
- `normalize("SSH://host/p")` → raises `ValueError` (strict: canonical form is lowercase).
- `normalize("GCS://x")` → raises `ValueError` (aliases are lowercase too).
- `normalize("gcs://x")` → `UPath("gs://x")` (alias resolved to canonical).

The two methods diverge deliberately: identify is tolerant; normalize is the gatekeeper.

## 7. Testing

New test tree:
```
tests/path_helpers/
├── __init__.py
├── test_scheme.py
├── test_storage_path.py
└── test_s3.py
```

- `test_scheme.py`: every entry in `SCHEMES` has a lowercase canonical; aliases don't collide; `_ALIAS_TO_CANONICAL` covers every alias exactly once.
- `test_storage_path.py`: parametrised happy-path + error-path for every scheme, every alias, every bare/relative/home form. Bugs 1–7 each become a named regression test (e.g. `test_bug_1_replace_count_kwarg_rejected`).
- `test_s3.py`: `s3_bucket`/`s3_key` across `s3://b`, `s3://b/k`, `s3://b/k/nested/file.parquet`, `None`, and a non-S3 path.

Deleted: `tests/test_path_utils.py` (superseded).

Updated: `tests/test_public_api.py:32–33` — `test_path_helper_importable` renamed to `test_storage_path_importable`, asserts `StoragePath` imports.

## 8. Removals

Files deleted:
- `src/mountainash_utils_files/path_helpers/base_path_helper.py`
- `src/mountainash_utils_files/path_helpers/path_helper.py`
- `src/mountainash_utils_files/path_helpers/local_path_helper.py`
- `src/mountainash_utils_files/path_helpers/az_path_helper.py`
- `src/mountainash_utils_files/path_helpers/gcs_path_helper.py`
- `src/mountainash_utils_files/path_helpers/sftp_path_helper.py`
- `src/mountainash_utils_files/path_helpers/ssh_path_helper.py`
- `src/mountainash_utils_files/path_helpers/s3_path_helper.py`
- `tests/test_path_utils.py`
- `docs/recommendations/path_helpers_consistency_analysis.md` (superseded)

Exports removed from `mountainash_utils_files/__init__.py`:
`PathHelper`, `BasePathHelper`, `LocalPathHelper`, `AZPathHelper`, `GCSPathHelper`, `S3PathHelper`, `SFTPPathHelper`, `SSHPathHelper`.

Export added to `mountainash_utils_files/__init__.py`: `StoragePath`.

## 9. Migration

None. The module has no external consumers (verified by grep: only `tests/test_path_utils.py`, `tests/test_public_api.py`, and re-export in `__init__.py` inside this package; a single import in `mountainash-utils-gpg/.../deprecated/` which is not load-bearing). Land in one PR.

Docs:
- Update `CLAUDE.md` Package Structure tree.
- Delete `docs/recommendations/path_helpers_consistency_analysis.md`.

## 10. Risks

- **Unknown scheme handling diverges.** Old: silent print + `LOCAL_DISK` fallback. New: `None` or `ValueError`. If there's undocumented code somewhere that relied on the silent fallback, it will now surface. Mitigation: grep confirms no such caller; the change is an improvement.
- **Mixed-case scheme rejection.** Old: `identify_storage_system("SSH://…")` returned `"SSH"` (accepted). New: `identify_scheme` still returns `"ssh"`, but `normalize` rejects mixed-case. Callers that passed raw user input through `normalize` will need to lowercase the scheme first. Mitigation: there are no such callers today.

## 11. Done criteria

- All eight per-scheme files deleted; `StoragePath`, `scheme.py`, `s3.py` present.
- `hatch run test:test` green, including new `tests/path_helpers/` suite.
- `hatch run ruff:check` clean.
- No `print()` calls in `path_helpers/`.
- `grep -R "PathHelper\b" src/` returns nothing; `grep -R "StoragePath\b" src/` returns the new module + the top-level re-export.
- `CLAUDE.md` Package Structure tree updated.
