# HTTP/HTTPS Backend + S3 Timeout Configuration

> **Date:** 2026-05-07
> **Status:** Draft
> **Backlog ref:** `mountainash-central/01.principles/mountainash-utils-files/h.backlog/mountainash-integration-gaps.md` (Gaps 1 & 2)
> **Consumer:** mountainash core (`relations/dag/readers/`, `core/io.py` refactor)

## Motivation

The mountainash core package needs to delegate all file I/O to
`StorageFacade.from_path()` instead of maintaining hand-rolled scheme detection
and urllib fallbacks. Two gaps in mountainash-utils-files block that refactor:

1. **No HTTP/HTTPS backend** — `StorageFacade.from_path("https://...")` fails
   with a missing-provider error. The current `read_bytes()` function works
   around this with a bare `urllib.request.urlopen()` bridge.
2. **No timeout configuration on S3** — DAG execution can hang indefinitely on
   degraded S3/R2 endpoints.

This spec addresses both. They are independent features bundled in one spec
because they share a deadline (the mountainash `core/io.py` refactor).

---

## Feature 1: HTTP/HTTPS Storage Backend

### Provider constant

Add `HTTP = "http"` to `CONST_STORAGE_PROVIDER_TYPE` in `constants.py`. Both
`http://` and `https://` schemes map to this single provider — the scheme
distinction lives in the URL itself, not the backend dispatch.

### Scheme registry update

In `path_helpers/scheme.py`, update the existing `http` and `https` entries:

```python
"http":  SchemeSpec(scheme="http",  provider=CONST_STORAGE_PROVIDER_TYPE.HTTP),
"https": SchemeSpec(scheme="https", provider=CONST_STORAGE_PROVIDER_TYPE.HTTP),
```

### Dependency

`httpx` is added as a **core dependency** (not an optional extra). It is
lightweight (~3 transitive deps) and HTTP is ubiquitous enough that gating it
behind an extra adds friction for little benefit.

### HTTPSettings (`settings/providers/http_settings.py`)

Follows the descriptor-driven pattern (Phase 4).

**HTTP_DESCRIPTOR fields:**

| ParameterSpec name | Type | Default | Driver key | Notes |
|--------------------|------|---------|------------|-------|
| `TIMEOUT_CONNECT` | `float` | `10.0` | — | Seconds; maps to `httpx.Timeout.connect` |
| `TIMEOUT_READ` | `float` | `30.0` | — | Seconds; maps to `httpx.Timeout.read` |
| `TIMEOUT_WRITE` | `float` | `60.0` | — | Seconds; maps to `httpx.Timeout.write` |
| `FOLLOW_REDIRECTS` | `bool` | `True` | — | httpx redirect following |
| `MAX_REDIRECTS` | `int` | `10` | — | Redirect limit |
| `VERIFY_SSL` | `bool` | `True` | — | TLS certificate verification |
| `HEADERS` | `dict[str, str]` | `{}` | — | Custom request headers merged with auth |

**Full descriptor:**

```python
HTTP_DESCRIPTOR = StorageDescriptor(
    name="http",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.HTTP,
    sdk_package="httpx",
    handler_module="mountainash_utils_files.storage_backends.http",
    handler_class="HTTPStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="TIMEOUT_CONNECT",
            type=float,
            tier="core",
            default=10.0,
            description="Connect timeout in seconds.",
        ),
        ParameterSpec(
            name="TIMEOUT_READ",
            type=float,
            tier="core",
            default=30.0,
            description="Read timeout in seconds.",
        ),
        ParameterSpec(
            name="TIMEOUT_WRITE",
            type=float,
            tier="advanced",
            default=60.0,
            description="Write timeout in seconds (for PUT requests).",
        ),
        ParameterSpec(
            name="FOLLOW_REDIRECTS",
            type=bool,
            tier="advanced",
            default=True,
            description="Whether to follow HTTP redirects.",
        ),
        ParameterSpec(
            name="MAX_REDIRECTS",
            type=int,
            tier="advanced",
            default=10,
            description="Maximum number of redirects to follow.",
        ),
        ParameterSpec(
            name="VERIFY_SSL",
            type=bool,
            tier="advanced",
            default=True,
            description="Whether to verify TLS certificates.",
        ),
        ParameterSpec(
            name="HEADERS",
            type=dict,
            tier="advanced",
            default=None,
            description="Custom request headers merged with auth headers.",
        ),
    ],
    auth_modes=[NoAuth, TokenAuth, PasswordAuth],
)
```

**Auth header resolution:**

- `TokenAuth` → `Authorization: Bearer <token>`
- `PasswordAuth` → `Authorization: Basic <base64(username:password)>`
- `NoAuth` → no auth header

### HTTP adapter (`settings/adapters/http.py`)

`build_handler_kwargs(profile: StorageProfile) -> dict[str, Any]`

Returns a dict consumed by the backend constructor:

```python
{
    "timeout": httpx.Timeout(
        connect=profile.TIMEOUT_CONNECT,
        read=profile.TIMEOUT_READ,
        write=profile.TIMEOUT_WRITE,
        pool=5.0,
    ),
    "follow_redirects": profile.FOLLOW_REDIRECTS,
    "max_redirects": profile.MAX_REDIRECTS,
    "verify": profile.VERIFY_SSL,
    "headers": {**profile.HEADERS, **auth_headers},
}
```

Auth header resolution follows the pattern in the S3 adapter (`_unwrap_secret`
for `SecretStr` values).

### HTTP backend (`storage_backends/http/__init__.py`)

**Implements:**

| Protocol | Methods | HTTP verb |
|----------|---------|-----------|
| `StorageReadProtocol` | `read_to_bytes(path)` | `GET` |
| | `read_to_stream(path)` | `GET` (streaming) |
| `StorageWriteProtocol` | `write_from_bytes(path, data)` | `PUT` |
| | `write_from_stream(path, stream)` | `PUT` (streaming) |
| `StorageMetadataProtocol` | `path_exists(path)` | `HEAD` (2xx→True, 404→False) |
| | `get_metadata(path)` | `HEAD` → `FileMetadata` from headers |
| | `get_size(path)` | `Content-Length` from `HEAD` |

**Does NOT implement:** `StorageListProtocol`, `StorageDeleteProtocol`,
`StorageCopyProtocol`, `StorageDirectoryProtocol`, `StorageConnectionProtocol`.

These could be added later for WebDAV or REST API use cases, but are not needed
for the mountainash DAG reader refactor.

**Client lifecycle:** httpx client is created lazily on first use and reused for
the backend instance's lifetime. No explicit `StorageConnectionProtocol` — HTTP
is stateless.

**Error mapping:**

| HTTP status | Behaviour |
|-------------|-----------|
| 2xx | Success |
| 404 | `path_exists` returns `False`; read/write raise `StorageError` |
| 401/403 | Raise `StorageError` with auth context |
| 4xx/5xx | Raise `StorageError` with status code and reason |
| Timeout | Raise `StorageError` wrapping `httpx.TimeoutException` |
| Connection error | Raise `StorageError` wrapping `httpx.ConnectError` |

**Streaming reads:** `read_to_stream` returns a `BinaryIO`-compatible wrapper
around `httpx.Response.stream()`. The response is not fully buffered in memory.

**Streaming writes:** `write_from_stream` passes the stream directly to
`httpx.Client.put(content=stream)`. httpx supports iterable/file-like content
natively. When the stream has a known length (via `seek`/`tell` or a `len`
attribute), httpx sets `Content-Length` automatically; otherwise it uses
chunked transfer encoding.

### `read_bytes()` cleanup

Once the HTTP backend is registered, the urllib bridge in
`storage_facade/read_bytes.py` (lines 61–67) is removed. The `urllib.request`
import is also removed. All schemes route through `StorageFacade.from_path()`
uniformly — the function collapses to a single dispatch path.

### Backend registration

In `storage_backends/http/__init__.py`:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend(...):
    ...
```

In `storage_backends/__init__.py`, add the import trigger:

```python
from mountainash_utils_files.storage_backends import http  # noqa: F401
```

---

## Feature 2: S3 Timeout Configuration

### New ParameterSpec entries in S3_DESCRIPTOR

| ParameterSpec name | Type | Default | Driver key | Notes |
|--------------------|------|---------|------------|-------|
| `CONNECT_TIMEOUT` | `float \| None` | `None` | — | Seconds. `None` = boto3 default (~60s) |
| `READ_TIMEOUT` | `float \| None` | `None` | — | Seconds. `None` = boto3 default (~60s) |

The `ParameterSpec` type is `Optional[float]` (not bare `float`) so that both
omitted values and explicit `None` / `null` in config files pass validation and
fall through to boto3 defaults. These map to
`botocore.config.Config(connect_timeout=..., read_timeout=...)`.

### Adapter change (`settings/adapters/s3.py`)

In `build_handler_kwargs()`, the existing `Config(s3=s3_config)` construction
(currently line 143) is expanded to include timeout values:

```python
config_kwargs: dict[str, Any] = {"s3": s3_config}
connect_timeout = getattr(profile, "CONNECT_TIMEOUT", None)
read_timeout = getattr(profile, "READ_TIMEOUT", None)
if connect_timeout is not None:
    config_kwargs["connect_timeout"] = connect_timeout
if read_timeout is not None:
    config_kwargs["read_timeout"] = read_timeout
base["config"] = _botocore_config.Config(**config_kwargs)
```

### Backward compatibility

Fully backward-compatible. Existing callers that omit `CONNECT_TIMEOUT` /
`READ_TIMEOUT` get boto3's defaults (unchanged). The fields default to `None`,
which means "don't override."

### Usage example

```python
from mountainash_utils_files.settings.providers import S3Settings
from mountainash_settings.auth import IAMAuth

s3 = S3Settings(
    FLAVOR="aws",
    REGION="ap-southeast-2",
    BUCKET="data-lake",
    CONNECT_TIMEOUT=5.0,
    READ_TIMEOUT=30.0,
    auth=IAMAuth(access_key_id="AKIA...", secret_access_key="..."),
)
kwargs = s3.to_handler_kwargs()
# kwargs["config"].connect_timeout == 5.0
# kwargs["config"].read_timeout == 30.0
```

---

## Testing Strategy

### HTTP backend tests

- **Unit tests** (`tests/backends/test_http.py`): Mock httpx responses using
  `httpx.MockTransport`. Test read/write/metadata/exists for success cases and
  error mapping (404, 401, 5xx, timeout).
- **Settings tests** (`tests/test_unit/settings/providers/test_http_settings.py`):
  Descriptor validation, adapter kwargs building, auth header resolution for
  each auth type.
- **Protocol conformance** (`tests/protocol_alignment/`): Verify
  `HTTPStorageBackend` satisfies `StorageReadProtocol`,
  `StorageWriteProtocol`, and `StorageMetadataProtocol`.
- **Integration with `read_bytes()`**: Verify that HTTP URLs now route through
  the facade instead of the urllib bridge. Existing `test_read_bytes.py` tests
  that monkeypatch urllib are replaced with httpx mock transport tests.
- **Scheme registry tests** (`tests/path_helpers/test_scheme.py`): Verify
  `http` and `https` resolve to `CONST_STORAGE_PROVIDER_TYPE.HTTP`.

### S3 timeout tests

- **Settings tests** (`tests/test_unit/settings/providers/test_s3_settings.py`):
  Verify `CONNECT_TIMEOUT` and `READ_TIMEOUT` appear in built kwargs.
- **Adapter tests**: Verify `botocore.config.Config` receives timeout values
  when set, and omits them when `None`.

---

## Files Changed

### New files

| File | Purpose |
|------|---------|
| `src/mountainash_utils_files/storage_backends/http/__init__.py` | HTTP backend |
| `src/mountainash_utils_files/settings/providers/http_settings.py` | HTTPSettings + descriptor |
| `src/mountainash_utils_files/settings/adapters/http.py` | httpx kwargs builder |
| `tests/backends/test_http.py` | Backend unit tests |
| `tests/test_unit/settings/providers/test_http_settings.py` | Settings tests |

### Modified files

| File | Change |
|------|--------|
| `constants.py` | Add `HTTP = "http"` to `CONST_STORAGE_PROVIDER_TYPE` |
| `path_helpers/scheme.py` | Set `provider=...HTTP` on http/https entries |
| `storage_backends/__init__.py` | Import trigger for http backend |
| `storage_facade/read_bytes.py` | Remove urllib bridge; uniform facade dispatch |
| `settings/providers/s3_settings.py` | Add `CONNECT_TIMEOUT`, `READ_TIMEOUT` ParameterSpecs |
| `settings/adapters/s3.py` | Propagate timeouts to `botocore.config.Config` |
| `__init__.py` | Export `HTTPSettings` if following existing pattern |
| `pyproject.toml` | Add `httpx` to core dependencies |
| `tests/storage_facade/test_read_bytes.py` | Replace urllib mocks with httpx mock transport |
| `tests/test_unit/settings/providers/test_s3_settings.py` | Add timeout field tests |

---

## Out of Scope

- **Gaps 3–5** from the backlog (consumer-side changes in mountainash core) —
  these land alongside or after the mountainash `core/io.py` refactor spec.
- **HTTP List/Delete/Copy/Directory protocols** — can be added later for
  WebDAV or REST API use cases.
- **Async HTTP** — httpx supports async, but the current facade API is sync.
  Async support is a broader architectural change across all backends.
- **HTTP retry logic** — httpx has retry via `httpx.HTTPTransport(retries=N)`.
  Not included in initial scope; can be added as a setting later.
