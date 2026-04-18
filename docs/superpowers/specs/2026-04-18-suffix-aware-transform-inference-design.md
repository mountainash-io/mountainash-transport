# Suffix-Aware Transform Inference — Design

**Status:** approved 2026-04-18
**Predecessors:** PR #40 (hygiene — `feat/path-helpers-hygiene`), PR #41 (canonical dispatcher — `feat/canonical-path-dispatcher`), PR #39 (stream transforms — `feat/stream-transforms`)
**Scope source:** `docs/path_helpers_full_scope.md`, Concern 3

## 1. Problem

A path's suffix chain already encodes the layering applied to the underlying bytes:

```
data.parquet.gz.gpg   ==   gpg(gzip(parquet))
```

The stream transforms delivered in PR #39 (`Pipeline`, `Gzip`, `GPG`) can strip those layers when handed the right `Pipeline` instance, but nothing today derives a `Pipeline` from the path. Callers must hand-construct:

```python
pipeline = Pipeline(GPG(...), Gzip())
raw = facade.read(path, pipeline=pipeline)
```

This is mechanical, easy to get wrong (GPG and Gzip swapped produces garbage), and duplicated across any downstream caller that wants encrypted-compressed data. The user story — "read an encrypted-compressed parquet file into a dataframe" — requires exactly one useful operation: `infer the pipeline from the suffix chain`.

## 2. Goals / Non-goals

**Goals:**
- Derive a `Pipeline` from the suffix chain of a path string, deterministically.
- Expose that inference as a pure, testable function.
- Wire it into `read_bytes` as a single opt-in keyword (`infer=True`), because `read_bytes` is the one-liner entry point established by the canonical-dispatcher spec.
- Preserve current default behaviour bit-for-bit: `read_bytes("x.gz")` without `infer=True` still returns the raw gzipped bytes.

**Non-goals:**
- Write-side inference (`write_bytes("x.gz", data)` does NOT auto-compress). Too easy a footgun — a user who names a file `.gz` but passes already-compressed bytes would double-encode. Deferred.
- Facade-level `read(..., infer=True)` / `read_stream(..., infer=True)`. The facade already accepts an explicit `pipeline=`; duplicating inference at the facade level is redundant. Can be added later if a concrete call site emerges.
- Extending the suffix map beyond `.gz`/`.gzip`/`.gpg`/`.asc`/`.pgp`. Other compression formats (`.bz2`, `.zst`, `.xz`, `.lz4`) don't have transform classes today; when one is added, the map entry is one line.
- Pydata reader dedup in the `mountainash` repo. Tracked as a separate follow-up (roadmap Follow-Up A).

## 3. Design

### 3.1 Suffix map

A single module-level `dict[str, str]` maps known lowercase suffix tokens to a *kind* string (not a `StreamTransform` class — the class is supplied at call time so the caller controls construction parameters, particularly GPG key material).

```python
# src/mountainash_utils_files/path_helpers/suffixes.py

SUFFIX_TRANSFORMS: dict[str, str] = {
    ".gz":   "gzip",
    ".gzip": "gzip",
    ".gpg":  "gpg",
    ".asc":  "gpg",
    ".pgp":  "gpg",
}
```

Rationale for the `kind` indirection: a `".gz"` suffix uniquely identifies the Gzip transform and requires no configuration, so `infer_pipeline` can default-construct `Gzip()`. A `".gpg"` suffix identifies the GPG transform but the caller MUST supply key material (gnupghome, recipients or passphrase). Encoding suffix→kind rather than suffix→class lets the parser detect the need for a GPG instance without holding a reference to a factory.

### 3.2 `infer_pipeline` — the public function

```python
def infer_pipeline(
    path: str,
    *,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> tuple[Pipeline | None, str]:
    """Parse the suffix chain of *path* right-to-left into a Pipeline.

    Stops at the first suffix not in SUFFIX_TRANSFORMS. Comparison on
    the suffix is case-insensitive.

    Args:
        path: Any path-like string (local, s3://..., etc). Only the
            suffix portion is inspected — no scheme validation.
        gpg: Required if the suffix chain contains any of {".gpg",
            ".asc", ".pgp"}. Supplies key material.
        gzip: Optional; defaults to Gzip() when a gzip suffix is seen.

    Returns:
        (pipeline, stripped_path):
          - pipeline is None when no known suffixes were found.
          - stripped_path is *path* with every stripped suffix removed,
            preserving the scheme and everything up to the first unknown
            suffix.

    Raises:
        ValueError: A gpg-family suffix was found but gpg is None.
    """
```

**Parsing algorithm:**

1. Split `path` into `(stem, suffix)` using `pathlib.PurePosixPath`-style rules (last `.` in the final segment). Do not split on `.` inside directory components.
2. Lowercase the suffix and look it up in `SUFFIX_TRANSFORMS`.
3. If unknown, stop — current stem is the stripped path, accumulated transforms are the pipeline.
4. If known, map `kind → StreamTransform instance`:
   - `"gzip"` → `gzip` if supplied, else `Gzip()`.
   - `"gpg"` → `gpg` if supplied, else raise `ValueError`.
5. Append the instance to the outer-to-inner list, set `path = stem`, loop.

**Pipeline order:** Right-most suffix is the outermost layer. Walking right-to-left yields the list in outermost-first order, matching `Pipeline.__init__`'s contract (`storage_transforms/pipeline.py:10-22`).

```
data.parquet.gz.gpg  →  parse .gpg, parse .gz, stop at .parquet
                    →  [GPG, Gzip]
                    →  Pipeline(GPG, Gzip)
                    →  stripped = "data.parquet"
```

**Empty chain:** `(None, path)`. `read_bytes` treats this as "nothing to strip, plain read".

**Repeated suffixes:** `data.gz.gz` → `Pipeline(Gzip(), Gzip())`. Unusual but handled by the loop without special-casing.

**Scheme in path:** Suffix parsing only inspects the final segment; `s3://bucket/x.gz` parses as expected. No scheme-aware logic needed.

### 3.3 `read_bytes` wiring

```python
def read_bytes(
    path: str,
    *,
    auth_params: Any = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    scheme = StoragePath.identify_scheme(path)

    if scheme in ("http", "https"):
        raw = _http_get(path)                       # existing urllib bridge, extracted
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

`_apply_pipeline_to_bytes` is a small helper that wraps `io.BytesIO(raw)`, calls `pipeline.apply_read`, and reads the result. It lives in `read_bytes.py` (private). No public helper function for this — it's only needed on the http bridge because that branch doesn't go through the facade.

`_stripped` is intentionally unused in `read_bytes` — stored bytes sit at the full path — but `infer_pipeline` still returns it as part of the public API for callers who want to know the logical filename (e.g. to pick a parquet vs csv reader based on `.parquet` vs `.csv` in the stripped name).

### 3.4 Public API diff

```python
# mountainash_utils_files/__init__.py  (additions to __all__)
+ "infer_pipeline",

# mountainash_utils_files.path_helpers  (new export)
+ from .suffixes import infer_pipeline, SUFFIX_TRANSFORMS

# mountainash_utils_files.storage_facade.read_bytes  (signature change)
- def read_bytes(path, auth_params=None) -> bytes: ...
+ def read_bytes(path, *, auth_params=None, infer=False, gpg=None, gzip=None) -> bytes: ...
```

Positional-argument callers are unaffected — `path` remains positional; `auth_params` was previously positional-or-keyword and is now keyword-only. Current in-tree callers all pass `auth_params` by keyword or not at all, so the tightening is safe. External callers (downstream packages) passing `auth_params` positionally will get a `TypeError` — acceptable because (a) the signature is new (merged hours ago in PR #41) and (b) the fix is trivial.

## 4. Error model

| Condition | Behaviour |
|---|---|
| Suffix chain has no known suffixes | Return `(None, path)`. `read_bytes` falls through to plain read. |
| `.gpg`/`.asc`/`.pgp` seen, `gpg is None` | `ValueError("path 'X' has a .gpg suffix; pass gpg=GPG(...) to infer")` |
| `.gz`/`.gzip` seen, `gzip is None` | Default-construct `Gzip()`. No error. |
| Unknown suffix mid-chain (`data.txt.gz`) | Stop parsing at `.txt`. Returns `Pipeline(Gzip())` + `"data.txt"`. No error — the loop simply halts. |
| `infer=True`, no known suffixes | Pipeline is None; `read_bytes` delegates to plain `facade.read`. |
| `infer=False` with `gpg=` or `gzip=` supplied | Kwargs ignored silently. (Rationale: permits passing a `gpg=` param conditionally without having to also toggle `infer`.) |

## 5. Testing plan

### 5.1 Pure-function tests — `tests/path_helpers/test_suffixes.py`

Table-driven coverage of `infer_pipeline`:

| Input path | gpg | gzip | Expected pipeline | Expected stripped |
|---|---|---|---|---|
| `"data.parquet"` | None | None | None | `"data.parquet"` |
| `"data.gz"` | None | None | `Pipeline(Gzip())` | `"data"` |
| `"data.gzip"` | None | None | `Pipeline(Gzip())` | `"data"` |
| `"data.GZ"` (upper) | None | None | `Pipeline(Gzip())` | `"data"` |
| `"data.gz.gz"` | None | None | `Pipeline(Gzip(), Gzip())` | `"data"` |
| `"data.gpg"` | `GPG(...)` | None | `Pipeline(GPG(...))` | `"data"` |
| `"data.asc"` | `GPG(...)` | None | `Pipeline(GPG(...))` | `"data"` |
| `"data.pgp"` | `GPG(...)` | None | `Pipeline(GPG(...))` | `"data"` |
| `"data.parquet.gz.gpg"` | `GPG(...)` | None | `Pipeline(GPG(...), Gzip())` | `"data.parquet"` |
| `"s3://bucket/path/to/data.parquet.gz"` | None | None | `Pipeline(Gzip())` | `"s3://bucket/path/to/data.parquet"` |
| `"data.txt.gz"` | None | None | `Pipeline(Gzip())` | `"data.txt"` (stops at .txt) |
| `"data.gpg"` | None | None | raises ValueError | — |

Assertions on the pipeline check:
- `isinstance(p, Pipeline)`
- The internal `_outer_to_inner` tuple length and per-position `type(...)` (exact types, not behaviour — behaviour is covered by the transforms' own tests).

### 5.2 Integration tests — `tests/storage_facade/test_read_bytes_infer.py`

Local-filesystem-only (no network):

1. `read_bytes("/tmp/x.gz", infer=True)` round-trips gzipped bytes written by the test fixture.
2. `read_bytes("/tmp/x.gz", infer=False)` returns raw gzipped bytes (current behaviour preserved).
3. `read_bytes("/tmp/x", infer=True)` — no suffix, delegates to plain read, returns bytes unchanged.
4. `read_bytes("/tmp/x.gz", infer=True, gzip=Gzip(level=9))` — custom instance threaded through.
5. `read_bytes("/tmp/x.gpg", infer=True, gpg=GPG(...))` — `@pytest.mark.integration`, uses throwaway keyring fixture already established by the stream-transforms tests.
6. `read_bytes("/tmp/x.gpg", infer=True)` (no gpg=) → `ValueError` propagated from `infer_pipeline`.
7. `read_bytes("/tmp/x.gz.gpg", infer=True, gpg=GPG(...))` (`@pytest.mark.integration`) — round-trip a gzip-then-gpg encoded file.

### 5.3 Regression

Existing `read_bytes` tests (`tests/storage_facade/test_read_bytes.py`) remain valid — default `infer=False` preserves all current behaviour. Add no new assertions to that file; the new file covers the new surface.

## 6. Migration

None. All additions are additive and opt-in:
- New module: `path_helpers/suffixes.py`.
- New keyword-only args on `read_bytes`, all defaulting to off/None.
- No existing behaviour changes.

Downstream callers in the `mountainash` repo can adopt on their own schedule — likely as part of pydata reader dedup (Follow-Up A on the roadmap).

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| User passes `infer=True` on a `.gz` file that isn't actually gzipped | `gzip.GzipFile` raises `BadGzipFile` on read — error surfaces naturally. No custom handling needed. |
| Suffix map grows unbounded | Explicit module-level constant + type annotation; any addition is visible in review. |
| GPG key material ergonomics (caller has to construct `GPG(...)` with correct gnupghome/passphrase) | By design — suffix can't encode key material, and hiding it behind env vars or global config would make tests brittle and failures cryptic. |
| Someone wants inference on `facade.read` | Deferred to follow-up (§8-A). `read_bytes` covers the one-liner case. |
| Write-side confusion (user expects `write_bytes("x.gz", raw)` to compress) | Documented in `read_bytes` docstring and CLAUDE.md usage example — writes are explicit. Named `infer` (not `auto`) to underline the direction. |

## 8. Follow-ups

- **A. Facade-level inference.** `StorageFacade.read(..., infer=True)` and `read_stream(..., infer=True)`. Low-urgency — `read_bytes` is the canonical entry point.
- **B. Write-side inference.** `write_bytes("x.gz", data, infer=True)` auto-compresses. Deferred until a concrete user story emerges. Must include strong opt-in and clear error when bytes appear to already be encoded (heuristic: magic-bytes check).
- **C. Additional suffixes.** `.bz2`, `.zst`, `.xz`, `.lz4`. Add when the corresponding `StreamTransform` classes exist. One-line map additions per suffix.
- **D. Pydata reader dedup** (already on the path_helpers roadmap). Replace the per-reader scheme ladders with `read_bytes(path, infer=True, gpg=...)` + in-memory parquet parse.

## 9. Done criteria

- `infer_pipeline` exported from `mountainash_utils_files.path_helpers` and top-level package.
- `read_bytes(path, infer=True, gpg=..., gzip=...)` routes through `infer_pipeline` and the facade's existing `pipeline=` parameter.
- Default `infer=False` preserves current `read_bytes` behaviour byte-for-byte (regression tests unchanged).
- All tests in §5 pass under `hatch run test:test`.
- `hatch run ruff:check` clean.
- Documentation in CLAUDE.md updated with a usage example under "Stream Transforms".
- No new runtime dependency added; `[encryption]` extra still gates GPG.
