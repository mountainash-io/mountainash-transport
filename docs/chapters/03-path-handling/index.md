---
title: "Chapter 3: Path Handling"
description: "How the library represents, normalizes, and resolves storage paths across URL schemes"
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 3: Path Handling

## Summary

This chapter covers how mountainash-transport represents and resolves storage
paths across different URL schemes. It introduces the StoragePath class,
SchemeSpec dataclass, and the SCHEMES registry that maps scheme strings to their
specifications. Readers learn about alias resolution, scheme identification, path
normalization, the GenericSchemePath fallback, path joining, UPath integration,
and how the library detects which storage provider a given path targets.

## Concepts Covered

- StoragePath Class
- SchemeSpec Dataclass
- SCHEMES Registry
- Alias Resolution
- Identify Scheme Method
- Normalize Method
- GenericSchemePath Fallback
- Path Joining
- UPath Integration
- Detect Provider From Path

## Learning Graph IDs

31, 32, 33, 34, 35, 36, 37, 38, 39, 40

## Prerequisites

- Chapter 1: Foundation Concepts (URL Schemes, Decorators, Registry Pattern)

---

## The Challenge of Multi-Scheme Paths

A storage abstraction library must handle paths from radically different systems. A local file path like `/data/reports/q1.csv` follows POSIX conventions. An S3 object key looks like `s3://my-bucket/data/reports/q1.csv`. An HTTP URL has `https://cdn.example.com/data/reports/q1.csv`. Each follows different parsing rules, casing conventions, and normalization requirements.

The mountainash-transport path handling layer solves this by establishing a canonical representation for every supported URL scheme. It parses raw path strings, resolves aliases, normalizes formatting, and maps the result to the correct storage provider -- all through a stateless utility class that performs no I/O and has no side effects.

<!-- concept:32 -->
## SchemeSpec Dataclass

Before understanding how paths are parsed, you need to understand how the library describes its supported schemes. A **SchemeSpec** is a frozen dataclass that captures the metadata for a single URL scheme:

```python
@dataclass(frozen=True)
class SchemeSpec:
    scheme: str
    aliases: tuple[str, ...] = ()
    strict: bool = True
    provider: CONST_STORAGE_PROVIDER_TYPE | None = None
```

Each `SchemeSpec` carries four pieces of information. The `scheme` field holds the canonical lowercase token (e.g., `"s3"`, `"gs"`, `"file"`). The `aliases` tuple lists alternative tokens that resolve to this canonical scheme -- for example, `"gcs"` is an alias for `"gs"`. The `strict` flag controls whether mixed-case scheme input is rejected. The `provider` field maps the scheme to a `CONST_STORAGE_PROVIDER_TYPE` enum member, or `None` for schemes with no registered backend.

The frozen nature of the dataclass ensures that scheme specifications are immutable after creation. This matters because scheme metadata is shared across all path operations and must not be accidentally modified.

| Field | Type | Purpose | Example |
|---|---|---|---|
| `scheme` | `str` | Canonical lowercase token | `"s3"` |
| `aliases` | `tuple[str, ...]` | Alternative tokens | `("gcs",)` for `gs` |
| `strict` | `bool` | Reject mixed-case input | `True` for all except bare paths |
| `provider` | `enum \| None` | Target backend | `CONST_STORAGE_PROVIDER_TYPE.S3` |

The `strict` flag deserves special attention. Most schemes enforce strict casing -- `S3://bucket/key` is rejected because the scheme portion must be lowercase `s3://`. The only exception is the bare-local entry (empty-string scheme), which uses `strict=False` because local paths have no scheme prefix to validate.

<!-- concept:33 -->
## SCHEMES Registry

The **SCHEMES registry** is a module-level dictionary that maps canonical scheme strings to their `SchemeSpec` instances. It serves as the single source of truth for which URL schemes the library recognizes:

```python
SCHEMES: dict[str, SchemeSpec] = {
    "":           SchemeSpec(scheme="",      strict=False, provider=LOCAL),
    "file":       SchemeSpec(scheme="file",  provider=LOCAL),
    "s3":         SchemeSpec(scheme="s3",    provider=S3),
    "s3express":  SchemeSpec(scheme="s3express", provider=S3EXPRESS),
    "gs":         SchemeSpec(scheme="gs",    aliases=("gcs",), provider=GCS),
    "azure":      SchemeSpec(scheme="azure", aliases=("az",),  provider=AZURE_BLOB),
    "r2":         SchemeSpec(scheme="r2",    provider=R2),
    "minio":      SchemeSpec(scheme="minio", provider=MINIO),
    "http":       SchemeSpec(scheme="http",  provider=HTTP),
    "https":      SchemeSpec(scheme="https", provider=HTTP),
    # ... plus sftp, ssh, ftp, smb, github, b2,
    #     dbfs, hdfs, webhdfs, spark, trino,
    #     gdrive, dropbox, onedrive, sharepoint
}
```

The registry currently contains 25 entries. Some entries have a `provider` mapping (meaning a backend exists or will exist), while others have `provider=None` (registered for path-parsing completeness). For example, `"hdfs"` and `"dbfs"` are recognized by the path parser but have no backend implementation -- attempting to construct a `StorageFacade` for them raises a `ValueError`.

An important design decision is that the SCHEMES registry is **decoupled** from the backend registry. Path parsing and scheme recognition happen independently of whether a working backend exists. This separation allows the path layer to normalize any recognized URL without needing the corresponding backend module to be installed.

<!-- concept:34 -->
## Alias Resolution

**Alias resolution** is the process of mapping alternative scheme tokens to their canonical form. The library maintains a reverse-lookup dictionary built automatically from the `aliases` tuples in each `SchemeSpec`:

```python
_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: spec.scheme
    for spec in SCHEMES.values()
    for alias in spec.aliases
}
# Result: {"gcs": "gs", "az": "azure"}
```

When the path parser encounters `gcs://bucket/data.csv`, it looks up `"gcs"` in `_ALIAS_TO_CANONICAL`, finds `"gs"`, and proceeds using the canonical scheme. This ensures that `gs://bucket/data.csv` and `gcs://bucket/data.csv` resolve to identical normalized paths and the same storage provider.

Aliases must also be lowercase when strict casing is enabled. The casing check compares the literal prefix from the input against the canonical scheme *and* all known aliases, rejecting anything that does not match in lowercase form.

<!-- concept:31 -->
## StoragePath Class

The **StoragePath** class is a stateless utility (all methods are `@classmethod`) that provides the public API for path operations. It does not store path state and is never instantiated -- you call its methods directly on the class:

```python
scheme = StoragePath.identify_scheme("s3://bucket/key")   # "s3"
normalized = StoragePath.normalize("s3://bucket/key/")     # UPath("s3://bucket/key")
joined = StoragePath.join("s3://bucket", "key/file.csv")   # UPath("s3://bucket/key/file.csv")
```

The classmethod-only design avoids the need to create throwaway instances and makes the API feel like a collection of pure functions. Each method accepts a path (as `str`, `UPath`, or `None`) and returns a result without side effects.

#### Diagram: StoragePath Method Pipeline

<iframe src="../../sims/storage-path-pipeline/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>StoragePath Method Pipeline</summary>
Type: workflow
**sim-id:** storage-path-pipeline<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Show how a raw path string flows through StoragePath methods: identify_scheme -> normalize -> join, with branching for alias resolution and error paths.

**Components:**

- Input node: raw path string (editable)
- identify_scheme node with output showing canonical scheme
- normalize node with strict-casing and URL-form checks
- join node for appending segments
- Error paths: ValueError for unknown scheme, mixed-case, malformed URL
- Output node: normalized UPath or GenericSchemePath

**Interactions:** Type a custom path in the input node and watch it flow through the pipeline. Click error paths to see example inputs that trigger them.

**Learning Objective:** Trace the path normalization pipeline from raw input to canonical output (Bloom: Apply)
</details>

<!-- concept:35 -->
## Identify Scheme Method

The **`identify_scheme`** method extracts and canonicalizes the URL scheme from a path string. It uses Python's `urlparse` to extract the raw scheme, converts it to lowercase, checks the SCHEMES registry, resolves any aliases, and returns the canonical scheme token.

The method handles several edge cases:

- `None` or empty string returns `""` (bare/local scheme).
- A path with no scheme (e.g., `/data/file.csv`) returns `""`.
- A recognized scheme (e.g., `"s3"` from `s3://bucket/key`) returns that scheme.
- An alias (e.g., `"gcs"` from `gcs://bucket/key`) returns the canonical form (`"gs"`).
- An unrecognized scheme returns `None` (not a `KeyError`), signaling that the path's scheme is outside the library's vocabulary.

The `None` vs `""` distinction is intentional. An empty string means "local path, no scheme prefix." `None` means "this scheme is not registered at all." Callers use this distinction to decide whether a path is local, known-remote, or completely unrecognized.

<!-- concept:36 -->
## Normalize Method

The **`normalize`** method is the workhorse of the path layer. It takes a raw path string and returns a clean, canonical path object suitable for further operations. The normalization process differs depending on whether the path has a scheme prefix.

For **bare (local) paths** without a scheme, normalization strips trailing slashes (except for root `/`), expands `~` to the home directory, and wraps the result in a `UPath` object. For example, `~/data/reports/` becomes `UPath("/home/user/data/reports")`.

For **schemed paths**, normalization performs several validation and cleanup steps:

1. **Strict casing check**: if the `SchemeSpec` has `strict=True`, the method rejects mixed-case scheme prefixes like `S3://` or `Http://`.
2. **URL form check**: the method rejects `scheme:path` without the double slash -- `s3:bucket/key` is ambiguous and must be written as `s3://bucket/key`.
3. **Alias resolution**: the scheme is resolved to its canonical form.
4. **Trailing slash removal**: the path portion is stripped of trailing slashes (except for root paths).
5. **Reconstruction**: the URL is rebuilt using `urlunparse` with the canonical scheme, preserving the netloc, query, and fragment components.

The return type is a union: `UPath` for schemes that fsspec supports, or `_GenericSchemePath` (a string subclass) for schemes that UPath cannot construct.

```python
# Returns UPath for supported schemes
StoragePath.normalize("s3://bucket/key")    # UPath("s3://bucket/key")
StoragePath.normalize("/data/file.csv")     # UPath("/data/file.csv")

# Returns _GenericSchemePath for unsupported schemes
StoragePath.normalize("azure://container/blob")  # _GenericSchemePath("azure://container/blob")
```

<!-- concept:37 -->
## GenericSchemePath Fallback

**`_GenericSchemePath`** is a string subclass that acts as a fallback when `UPath` cannot handle a particular scheme. UPath relies on fsspec for filesystem implementations, and fsspec does not support every scheme in the library's registry (e.g., `azure://`, `b2://`, `smb://`).

Rather than failing on these schemes, the normalize method catches UPath's `ValueError` and wraps the canonical URL in a `_GenericSchemePath`. This string subclass preserves the URL for display and comparison while also supporting path joining via the `/` operator:

```python
class _GenericSchemePath(str):
    def __truediv__(self, name: str) -> _GenericSchemePath:
        base = str(self).rstrip("/")
        clean = name.strip("/\\")
        return _GenericSchemePath(f"{base}/{clean}")
```

This means `StoragePath.join("azure://container", "path/to/blob")` works correctly even though UPath cannot construct an Azure path. The result is a `_GenericSchemePath` that stringifies to `"azure://container/path/to/blob"` and can be passed to any function expecting a string.

The fallback is transparent to callers because both `UPath` and `_GenericSchemePath` support `str()` conversion and the `/` operator. Callers should treat the result of `normalize()` as "path-like via `str()`" rather than assuming a specific type.

<!-- concept:38 -->
## Path Joining

The **`join`** method combines a base path with a relative name segment. It normalizes the base path, strips leading and trailing slashes from the name, and uses the `/` operator to concatenate them:

```python
StoragePath.join("s3://bucket", "data/file.csv")
# -> UPath("s3://bucket/data/file.csv")

StoragePath.join("/local/dir", "subdir/file.txt")
# -> UPath("/local/dir/subdir/file.txt")

StoragePath.join("azure://container", "path/to/blob")
# -> _GenericSchemePath("azure://container/path/to/blob")
```

The method returns `None` in several safety cases: if either argument is `None`, if the name is empty after stripping, or if the base path fails normalization. This prevents accidental construction of malformed paths from missing data.

The StoragePath class also provides a `matches` method that performs wildcard matching using Python's `fnmatch` module, supporting `*` and `?` patterns. While not strictly a joining operation, it complements path manipulation by enabling pattern-based file filtering.

!!! note "Path Joining vs String Concatenation"
    Never construct storage paths by string concatenation (`base + "/" + name`). Use `StoragePath.join()` to ensure proper normalization, slash handling, and scheme preservation. String concatenation can produce double-slashes, missing scheme components, or platform-specific path separator issues.

<!-- concept:39 -->
## UPath Integration

**UPath** (Universal Path) from the `upath` package extends Python's `pathlib.PurePosixPath` to work with fsspec-backed filesystems. When you construct `UPath("s3://bucket/key")`, you get a path object that understands S3 semantics -- its `.name`, `.parent`, `.suffix`, and other `pathlib` properties work correctly across schemes.

The mountainash-transport library integrates UPath at the normalization layer. For schemes that fsspec supports (S3, GCS, local files, and others), `normalize()` returns a `UPath` instance, giving callers access to the full `pathlib` API:

```python
path = StoragePath.normalize("s3://bucket/data/report.csv.gz")
path.name      # "report.csv.gz"
path.suffix    # ".gz"
path.parent    # UPath("s3://bucket/data")
path.stem      # "report.csv"
```

For schemes that fsspec does not support, the library falls back to `_GenericSchemePath` (described above). This dual-return strategy ensures that path operations never fail due to missing fsspec implementations while still providing rich path semantics when available.

The integration is deliberately shallow -- UPath is used for path *parsing* and *manipulation*, not for I/O. The library does not call `UPath.read_bytes()` or `UPath.write_text()`; all actual I/O flows through the backend protocols and the StorageFacade.

#### Diagram: Path Normalization Decision Tree

<iframe src="../../sims/path-normalization-tree/main.html" width="100%" height="500px" scrolling="no"></iframe>
<details markdown="1">
<summary>Path Normalization Decision Tree</summary>
Type: diagram
**sim-id:** path-normalization-tree<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Interactive decision tree showing the branching logic inside StoragePath.normalize() -- from raw input through scheme identification, casing checks, URL form validation, and output type selection (UPath vs GenericSchemePath).

**Components:**

- Root: "Raw path input"
- Decision nodes: "Has scheme?", "Scheme in SCHEMES?", "Strict casing?", "Case valid?", "URL has ://?", "UPath supports scheme?"
- Leaf nodes: UPath (local), UPath (schemed), GenericSchemePath, ValueError (various)
- Color: green for success paths, red for error paths, blue for decision nodes

**Interactions:** Click any decision node to expand its details. Hover over leaf nodes to see example inputs that reach that outcome. Click "Run Example" to trace a specific path through the tree.

**Learning Objective:** Trace the branching logic of path normalization (Bloom: Analyze)
</details>

<!-- concept:40 -->
## Detect Provider From Path

The **`detect_provider_from_path`** function is the bridge between the path layer and the backend layer. Given a raw path string, it returns the `CONST_STORAGE_PROVIDER_TYPE` enum member that identifies which storage backend should handle that path.

The function performs two lookups in sequence. First, it calls `StoragePath.identify_scheme()` to extract the canonical scheme. Then it looks up the scheme in `SCHEMES` and reads the `provider` field from the corresponding `SchemeSpec`. The function raises `ValueError` in two cases: when the scheme is unrecognized (`identify_scheme` returns `None`) and when the scheme is registered but has no backend (`provider` is `None`).

```python
detect_provider_from_path("s3://bucket/key")       # CONST_STORAGE_PROVIDER_TYPE.S3
detect_provider_from_path("/local/file.txt")        # CONST_STORAGE_PROVIDER_TYPE.LOCAL
detect_provider_from_path("https://example.com/f")  # CONST_STORAGE_PROVIDER_TYPE.HTTP
detect_provider_from_path("hdfs://cluster/path")    # ValueError (no backend)
```

This function is the core of the `StorageFacade.from_path()` factory method, which constructs a facade from a path string without requiring the caller to know the provider type in advance. The full resolution chain is:

1. Raw path string (e.g., `"gcs://bucket/data.csv"`)
2. `identify_scheme()` resolves alias to canonical scheme (`"gs"`)
3. `SCHEMES["gs"]` returns `SchemeSpec(provider=CONST_STORAGE_PROVIDER_TYPE.GCS)`
4. Backend registry lookup for `GCS` returns the appropriate backend class
5. `StorageFacade` wraps the instantiated backend

#### Diagram: Full Path Resolution Chain

<iframe src="../../sims/path-resolution-chain/main.html" width="100%" height="450px" scrolling="no"></iframe>
<details markdown="1">
<summary>Full Path Resolution Chain</summary>
Type: workflow
**sim-id:** path-resolution-chain<br/>
**Library:** vis-network<br/>
**Status:** Specified

**Purpose:** Animate the complete chain from raw path input through scheme identification, alias resolution, SCHEMES lookup, provider extraction, and backend registry lookup.

**Components:**

- Linear flow of 6 nodes representing each stage
- Animated data packet showing the value being transformed at each stage (path string -> scheme token -> canonical scheme -> SchemeSpec -> provider enum -> backend class)
- Side panel showing the intermediate value at the currently highlighted stage
- Multiple example paths to cycle through

**Interactions:** Click play to animate the resolution chain. Use prev/next buttons to step through stages. Select different example paths from a dropdown to see how different schemes resolve.

**Learning Objective:** Trace the full resolution from path string to backend instance (Bloom: Apply)
</details>

## Error Handling in Path Operations

The path layer raises `ValueError` for three categories of invalid input, each with a descriptive message:

- **Unknown scheme**: `StoragePath.normalize("xyz://path")` raises `ValueError: Unknown scheme in path: 'xyz://path'` when the scheme is not in `SCHEMES` and not a known alias.
- **Mixed-case scheme**: `StoragePath.normalize("S3://bucket/key")` raises `ValueError: mixed-case scheme not accepted: 'S3' (expected lowercase canonical 's3')` for strict schemes.
- **Malformed URL**: `StoragePath.normalize("s3:bucket/key")` raises `ValueError: malformed URL -- missing '//' after scheme: 's3:bucket/key'`.

These are all caught at the normalization stage, before any backend interaction occurs. This fail-fast design ensures that invalid paths never reach the storage layer, where errors would be harder to diagnose.

## Key Takeaways

- **StoragePath** is a stateless utility class (all `@classmethod` methods) that parses, normalizes, and joins paths without performing I/O.
- **SchemeSpec** is a frozen dataclass that stores metadata about a URL scheme: its canonical name, aliases, casing strictness, and target provider.
- The **SCHEMES registry** maps 25 scheme strings to their specifications, decoupled from whether a backend implementation exists.
- **Alias resolution** maps alternative tokens (like `gcs://`) to canonical schemes (like `gs://`) through an automatically-built reverse-lookup dictionary.
- The **`identify_scheme`** method returns `""` for local paths, the canonical scheme string for recognized URLs, and `None` for unknown schemes.
- The **`normalize`** method validates casing and URL form, resolves aliases, strips trailing slashes, and returns either a `UPath` or a `_GenericSchemePath`.
- **`_GenericSchemePath`** is a string subclass fallback for schemes that UPath/fsspec cannot handle, supporting the `/` operator for path joining.
- **UPath integration** provides rich `pathlib`-style path semantics for fsspec-supported schemes without performing any I/O.
- **`detect_provider_from_path`** bridges the path layer to the backend layer by resolving a path string to a `CONST_STORAGE_PROVIDER_TYPE` enum member.
- The path layer follows a **fail-fast** strategy, raising `ValueError` with descriptive messages for unknown schemes, mixed casing, and malformed URLs before any backend interaction.
