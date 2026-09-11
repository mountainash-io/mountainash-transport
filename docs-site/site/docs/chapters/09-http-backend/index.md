---
title: HTTP Backend
description: Read-only HTTP/HTTPS storage backend using httpx with error mapping to the standard exception hierarchy
generated_by: claude skill chapter-content-generator
date: 2026-06-03
version: 0.08
---

# Chapter 9: HTTP Backend

## Summary

This chapter presents the read-only HTTP backend for accessing files over
HTTP and HTTPS URLs. It introduces the HTTPStorageBackend class and its three
supported capabilities: connection management, read operations, and metadata
retrieval. Readers learn about the Httpx client integration that powers network
requests and the HTTP error mapping layer that translates HTTP status codes into
the library's standard exception hierarchy.

## Concepts Covered

- HTTPStorageBackend Class
- HTTP Read Support
- HTTP Metadata Support
- HTTP Connection Support
- Httpx Client
- HTTP Error Mapping

## Learning Graph IDs

77, 78, 79, 80, 81, 82

## Prerequisites

- Chapter 1: Foundation Concepts (URL Schemes, Registry Pattern)
- Chapter 2: Storage Protocols (StorageConnectionProtocol, StorageReadProtocol, StorageMetadataProtocol)

---

## Why an HTTP Backend?

The previous chapters covered the Local and S3 backends, both of which operate on storage systems where the library controls the full lifecycle of files -- reading, writing, listing, deleting, and copying. HTTP endpoints represent a fundamentally different access pattern. A public dataset hosted at a URL, an API that serves files, or a CDN delivering assets all expose data over HTTP, but they do not necessarily support the full range of storage operations. You can download a file from a URL, and you can check whether it exists, but you cannot typically list directory contents or delete remote resources through a simple GET or HEAD request.

The **HTTPStorageBackend** addresses this asymmetry by implementing only the protocols that make sense for HTTP: read operations, metadata retrieval, and basic write operations (via PUT). It does not implement the list, delete, copy, or directory protocols. When the StorageFacade (Chapter 3) dispatches an unsupported operation to the HTTP backend, the protocol-checked dispatch mechanism raises an `UnsupportedOperationError` automatically -- no code in the HTTP backend needs to handle those cases.

This design follows the same mixin-free, protocol-based architecture you saw in the Local and S3 backends, but with a deliberately smaller surface area. The HTTP backend demonstrates that the protocol system gracefully handles backends with partial capability sets.

#### Diagram: HTTP Backend Protocol Coverage

<iframe src="../../sims/http-protocol-coverage/main.html" width="100%" height="450px" scrolling="no"></iframe>

<details markdown="1">
<summary>HTTP Backend Protocol Coverage</summary>
Type: comparison matrix | **sim-id:** http-protocol-coverage<br/> | **Library:** vis-network<br/> | **Status:** Specified

**Learning Objective:** Compare the HTTP backend's protocol coverage against the Local and S3 backends.
**Bloom Level:** Understand
**Interactions:** Hover over each protocol-backend intersection to see whether it is implemented (green), not implemented (red), or partially implemented (yellow). Click the HTTP column to highlight which protocols it supports and which StorageFacade methods are available.
</details>

<!-- concept:77 -->
## The HTTPStorageBackend Class

The **HTTPStorageBackend** class is the central class of the HTTP backend module. It is registered with the storage backend registry using the `@register_storage_backend` decorator (the Registry Pattern from Chapter 1), which associates it with the `CONST_STORAGE_PROVIDER_TYPE.HTTP` provider type. This registration means that the StorageFacade can automatically select the HTTP backend when it encounters an `http://` or `https://` URL.

The class constructor accepts an `auth_params` argument (consistent with the other backends) and initializes a private `_client` attribute to `None`. The httpx client is created lazily on first use, which avoids the overhead of establishing a connection pool until an actual HTTP request is needed.

```python
from mountainash_utils_files.storage_backends.http import HTTPStorageBackend

# Create a backend instance (typically done by the facade, not manually)
backend = HTTPStorageBackend(auth_params=None)

<!-- concept:81 -->
# The httpx client is created on first use
data = backend.read_to_bytes("https://example.com/data.csv")
```

The code above creates a backend and reads a file from a URL. The first call to `read_to_bytes()` triggers lazy initialization of the httpx client. Subsequent calls reuse the same client, benefiting from httpx's connection pooling for repeated requests to the same host.

Unlike the Local backend (which builds on eight mixins) and the S3 backend (which builds on seven mixins plus a flavor dispatch layer), the HTTP backend is a single flat class with no mixins. This simplicity reflects the backend's limited scope -- there are not enough capabilities to warrant decomposition into separate concerns.

## The Httpx Client

The **httpx client** is the HTTP library that powers all network requests in the HTTP backend. Httpx is a modern Python HTTP client that provides both synchronous and asynchronous APIs, connection pooling, timeout management, and a transport layer that can be swapped for testing.

The HTTP backend uses the synchronous `httpx.Client` class, which maintains a connection pool and reuses TCP connections across requests. The client is stored in the `_client` instance variable and created via the `_get_client()` helper method. This method implements the lazy initialization pattern: it creates the client on first call and returns the cached instance on subsequent calls.

```python
def _get_client(self) -> httpx.Client:
    if self._client is None:
        self._client = httpx.Client()
    return self._client
```

The lazy initialization approach has two benefits. First, importing the HTTP backend module does not establish any network connections -- the cost is deferred until an actual operation is performed. Second, tests can replace `_client` with a mock transport before any real request is made, enabling fully offline testing.

The httpx library translates network-level failures into specific exception types. A DNS resolution failure or TCP connection refusal raises `httpx.ConnectError`. A request that exceeds the configured timeout raises `httpx.TimeoutException`. The HTTP backend catches both of these and wraps them in the library's `StorageConnectionError`, maintaining a consistent exception interface regardless of the underlying network library.

<!-- concept:78 -->
## HTTP Read Support

**HTTP read support** is provided through two methods that implement the `StorageReadProtocol`: `read_to_bytes()` and `read_to_stream()`. Both methods issue an HTTP GET request to the specified URL and return the response body.

The `read_to_bytes()` method returns the raw response content as a `bytes` object. This is the simplest and most common read pattern, suitable for files that fit comfortably in memory.

```python
backend = HTTPStorageBackend(auth_params=None)

# Read a file as bytes
content = backend.read_to_bytes("https://example.com/report.json")
print(len(content))  # Size in bytes
```

The `read_to_stream()` method wraps the response content in a `BytesIO` object and returns it as a `BinaryIO` stream. This provides the same interface as file-like objects, enabling compatibility with code that expects to read from streams rather than byte buffers.

```python
# Read a file as a stream
stream = backend.read_to_stream("https://example.com/report.json")
first_line = stream.readline()
```

Both methods follow the same error handling pattern: they catch httpx-specific exceptions (`TimeoutException`, `ConnectError`) and wrap them in `StorageConnectionError`, then call `_raise_for_status()` to translate HTTP status codes into the library's exception hierarchy.

It is worth noting that the current implementation reads the entire response into memory before returning, even in the stream case. The `BytesIO` wrapper provides a stream interface but does not enable true streaming downloads where data is consumed incrementally as it arrives. For the typical use cases of the storage library (configuration files, metadata documents, moderately sized datasets), this trade-off is acceptable.

#### Diagram: HTTP Read Request Flow

<iframe src="../../sims/http-read-flow/main.html" width="100%" height="450px" scrolling="no"></iframe>

<details markdown="1">
<summary>HTTP Read Request Flow</summary>
Type: sequence diagram | **sim-id:** http-read-flow<br/> | **Library:** vis-network<br/> | **Status:** Specified

**Learning Objective:** Trace the full request lifecycle from method call through httpx to response handling and error mapping.
**Bloom Level:** Apply
**Interactions:** Step through the sequence: caller invokes read_to_bytes -> _get_client() -> httpx.Client.get() -> HTTP server -> response -> _raise_for_status() -> return bytes. Toggle error scenarios (404, 401, timeout) to see the exception mapping path.
</details>

<!-- concept:79 -->
## HTTP Metadata Support

**HTTP metadata support** provides three methods that implement the `StorageMetadataProtocol`: `path_exists()`, `get_metadata()`, and `get_size()`. All three use HTTP HEAD requests, which retrieve response headers without downloading the body. This makes metadata operations lightweight -- even for very large remote files, a HEAD request returns only a few hundred bytes of headers.

The `path_exists()` method checks whether a URL is accessible. It issues a HEAD request and interprets the status code: 2xx means the resource exists, 404 means it does not, and any other error status raises an exception through the standard error mapping.

```python
backend = HTTPStorageBackend(auth_params=None)

# Check if a URL is accessible
exists = backend.path_exists("https://example.com/data.csv")
print(exists)  # True or False
```

The `get_metadata()` method returns a `FileMetadata` object populated from HTTP response headers. It extracts the filename from the URL path, the file size from the `Content-Length` header, the last modification time from the `Last-Modified` header (parsed using Python's `email.utils.parsedate_to_datetime()`), and the entity tag from the `ETag` header. The `source` field is set to `"http"` to distinguish HTTP metadata from local or S3 metadata.

The following code demonstrates metadata retrieval and shows which HTTP headers map to which FileMetadata fields.

```python
meta = backend.get_metadata("https://cdn.example.com/reports/q4-2025.pdf")

print(meta.filename)       # "q4-2025.pdf"
print(meta.directory)      # "/reports"
print(meta.full_path)      # "https://cdn.example.com/reports/q4-2025.pdf"
print(meta.size)           # From Content-Length header
print(meta.last_modified)  # From Last-Modified header (datetime or None)
print(meta.etag)           # From ETag header
print(meta.source)         # "http"
```

| HTTP Header | FileMetadata Field | Fallback |
|---|---|---|
| Content-Length | size | 0 |
| Last-Modified | last_modified | None |
| ETag | etag | "" |
| (URL path) | filename | Last path segment |
| (URL path) | directory | Parent path segment |

The `get_size()` method is a convenience shortcut that returns only the integer size from the `Content-Length` header. If the header is missing (some servers omit it for dynamically generated content), the method returns 0.

Two helper functions support the metadata methods. The `_filename_from_url()` function extracts the last path segment from a URL using `urlparse`. The `_directory_from_url()` function extracts everything before the last path segment. Both handle edge cases like trailing slashes and root-level paths.

<!-- concept:80 -->
## HTTP Connection Support

**HTTP connection support** in the HTTP backend refers to the lazy client lifecycle rather than a formal `connect()`/`disconnect()` pair. Unlike the S3 backend, which establishes a boto3 session, or the Local backend, which validates the base directory, the HTTP backend has no explicit connection step. The httpx client is created on demand and manages its own connection pool internally.

This means the HTTP backend does not implement the `StorageConnectionProtocol`. The test suite explicitly verifies this:

```python
def test_does_not_implement_connection(self, backend):
    assert not isinstance(backend, StorageConnectionProtocol)
```

The absence of `StorageConnectionProtocol` is intentional. HTTP is a stateless protocol -- each request is independent, and there is no persistent session to establish or tear down. The httpx client handles TCP connection reuse transparently through its connection pool, but this is an optimization detail, not a semantic connection lifecycle.

If the StorageFacade attempts to call `connect()` or `disconnect()` on an HTTP backend, the protocol-checked dispatch detects the missing protocol and raises `UnsupportedOperationError`. Callers who need connection lifecycle management should use the S3 or Local backends instead.

<!-- concept:82 -->
#### Diagram: HTTP Error Mapping

<iframe src="../../sims/http-error-mapping/main.html" width="100%" height="500px" scrolling="no"></iframe>

<details markdown="1">
<summary>HTTP Error Mapping</summary>
Type: decision tree | **sim-id:** http-error-mapping<br/> | **Library:** vis-network<br/> | **Status:** Specified

**Learning Objective:** Understand how HTTP status codes and httpx exceptions map to the library's exception hierarchy.
**Bloom Level:** Apply
**Interactions:** Enter an HTTP status code or select an httpx exception type and see the corresponding storage exception. The tree shows three paths: 2xx (success, no exception), 4xx/5xx (mapped via _raise_for_status), and network errors (caught from httpx and wrapped in StorageConnectionError).
</details>

## HTTP Error Mapping

The **HTTP error mapping** layer is the bridge between HTTP's status code system and the library's exception hierarchy. Every storage backend in the library raises exceptions from a common set: `PathNotFoundError`, `AuthenticationError`, `StorageConnectionError`, and `StorageError`. The HTTP backend maps HTTP responses and httpx exceptions to these types through two mechanisms.

The first mechanism is the `_raise_for_status()` function, which examines the HTTP response status code:

- **2xx (200-299)** -- Success. The function returns without raising.
- **404** -- Maps to `PathNotFoundError`. The requested URL does not exist.
- **401 or 403** -- Maps to `AuthenticationError`. The server rejected the request due to missing or invalid credentials.
- **Any other non-2xx code** -- Maps to `StorageError` with the status code and reason phrase in the message.

```python
def _raise_for_status(response: httpx.Response, path: str) -> None:
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
```

The second mechanism is exception wrapping in each method. Before calling `_raise_for_status()`, each method catches `httpx.TimeoutException` and `httpx.ConnectError` and wraps them in `StorageConnectionError`. This ensures that network-level failures (DNS resolution failures, TCP connection refusals, timeouts) are presented through the same exception interface as storage-level errors.

The two-layer approach means that callers never need to handle httpx-specific exceptions. They can catch `PathNotFoundError` when a URL might not exist, `AuthenticationError` when credentials might be wrong, `StorageConnectionError` when the network might be unreliable, and `StorageError` as a catch-all for unexpected failures. This is the same set of exceptions they would handle for the Local or S3 backends, achieving the library's goal of backend-agnostic error handling.

| Error Source | HTTP Indicator | Library Exception |
|---|---|---|
| Resource not found | 404 status code | `PathNotFoundError` |
| Authentication failure | 401 or 403 status code | `AuthenticationError` |
| Server error | 5xx status code | `StorageError` |
| Client error | Other 4xx status code | `StorageError` |
| Network timeout | `httpx.TimeoutException` | `StorageConnectionError` |
| Connection failure | `httpx.ConnectError` | `StorageConnectionError` |

## Write Support via PUT

While the HTTP backend is primarily read-oriented, it also implements the `StorageWriteProtocol` through `write_from_bytes()` and `write_from_stream()` methods. Both methods issue HTTP PUT requests to the target URL. This enables writing to HTTP endpoints that accept PUT-based uploads, such as WebDAV servers, pre-signed S3 URLs, or custom upload APIs.

The `write_from_bytes()` method sends the raw bytes as the request body:

```python
backend = HTTPStorageBackend(auth_params=None)
backend.write_from_bytes(
    "https://upload.example.com/files/report.csv",
    b"id,name\n1,Alice\n2,Bob",
)
```

The `write_from_stream()` method reads the entire stream into memory and sends it as the PUT body. Like the read methods, this is a full-materialization approach rather than a chunked upload, which keeps the implementation simple at the cost of requiring the entire payload to fit in memory.

Both write methods follow the same error handling pattern as reads: httpx exceptions are caught and wrapped in `StorageConnectionError`, and the response is passed through `_raise_for_status()`. A 404 response on a PUT typically indicates that the target bucket or directory does not exist, while a 401/403 indicates that the upload endpoint requires authentication that was not provided.

It is important to note that not all HTTP servers accept PUT requests. A standard web server serving static files will return a 405 (Method Not Allowed) response, which the error mapping layer translates to a generic `StorageError`. The write methods are most useful when combined with authenticated endpoints or services that explicitly support file uploads via PUT.

## Backend Registration and Discovery

The HTTP backend registers itself with the storage registry using the `@register_storage_backend` decorator:

```python
@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend:
    ...
```

This decorator, part of the Registry Pattern covered in Chapter 1, adds the backend class to a global dictionary keyed by provider type. When the StorageFacade encounters a URL with an `http://` or `https://` scheme, it looks up `CONST_STORAGE_PROVIDER_TYPE.HTTP` in the registry and instantiates the `HTTPStorageBackend`.

The registration is triggered by importing the backend module. The library's storage backends package ensures that all backend modules are imported during initialization, so the HTTP backend is always available without explicit setup by the caller.

You can verify registration programmatically:

```python
from mountainash_utils_files.storage_registry import get_registered_backends
from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

backends = get_registered_backends()
assert CONST_STORAGE_PROVIDER_TYPE.HTTP in backends
```

This discovery mechanism means that adding a new backend to the library requires only implementing the class with the decorator -- no central configuration file needs to be updated, and no factory function needs to be modified.

## Comparison with Other Backends

The HTTP backend is the most constrained of the three backends in the library. Understanding what it omits is as instructive as understanding what it provides.

The Local backend implements all eight storage protocols, providing full read, write, list, delete, copy, metadata, directory, and connection capabilities. This reflects the nature of local file systems, which support the complete set of file operations.

The S3 backend implements seven of the eight protocols (omitting only the directory protocol, since S3 uses a flat key-value namespace rather than true directories). It adds complexity through the flavor dispatch layer to handle differences between AWS S3, S3 Express One Zone, Cloudflare R2, and MinIO.

The HTTP backend implements only read, write, and metadata -- three of the eight protocols. It has no flavors, no mixins, and no complex dispatch logic. This minimalism is appropriate for a protocol that was designed for document retrieval, not general-purpose storage.

| Capability | Local | S3 | HTTP |
|---|---|---|---|
| Read (bytes + stream) | Yes | Yes | Yes |
| Write (bytes + stream) | Yes | Yes | Yes (PUT) |
| List | Yes | Yes | No |
| Delete | Yes | Yes | No |
| Copy | Yes | Yes | No |
| Metadata | Yes | Yes | Yes (HEAD) |
| Directory | Yes | No | No |
| Connection | Yes | Yes | No |

This comparison reinforces the protocol-based architecture's value: each backend implements exactly the capabilities it can support, and the facade's protocol-checked dispatch prevents callers from accidentally invoking unsupported operations.

## Testing the HTTP Backend

The HTTP backend's test suite uses httpx's `MockTransport` to intercept all HTTP requests without making real network calls. A mock transport is a callable that receives an `httpx.Request` and returns an `httpx.Response`, giving tests complete control over the server's behavior.

The test setup replaces the backend's `_client` with a client configured to use a mock transport. This approach works because of the lazy initialization pattern -- the test injects the mock client before any real client is created.

```python
import httpx
from mountainash_utils_files.storage_backends.http import HTTPStorageBackend

def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/data.csv":
        return httpx.Response(200, content=b"id,name\n1,Alice")
    return httpx.Response(404)

backend = HTTPStorageBackend(auth_params=None)
backend._client = httpx.Client(transport=httpx.MockTransport(_handler))

# This hits the mock, not the real network
data = backend.read_to_bytes("https://example.com/data.csv")
assert data == b"id,name\n1,Alice"
```

The test suite covers protocol conformance (verifying that the backend implements exactly the expected protocols and no others), successful operations (read, metadata, size), error mapping (404, 401, 500), and backend registration (confirming the HTTP provider type appears in the registry). This coverage ensures that the error mapping layer works correctly for every status code category and that the backend integrates properly with the facade's dispatch mechanism.

## Key Takeaways

- The **HTTPStorageBackend** implements read, write, and metadata protocols but intentionally omits list, delete, copy, directory, and connection protocols, reflecting HTTP's limited storage semantics.
- The **httpx client** is lazily initialized on first use, providing connection pooling without upfront overhead, and its transport layer can be swapped for mock transports in tests.
- **HTTP read support** provides `read_to_bytes()` and `read_to_stream()` methods that issue GET requests and return the response body as bytes or a BytesIO stream.
- **HTTP metadata support** uses HEAD requests to extract file size, last-modified time, ETag, filename, and directory from HTTP response headers without downloading the body.
- **HTTP connection support** is deliberately absent -- HTTP is stateless, and the httpx client manages connection reuse internally through its pool.
- **HTTP error mapping** translates HTTP status codes (404, 401/403, 5xx) and httpx exceptions (TimeoutException, ConnectError) into the library's standard exception hierarchy, ensuring backend-agnostic error handling for callers.
