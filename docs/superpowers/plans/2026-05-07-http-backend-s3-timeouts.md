# HTTP/HTTPS Backend + S3 Timeout Configuration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an httpx-based HTTP/HTTPS storage backend (read + write + metadata) and surface timeout configuration on the S3 backend, unblocking uniform `StorageFacade.from_path()` dispatch for the mountainash core refactor.

**Architecture:** Two independent features. Feature 1 adds `HTTP` provider constant, scheme registry wiring, HTTPSettings descriptor, httpx adapter, and HTTPStorageBackend implementing Read/Write/Metadata protocols. Feature 2 adds `CONNECT_TIMEOUT` and `READ_TIMEOUT` ParameterSpecs to the S3 descriptor and propagates them through the S3 adapter to `botocore.config.Config`. Both features are fully backward-compatible.

**Tech Stack:** httpx (core dep), botocore.config.Config, existing descriptor-driven settings framework.

**Spec:** `docs/superpowers/specs/2026-05-07-http-backend-s3-timeouts-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|----------------|
| `src/mountainash_utils_files/settings/providers/http_settings.py` | HTTP_DESCRIPTOR + HTTPSettings class + lazy adapter wrapper |
| `src/mountainash_utils_files/settings/adapters/http.py` | `build_handler_kwargs()` → httpx client kwargs dict |
| `src/mountainash_utils_files/storage_backends/http/__init__.py` | HTTPStorageBackend (Read + Write + Metadata protocols) |
| `tests/test_unit/settings/providers/test_http_settings.py` | Descriptor, settings, adapter kwargs tests |
| `tests/backends/test_http.py` | Backend protocol tests with httpx MockTransport |

### Modified files

| File | Change |
|------|--------|
| `src/mountainash_utils_files/constants.py` | Add `HTTP = "http"` to `CONST_STORAGE_PROVIDER_TYPE` |
| `src/mountainash_utils_files/path_helpers/scheme.py` | Set `provider=CONST_STORAGE_PROVIDER_TYPE.HTTP` on http/https entries |
| `src/mountainash_utils_files/storage_backends/__init__.py` | Add `from . import http` import trigger |
| `src/mountainash_utils_files/settings/providers/__init__.py` | Export `HTTP_DESCRIPTOR`, `HTTPSettings` |
| `src/mountainash_utils_files/storage_facade/read_bytes.py` | Remove urllib bridge; all schemes through facade |
| `src/mountainash_utils_files/settings/providers/s3_settings.py` | Add `CONNECT_TIMEOUT`, `READ_TIMEOUT` ParameterSpecs |
| `src/mountainash_utils_files/settings/adapters/s3.py` | Propagate timeouts to `botocore.config.Config` |
| `pyproject.toml` | Add `httpx>=0.27` to core dependencies |
| `tests/path_helpers/test_scheme.py` | Move http/https from describe-only to expected-providers |
| `tests/storage_facade/test_read_bytes.py` | Replace urllib mocks with httpx MockTransport |
| `tests/test_unit/settings/providers/test_s3_settings.py` | Add timeout kwargs tests |

---

## Task 1: Add HTTP provider constant and scheme wiring

**Files:**
- Modify: `src/mountainash_utils_files/constants.py:50` (after `R2 = "r2"`)
- Modify: `src/mountainash_utils_files/path_helpers/scheme.py:50-51` (http/https entries)
- Modify: `tests/path_helpers/test_scheme.py:81-101`

- [ ] **Step 1: Write failing tests — http/https schemes resolve to HTTP provider**

In `tests/path_helpers/test_scheme.py`, move `"http"` and `"https"` from
`_DESCRIBE_ONLY_SCHEMES` to `_EXPECTED_PROVIDERS`:

```python
# In _EXPECTED_PROVIDERS, add these two lines:
    "http":      CONST_STORAGE_PROVIDER_TYPE.HTTP,
    "https":     CONST_STORAGE_PROVIDER_TYPE.HTTP,

# In _DESCRIBE_ONLY_SCHEMES, remove "http" and "https" from the tuple:
_DESCRIBE_ONLY_SCHEMES: tuple[str, ...] = (
    "s3u", "dbfs", "hdfs", "webhdfs", "spark", "trino",
    "gdrive", "dropbox", "onedrive", "sharepoint",
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/path_helpers/test_scheme.py -v -k "test_known_schemes_map_to_expected_providers or test_describe_only_schemes_have_none_provider"`
Expected: `AttributeError: 'HTTP'` — the constant doesn't exist yet.

- [ ] **Step 3: Add HTTP to CONST_STORAGE_PROVIDER_TYPE**

In `src/mountainash_utils_files/constants.py`, add after line 50 (`R2 = "r2"`):

```python
    HTTP = "http"
```

- [ ] **Step 4: Wire http/https schemes to the HTTP provider**

In `src/mountainash_utils_files/path_helpers/scheme.py`, replace lines 50–51:

```python
    "http":       SchemeSpec(scheme="http",  provider=CONST_STORAGE_PROVIDER_TYPE.HTTP),
    "https":      SchemeSpec(scheme="https", provider=CONST_STORAGE_PROVIDER_TYPE.HTTP),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/path_helpers/test_scheme.py -v`
Expected: All pass, including the relocated http/https assertions.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/constants.py \
        src/mountainash_utils_files/path_helpers/scheme.py \
        tests/path_helpers/test_scheme.py
git commit -m "feat(http): add HTTP provider constant and wire http/https schemes"
```

---

## Task 2: Add httpx core dependency

**Files:**
- Modify: `pyproject.toml:25-46`

- [ ] **Step 1: Add httpx to core dependencies**

In `pyproject.toml`, add to the `dependencies` list (after the `xsdata` entry):

```toml
    "httpx>=0.27",
```

- [ ] **Step 2: Install the updated dependencies**

Run: `uv pip install -e ".[all]"`
Expected: httpx installed alongside existing deps.

- [ ] **Step 3: Verify httpx is importable**

Run: `python -c "import httpx; print(httpx.__version__)"`
Expected: Prints version >= 0.27.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add httpx as core dependency for HTTP storage backend"
```

---

## Task 3: HTTPSettings descriptor and adapter

**Files:**
- Create: `src/mountainash_utils_files/settings/providers/http_settings.py`
- Create: `src/mountainash_utils_files/settings/adapters/http.py`
- Modify: `src/mountainash_utils_files/settings/providers/__init__.py`
- Create: `tests/test_unit/settings/providers/test_http_settings.py`

- [ ] **Step 1: Write failing tests for HTTPSettings**

Create `tests/test_unit/settings/providers/test_http_settings.py`:

```python
"""Tests for HTTPSettings — HTTP/HTTPS provider settings."""
from __future__ import annotations

import pytest

from mountainash_settings.auth import NoAuth, PasswordAuth, TokenAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


def _make(**overrides):
    """Return an HTTPSettings with minimal required fields."""
    from mountainash_utils_files.settings.providers.http_settings import HTTPSettings

    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.HTTP,
        "auth": NoAuth(),
    }
    kwargs.update(overrides)
    return HTTPSettings(**kwargs)


@pytest.mark.unit
class TestHTTPSettingsConstruction:
    def test_defaults(self):
        s = _make()
        assert s.TIMEOUT_CONNECT == 10.0
        assert s.TIMEOUT_READ == 30.0
        assert s.TIMEOUT_WRITE == 60.0
        assert s.FOLLOW_REDIRECTS is True
        assert s.MAX_REDIRECTS == 10
        assert s.VERIFY_SSL is True

    def test_custom_timeouts(self):
        s = _make(TIMEOUT_CONNECT=5.0, TIMEOUT_READ=15.0, TIMEOUT_WRITE=120.0)
        assert s.TIMEOUT_CONNECT == 5.0
        assert s.TIMEOUT_READ == 15.0
        assert s.TIMEOUT_WRITE == 120.0

    def test_custom_headers_none_default(self):
        s = _make()
        assert s.HEADERS is None


@pytest.mark.unit
class TestHTTPDescriptor:
    def test_descriptor_name(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_DESCRIPTOR

        assert HTTP_DESCRIPTOR.name == "http"

    def test_descriptor_provider_type(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_DESCRIPTOR

        assert HTTP_DESCRIPTOR.provider_type == CONST_STORAGE_PROVIDER_TYPE.HTTP

    def test_descriptor_sdk_is_httpx(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_DESCRIPTOR

        assert HTTP_DESCRIPTOR.sdk_package == "httpx"

    def test_descriptor_not_read_only(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_DESCRIPTOR

        assert HTTP_DESCRIPTOR.read_only is False

    def test_descriptor_no_multipart(self):
        from mountainash_utils_files.settings.providers.http_settings import HTTP_DESCRIPTOR

        assert HTTP_DESCRIPTOR.supports_multipart is False


@pytest.mark.unit
class TestHTTPHandlerKwargs:
    def test_noauth_kwargs(self):
        s = _make()
        kw = s.to_handler_kwargs()
        assert kw["follow_redirects"] is True
        assert kw["max_redirects"] == 10
        assert kw["verify"] is True
        assert "Authorization" not in kw.get("headers", {})

    def test_token_auth_produces_bearer_header(self):
        s = _make(auth=TokenAuth(token=SecretStr("mytoken")))
        kw = s.to_handler_kwargs()
        assert kw["headers"]["Authorization"] == "Bearer mytoken"

    def test_password_auth_produces_basic_header(self):
        import base64

        s = _make(auth=PasswordAuth(username="user", password=SecretStr("pass")))
        kw = s.to_handler_kwargs()
        expected = "Basic " + base64.b64encode(b"user:pass").decode()
        assert kw["headers"]["Authorization"] == expected

    def test_timeout_object_in_kwargs(self):
        import httpx

        s = _make(TIMEOUT_CONNECT=2.0, TIMEOUT_READ=5.0, TIMEOUT_WRITE=10.0)
        kw = s.to_handler_kwargs()
        timeout = kw["timeout"]
        assert isinstance(timeout, httpx.Timeout)
        assert timeout.connect == 2.0
        assert timeout.read == 5.0
        assert timeout.write == 10.0

    def test_custom_headers_merged_with_auth(self):
        s = _make(
            HEADERS={"X-Custom": "value"},
            auth=TokenAuth(token=SecretStr("tok")),
        )
        kw = s.to_handler_kwargs()
        assert kw["headers"]["X-Custom"] == "value"
        assert kw["headers"]["Authorization"] == "Bearer tok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_unit/settings/providers/test_http_settings.py -v`
Expected: `ModuleNotFoundError: No module named 'mountainash_utils_files.settings.providers.http_settings'`

- [ ] **Step 3: Create the HTTP adapter**

Create `src/mountainash_utils_files/settings/adapters/http.py`:

```python
"""httpx adapter — builds client kwargs from an HTTPSettings profile."""
from __future__ import annotations

import base64
import typing as t

import httpx

if t.TYPE_CHECKING:
    from ..profile import StorageProfile

__all__ = ["build_handler_kwargs"]


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _resolve_auth_headers(auth: t.Any) -> dict[str, str]:
    """Build Authorization header from an AuthSpec instance."""
    if auth is None:
        return {}
    auth_type = type(auth).__name__
    if auth_type == "TokenAuth":
        token = _unwrap_secret(getattr(auth, "token", None))
        if token:
            return {"Authorization": f"Bearer {token}"}
    elif auth_type == "PasswordAuth":
        username = getattr(auth, "username", None) or ""
        password = _unwrap_secret(getattr(auth, "password", None)) or ""
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    return {}


def build_handler_kwargs(profile: "StorageProfile") -> dict[str, t.Any]:
    """Build httpx.Client kwargs from an :class:`HTTPSettings` profile."""
    timeout_connect = getattr(profile, "TIMEOUT_CONNECT", 10.0)
    timeout_read = getattr(profile, "TIMEOUT_READ", 30.0)
    timeout_write = getattr(profile, "TIMEOUT_WRITE", 60.0)
    follow_redirects = getattr(profile, "FOLLOW_REDIRECTS", True)
    max_redirects = getattr(profile, "MAX_REDIRECTS", 10)
    verify = getattr(profile, "VERIFY_SSL", True)
    custom_headers = getattr(profile, "HEADERS", None) or {}

    auth = getattr(profile, "auth", None)
    auth_headers = _resolve_auth_headers(auth)

    headers = {**custom_headers, **auth_headers}

    kwargs: dict[str, t.Any] = {
        "timeout": httpx.Timeout(
            connect=timeout_connect,
            read=timeout_read,
            write=timeout_write,
            pool=5.0,
        ),
        "follow_redirects": follow_redirects,
        "max_redirects": max_redirects,
        "verify": verify,
    }
    if headers:
        kwargs["headers"] = headers

    return kwargs
```

- [ ] **Step 4: Create HTTPSettings and HTTP_DESCRIPTOR**

Create `src/mountainash_utils_files/settings/providers/http_settings.py`:

```python
"""HTTP/HTTPS provider settings.

A single :class:`HTTPSettings` class for both ``http://`` and ``https://``
schemes. Uses httpx under the hood.
"""
from __future__ import annotations

import typing as t

from mountainash_settings.auth import NoAuth, PasswordAuth, TokenAuth

from ..descriptor import ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ..base import StorageAuthBase
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["HTTP_DESCRIPTOR", "HTTPSettings"]


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


def _adapter(profile: "HTTPSettings") -> dict[str, t.Any]:
    from ..adapters.http import build_handler_kwargs

    return build_handler_kwargs(profile)


@register(HTTP_DESCRIPTOR)
class HTTPSettings(StorageProfile, StorageAuthBase):
    """HTTP/HTTPS provider settings.

    Fields are installed from :data:`HTTP_DESCRIPTOR` by the
    :class:`~mountainash_settings.profiles.DescriptorProfile` metaclass.
    """

    __descriptor__ = HTTP_DESCRIPTOR
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a placeholder connection URL for logging/inspection."""
        return "http(s)://<dynamic>"
```

- [ ] **Step 5: Export from providers __init__.py**

In `src/mountainash_utils_files/settings/providers/__init__.py`, add after the
existing imports:

```python
from .http_settings import HTTP_DESCRIPTOR, HTTPSettings
```

And add to `__all__`:

```python
    "HTTP_DESCRIPTOR",
    "HTTPSettings",
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_unit/settings/providers/test_http_settings.py -v`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_utils_files/settings/providers/http_settings.py \
        src/mountainash_utils_files/settings/adapters/http.py \
        src/mountainash_utils_files/settings/providers/__init__.py \
        tests/test_unit/settings/providers/test_http_settings.py
git commit -m "feat(http): add HTTPSettings descriptor and httpx adapter"
```

---

## Task 4: HTTP storage backend

**Files:**
- Create: `src/mountainash_utils_files/storage_backends/http/__init__.py`
- Modify: `src/mountainash_utils_files/storage_backends/__init__.py`
- Create: `tests/backends/test_http.py`

- [ ] **Step 1: Write failing tests for HTTPStorageBackend**

Create `tests/backends/test_http.py`:

```python
"""Tests for the HTTPStorageBackend."""
from __future__ import annotations

import io
from datetime import datetime, timezone

import httpx
import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageListProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)


def _transport(handler):
    """Return an httpx.MockTransport wrapping *handler*."""
    return httpx.MockTransport(handler)


def _make_backend(transport: httpx.MockTransport):
    """Return an HTTPStorageBackend with an injected httpx client."""
    import mountainash_utils_files.storage_backends  # noqa: F401
    from mountainash_utils_files.storage_backends.http import HTTPStorageBackend

    backend = HTTPStorageBackend(auth_params=None)
    backend._client = httpx.Client(transport=transport)
    return backend


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """HTTPStorageBackend must satisfy Read, Write, and Metadata protocols."""

    @pytest.fixture()
    def backend(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"ok")

        return _make_backend(_transport(_handler))

    def test_implements_read_protocol(self, backend):
        assert isinstance(backend, StorageReadProtocol)

    def test_implements_write_protocol(self, backend):
        assert isinstance(backend, StorageWriteProtocol)

    def test_implements_metadata_protocol(self, backend):
        assert isinstance(backend, StorageMetadataProtocol)

    def test_does_not_implement_list(self, backend):
        assert not isinstance(backend, StorageListProtocol)

    def test_does_not_implement_delete(self, backend):
        assert not isinstance(backend, StorageDeleteProtocol)

    def test_does_not_implement_copy(self, backend):
        assert not isinstance(backend, StorageCopyProtocol)

    def test_does_not_implement_directory(self, backend):
        assert not isinstance(backend, StorageDirectoryProtocol)

    def test_does_not_implement_connection(self, backend):
        assert not isinstance(backend, StorageConnectionProtocol)


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------


class TestReadToBytes:
    def test_returns_response_body(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            return httpx.Response(200, content=b"hello world")

        backend = _make_backend(_transport(_handler))
        assert backend.read_to_bytes("https://example.com/file.txt") == b"hello world"

    def test_404_raises_path_not_found(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        backend = _make_backend(_transport(_handler))
        with pytest.raises(PathNotFoundError):
            backend.read_to_bytes("https://example.com/missing")

    def test_401_raises_authentication_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        backend = _make_backend(_transport(_handler))
        with pytest.raises(AuthenticationError):
            backend.read_to_bytes("https://example.com/secret")

    def test_500_raises_storage_error(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        backend = _make_backend(_transport(_handler))
        with pytest.raises(StorageError):
            backend.read_to_bytes("https://example.com/error")


class TestReadToStream:
    def test_returns_readable_stream(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"stream data")

        backend = _make_backend(_transport(_handler))
        stream = backend.read_to_stream("https://example.com/file.txt")
        assert stream.read() == b"stream data"


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


class TestWriteFromBytes:
    def test_sends_put_with_body(self):
        captured: dict[str, bytes] = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "PUT"
            captured["body"] = request.content
            return httpx.Response(200)

        backend = _make_backend(_transport(_handler))
        backend.write_from_bytes("https://example.com/upload", b"payload")
        assert captured["body"] == b"payload"

    def test_404_on_put_raises_path_not_found(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        backend = _make_backend(_transport(_handler))
        with pytest.raises(PathNotFoundError):
            backend.write_from_bytes("https://example.com/no-bucket", b"data")


class TestWriteFromStream:
    def test_sends_put_with_stream_content(self):
        captured: dict[str, bytes] = {}

        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "PUT"
            captured["body"] = request.content
            return httpx.Response(200)

        backend = _make_backend(_transport(_handler))
        backend.write_from_stream("https://example.com/upload", io.BytesIO(b"streamed"))
        assert captured["body"] == b"streamed"


# ---------------------------------------------------------------------------
# Metadata operations
# ---------------------------------------------------------------------------


class TestPathExists:
    def test_2xx_returns_true(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "HEAD"
            return httpx.Response(200)

        backend = _make_backend(_transport(_handler))
        assert backend.path_exists("https://example.com/file") is True

    def test_404_returns_false(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        backend = _make_backend(_transport(_handler))
        assert backend.path_exists("https://example.com/missing") is False

    def test_500_raises(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        backend = _make_backend(_transport(_handler))
        with pytest.raises(StorageError):
            backend.path_exists("https://example.com/error")


class TestGetMetadata:
    def test_builds_file_metadata_from_headers(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={
                    "Content-Length": "1234",
                    "Content-Type": "text/plain",
                    "Last-Modified": "Wed, 07 May 2026 12:00:00 GMT",
                    "ETag": '"abc123"',
                },
            )

        backend = _make_backend(_transport(_handler))
        meta = backend.get_metadata("https://example.com/data.txt")
        assert meta.filename == "data.txt"
        assert meta.size == 1234
        assert meta.etag == '"abc123"'
        assert meta.source == "http"


class TestGetSize:
    def test_returns_content_length(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, headers={"Content-Length": "5678"})

        backend = _make_backend(_transport(_handler))
        assert backend.get_size("https://example.com/file") == 5678

    def test_missing_content_length_returns_zero(self):
        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        backend = _make_backend(_transport(_handler))
        assert backend.get_size("https://example.com/file") == 0


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_http_provider_registered(self):
        import mountainash_utils_files.storage_backends  # noqa: F401
        from mountainash_utils_files.storage_registry import get_registered_backends

        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.HTTP in backends
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backends/test_http.py -v`
Expected: `ModuleNotFoundError: No module named 'mountainash_utils_files.storage_backends.http'`

- [ ] **Step 3: Create the HTTP backend**

Create `src/mountainash_utils_files/storage_backends/http/__init__.py`:

```python
"""HTTP/HTTPS storage backend — read, write, and metadata via httpx."""
from __future__ import annotations

import io
import typing as t
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.dataclasses.file_metadata import FileMetadata
from mountainash_utils_files.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
from mountainash_utils_files.storage_registry import register_storage_backend


def _raise_for_status(response: httpx.Response, path: str) -> None:
    """Map HTTP error responses to storage exceptions."""
    code = response.status_code
    if 200 <= code < 300:
        return
    if code == 404:
        raise PathNotFoundError(f"Path not found: {path}")
    if code in (401, 403):
        raise AuthenticationError(
            f"Authentication failed ({code}) for {path}"
        )
    raise StorageError(
        f"HTTP {code} for {path}: {response.reason_phrase}"
    )


def _filename_from_url(url: str) -> str:
    """Extract filename from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.rsplit("/", 1)[-1] if "/" in path else path


def _directory_from_url(url: str) -> str:
    """Extract directory from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "/" in path:
        return path.rsplit("/", 1)[0]
    return "/"


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend:
    """HTTP/HTTPS storage backend.

    Implements :class:`StorageReadProtocol`, :class:`StorageWriteProtocol`,
    and :class:`StorageMetadataProtocol` using httpx.
    """

    def __init__(self, auth_params: t.Any) -> None:
        self.auth_params = auth_params
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        """Return or lazily create the httpx client."""
        if self._client is None:
            self._client = httpx.Client()
        return self._client

    # -- StorageReadProtocol ------------------------------------------------

    def read_to_bytes(self, path: str) -> bytes:
        """Read the full content of *path* via GET."""
        client = self._get_client()
        try:
            response = client.get(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout reading {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return response.content

    def read_to_stream(self, path: str) -> t.BinaryIO:
        """Read *path* via GET and return a binary stream."""
        client = self._get_client()
        try:
            response = client.get(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout reading {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return io.BytesIO(response.content)

    # -- StorageWriteProtocol -----------------------------------------------

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Write *data* to *path* via PUT."""
        client = self._get_client()
        try:
            response = client.put(path, content=data)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout writing {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        """Write *stream* to *path* via PUT."""
        client = self._get_client()
        try:
            response = client.put(path, content=stream.read())
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout writing {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

    # -- StorageMetadataProtocol --------------------------------------------

    def path_exists(self, path: str) -> bool:
        """Check existence via HEAD. Returns False for 404, raises on other errors."""
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout checking {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        if response.status_code == 404:
            return False
        if 200 <= response.status_code < 300:
            return True
        _raise_for_status(response, path)
        return False  # unreachable but keeps mypy happy

    def get_metadata(self, path: str) -> FileMetadata:
        """Build FileMetadata from HEAD response headers."""
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

        headers = response.headers
        size = int(headers.get("content-length", "0"))
        etag = headers.get("etag", "")
        last_modified = None
        lm_header = headers.get("last-modified")
        if lm_header:
            try:
                last_modified = parsedate_to_datetime(lm_header)
            except (ValueError, TypeError):
                pass

        return FileMetadata(
            filename=_filename_from_url(path),
            directory=_directory_from_url(path),
            full_path=path,
            size=size,
            last_modified=last_modified,
            etag=etag,
            source="http",
        )

    def get_size(self, path: str) -> int:
        """Return Content-Length from HEAD, or 0 if absent."""
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return int(response.headers.get("content-length", "0"))


__all__ = ["HTTPStorageBackend"]
```

- [ ] **Step 4: Register the backend in storage_backends/__init__.py**

In `src/mountainash_utils_files/storage_backends/__init__.py`, add:

```python
from . import http  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/backends/test_http.py -v`
Expected: All pass.

- [ ] **Step 6: Run the full test suite to check for regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests pass. The scheme registry test `test_describe_only_schemes_have_none_provider` should now exclude http/https.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_utils_files/storage_backends/http/__init__.py \
        src/mountainash_utils_files/storage_backends/__init__.py \
        tests/backends/test_http.py
git commit -m "feat(http): add HTTPStorageBackend with read/write/metadata protocols"
```

---

## Task 5: Remove urllib bridge from read_bytes

**Files:**
- Modify: `src/mountainash_utils_files/storage_facade/read_bytes.py`
- Modify: `tests/storage_facade/test_read_bytes.py`

- [ ] **Step 1: Update read_bytes tests to use the facade path**

Replace the urllib-based tests in `tests/storage_facade/test_read_bytes.py`.
The `test_read_bytes_http_uses_urllib` and `test_read_bytes_https_uses_urllib`
tests should be replaced with tests that verify HTTP URLs route through the
facade (similar to the existing `test_read_bytes_routes_s3_through_facade`).

Replace the two urllib tests and the infer+urllib test with:

```python
def test_read_bytes_http_routes_through_facade(monkeypatch):
    """http:// → StorageFacade.from_path(...).read(...) — no urllib."""
    calls: list[str] = []

    class _StreamBackend:
        def read_to_stream(self, path: str):
            calls.append(path)
            return io.BytesIO(b"http body")

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, auth=None: _StreamBackend()
    )
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("http://example.com/file") == b"http body"
    assert calls == ["http://example.com/file"]


def test_read_bytes_https_routes_through_facade(monkeypatch):
    """https:// → StorageFacade.from_path(...).read(...) — no urllib."""
    class _StreamBackend:
        def read_to_stream(self, path: str):
            return io.BytesIO(b"https body")

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, auth=None: _StreamBackend()
    )
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("https://example.com/file") == b"https body"
```

Also replace `test_read_bytes_http_infer_applies_pipeline_to_bytes` to go
through the facade instead of urllib:

```python
def test_read_bytes_http_infer_applies_pipeline_to_bytes(monkeypatch):
    """http body with a .gz suffix + infer=True must be gunzipped."""
    import gzip as gzlib
    payload = gzlib.compress(b"plain text from web")

    class _StreamBackend:
        def read_to_stream(self, path: str):
            return io.BytesIO(payload)

    from mountainash_utils_files.storage_facade import facade as facade_mod
    from mountainash_utils_files.storage_facade.facade import StorageFacade

    monkeypatch.setattr(
        facade_mod, "get_storage_backend", lambda provider, auth=None: _StreamBackend()
    )
    monkeypatch.setattr(StorageFacade, "_require", lambda self, protocol, op: None)

    assert read_bytes("https://example.com/file.gz", infer=True) == b"plain text from web"
```

- [ ] **Step 2: Run updated tests to verify they fail**

Run: `pytest tests/storage_facade/test_read_bytes.py -v`
Expected: The new facade-routing tests fail because `read_bytes` still has the
urllib branch that intercepts http/https before hitting the facade.

- [ ] **Step 3: Remove the urllib bridge from read_bytes**

Rewrite `src/mountainash_utils_files/storage_facade/read_bytes.py`:

```python
"""Top-level read helper that dispatches by URL scheme.

All schemes — including http/https — route through StorageFacade.from_path().
"""
from __future__ import annotations

import typing

from mountainash_utils_files.path_helpers.suffixes import infer_pipeline
from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline


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
    if not infer:
        return facade.read(path)

    pipeline, _stripped = infer_pipeline(path, gpg=gpg, gzip=gzip)
    if pipeline is None:
        return facade.read(path)
    return facade.read(path, pipeline=pipeline)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/storage_facade/test_read_bytes.py -v`
Expected: All pass.

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All pass. No remaining references to `urllib.request.urlopen` in the
production code.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_utils_files/storage_facade/read_bytes.py \
        tests/storage_facade/test_read_bytes.py
git commit -m "refactor(read_bytes): remove urllib bridge — all schemes via facade"
```

---

## Task 6: S3 timeout configuration

**Files:**
- Modify: `src/mountainash_utils_files/settings/providers/s3_settings.py:157` (before closing `]` of parameters list)
- Modify: `src/mountainash_utils_files/settings/adapters/s3.py:135-143`
- Modify: `tests/test_unit/settings/providers/test_s3_settings.py`

- [ ] **Step 1: Write failing tests for S3 timeout kwargs**

Add to `tests/test_unit/settings/providers/test_s3_settings.py`:

```python
@pytest.mark.unit
class TestS3TimeoutConfiguration:
    """CONNECT_TIMEOUT and READ_TIMEOUT propagate to botocore.config.Config."""

    def test_timeouts_default_to_none(self):
        s = _make("aws")
        assert s.CONNECT_TIMEOUT is None
        assert s.READ_TIMEOUT is None

    def test_timeouts_in_handler_kwargs_when_set(self):
        s = _make("aws", CONNECT_TIMEOUT=5.0, READ_TIMEOUT=30.0)
        kw = s.to_handler_kwargs()
        config = kw["config"]
        assert config._user_provided_options.get("connect_timeout") == 5.0
        assert config._user_provided_options.get("read_timeout") == 30.0

    def test_timeouts_omitted_from_config_when_none(self):
        s = _make("aws")
        kw = s.to_handler_kwargs()
        config = kw["config"]
        opts = config._user_provided_options
        assert "connect_timeout" not in opts
        assert "read_timeout" not in opts

    def test_explicit_none_omitted_from_config(self):
        s = _make("aws", CONNECT_TIMEOUT=None, READ_TIMEOUT=None)
        kw = s.to_handler_kwargs()
        config = kw["config"]
        opts = config._user_provided_options
        assert "connect_timeout" not in opts
        assert "read_timeout" not in opts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_unit/settings/providers/test_s3_settings.py::TestS3TimeoutConfiguration -v`
Expected: `AttributeError: 'S3Settings' object has no attribute 'CONNECT_TIMEOUT'`

- [ ] **Step 3: Add timeout ParameterSpecs to S3_DESCRIPTOR**

In `src/mountainash_utils_files/settings/providers/s3_settings.py`, add two
new ParameterSpec entries inside the `parameters` list, before the closing `]`
(after the ROLE_ARN entry at line ~157):

```python
        ParameterSpec(
            name="CONNECT_TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            description=(
                "Connection timeout in seconds for boto3 client. "
                "None defers to boto3 default (~60s)."
            ),
        ),
        ParameterSpec(
            name="READ_TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            description=(
                "Read timeout in seconds for boto3 client. "
                "None defers to boto3 default (~60s)."
            ),
        ),
```

- [ ] **Step 4: Propagate timeouts in the S3 adapter**

In `src/mountainash_utils_files/settings/adapters/s3.py`, replace the
`Config` construction block (lines ~135–143):

```python
    if _botocore_config is not None:
        s3_config: dict[str, t.Any] = {"addressing_style": addressing_style}
        if flavor == "aws":
            if accelerate:
                s3_config["use_accelerate_endpoint"] = True
            if dualstack:
                s3_config["use_dualstack_endpoint"] = True
        config_kwargs: dict[str, t.Any] = {"s3": s3_config}
        connect_timeout = getattr(profile, "CONNECT_TIMEOUT", None)
        read_timeout = getattr(profile, "READ_TIMEOUT", None)
        if connect_timeout is not None:
            config_kwargs["connect_timeout"] = connect_timeout
        if read_timeout is not None:
            config_kwargs["read_timeout"] = read_timeout
        base["config"] = _botocore_config.Config(**config_kwargs)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_unit/settings/providers/test_s3_settings.py -v`
Expected: All pass including the new timeout tests.

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add src/mountainash_utils_files/settings/providers/s3_settings.py \
        src/mountainash_utils_files/settings/adapters/s3.py \
        tests/test_unit/settings/providers/test_s3_settings.py
git commit -m "feat(s3): add CONNECT_TIMEOUT and READ_TIMEOUT configuration"
```

---

## Task 7: Final verification and cleanup

**Files:** None new — verification only.

- [ ] **Step 1: Run the full test suite with coverage**

Run: `hatch run test:cov`
Expected: All pass. No regressions.

- [ ] **Step 2: Run linting**

Run: `hatch run ruff:check`
Expected: Clean.

- [ ] **Step 3: Run type checking**

Run: `hatch run mypy:check`
Expected: Clean (or pre-existing issues only — no new errors).

- [ ] **Step 4: Verify no urllib references remain in production code**

Run: `grep -rn "urllib" src/mountainash_utils_files/`
Expected: No matches.

- [ ] **Step 5: Verify HTTP backend is accessible from the public API**

Run: `python -c "from mountainash_utils_files import StorageFacade, CONST_STORAGE_PROVIDER_TYPE; f = StorageFacade.from_path('https://example.com/test'); print('OK')"`
Expected: Prints `OK` (no missing-provider error).

- [ ] **Step 6: Commit any cleanup**

If any lint/type fixes were needed, commit them:

```bash
git add -u
git commit -m "chore: lint and type fixes for HTTP backend + S3 timeouts"
```
