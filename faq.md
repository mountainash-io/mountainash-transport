# Frequently Asked Questions for Mountainash Utils Files

## General Architecture

### What is mountainash-transport and what problem does it solve?

Mountainash-transport is a cloud-native storage abstraction library for Python that provides a unified, protocol-driven interface for reading, writing, copying, and managing files across multiple storage backends. Instead of writing separate code for local filesystem operations, S3 uploads, and HTTP downloads, developers use a single StorageFacade API that dispatches operations to the correct backend automatically based on the file path or URL scheme.

The library solves the problem of backend-specific code proliferating through an application. Without it, a function that reads a file from the local filesystem needs entirely different code to read the same logical file from S3 or an HTTP endpoint. With mountainash-transport, the same `read_bytes("s3://bucket/key")` or `read_bytes("/local/path")` call works transparently. The protocol-driven architecture also means backends only need to implement the capabilities they support, and the facade raises clear errors when an unsupported operation is attempted.

### How does the protocol-driven architecture work?

The library defines 8 runtime-checkable protocols that represent fine-grained storage capabilities: Connection, Read, Write, List, Delete, Metadata, Copy, and Directory. Each protocol is a Python Protocol class decorated with `@runtime_checkable`, which means you can use `isinstance()` checks at runtime to determine whether a backend supports a particular operation.

When you call a method on StorageFacade, it checks whether the underlying backend implements the required protocol before dispatching the call. If the backend does not implement that protocol, the facade raises an UnsupportedOperationError with a clear message indicating which capability is missing. This design avoids the "lowest common denominator" problem where all backends must implement every operation. Instead, the Local backend implements all 8 protocols, the S3 backend implements 7 of 8 (missing Directory), and the HTTP backend implements only 3 (Connection, Read, Metadata).

### What backends are currently supported?

Mountainash-transport ships with three storage backends. The Local backend provides full 8-protocol coverage for filesystem operations, implementing Connection, Read, Write, List, Delete, Metadata, Copy, and Directory protocols through 8 corresponding mixin classes. The S3 backend unifies five S3-compatible services (AWS S3, S3 Express One Zone, Cloudflare R2, MinIO, and Backblaze B2) under a single class with flavor dispatch, implementing 7 of 8 protocols. The HTTP backend is a read-only backend for HTTP and HTTPS URLs, implementing Connection, Read, and Metadata protocols using the httpx client library.

Each backend is registered with the StorageRegistry and selected automatically based on the URL scheme or path pattern of the file being accessed.

### What is the mixin composition pattern and why is it used?

The mixin composition pattern is a design approach where each storage protocol is implemented as a separate mixin class, and a backend class composes the mixins it supports. For example, the LocalStorageBackend class inherits from LocalConnectionMixin, LocalReadMixin, LocalWriteMixin, LocalListMixin, LocalDeleteMixin, LocalMetadataMixin, LocalCopyMixin, and LocalDirectoryMixin.

This pattern provides several benefits. It keeps each protocol implementation isolated and testable. It allows backends to implement only the capabilities they support by including only the relevant mixins. It makes it straightforward to add a new protocol by creating a new mixin without modifying existing code. The S3 backend uses the same approach, composing 7 mixins corresponding to the 7 protocols it supports.

### How do I install and configure mountainash-transport?

Mountainash-transport is a Python package designed for Python developers and platform engineers. It requires intermediate Python knowledge, including familiarity with protocols, dataclasses, mixins, and context managers. You also need basic understanding of file I/O, binary streams, URL schemes, and cloud object storage concepts such as buckets and keys.

Configuration is handled through the settings system. StorageAuthBase is the base class for provider settings, and each provider type has its own settings class with fields for credentials, endpoints, and provider-specific options. Settings can be loaded from profiles, and settings adapters transform credentials into the format expected by each backend's client library (boto3 for S3, httpx for HTTP).

### What topics does mountainash-transport intentionally exclude?

The library focuses specifically on the storage abstraction layer and deliberately excludes several adjacent concerns. It does not handle cloud provider account management or IAM policy authoring. Network transport layer details such as TCP connections and TLS handshakes are outside its scope. Database or lakehouse storage is handled by the separate mountainash-data package. File format parsing for CSV, Parquet, or JSON deserialization is not included. Deployment and infrastructure provisioning are also excluded. This focused scope keeps the library lean and composable, allowing it to integrate with other mountainash packages that handle those responsibilities.

## Storage Protocols

### What are the 8 storage protocols and what does each one do?

The 8 storage protocols are Connection, Read, Write, List, Delete, Metadata, Copy, and Directory. StorageConnectionProtocol handles establishing and verifying connections to the storage backend. StorageReadProtocol defines methods for reading file content as bytes or streams. StorageWriteProtocol defines methods for writing bytes or streams to a storage location. StorageListProtocol provides file listing within a path prefix. StorageDeleteProtocol handles file deletion. StorageMetadataProtocol retrieves file metadata such as size, modification time, and content type. StorageCopyProtocol enables copying files within the same backend. StorageDirectoryProtocol manages directory creation and deletion operations.

Each protocol is a Python Protocol class decorated with `@runtime_checkable`, enabling isinstance checks at runtime to determine backend capabilities.

### What does runtime-checkable mean for storage protocols?

Runtime-checkable protocols are Python Protocol classes that support `isinstance()` checks at runtime. Normally, Python protocols are only checked statically by type checkers like mypy. By decorating a protocol with `@runtime_checkable`, the library enables dynamic dispatch where the StorageFacade can test at runtime whether a backend implements a specific capability.

This is central to the protocol-checked dispatch pattern. When you call `facade.read_bytes(path)`, the facade first checks `isinstance(backend, StorageReadProtocol)`. If the check passes, the call is dispatched. If it fails, an UnsupportedOperationError is raised. This approach provides both static type safety during development and dynamic capability detection at runtime, ensuring that operations never silently fail on backends that do not support them.

### What is the StorageConnectionProtocol and when is it used?

StorageConnectionProtocol defines the interface for establishing and verifying connections to a storage backend. All three backends (Local, S3, HTTP) implement this protocol. For the Local backend, a "connection" is simply verifying that the base directory exists and is accessible. For the S3 backend, it involves creating a boto3 client with the appropriate credentials and endpoint. For the HTTP backend, it involves configuring an httpx client.

The Connection protocol is a prerequisite for all other operations. Before reading, writing, or listing files, the backend must have an active connection. The StorageFacade checks the Connection protocol first when initializing a backend for a given path.

### What is the StorageCopyProtocol and how does it differ from cross-backend copy?

StorageCopyProtocol defines the interface for copying files within a single storage backend. When both the source and destination paths resolve to the same backend, the copy operation can use native, optimized mechanisms. For example, the Local backend uses filesystem copy operations, and the S3 backend uses S3's server-side copy API, which avoids downloading and re-uploading the file data.

Cross-backend copy, handled by the `copy_between` function, is fundamentally different. It reads data from the source backend and writes it to the destination backend, streaming bytes through the local process. This is necessary when the source and destination are on different providers (for example, copying from S3 to local filesystem). The StorageCopyProtocol is for same-backend optimization, while copy_between handles the general cross-backend case.

### How does the capability matrix differ across backends?

The three backends have different capability profiles. The Local backend has full protocol coverage, implementing all 8 protocols (Connection, Read, Write, List, Delete, Metadata, Copy, Directory). The S3 backend implements 7 of 8 protocols, supporting everything except the Directory protocol because S3 object storage does not have true directory semantics (prefixes simulate directories). The HTTP backend implements only 3 protocols (Connection, Read, Metadata) because HTTP endpoints are fundamentally read-only from the client's perspective.

This capability matrix is the reason for protocol-checked dispatch. Rather than forcing all backends to implement stub methods that raise NotImplementedError, each backend only implements what it genuinely supports, and the facade handles unsupported operations gracefully.

### What happens when I call an unsupported operation on a backend?

When you call a method on StorageFacade that requires a protocol the underlying backend does not implement, the facade raises an UnsupportedOperationError. For example, calling `facade.write_bytes()` on an HTTP-backed path will raise this error because the HTTP backend does not implement StorageWriteProtocol.

The error message clearly identifies which protocol is missing and which backend was involved, making it straightforward to diagnose the issue. This is a deliberate design choice that favors explicit failure over silent behavior. It prevents bugs where code appears to work but quietly drops writes or returns empty results. Developers can also perform their own isinstance checks before calling operations if they need to handle multiple backends with different capabilities gracefully.

### What is Protocol Checked Dispatch?

Protocol Checked Dispatch is the core dispatch mechanism in StorageFacade. When a method is called on the facade, it does not blindly forward the call to the backend. Instead, it first performs an `isinstance()` check against the relevant runtime-checkable protocol. Only if the backend satisfies the protocol is the call dispatched.

This pattern decouples the facade's API surface from any individual backend's implementation. The facade offers the full union of all protocol methods, but each call is guarded by a runtime capability check. This means new backends can be added with partial protocol support without breaking existing code, and callers get immediate, descriptive errors rather than AttributeError or NotImplementedError exceptions when they attempt unsupported operations.

## StorageFacade and Core Operations

### What is StorageFacade and how do I use it?

StorageFacade is the primary user-facing class in the library. It provides a unified API for all storage operations, abstracting away the details of which backend handles each path. You interact with StorageFacade using methods like `read_bytes()`, `write_bytes()`, `read_stream()`, `write_stream()`, `list_files()`, `delete()`, `exists()`, `get_metadata()`, and `copy()`.

The facade accepts paths as strings with URL schemes (like `s3://bucket/key`, `file:///local/path`, or `https://example.com/file`) and uses the StorageRegistry and path detection to route each call to the appropriate backend. Internally, it checks that the target backend supports the requested protocol before dispatching the operation. This design means you write storage code once and it works across all backends.

### How does read_bytes work and what is the top-level helper?

The `read_bytes` method on StorageFacade reads the entire content of a file at a given path and returns it as bytes. The facade first resolves the path to the appropriate backend using path-driven provider detection, checks that the backend implements StorageReadProtocol via an isinstance check, and then delegates the actual read operation to the backend.

There is also a top-level `read_bytes` function that serves as a convenience helper. It creates or reuses a facade instance, resolves the path, and returns the file content in a single call. This is useful for quick one-off reads where you do not need to manage a facade instance. Both the method and the top-level helper support transform pipelines, so reading a `.gz` file can automatically decompress the content if a pipeline is inferred from the file suffix.

### What is the difference between read_bytes and read_stream?

`read_bytes` reads the entire file content into memory and returns it as a bytes object. This is convenient for small to medium files where holding the full content in memory is acceptable. `read_stream` returns a BinaryIO stream that you can read incrementally, which is essential for large files that would exceed available memory.

The stream-based approach also integrates with the transform pipeline system differently. When reading a stream with transforms, the pipeline wraps the underlying stream with transform layers (using the Unwrap method for read direction), allowing streaming decompression or decryption without buffering the entire file. The bytes-based approach applies transforms after reading all data. Choose `read_stream` for large files or when you need streaming processing, and `read_bytes` for simplicity with smaller files.

### How do write_bytes and write_stream work?

`write_bytes` accepts a bytes object and writes it to the specified path. The facade resolves the path to the appropriate backend, checks that StorageWriteProtocol is supported, and delegates the write. `write_stream` accepts a BinaryIO stream and writes its content to the destination, which is useful for large files or when data is being produced incrementally.

Both methods support transform pipelines. When writing with transforms, the pipeline applies them in write direction (using the Wrap method), so writing to a path ending in `.gz` can automatically compress the data. The Local and S3 backends both support Write protocol, but the HTTP backend does not, so attempting to write to an HTTP URL raises UnsupportedOperationError.

### How does the copy method work within StorageFacade?

The `copy` method on StorageFacade copies a file from one path to another. When both paths resolve to the same backend, the facade uses the backend's native StorageCopyProtocol implementation for an optimized copy. The Local backend uses filesystem copy, and the S3 backend uses S3 server-side copy, both avoiding unnecessary data transfer through the client.

For the same-backend case, this is significantly more efficient than reading and writing because the data never passes through the local process. The facade checks that the backend implements StorageCopyProtocol before attempting the native copy. If you need to copy between different backends (for example, from S3 to local), you should use the `copy_between` function instead, which handles the cross-backend streaming transfer.

### What is the Exists method and how does it relate to metadata?

The `exists` method on StorageFacade checks whether a file exists at the given path. It relies on StorageMetadataProtocol rather than having its own dedicated protocol, because checking existence is fundamentally a metadata operation. The method attempts to retrieve metadata for the path and returns True if metadata is available, or False if the file is not found.

This design avoids duplicating protocol definitions. All three backends support StorageMetadataProtocol, so `exists` works across Local, S3, and HTTP backends. For the Local backend, it checks the filesystem. For S3, it performs a HEAD request on the object. For HTTP, it performs a HEAD request on the URL. The exists check is lightweight because it only retrieves metadata without downloading file content.

### What is the from_path factory function?

The `from_path` factory function creates a StorageFacade instance configured for a specific path. It uses the path-driven provider detection system to determine which backend and configuration to use, then returns a ready-to-use facade. This is a convenience for cases where you know the specific path you want to work with and want the library to handle all setup automatically.

The function integrates with the StorageRegistry and the SCHEMES registry to resolve the URL scheme to a provider type, look up the registered backend class, and configure it with the appropriate settings. It simplifies the common case of "give me a facade that works for this path" into a single function call.

## Path Handling and Provider Detection

### How does StoragePath handle different URL schemes?

StoragePath is the path handling class that parses, normalizes, and provides scheme detection for storage paths. It accepts paths in various formats: local filesystem paths (`/home/user/file.txt`), S3 URLs (`s3://bucket/key`), HTTP URLs (`https://example.com/file`), and other registered scheme URLs. The class extracts the scheme component, normalizes the path, and provides methods for suffix detection and path joining.

StoragePath works with the SchemeSpec dataclass and the SCHEMES registry to map URL schemes to provider types. When a path is parsed, StoragePath identifies the scheme and looks up the corresponding SchemeSpec to determine which provider handles that scheme. This separation of path parsing from backend selection keeps the path logic reusable and independent of any specific backend implementation.

### What is the SCHEMES registry and how does scheme mapping work?

The SCHEMES registry is a mapping from URL scheme strings to SchemeSpec dataclass instances. Each SchemeSpec defines the scheme name, the provider type it maps to, and any normalization rules specific to that scheme. For example, the `s3` scheme maps to the S3 provider type, while `file` maps to the Local provider type.

The registry supports alias resolution, where multiple scheme strings can map to the same provider. This is how S3-family services are unified: schemes like `s3`, `r2`, and `minio` can all route to the S3 backend with appropriate flavor configuration. The registry is extensible, so new schemes can be registered for custom backends. The `identify_scheme` method on StoragePath uses this registry to determine the provider for any given path.

### How does path-driven provider detection work?

Path-driven provider detection is the mechanism by which the library automatically determines which storage backend should handle a given path. The process starts with StoragePath parsing the URL scheme from the path, then the `identify_scheme` method looks up the scheme in the SCHEMES registry to find the corresponding SchemeSpec. The `detect_provider_from_path` function then uses the SchemeSpec to determine the ProviderType.

Once the provider type is known, the StorageRegistry maps it to the registered backend class. This entire chain happens transparently when you use StorageFacade or the top-level `read_bytes` helper. You pass a path like `s3://my-bucket/data.csv` and the library automatically routes it to the S3StorageBackend with the AWS S3 flavor. This path-driven dispatch is what makes the unified API possible.

### What is alias resolution in the SCHEMES registry?

Alias resolution is the feature that allows multiple URL scheme strings to map to the same underlying provider type. This is particularly useful for S3-compatible services. Rather than requiring users to always use `s3://` for all S3-family services, the registry can map `r2://` to the S3 provider with the Cloudflare R2 flavor, and `minio://` to the S3 provider with the MinIO flavor.

When the `identify_scheme` method encounters a scheme string, it first checks for an exact match in the SCHEMES registry. If no exact match is found, it checks for registered aliases. This resolution is transparent to the user. The practical benefit is that paths are self-documenting: `r2://bucket/key` clearly indicates the file is on Cloudflare R2, even though it is handled by the same S3StorageBackend class with flavor-specific configuration.

### What is GenericSchemePath and when does it activate?

GenericSchemePath is a fallback mechanism that activates when a path's URL scheme is not found in the SCHEMES registry. Rather than raising an error immediately for unrecognized schemes, the path normalization system falls back to GenericSchemePath, which provides basic path handling without scheme-specific normalization rules.

This fallback enables forward compatibility. If a new storage backend is registered at runtime with a previously unknown scheme, paths using that scheme can still be parsed and normalized. GenericSchemePath preserves the scheme, authority, and path components of the URL without applying any scheme-specific transformations. It is a safety net that prevents the path system from being a bottleneck when extending the library with new backends.

### How does path joining work in StoragePath?

Path joining in StoragePath combines a base path with one or more relative path segments while preserving the URL scheme and normalization rules of the base path. For example, joining `s3://bucket/` with `subdir/file.txt` produces `s3://bucket/subdir/file.txt`. The joining logic is scheme-aware, so it handles the differences between local filesystem path separators and URL path conventions.

StoragePath also integrates with UPath, providing compatibility with the universal-pathlib library. This integration allows StoragePath instances to be used in contexts that expect pathlib-like objects, bridging the gap between the library's URL-scheme-based paths and Python's standard path handling conventions.

## Transforms and Pipelines

### What is the StreamTransform protocol?

StreamTransform is a Python protocol that defines the interface for composable stream transformations. It requires two methods: `wrap` and `unwrap`. The `wrap` method transforms a stream for writing (for example, compressing data before storage), and the `unwrap` method reverses the transformation for reading (for example, decompressing data after retrieval).

This bidirectional design is essential for transforms like compression and encryption where the read and write paths require inverse operations. By defining a standard protocol, any class that implements `wrap` and `unwrap` can be used in transform pipelines. The library ships with Gzip and GPG transforms, but custom transforms can be created by implementing the StreamTransform protocol.

### How does the Pipeline class work?

The Pipeline class manages an ordered collection of StreamTransform instances and applies them in the correct order for read or write operations. When writing, it applies transforms in forward order using each transform's `wrap` method: first compress (Gzip), then encrypt (GPG). When reading, it applies transforms in reverse order using each transform's `unwrap` method: first decrypt (GPG), then decompress (Gzip).

This automatic direction handling means you define the pipeline once with transforms in logical order (compression before encryption) and the Pipeline class handles reversing the order for reads. The `apply_read_direction` and `apply_write_direction` methods encapsulate this logic, ensuring transforms are always applied correctly regardless of the operation direction.

### What is the Gzip transform and how do I use it?

The Gzip transform implements the StreamTransform protocol for gzip compression and decompression. Its `wrap` method takes a BinaryIO stream and returns a new stream that compresses data as it is written. Its `unwrap` method takes a compressed stream and returns a stream that decompresses data as it is read.

You rarely need to use the Gzip transform directly. When a file path ends with `.gz`, the `infer_pipeline` function automatically includes the Gzip transform in the pipeline. So reading `s3://bucket/data.csv.gz` will automatically decompress the data, and writing to `/local/output.csv.gz` will automatically compress it. For explicit control, you can create a Gzip transform instance and add it to a Pipeline manually.

### What is the GPG transform and when should I use it?

The GPG transform implements the StreamTransform protocol for GPG encryption and decryption. Its `wrap` method encrypts data for writing, and its `unwrap` method decrypts data for reading. This transform is used when files need to be stored in encrypted form, which is common for sensitive data in cloud storage.

Like the Gzip transform, the GPG transform integrates with the suffix-based inference system. Files ending in `.gpg` will automatically have the GPG transform included in their pipeline. For files that are both compressed and encrypted (ending in `.csv.gz.gpg`), the `infer_pipeline` function creates a pipeline with both transforms in the correct order: Gzip first, then GPG for writing, and GPG first, then Gzip for reading.

### How does infer_pipeline automatically detect transforms from file suffixes?

The `infer_pipeline` function examines the suffixes of a file path and builds an appropriate Pipeline by consulting the Suffix Transforms Map. This map associates file extensions with their corresponding StreamTransform classes: `.gz` maps to Gzip and `.gpg` maps to GPG.

The function processes suffixes from right to left (outermost to innermost). For a file named `data.csv.gz.gpg`, it detects `.gpg` first, then `.gz`, and constructs a Pipeline where Gzip is applied before GPG on writes (matching the innermost-to-outermost order of the suffixes). This suffix-driven inference means developers do not need to manually configure transforms for common compression and encryption scenarios. The inference is automatic when using StorageFacade or the top-level helpers.

### What is the Materialize utility and when is it needed?

The Materialize utility converts a stream into a fully materialized bytes object or a seekable stream. This is necessary in certain situations where a transform pipeline produces a non-seekable stream but the downstream consumer (such as an S3 upload API) requires a seekable stream or needs to know the content length in advance.

Materialization involves reading the entire stream into memory, which trades memory usage for compatibility. It is typically used internally by the library when a backend requires seekable input. For most operations, the streaming pipeline works without materialization, but the utility provides a fallback when stream characteristics do not match backend requirements.

### What is the PairedStream helper?

PairedStream is a helper class that connects a read stream to a write stream through a shared buffer or pipe mechanism. It is used internally when transform pipelines need to bridge between a stream being read (such as from a source backend) and a stream being written (such as to a destination backend) with transforms applied in between.

The PairedStream helper works with the `read_stream` method on StorageFacade to enable streaming transforms without buffering the entire file in memory. It is an implementation detail that most users will not interact with directly, but it is essential for the library's ability to handle large files efficiently through transform pipelines.

### How do I create a custom StreamTransform?

To create a custom StreamTransform, implement a class with `wrap` and `unwrap` methods that conform to the StreamTransform protocol. The `wrap` method should accept a BinaryIO stream and return a new BinaryIO stream that applies the transformation for writing. The `unwrap` method should accept a BinaryIO stream and return a new BinaryIO stream that reverses the transformation for reading.

Once implemented, you can add your custom transform to a Pipeline alongside built-in transforms like Gzip and GPG. For automatic suffix-based inference, add an entry to the Suffix Transforms Map associating your file extension with your transform class. This extensibility is a direct benefit of the protocol-driven architecture: any class satisfying the StreamTransform protocol works with the entire pipeline system.

## Backends and S3 Flavors

### How does the Local backend implement all 8 protocols?

The LocalStorageBackend class achieves full 8-protocol coverage through mixin composition. It inherits from 8 separate mixin classes: LocalConnectionMixin (verifies directory access), LocalReadMixin (reads files from disk), LocalWriteMixin (writes files to disk), LocalListMixin (lists directory contents), LocalDeleteMixin (deletes files), LocalMetadataMixin (retrieves file size, timestamps, and attributes), LocalCopyMixin (copies files using filesystem operations), and LocalDirectoryMixin (creates and removes directories).

Each mixin implements exactly one protocol, keeping the code modular and testable. The LocalStorageBackend class simply composes all 8 mixins and registers itself with the StorageRegistry. This is the only backend that implements StorageDirectoryProtocol, because local filesystems have true directory semantics that S3 and HTTP lack.

### How does the S3 backend unify five different S3-compatible services?

The S3StorageBackend class uses a flavor dispatch mechanism to handle AWS S3, S3 Express One Zone, Cloudflare R2, MinIO, and Backblaze B2 through a single codebase. Each S3-compatible service has slightly different behaviors (endpoint URLs, authentication patterns, API quirks), and the flavor system encapsulates these differences.

When an S3 backend is instantiated, the flavor is determined from the provider settings or URL scheme. The S3 Flavor Dispatch mechanism selects the appropriate configuration: AWS S3 uses standard AWS endpoints, S3 Express uses zone-specific endpoints, R2 uses Cloudflare account-specific endpoints, MinIO uses custom endpoints, and B2 uses Backblaze-specific settings. The boto3 client is configured according to the selected flavor, but all operations use the same mixin implementations, ensuring consistent behavior across all five services.

### What S3 protocols are supported and which one is missing?

The S3 backend implements 7 of the 8 storage protocols: Connection (via S3ConnectionMixin and boto3 client), Read (via S3ReadMixin), Write (via S3WriteMixin), List (via S3ListMixin), Delete (via S3DeleteMixin), Metadata (via S3MetadataMixin), and Copy (via S3CopyMixin). The missing protocol is StorageDirectoryProtocol.

S3 lacks Directory protocol support because S3 object storage does not have true directory semantics. In S3, directories are simulated through key prefixes: a "folder" is just a common prefix shared by multiple object keys. Creating or deleting a "directory" in S3 has no meaningful equivalent to filesystem directory operations. The library accurately reflects this by not implementing the Directory protocol for S3, and the facade's protocol-checked dispatch will raise UnsupportedOperationError if you attempt directory operations on S3 paths.

### What are the differences between the S3 flavors?

The five S3 flavors handle service-specific differences in endpoints, authentication, and behavior. AWS S3 is the standard flavor using default AWS endpoints and IAM credentials. S3 Express One Zone targets the low-latency, single-availability-zone storage class with zone-specific endpoints and different pricing characteristics. Cloudflare R2 uses account-specific endpoints and has no egress fees, with some API differences from standard S3.

MinIO targets self-hosted or managed MinIO deployments with custom endpoint URLs and optional TLS configuration. Backblaze B2 uses B2-specific endpoints and has its own authentication mechanism. The flavor dispatch system means developers do not need to know these differences: they configure their provider settings once, and the S3StorageBackend handles the rest transparently.

### How does the HTTP backend work and what are its limitations?

The HTTPStorageBackend class provides read-only access to files served over HTTP and HTTPS. It implements only 3 of 8 protocols: Connection (establishing an httpx client session), Read (downloading file content via GET requests), and Metadata (retrieving file information via HEAD requests, including content type and size from HTTP headers).

The HTTP backend does not support Write, List, Delete, Copy, or Directory operations because standard HTTP endpoints do not provide these capabilities. This means you can use the HTTP backend to download files and check their existence, but not to upload, delete, or manage files. The HTTP Error Mapping component translates HTTP status codes into appropriate library exceptions, providing consistent error handling.

### What is the HTTPx client and why is it used instead of requests?

The HTTP backend uses the httpx client library rather than the more widely known requests library. Httpx provides both synchronous and asynchronous HTTP client capabilities, with a modern API that supports HTTP/2, connection pooling, and streaming responses. Its streaming support is particularly important for the library's stream-based read operations, where large files need to be downloaded incrementally without loading the entire response into memory.

The httpx client is configured as part of the HTTP Connection support, establishing a session with appropriate timeout settings and connection parameters. The HTTP backend wraps httpx responses to conform to the StorageReadProtocol and StorageMetadataProtocol interfaces, mapping HTTP-specific concepts (status codes, headers, content-type) to the library's abstract metadata model.

### How do I add a new storage backend?

To add a new storage backend, follow the mixin and protocol pattern used by the existing backends. First, identify which of the 8 storage protocols your backend will support. For each supported protocol, create a mixin class that implements the protocol's methods. Then create a backend class that inherits from all your mixin classes.

Register your backend with the StorageRegistry using the registry decorator, specifying the provider type and supported URL schemes. Add the schemes to the SCHEMES registry with appropriate SchemeSpec entries so that path-driven provider detection can route to your backend. Create a settings class extending StorageAuthBase for any authentication or configuration your backend requires. The protocol-driven architecture ensures your new backend integrates seamlessly with StorageFacade without modifying any existing code.

## Settings, Configuration, and Registry

### What is StorageAuthBase and how does it handle credentials?

StorageAuthBase is the base Pydantic model for all storage provider settings. It defines common fields that all providers share, including the provider type (an enum indicating Local, S3, HTTP, or custom providers), authentication method, and access type. Each storage backend extends StorageAuthBase with provider-specific fields: S3 settings include AWS credentials, endpoint URLs, and region; HTTP settings include headers and authentication tokens.

The settings system uses Pydantic for validation, ensuring that configuration values are type-checked and constrained before they reach the backend. StorageAuthBase also supports settings profiles, allowing multiple named configurations for the same provider type. This is useful for managing different environments (development, staging, production) or different accounts within the same provider.

### What are Settings Adapters and why are they needed?

Settings Adapters transform storage settings from the library's normalized format into the specific format expected by each backend's client library. For example, the S3 backend uses boto3, which expects credentials in a specific structure (access key, secret key, session token, region, endpoint URL). The settings adapter takes a StorageAuthBase-derived settings object and produces the dictionary or configuration object that boto3 expects.

Adapters are necessary because the library's settings model is designed for consistency and user convenience, while each client library has its own configuration format. Without adapters, settings classes would need to mirror the exact structure of each client library, making the configuration API inconsistent across providers. The adapter layer keeps the user-facing settings clean and handles the translation to library-specific formats internally.

### How does the StorageRegistry work?

The StorageRegistry maintains a mapping from provider types to backend classes. Backends register themselves using a decorator pattern, associating a provider type and supported URL schemes with the backend class. When StorageFacade needs to handle a path, it uses the path-driven detection system to determine the provider type, then looks up the corresponding backend class in the registry.

The registry supports runtime registration, meaning new backends can be added after the library is imported. This enables plugin-like extensibility where third-party packages can register custom backends. The decorator-based registration pattern keeps the registry populated automatically when backend modules are imported, without requiring manual registration code.

### What is the Provider Type Enum and how does it relate to flavors?

The Provider Type Enum defines the recognized storage provider categories in the library. Each enum value represents a distinct provider type (Local, S3, HTTP, and potentially custom types). The enum is used throughout the settings system, registry, and path detection to identify and route to the correct backend.

For the S3 backend, the Provider Type Enum works together with the S3 Flavor Dispatch system. While the enum identifies the broad category (S3), the flavor system handles the variations within that category (AWS, Express, R2, MinIO, B2). This two-level identification allows the registry to map all S3-family services to a single backend class, while the flavor dispatch handles the service-specific differences internally.

### What is the Settings Descriptor and how does it work?

The Settings Descriptor is a Python descriptor that provides attribute-level access to storage settings within backend classes. It acts as a bridge between the settings system and the backend implementation, allowing backend code to access configuration values through simple attribute access rather than manual settings lookup.

The descriptor handles settings resolution, including profile selection, default values, and validation. When a backend accesses a setting through the descriptor, it resolves the current profile, retrieves the value from the settings object, and returns it in the appropriate type. This pattern keeps backend code clean and focused on storage operations rather than configuration management.

### What are Settings Profiles and when would I use multiple profiles?

Settings Profiles allow you to define multiple named configurations for the same provider type. Each profile contains a complete set of settings (credentials, endpoints, options) identified by a name. This is useful when you need to work with multiple accounts or environments within the same application.

For example, you might have a "production" profile pointing to your main S3 bucket with production credentials, a "staging" profile pointing to a test bucket, and a "archive" profile pointing to a cold storage bucket. Profiles can also represent different S3-compatible services: an "aws" profile for standard S3 and an "r2" profile for Cloudflare R2. The settings system resolves the active profile based on configuration, allowing the same code to work with different storage targets.

### How does cross-backend copy work with copy_between?

The `copy_between` function handles copying files between different storage backends. Unlike the `copy` method on StorageFacade (which uses native same-backend copy), `copy_between` reads data from the source backend and writes it to the destination backend. It streams the data through the local process, applying any necessary transforms from the source and destination pipelines.

For example, copying from `s3://source-bucket/data.csv.gz` to `/local/data.csv` would read from S3, decompress the gzip content, and write the plain CSV to the local filesystem. The function handles the transform pipeline logic for both the source (read direction) and destination (write direction) paths. While less efficient than native same-backend copy (because data passes through the client), it is the only way to move files between different provider types.

### What is FileMetadata and what information does it provide?

FileMetadata is the data structure returned by the `get_metadata` method on StorageFacade. It provides a normalized view of file attributes across all backends, including file size in bytes, last modification timestamp, content type (MIME type), and backend-specific additional attributes.

The normalization is important because each backend represents metadata differently. Local filesystem metadata comes from `os.stat()` calls with POSIX attributes. S3 metadata comes from HEAD object responses with S3-specific headers. HTTP metadata comes from HEAD response headers with content-type and content-length. FileMetadata presents these in a consistent structure, so code that processes file metadata does not need to handle backend-specific formats. The `exists` method on StorageFacade leverages this metadata system to check file existence across all backends.
