# Facade-Level Suffix Inference

> **Date:** 2026-05-07
> **Status:** Draft
> **Backlog ref:** `mountainash-central/01.principles/mountainash-utils-files/h.backlog/mountainash-integration-gaps.md` (Gap 4)
> **Consumer:** mountainash core (`core/io.py` refactor)

## Motivation

The mountainash DAG readers need to read compressed resources (`.csv.gz`,
`.parquet.gz.gpg`) through `StorageFacade`. Today suffix-driven transform
inference lives only on the top-level `read_bytes()` helper. Callers who use
the facade directly — including `StorageFacade.from_path().read(path)` — must
manually call `infer_pipeline()` and pass the pipeline. This is friction that
pushes consumers toward `read_bytes()` when they'd prefer the facade's richer
API (streams, metadata, exists checks).

This spec moves the `infer` capability into the facade's `read()` and
`read_stream()` methods, so consumers can write:

```python
facade = StorageFacade.from_path(path, auth_params)
data = facade.read(path, infer=True, gpg=GPG(gnupghome="..."))
```

## Design Decisions

### Default stays `False`

The existing principle (`suffix-inference-is-opt-in-and-read-only.md`) is
preserved. `infer` defaults to `False` on both `read()` and `read_stream()`.
Existing callers are byte-for-byte unchanged. The rationale in the principle
doc (backward compat, explicit-over-implicit, GPG key material) all still
apply.

### `infer=True` + `pipeline=` is a `ValueError`

If a caller passes both `infer=True` and an explicit `pipeline`, the facade
raises `ValueError("Cannot pass both infer=True and an explicit pipeline")`.
The two mechanisms are mutually exclusive — silently picking one would be
surprising.

### Stripped path via existing `infer_pipeline()`

The consumer (mountainash core) needs the stripped path for format detection
(e.g. `data.parquet` from `data.parquet.gz`). This is already available from
`infer_pipeline(path)` which returns `(Pipeline | None, stripped_path)`. No
new API is needed — the consumer calls `infer_pipeline()` for format detection,
then passes the pipeline to `facade.read()`.

### `read_bytes()` delegates to facade

After this change, `read_bytes()` simplifies to:

```python
def read_bytes(path, *, auth_params=None, infer=False, gpg=None, gzip=None):
    facade = StorageFacade.from_path(path, auth_params)
    return facade.read(path, infer=infer, gpg=gpg, gzip=gzip)
```

The inference logic moves out of `read_bytes` and into the facade. The
function remains the canonical one-liner entry point.

---

## API Changes

### `StorageFacade.read()`

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
```

Behavior:
- `infer=False` (default): unchanged — uses explicit `pipeline` or no
  transforms.
- `infer=True, pipeline=None`: calls `infer_pipeline(path, gpg=gpg,
  gzip=gzip)` and applies the resulting pipeline. If inference produces
  `None` (no known suffixes), reads raw.
- `infer=True, pipeline=<something>`: raises `ValueError`.

### `StorageFacade.read_stream()`

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
```

Same conflict check and inference logic as `read()`.

### `read_bytes()`

Signature unchanged. Internal implementation delegates to
`facade.read(path, infer=infer, gpg=gpg, gzip=gzip)`.

### Write methods

**No changes.** `write()` and `write_stream()` do not gain `infer`. The
write-side rationale in the principle doc (double-compression footgun) still
applies.

---

## Implementation

### Inference in the facade

The facade gains a new import (`from mountainash_utils_files.path_helpers.suffixes
import infer_pipeline`) and a private helper that resolves the effective pipeline:

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
    if infer and pipeline is not None:
        raise ValueError(
            "Cannot pass both infer=True and an explicit pipeline"
        )
    if infer:
        inferred, _ = infer_pipeline(path, gpg=gpg, gzip=gzip)
        if inferred is not None:
            return inferred
    return self._coerce_pipeline(pipeline)
```

`read()` and `read_stream()` call `_resolve_pipeline()` instead of
`_coerce_pipeline()` directly.

### `read_bytes()` simplification

The body reduces to:

```python
facade = StorageFacade.from_path(path, auth_params)
return facade.read(path, infer=infer, gpg=gpg, gzip=gzip)
```

The `_apply_pipeline_to_bytes` helper and the manual `infer_pipeline` call
are removed (these were already removed when the urllib bridge was deleted —
what remains is just the delegation pattern).

---

## Testing Strategy

### Facade inference tests (`tests/facade/test_facade_infer.py`)

- `test_read_infer_false_returns_raw_bytes` — `.gz` file, `infer=False`,
  returns compressed bytes.
- `test_read_infer_true_decompresses_gz` — `.gz` file, `infer=True`,
  returns decompressed bytes.
- `test_read_infer_true_no_known_suffix_returns_raw` — `.parquet` file,
  `infer=True`, returns raw bytes (no transform).
- `test_read_infer_true_with_pipeline_raises` — `infer=True` and
  `pipeline=Gzip()` raises `ValueError`.
- `test_read_stream_infer_true_decompresses_gz` — same as read but via
  `read_stream()`, verify stream yields decompressed bytes.
- `test_read_stream_infer_true_with_pipeline_raises` — same conflict check.
- `test_read_infer_gpg_suffix_without_gpg_raises` — `.gpg` suffix without
  `gpg=` raises `ValueError` (from `infer_pipeline`).

### `read_bytes` delegation tests

- Verify `read_bytes(path, infer=True)` still works (delegates to facade).
- Verify existing `test_read_bytes.py` and `test_read_bytes_infer.py` still
  pass unchanged.

---

## Files Changed

### Modified files

| File | Change |
|------|--------|
| `src/mountainash_utils_files/storage_facade/facade.py` | Add `_resolve_pipeline()`, add `infer`/`gpg`/`gzip` kwargs to `read()` and `read_stream()` |
| `src/mountainash_utils_files/storage_facade/read_bytes.py` | Simplify to delegate `infer` to facade |

### New files

| File | Purpose |
|------|---------|
| `tests/facade/test_facade_infer.py` | Facade-level inference tests |

### Docs to update

| File | Change |
|------|--------|
| `mountainash-central/.../suffix-inference-is-opt-in-and-read-only.md` | Update "Future Considerations" — facade-level inference is no longer deferred |
| `mountainash-central/.../mountainash-integration-gaps.md` | Update Gap 4 — utils-files side resolved |

---

## Out of Scope

- **Default `infer=True`** — the principle is preserved; default stays `False`.
- **Write-side inference** — still explicitly ruled out per the principle.
- **New suffixes (`.bz2`, `.zst`, `.xz`)** — deferred until `StreamTransform`
  classes exist.
- **Magic-byte sniffing** — content-based detection remains out of scope.
- **`copy_between` with inference** — cross-backend copy doesn't gain `infer`.
