# Glossary

Definitions of the terms used in the mountainash-transport documentation, sorted alphabetically. Each entry links to the section that explains the term in full.

## Auth profile

A credential description from `mountainash-auth-client`, such as `IAMAuthProfile`, `PasswordAuthProfile` or `OAuth2AuthProfile`, that renders its credentials for a target client library. Transport pairs it with a storage profile when it builds a connection and defines no credential fields of its own.

Related: [Storage profile](#storage-profile), [Credential delegation](#credential-delegation), [Target family](#target-family).

Explained in [Auth profiles](chapters/05-storage-profiles/index.md#auth-profiles).

## Backend divergence

A behaviour that differs between backends because each keeps its store's own semantics instead of emulating the others. Documented cases include `rmdir` removing a non-empty local directory but failing on SFTP, SFTP buffering stream writes in memory, single-request S3 copy and S3 listing with a limit.

Related: [Support matrix](#support-matrix).

Explained in [Where backends differ](chapters/14-backends/index.md#where-backends-differ).

## Backend error mapping

The translation each backend applies around its native SDK calls, turning exceptions such as `FileNotFoundError`, botocore `NoSuchKey` or a paramiko `ENOENT` into `StorageError` subclasses raised from the original, so the native exception stays available as `__cause__`.

Related: [Error families](#error-families), [`StorageError`](#storageerror).

Explained in [Backend error mapping](chapters/14-backends/index.md#backend-error-mapping).

## Backend registry

The process-wide mapping from `CONST_STORAGE_PROVIDER_TYPE` members to backend classes. The built-in backends register before any lookup or registration, a facade creates a new instance of the registered class, and a later registration for the same provider type replaces the earlier one.

Related: [`register_storage_backend`](#register_storage_backend), [`get_storage_backend`](#get_storage_backend), [`STORAGE_REGISTRY`](#storage_registry).

Explained in [The backend registry](chapters/13-architecture/index.md#the-backend-registry).

## `BackendNotImplementedError`

The `StorageError` subclass raised when a recognised provider type has no registered backend, as for the settings-only providers. `StorageFacade.from_path` without a storage profile raises it before any connection is made, `get_storage_backend` raises it too, and its message lists the implemented provider types. A facade constructed with a settings-only provider's storage profile fails earlier with `TransportConnectionError`, because `create_connection` falls back to an HTTP connection; see [Settings-only providers](reference/support-matrix.md#settings-only-providers).

Related: [Settings-only provider](#settings-only-provider), [Backend registry](#backend-registry).

Explained in [BackendNotImplementedError](chapters/05-storage-profiles/index.md#backendnotimplementederror).

## Base install

The package installed without extras, whose only runtime dependency is `typing-extensions`. It covers local storage through `StorageFacade`, the `Gzip` transform, `Pipeline`, `infer_pipeline`, `LocationPolicy` and the error classes. Remote backends, profiles and connections need extras.

Related: [Optional extras](#optional-extras), [`MissingExtraError`](#missingextraerror), [Slim install test](#slim-install-test).

Explained in [The base install](chapters/03-installation/index.md#the-base-install).

## Bastion tunnel

An SSH route to a private service through a reachable jump host. `create_tunnelled_connection` builds a `TunnelledConnection` that connects to the bastion, starts a listener on `127.0.0.1` that forwards each connection to the remote host and port through the bastion, and connects an inner connection to that listener.

Related: [Decorator connection](#decorator-connection), [`SSHConnection`](#sshconnection).

Explained in [Bastion tunnels](chapters/11-connections/index.md#bastion-tunnels).

## Binary stream

A file-like object whose `read(n)` returns up to `n` bytes and `b""` at the end, like a file opened with `open(path, "rb")` or an `io.BytesIO`. `read_stream` returns one and `write_stream` consumes one, so data can flow through without being held in memory at once.

Related: [`read_stream` and `write_stream`](#read_stream-and-write_stream).

Explained in [Bytes and streams](chapters/01-what-transport-does/index.md#bytes-and-streams).

## Buffered access

The read access mode, selected with `access="buffered"`, that reads and decodes the whole object before `read_stream()` returns a seekable in-memory buffer. Every transfer and decoding error surfaces in that call, and the buffer stays usable after the facade closes.

Related: [Read access mode](#read-access-mode), [`materialize`](#materialize).

Explained in [Buffered access](chapters/09-read-access-modes/index.md#buffered-access).

## Byte storage endpoint

Any place that holds named sequences of bytes and lets a program fetch or store them by name: a local directory, an S3 bucket, a directory on an SFTP server or a web server that answers `GET` requests. Transport puts the same `StorageFacade` methods in front of each.

Related: [`StorageFacade`](#storagefacade), [URL scheme](#url-scheme).

Explained in [Byte storage endpoints](chapters/01-what-transport-does/index.md#byte-storage-endpoints).

## Capability check

A call to `facade.supports(protocol)` that reports whether the facade's backend implements a storage protocol. Code that accepts any store uses it to pick a fallback; calling an unsupported operation instead raises `UnsupportedOperationError` before any I/O.

Related: [Storage protocol](#storage-protocol), [`UnsupportedOperationError`](#unsupportedoperationerror).

Explained in [Checking before you call](chapters/06-storage-facade/index.md#checking-before-you-call).

## Capability mixin

A class that implements one storage protocol for one backend, such as `S3ReadMixin` or `S3CopyMixin`. Each built-in backend class inherits one mixin per capability, so its protocol set is the union of its mixins, which share state through attributes the backend class sets up.

Related: [Storage protocol](#storage-protocol), [Conformance tests](#conformance-tests).

Explained in [Composing backends from mixins](chapters/13-architecture/index.md#composing-backends-from-mixins).

## Conformance tests

The maintainer tests in `tests/storage/protocols/test_backend_conformance.py` that assert each registered backend class implements exactly its expected storage protocols, so a mixin added or removed by accident fails a test. Protocol shapes and random-read behaviour are tested in separate files.

Related: [Registry completeness tests](#registry-completeness-tests), [Support matrix](#support-matrix).

Explained in [Conformance tests](chapters/15-maintaining/index.md#conformance-tests).

## `ConnectionProtocol`

The interface every connection implements: `connect()` acquires a native client and returns the connection, `disconnect()` releases everything it owns and is safe to repeat, and `client` and `is_connected` expose the current state. Leaving a `with` block disconnects; entering it does not connect.

Related: [Leaf connection](#leaf-connection), [Decorator connection](#decorator-connection), [`create_connection`](#create_connection).

Explained in [Opening and closing](chapters/06-storage-facade/index.md#opening-and-closing).

## `copy`

The facade method that copies one file to another path in the same store using the store's own mechanism: `shutil.copy2` on local disk and a server-side copy on the S3 family. SFTP and HTTP stores raise `UnsupportedOperationError` for it.

Related: [`copy_between`](#copy_between), [`StorageCopyProtocol`](#storagecopyprotocol).

Explained in [Copying](chapters/07-file-operations/index.md#copying).

## `copy_between`

The function that copies one file between two open facades, possibly on different backends, by streaming the source's `read_stream` into the destination's `write_stream`. Optional source and destination pipelines decode and encode during the copy, and both facades stay open afterwards.

Related: [`copy`](#copy), [`Pipeline`](#pipeline).

Explained in [Copying between backends](chapters/10-stream-transforms/index.md#copying-between-backends).

## `create_connection`

The factory that builds an unconnected connection from a storage profile and an optional auth profile. It checks the auth mode against the provider's `supported_auth`, picks the connection class from the provider type and emits the SDK arguments, all without network I/O.

Related: [`ConnectionProtocol`](#connectionprotocol), [Emission](#emission), [Target family](#target-family).

Explained in [create_connection](chapters/11-connections/index.md#create_connection).

## Credential delegation

The division of work in which storage profiles describe a store without credentials, and credentials arrive separately as an auth profile from `mountainash-auth-client`. Transport checks the pair against the provider's `supported_auth` and combines them only when it builds a connection.

Related: [Auth profile](#auth-profile), [Emission](#emission), [`mountainash-auth-client`](#mountainash-auth-client).

Explained in [How transport delegates credentials](chapters/02-mountainash-ecosystem/index.md#how-transport-delegates-credentials).

## Credential redaction (HTTP engine)

The HTTP request engine's replacement of URL userinfo with `***` in every `HttpTransportError` message and in the `url` attribute of responses and response errors. When userinfo is present, the engine also drops the displayed cause, so a traceback does not print the native httpx exception.

Related: [`HttpTransportError`](#httptransporterror), [Credential redaction (location policy)](#credential-redaction-location-policy).

Explained in [Error redaction](chapters/12-http-engine/index.md#error-redaction).

## Credential redaction (location policy)

The removal of user name and password from a URL before `LocationNotAllowed` stores it in `location` or its message. A URL that cannot be parsed is reported as `invalid location` without chaining the parser's exception. Errors raised without an active policy may still quote the path as given.

Related: [`LocationNotAllowed`](#locationnotallowed), [Credential redaction (HTTP engine)](#credential-redaction-http-engine).

Explained in [Credential redaction](chapters/08-location-policy/index.md#credential-redaction).

## Decorator connection

A connection that wraps and exclusively owns another connection and adds a layer to it, such as an SFTP channel or a network tunnel. Its `connect()` connects the inner connection first, and its `disconnect()` removes its own layer before disconnecting the inner one. `SFTPConnection` and `TunnelledConnection` are the two provided.

Related: [Leaf connection](#leaf-connection), [Bastion tunnel](#bastion-tunnel).

Explained in [Decorator connections](chapters/11-connections/index.md#decorator-connections).

## Deferred read error

A failure that surfaces after `read_stream()` has returned, during `read()` or `close()`, because sequential transfers, lazy transform decoding and random-mode range fetches happen while the data is consumed. Buffered access raises such errors when the stream is opened instead.

Related: [Read access mode](#read-access-mode), [Stream ownership](#stream-ownership).

Explained in [Deferred read errors](chapters/09-read-access-modes/index.md#deferred-read-errors).

## `delete`

The facade method that removes one file or object, never a directory. A missing path raises `PathNotFoundError` on local and SFTP stores, while deleting an absent S3 key succeeds silently. HTTP stores do not support it.

Related: [`StorageDeleteProtocol`](#storagedeleteprotocol), [Directory operations](#directory-operations).

Explained in [Deleting, directories and parent creation](chapters/07-file-operations/index.md#deleting-directories-and-parent-creation).

## Directory operations

The facade methods `list_dir`, `mkdir` and `rmdir`, available on local and SFTP stores, which have real directories. The S3 family and HTTP raise `UnsupportedOperationError` for them, because object keys and URLs have no directories to manage.

Related: [`StorageDirectoryProtocol`](#storagedirectoryprotocol), [Backend divergence](#backend-divergence), [Parent creation](#parent-creation).

Explained in [Directory operations](chapters/07-file-operations/index.md#directory-operations).

## Emission

The step that turns a storage profile and an auth profile into keyword arguments for one SDK. The storage profile emits its configuration for a target family, and the auth profile layers its credentials on top, without either knowing the other's fields.

Related: [Target family](#target-family), [`create_connection`](#create_connection).

Explained in [How profiles become SDK arguments](chapters/05-storage-profiles/index.md#how-profiles-become-sdk-arguments).

## Error families

The three exception hierarchies transport raises in place of native library errors, one per layer and with no shared base class: `StorageError` for facades, backends, profiles and location policy, `TransportConnectionError` for connections, and `HttpTransportError` for the HTTP request engine.

Related: [`StorageError`](#storageerror), [`TransportConnectionError`](#transportconnectionerror), [`HttpTransportError`](#httptransporterror).

Explained in [The error families](chapters/03-installation/index.md#the-error-families).

## Facade dispatch

The fixed sequence a `StorageFacade` follows for each operation: confirm the facade is open and the backend implements the operation's protocol, apply the location policy to the path, resolve the transform pipeline for reads and writes, and call the backend method.

Related: [Scheme dispatch](#scheme-dispatch), [Facade policy check](#facade-policy-check).

Explained in [How the facade dispatches](chapters/13-architecture/index.md#how-the-facade-dispatches).

## Facade lifecycle

The constructing, open and closed states of a `StorageFacade`. The facade owns the connection it created and releases it on `close()` or at the end of its `with` block. A failed construction releases partial resources, and closing a closed facade does nothing.

Related: [`StorageFacade`](#storagefacade), [`ConnectionProtocol`](#connectionprotocol).

Explained in [Facade lifecycle](chapters/06-storage-facade/index.md#facade-lifecycle).

## Facade policy check

The facade's application of its location policy to every operation that takes a path, including both ends of `copy`, before the backend is called. The policy is fixed when the facade is created, and `copy_between` checks each path against its own facade's policy.

Related: [`LocationPolicy`](#locationpolicy), [Facade dispatch](#facade-dispatch).

Explained in [Policy on the facade](chapters/08-location-policy/index.md#policy-on-the-facade).

## `for_local`

The `StorageFacade` class method that opens a facade on the local filesystem without a storage profile or connection, so construction cannot fail on the network. An optional `policy` confines it to a directory tree.

Related: [`from_path`](#from_path), [Root confinement](#root-confinement).

Explained in [for_local()](chapters/06-storage-facade/index.md#for_local).

## Format-agnostic storage

The design rule that transport holds no knowledge of file formats: it has no dependency on PyArrow, polars or pandas and never picks an access mode from a file extension. The consumer chooses how to read and catches typed errors to fall back.

Related: [Read access mode](#read-access-mode), [`mountainash-files`](#mountainash-files).

Explained in [Format-agnostic storage](chapters/02-mountainash-ecosystem/index.md#format-agnostic-storage).

## Forward-only stream

The non-seekable stream a sequential read returns from S3, SFTP or HTTP. It is wrapped in `io.BufferedReader`, so it requests data only as the caller reads and reads at most one buffer (8 KiB by default) ahead of the caller, and it translates errors raised partway through into `StorageError` subclasses with the native exception as cause.

Related: [Sequential access](#sequential-access), [Deferred read error](#deferred-read-error).

Explained in [Sequential stream adapters](chapters/14-backends/index.md#sequential-stream-adapters).

## `from_path`

The `StorageFacade` class method that reads a path's URL scheme, maps it to a provider type and constructs the facade with the remaining arguments. An unrecognised scheme raises `ValueError`, and a recognised scheme without a backend raises `BackendNotImplementedError`.

Related: [Scheme dispatch](#scheme-dispatch), [`for_local`](#for_local).

Explained in [from_path()](chapters/06-storage-facade/index.md#from_path).

## `get_storage_backend`

The package-root function that resolves a provider type to a new backend instance. A registered class is instantiated, a valid provider type without a registered class raises `BackendNotImplementedError`, and any other value raises `ValueError`.

Related: [Backend registry](#backend-registry), [`register_storage_backend`](#register_storage_backend).

Explained in [Backend lookup](chapters/13-architecture/index.md#backend-lookup).

## `GPG`

The stream transform that encrypts on `wrap()` and decrypts on `unwrap()` through `python-gnupg`. It needs the `[encryption]` extra and a `gpg` binary, takes recipients and keyring settings, and buffers internally instead of streaming. Key management stays with the gpg keyring.

Related: [`StreamTransform`](#streamtransform), [`Gzip`](#gzip), [Suffix inference](#suffix-inference).

Explained in [GPG](chapters/10-stream-transforms/index.md#gpg).

## `Gzip`

The standard-library stream transform that compresses on `wrap()` and decompresses on `unwrap()`, both lazily as the result is read. It works on a base install, writes a fixed header time by default for reproducible output, and bounds decoded size with `max_decompressed_bytes`. On writes, it closes the source stream it compressed.

Related: [`StreamTransform`](#streamtransform), [`GPG`](#gpg), [`TransformError`](#transformerror).

Explained in [Gzip](chapters/10-stream-transforms/index.md#gzip).

## `HTTPConnection`

The leaf connection that creates an `httpx.Client` from emitted profile and auth arguments: timeouts, redirect settings, TLS verification, headers and credentials. Its `connect()` performs no network I/O, and it carries no base URL, so requests use absolute URLs.

Related: [Leaf connection](#leaf-connection), [`HttpRequestEngine`](#httprequestengine).

Explained in [HTTPConnection](chapters/11-connections/index.md#httpconnection).

## `HttpRequestEngine`

The request layer that sends HTTP requests through a caller-owned `httpx.Client` and adds retries, timeouts, redirect limits, refreshable authentication, per-URL location checks and typed errors. `request()` returns a buffered `HttpResponse`, and `stream()` yields an `HttpStreamResponse`.

Related: [`RequestPolicy`](#requestpolicy), [`HttpResponse`](#httpresponse), [`RefreshableAuthStrategy`](#refreshableauthstrategy).

Explained in [Making requests](chapters/12-http-engine/index.md#making-requests).

## `HttpResponse`

The frozen result of `HttpRequestEngine.request()`, holding `status_code`, `headers`, `content`, the final `url` and `method`, with `text` and `json()` helpers. `HttpStreamResponse` carries the same metadata and reads the body incrementally. Only 2xx responses are returned.

Related: [`HttpRequestEngine`](#httprequestengine), [`HttpTransportError`](#httptransporterror).

Explained in [Responses and errors](chapters/12-http-engine/index.md#responses-and-errors).

## `HTTPStorageBackend`

The backend for `http://` and `https://` paths, which sends every request through `HttpRequestEngine`. It implements read (`GET`), write (`PUT`), metadata (`HEAD`) and ranged read, and is the only backend that accepts an auth strategy and a per-request location check.

Related: [`HTTPStorageProfile`](#httpstorageprofile), [Support matrix](#support-matrix).

Explained in [HTTP](chapters/14-backends/index.md#http).

## `HTTPStorageProfile`

The storage profile for HTTP(S), which describes an httpx client rather than a server: connect, read and write timeouts, redirect handling, TLS verification, headers and range settings. Each path supplies its URL, and a default profile applies when none is given.

Related: [Storage profile](#storage-profile), [`HTTPConnection`](#httpconnection).

Explained in [HTTP profile](chapters/05-storage-profiles/index.md#http-profile).

## `HttpTransportError`

The root of the HTTP request engine's exception family. Responses other than 2xx raise `HttpResponseError` subclasses such as `HttpNotFoundError`, and failures to complete a request raise classes such as `HttpConnectionError` and `HttpTimeoutError`. Through a facade, these become storage errors.

Related: [Error families](#error-families), [Credential redaction (HTTP engine)](#credential-redaction-http-engine).

Explained in [Responses and errors](chapters/12-http-engine/index.md#responses-and-errors).

## `implemented` flag

The `StorageProfileSpec` field that records whether a backend exists for a provider: `True` for local, S3, SFTP and HTTP, and `False` for the settings-only providers. Dispatch consults the backend registry instead, and a test keeps the two in agreement.

Related: [Settings-only provider](#settings-only-provider), [Registry completeness tests](#registry-completeness-tests).

Explained in [The implemented flag](chapters/05-storage-profiles/index.md#the-implemented-flag).

## Lazy package root

The package root's on-demand resolution of public names through a module `__getattr__` (PEP 562). Importing `mountainash_transport` loads almost nothing, and each name imports its own module on first access, so local-only code never imports httpx or the cloud SDKs.

Related: [Base install](#base-install).

Explained in [The lazy package root](chapters/03-installation/index.md#the-lazy-package-root).

## Leaf connection

A connection that wraps exactly one SDK client and depends on no other connection: `HTTPConnection`, `S3Connection`, `SSHConnection` or `NullConnection`. Decorator connections build their layers on top of leaf connections.

Related: [`ConnectionProtocol`](#connectionprotocol), [Decorator connection](#decorator-connection).

Explained in [Leaf connections](chapters/11-connections/index.md#leaf-connections).

## `list_objects`

The facade method that lists a store under a prefix and returns an `EnumerateResult` whose `objects` and `common_prefixes` are tuples of `StorageEntry`. The default `"/"` delimiter lists one level and `delimiter=None` recurses. On S3 the prefix is a literal key prefix; on local and SFTP it is an exact path.

Related: [`StorageEntry`](#storageentry), [`StorageEnumerateProtocol`](#storageenumerateprotocol), [Object storage](#object-storage).

Explained in [Listing and metadata](chapters/07-file-operations/index.md#listing-and-metadata).

## `LocalStorageBackend`

The standard-library backend for local paths and `file://` URLs, the one backend available on a base install. It implements every storage protocol except `RangedReadProtocol`, serves random access from the native file handle, and translates `OSError` into storage errors.

Related: [Native local handle](#native-local-handle), [`LocalStorageProfile`](#localstorageprofile).

Explained in [Local](chapters/14-backends/index.md#local).

## `LocalStorageProfile`

The storage profile for local disk, with `ROOT_PATH` and `CREATE_PATH` fields. A facade opened with a `ROOT_PATH` uses that directory as its location policy root unless the caller's policy sets its own root or disables confinement.

Related: [Root confinement](#root-confinement), [`LocationPolicy`](#locationpolicy).

Explained in [The local profile](chapters/08-location-policy/index.md#the-local-profile).

## `LocationNotAllowed`

The `StorageError` subclass raised when a location policy refuses a path, before the backend is called. It is imported from `mountainash_transport.location` and carries `location`, with credentials removed, and `reason`, a short code such as `outside root` or `remote not allowed`.

Related: [`LocationPolicy`](#locationpolicy), [Credential redaction (location policy)](#credential-redaction-location-policy).

Explained in [LocationNotAllowed](chapters/08-location-policy/index.md#locationnotallowed).

## `LocationPolicy`

A frozen dataclass, passed as `policy=` to a facade, that limits where the facade may reach: `root` confines local paths, `allowed_remote` lists hosts or buckets per URL scheme, and `allow_unconfined=True` disables checking. A facade without a policy checks no paths.

Related: [Root confinement](#root-confinement), [Remote allow-list](#remote-allow-list), [Facade policy check](#facade-policy-check).

Explained in [LocationPolicy](chapters/08-location-policy/index.md#locationpolicy).

## `materialize`

A helper that drains a stream into a seekable buffer and returns the buffer with its length, held either in memory or in a spooled temporary file that moves to disk beyond `memory_cutoff`. It is imported from `mountainash_transport._core.transforms.util`, not the package root.

Related: [Buffered access](#buffered-access).

Explained in [materialize](chapters/09-read-access-modes/index.md#materialize).

## Metadata queries

The facade methods `exists`, `get_size` and `metadata`, which answer questions about one path without reading it. `exists` returns `False` only when absence is established, `get_size` raises `PathNotFoundError` for a missing path, and `metadata` returns a `StorageEntry`.

Related: [`StorageEntry`](#storageentry), [`StorageMetadataProtocol`](#storagemetadataprotocol).

Explained in [Metadata queries](chapters/07-file-operations/index.md#metadata-queries).

## `MissingExtraError`

The error raised when a feature needs a package from the `[http]` dependency stack that is not installed. It subclasses both `StorageError` and `ImportError`, and its `extra` and `feature` attributes name the extra to install and the feature that needed it.

Related: [Optional extras](#optional-extras), [Base install](#base-install).

Explained in [MissingExtraError](chapters/03-installation/index.md#missingextraerror).

## Mountainash ecosystem

The set of Python packages that split data work by responsibility, each depending only on packages beneath it. Around transport sit `mountainash-settings` for configuration, `mountainash-auth-client` for credentials, and `mountainash-files` and `mountainash` as consumers that interpret the bytes.

Related: [Responsibility boundary](#responsibility-boundary).

Explained in [The Mountainash packages](chapters/02-mountainash-ecosystem/index.md#the-mountainash-packages).

## `mountainash` (package)

The Mountainash package for cross-backend data frame expressions, relations and schema management. It requires transport directly, reads data resources by format through `mountainash-files`, and conforms data to a target schema. To transport it is a consumer of bytes, streams and typed errors.

Related: [Mountainash ecosystem](#mountainash-ecosystem), [`mountainash-files`](#mountainash-files).

Explained in [mountainash relations readers](chapters/02-mountainash-ecosystem/index.md#mountainash-relations-readers).

## `mountainash-auth-client`

The Mountainash package that owns credentials: auth profiles that render credentials for each target family, OAuth 1.0a and 2.0 flows, and token managers. Transport depends on it through the `[http]` extra and uses its output to configure clients.

Related: [Auth profile](#auth-profile), [Credential delegation](#credential-delegation).

Explained in [mountainash-auth-client](chapters/02-mountainash-ecosystem/index.md#mountainash-auth-client).

## `mountainash-files`

The Mountainash package that parses and writes file formats from registered format specs, returning Arrow tables for tabular data. It reaches storage only through transport's package-root API and decides how each format reads its source.

Related: [Format-agnostic storage](#format-agnostic-storage), [Mountainash ecosystem](#mountainash-ecosystem).

Explained in [mountainash-files](chapters/02-mountainash-ecosystem/index.md#mountainash-files).

## `mountainash-settings`

The Mountainash package that loads configuration from environment variables, files and secret stores, and provides the `Profile` base class, `ProfileSpec` metadata and `Registry`. Transport's storage profiles, specs and profile registry are built on these.

Related: [Storage profile](#storage-profile), [`STORAGE_REGISTRY`](#storage_registry), [Named profile](#named-profile).

Explained in [Configuration comes from settings](chapters/02-mountainash-ecosystem/index.md#configuration-comes-from-settings).

## Named profile

A storage profile and its credentials declared by name in a configuration file's `storage_profiles:` section, with a `provider`, `parameters` and an optional `auth` block. Secret references in it are resolved by `mountainash-settings`, and `resolve_storage` loads it.

Related: [`resolve_storage`](#resolve_storage), [`STORAGE_REGISTRY`](#storage_registry).

Explained in [Named profiles](chapters/05-storage-profiles/index.md#named-profiles).

## Native local handle

The reader that a read stream on local storage returns, wrapping the native file object from `open(path, "rb")` without a ranged reader or extra buffer. It forwards the native object's attributes, so it keeps methods such as `seek`, `tell` and `fileno`, and translates OS errors those methods raise. This is how local storage serves random access.

Related: [`LocalStorageBackend`](#localstoragebackend), [Random access](#random-access).

Explained in [Native local handles](chapters/14-backends/index.md#native-local-handles).

## `NullConnection`

The connection used for local storage. It holds no client, always reports `is_connected` as `True`, and its `connect()` and `disconnect()` do nothing, so code written against `ConnectionProtocol` runs unchanged on local disk.

Related: [`ConnectionProtocol`](#connectionprotocol), [Leaf connection](#leaf-connection).

Explained in [NullConnection](chapters/11-connections/index.md#nullconnection).

## Object storage

A storage model, used by the S3 family, in which a bucket holds objects addressed by flat string keys. Slashes in a key have no structural meaning, listing works by key prefix, and a delimiter groups keys into common prefixes that only look like directories.

Related: [`list_objects`](#list_objects), [S3 family](#s3-family).

Explained in [Object storage has keys, not directories](chapters/01-what-transport-does/index.md#object-storage-has-keys-not-directories).

## `ObjectChangedError`

The `StorageError` subclass raised when a stored object changes between the range fetches of one random-access read. The S3 family and HTTP detect the change by pinning the object's strong ETag; SFTP has no such check.

Related: [Random access](#random-access).

Explained in [Random access](chapters/09-read-access-modes/index.md#random-access).

## Optional extras

Installable dependency groups that enable features beyond the base install: `[http]` for HTTP, profiles and connections; `[s3]` and `[sftp]` for those backends; `[encryption]` for GPG; `[oauth1]` for OAuth 1.0a signing; and `[gcs]` and `[azure]`, which add SDKs but no backend. `[all]` installs them all.

Related: [Base install](#base-install), [`MissingExtraError`](#missingextraerror).

Explained in [Optional extras](chapters/03-installation/index.md#optional-extras).

## Parent creation

The default behaviour of `write()` and `write_stream()` that creates missing parent directories before writing. `create_parents=False` turns it off on local and SFTP stores; the S3 family and HTTP accept the keyword and ignore it. It does not make a write atomic.

Related: [Directory operations](#directory-operations), [`StorageWriteProtocol`](#storagewriteprotocol).

Explained in [Parent creation](chapters/07-file-operations/index.md#parent-creation).

## `PathNotFoundError`

The `StorageError` subclass that reports the established absence of a path. Backends map native conditions to it, such as `FileNotFoundError` on local disk, `NoSuchKey` on S3 or a 404 from an HTTP store read through a facade.

Related: [`StorageError`](#storageerror), [Backend error mapping](#backend-error-mapping).

Explained in [The error families](chapters/03-installation/index.md#the-error-families).

## `Pipeline`

An ordered stack of stream transforms describing how stored bytes are layered, listed outermost first, which is the order a reader removes them. Facade methods accept a `Pipeline`, a single transform or `None` through `pipeline=`, and one instance serves reads, writes and copies.

Related: [`StreamTransform`](#streamtransform), [Transform direction](#transform-direction), [Suffix inference](#suffix-inference).

Explained in [Pipelines](chapters/10-stream-transforms/index.md#pipelines).

## Profile-granted host

A host or bucket that a storage profile passed to the facade allows without an `allowed_remote` entry: an SFTP profile's `HOST`, or an S3-family profile's `BUCKET`. An S3-family profile without a `BUCKET` allows every bucket at its endpoint.

Related: [Remote allow-list](#remote-allow-list), [`LocationPolicy`](#locationpolicy).

Explained in [Hosts granted by a profile](chapters/08-location-policy/index.md#hosts-granted-by-a-profile).

## Provider type

A member of `CONST_STORAGE_PROVIDER_TYPE`, the key that links a path's URL scheme, a profile class's spec and a registered backend. Dispatch maps a scheme to a provider type and then to the backend class registered for it.

Related: [Scheme dispatch](#scheme-dispatch), [Backend registry](#backend-registry).

Explained in [Provider types](chapters/05-storage-profiles/index.md#provider-types).

## Random access

The read access mode, selected with `access="random"`, that returns a seekable handle over the stored bytes and fetches only the byte ranges reads need. The S3 family, SFTP and HTTP serve ranges, local storage returns its native handle, and any transform pipeline is refused because encoded bytes have no usable plaintext offsets.

Related: [Read access mode](#read-access-mode), [`RangePolicy`](#rangepolicy), [Random-access handle](#random-access-handle).

Explained in [Random access](chapters/09-read-access-modes/index.md#random-access).

## Random-access handle

The seekable stream a random-access read returns from the S3 family, SFTP or HTTP, implemented by `RangedReader`. Seeking only moves a position; each read goes through a cache set by the `RangePolicy`, which fetches missing byte ranges from the backend.

Related: [Random access](#random-access), [`RangePolicy`](#rangepolicy), [`RangedReadProtocol`](#rangedreadprotocol).

Explained in [RangedReader](chapters/14-backends/index.md#rangedreader).

## `RangedReadProtocol`

The storage protocol for random access, whose `open_ranged(path)` returns the object's size and a callable that fetches byte ranges. The S3, SFTP and HTTP backends satisfy it structurally; local storage does not and serves random reads from its native handle.

Related: [Random access](#random-access), [Storage protocol](#storage-protocol).

Explained in [Ranged read](chapters/13-architecture/index.md#ranged-read).

## `RangeNotSupportedError`

The `StorageError` subclass a backend raises when it cannot serve byte ranges for a resource, for example an HTTP server that answers `200` instead of `206`. A consumer catches it to fall back to buffered access.

Related: [Random access](#random-access), [Buffered access](#buffered-access).

Explained in [Ranged read](chapters/13-architecture/index.md#ranged-read).

## `RangePolicy`

A frozen dataclass that sets how a random-access handle caches fetched bytes: `cache` (`readahead`, `none`, `blockcache` or `bytes`), `block_size` and `max_blocks`. A `range_policy` argument overrides a profile's `RANGE_*` fields, which override the library default.

Related: [Random access](#random-access), [Random-access handle](#random-access-handle).

Explained in [Range tuning](chapters/09-read-access-modes/index.md#range-tuning).

## Read access mode

The `access` argument of `read_stream()` that selects how bytes are fetched: `"sequential"` (the default), `"random"` or `"buffered"`. The caller chooses it from what the format needs; transport never infers it, and `read()` is unaffected by it.

Related: [Sequential access](#sequential-access), [Random access](#random-access), [Buffered access](#buffered-access).

Explained in [Choosing an access mode](chapters/09-read-access-modes/index.md#choosing-an-access-mode).

## `read` and `write`

The facade methods that move a whole object as `bytes`: `read(path)` returns the content, and `write(path, data)` replaces it. Both accept a `pipeline` so the stored form can be compressed or encrypted; `read` can infer one from suffixes, and `write` creates parent directories by default.

Related: [`read_stream` and `write_stream`](#read_stream-and-write_stream), [`Pipeline`](#pipeline).

Explained in [Reading and writing](chapters/07-file-operations/index.md#reading-and-writing).

## `read_stream` and `write_stream`

The facade methods that move data as binary streams instead of whole objects. `read_stream` returns a caller-owned stream, sequential by default, and accepts `access` and `range_policy`; `write_stream` stores the content of any readable binary stream you supply.

Related: [Binary stream](#binary-stream), [Read access mode](#read-access-mode), [Stream ownership](#stream-ownership).

Explained in [Streaming reads and writes](chapters/07-file-operations/index.md#streaming-reads-and-writes).

## `RefreshableAuthStrategy`

The protocol the HTTP request engine uses for credentials that expire: `get_headers()` before each request, `refresh()` once after the first `401` before resending, and `apply()` for client construction. Transport adapts `mountainash-auth-client` OAuth 2.0 token managers to it.

Related: [`HttpRequestEngine`](#httprequestengine), [`mountainash-auth-client`](#mountainash-auth-client).

Explained in [Authentication strategies](chapters/12-http-engine/index.md#authentication-strategies).

## `register_storage_backend`

The class decorator that registers a backend class for a provider type and returns the class unchanged. A later registration replaces an earlier one, so a caller's class overrides a built-in. The class must accept a profile argument and a `connection` keyword.

Related: [Backend registry](#backend-registry), [`get_storage_backend`](#get_storage_backend).

Explained in [register_storage_backend](chapters/13-architecture/index.md#register_storage_backend).

## Registry completeness tests

The maintainer tests that keep profile specs, schemes and the backend registry in agreement: `implemented` must be `True` exactly when a backend is registered, and every scheme with a provider must resolve to a backend or raise `BackendNotImplementedError`.

Related: [`implemented` flag](#implemented-flag), [Conformance tests](#conformance-tests).

Explained in [Registry completeness tests](chapters/15-maintaining/index.md#registry-completeness-tests).

## Remote allow-list

The `allowed_remote` field of a `LocationPolicy`: a mapping from canonical URL scheme to the host names, or S3 bucket names, a facade may reach. Hosts are compared lowercased and IDNA-encoded, ignoring ports, and for HTTP the check also runs on every redirect.

Related: [`LocationPolicy`](#locationpolicy), [Profile-granted host](#profile-granted-host).

Explained in [Allowing remote hosts](chapters/08-location-policy/index.md#allowing-remote-hosts).

## `RequestPolicy`

A frozen dataclass that bundles the HTTP request engine's `RetryPolicy`, `TimeoutPolicy` and `RedirectPolicy` with the `auth_refresh_on_401` flag. The engine holds a default, a single call can replace it through `policy=`, and `with_retry()`, `with_timeout()` and `with_redirect()` derive variations.

Related: [`RetryPolicy`](#retrypolicy), [`HttpRequestEngine`](#httprequestengine).

Explained in [Policies](chapters/12-http-engine/index.md#policies).

## `resolve_storage`

The function that loads a named profile from configuration and returns `(storage_profile, auth_profile)` after checking the pair against the provider's `supported_auth`. Configuration files come from `SettingsParameters` or from the `MOUNTAINASH_PROFILES_CONFIG` environment variable.

Related: [Named profile](#named-profile), [`STORAGE_REGISTRY`](#storage_registry).

Explained in [resolve_storage](chapters/05-storage-profiles/index.md#resolve_storage).

## Responsibility boundary

The line between what transport owns and what it delegates. Transport owns backend selection, connections, byte movement, stream transforms, access modes and location policy; credentials, configuration loading and the meaning of the bytes belong to other packages or to the consumer.

Related: [Mountainash ecosystem](#mountainash-ecosystem), [Credential delegation](#credential-delegation), [Format-agnostic storage](#format-agnostic-storage).

Explained in [What transport owns](chapters/01-what-transport-does/index.md#what-transport-owns).

## `RetryPolicy`

The policy that decides which HTTP failures the engine retries: `max_attempts` including the first, exponential backoff with optional jitter, retried status codes, connection and timeout errors, and a cap on honoured `Retry-After` waits. Only idempotent methods are retried unless `retry_unsafe_methods` is set, except that a 429 is retried for any method.

Related: [`RequestPolicy`](#requestpolicy), [`HttpRequestEngine`](#httprequestengine).

Explained in [Retries](chapters/12-http-engine/index.md#retries).

## Root confinement

The location policy check that keeps local paths inside `root`. Each path is joined to the root, resolved through symbolic links and `..`, and compared with the resolved root, so the check applies to where a path points rather than how it is spelled.

Related: [`LocationPolicy`](#locationpolicy), [`LocalStorageProfile`](#localstorageprofile).

Explained in [Confining local paths](chapters/08-location-policy/index.md#confining-local-paths).

## Runtime-checkable protocol

A `typing.Protocol` decorated with `@runtime_checkable`, so `isinstance()` and `issubclass()` report whether a class has every listed method, without inheritance or registration. The check is shallow: it confirms method names, not signatures or behaviour.

Related: [Storage protocol](#storage-protocol).

Explained in [Protocols as contracts](chapters/13-architecture/index.md#protocols-as-contracts).

## S3 family

The five provider types and URL schemes served by one backend class, `S3StorageBackend`: `s3`, `s3express`, `r2`, `minio` and `b2`. Service differences are settled by the storage profile's `FLAVOR` when the client is built, not by backend code.

Related: [S3 flavour](#s3-flavour), [`S3StorageBackend`](#s3storagebackend).

Explained in [One class, five provider types](chapters/14-backends/index.md#one-class-five-provider-types).

## S3 flavour

The `FLAVOR` value on `S3StorageProfile` (`aws`, `express`, `r2`, `minio` or `b2`) that determines how the endpoint, region and addressing style are derived for AWS S3, S3 Express One Zone, Cloudflare R2, MinIO or Backblaze B2.

Related: [S3 family](#s3-family), [`S3Connection`](#s3connection).

Explained in [S3 flavours](chapters/05-storage-profiles/index.md#s3-flavours).

## `s3_bucket` and `s3_key`

Helpers in `mountainash_transport.storage.path_helpers.s3` that split an S3-family path into its bucket and object key. They return `None` instead of raising for a path that is not an addressable S3 path, including one whose host position carries a port.

Related: [Object storage](#object-storage), [S3 family](#s3-family).

Explained in [S3 bucket and key parsing](chapters/04-paths-and-schemes/index.md#s3-bucket-and-key-parsing).

## `S3Connection`

The leaf connection that creates a boto3 S3 client for any S3 flavour, from explicit keys, a named AWS profile or refreshable assume-role credentials. Assume-role works only with the `aws` and `express` flavours.

Related: [Leaf connection](#leaf-connection), [S3 flavour](#s3-flavour).

Explained in [S3Connection](chapters/11-connections/index.md#s3connection).

## `S3StorageBackend`

The backend for S3-family paths, wrapping a boto3 client from `S3Connection`. It implements read, write, enumerate, delete, metadata, server-side copy and ranged read, but no directories. Ranged reads pin the object's strong ETag, so a changed object raises `ObjectChangedError`.

Related: [S3 family](#s3-family), [Support matrix](#support-matrix).

Explained in [S3 family](chapters/14-backends/index.md#s3-family).

## Scheme dispatch

The chain that turns a path into a backend: identify the canonical URL scheme, take the provider type from its `SchemeSpec`, then look up the backend registered for that provider type. `StorageFacade.from_path` runs it, and `detect_provider_from_path` exposes the first two steps.

Related: [`SchemeSpec`](#schemespec), [Provider type](#provider-type), [Backend registry](#backend-registry).

Explained in [From path to backend](chapters/04-paths-and-schemes/index.md#from-path-to-backend).

## `SchemeSpec`

An entry in transport's table of recognised URL schemes, holding the canonical `scheme`, its `aliases`, a `strict` flag for case checking and the `provider` type it routes to. Dispatch, `StoragePath` and the location policy all read the same table.

Related: [Scheme dispatch](#scheme-dispatch), [URL scheme](#url-scheme).

Explained in [The scheme registry](chapters/04-paths-and-schemes/index.md#the-scheme-registry).

## Sequential access

The default read access mode, which returns a stream that fetches data as it is read so memory stays flat. Remote stores give a forward-only stream, local storage gives the native file handle, and transforms decode chunk by chunk.

Related: [Read access mode](#read-access-mode), [Forward-only stream](#forward-only-stream).

Explained in [Sequential access](chapters/09-read-access-modes/index.md#sequential-access).

## Settings-only provider

A provider (GCS, Azure Storage, FTP/FTPS, SMB or GitHub repositories) whose profile class is complete and registered but which has no backend. Its configuration can be written, validated and loaded by name. Opening storage for it from a path alone, or looking up its backend, raises `BackendNotImplementedError`; a facade built with its storage profile fails earlier with `TransportConnectionError` ([Settings-only providers](reference/support-matrix.md#settings-only-providers)).

Related: [`BackendNotImplementedError`](#backendnotimplementederror), [`implemented` flag](#implemented-flag).

Explained in [Settings-only providers](chapters/05-storage-profiles/index.md#settings-only-providers).

## `SFTPConnection`

The decorator connection that opens an SFTP channel over an `SSHConnection` it owns; its `client` is a `paramiko.SFTPClient`. `create_connection` returns one for any SFTP profile, and reconnecting reuses a still-connected SSH session.

Related: [Decorator connection](#decorator-connection), [`SSHConnection`](#sshconnection).

Explained in [SFTPConnection](chapters/11-connections/index.md#sftpconnection).

## `SFTPStorageBackend`

The backend for SFTP, using a paramiko `SFTPClient`. It implements read, write, enumerate, delete, metadata, directories and ranged read, but not server-side copy. `sftp://` URLs must match the connected profile's host and port, and stream writes are buffered in memory.

Related: [`SFTPStorageProfile`](#sftpstorageprofile), [Backend divergence](#backend-divergence).

Explained in [SFTP](chapters/14-backends/index.md#sftp).

## `SFTPStorageProfile`

The storage profile for an SSH server used through SFTP, with required `HOST` and `USERNAME`, `PORT` defaulting to 22, paramiko connection options and host-key settings. `HOST_KEY_POLICY` defaults to `reject`, which refuses hosts whose key is not known.

Related: [Storage profile](#storage-profile), [`SSHConnection`](#sshconnection).

Explained in [SFTP profile](chapters/05-storage-profiles/index.md#sftp-profile).

## Slim install test

The maintainer test that runs code in a subprocess allowed to import only the standard library, `typing_extensions` and `mountainash_transport`. It checks that local storage works on a base install, every backend registers, and remote entry points raise `MissingExtraError`.

Related: [Base install](#base-install).

Explained in [Slim install test](chapters/15-maintaining/index.md#slim-install-test).

## `SSHConnection`

The leaf connection that creates and connects a `paramiko.SSHClient`, checking host keys against the system known-hosts files and an optional `known_hosts_file`. Unknown hosts follow the host-key policy: `reject` by default, or `warn` and `auto_add`, which allow a man-in-the-middle.

Related: [Leaf connection](#leaf-connection), [`SFTPConnection`](#sftpconnection), [Bastion tunnel](#bastion-tunnel).

Explained in [SSHConnection](chapters/11-connections/index.md#sshconnection).

## `storage()`

A package-root function that constructs a `StorageFacade` from a provider type, defaulting to local, with an optional storage profile and auth profile. It accepts no location policy or OAuth arguments.

Related: [`StorageFacade`](#storagefacade), [`from_path`](#from_path).

Explained in [The storage() factory](chapters/06-storage-facade/index.md#the-storage-factory).

## Storage profile

An instance of a provider's profile class, built on the `mountainash-settings` `Profile`, that describes a store, such as its endpoint, region, bucket, host and timeouts, but holds no credentials. Its uppercase fields are validated on construction and can come from arguments, environment or configuration.

Related: [Auth profile](#auth-profile), [`StorageProfileSpec`](#storageprofilespec), [Named profile](#named-profile).

Explained in [What a storage profile is](chapters/05-storage-profiles/index.md#what-a-storage-profile-is).

## Storage protocol

A small runtime-checkable protocol class that describes one storage capability, such as reading, listing or copying. Each backend implements only the protocols its store supports, each facade method maps to one protocol, and `supports()` tests a facade against one.

Related: [Runtime-checkable protocol](#runtime-checkable-protocol), [Capability check](#capability-check), [Support matrix](#support-matrix).

Explained in [Capabilities and supports()](chapters/06-storage-facade/index.md#capabilities-and-supports).

## `StorageCopyProtocol`

The storage protocol for copying within one backend through `copy(source, destination)`, using the store's own mechanism. Local storage and the S3 family implement it; SFTP and HTTP do not.

Related: [`copy`](#copy), [Storage protocol](#storage-protocol).

Explained in [Copy](chapters/13-architecture/index.md#copy).

## `StorageDeleteProtocol`

The storage protocol for removing one file or object through `delete_file(path)`. The result for a missing path follows the store: local storage raises `PathNotFoundError` and S3 succeeds. HTTP does not implement it.

Related: [`delete`](#delete), [Storage protocol](#storage-protocol).

Explained in [Delete](chapters/13-architecture/index.md#delete).

## `StorageDirectoryProtocol`

The storage protocol for directories, with `list_dir`, `mkdir` and `rmdir`. Local storage and SFTP implement it; object stores and HTTP do not. The handling of non-empty and missing directories by `rmdir` is left to each backend.

Related: [Directory operations](#directory-operations), [Backend divergence](#backend-divergence).

Explained in [Directory](chapters/13-architecture/index.md#directory).

## `StorageEntry`

The frozen dataclass that describes one resource in listings and metadata queries: `path`, `name`, `size`, `last_modified`, `entry_type` (`FILE`, `DIRECTORY` or `PREFIX`) and object-store details such as `etag`. Backends fill the fields they know.

Related: [`list_objects`](#list_objects), [Metadata queries](#metadata-queries).

Explained in [StorageEntry](chapters/07-file-operations/index.md#storageentry).

## `StorageEnumerateProtocol`

The storage protocol for listing, whose `list_objects(prefix, *, delimiter=None, max_results=None)` returns an `EnumerateResult`. A failure on any page raises instead of returning a partial result. HTTP does not implement it.

Related: [`list_objects`](#list_objects), [Storage protocol](#storage-protocol).

Explained in [Enumerate](chapters/13-architecture/index.md#enumerate).

## `StorageError`

The root of the storage error family, raised by facades, backends, profiles and location policy. Its subclasses mark distinct conditions, including `PathNotFoundError`, `UnsupportedOperationError`, `BackendNotImplementedError`, `MissingExtraError`, `TransformError` and `LocationNotAllowed`.

Related: [Error families](#error-families), [Backend error mapping](#backend-error-mapping).

Explained in [The error families](chapters/03-installation/index.md#the-error-families).

## `StorageFacade`

The object through which code reads, writes, lists and manages files on one store. Bound to one provider type for its life, it builds and owns the connection, resolves the backend, applies the location policy and checks each operation's capability before delegating to the backend.

Related: [`from_path`](#from_path), [Facade lifecycle](#facade-lifecycle), [Facade dispatch](#facade-dispatch).

Explained in [Creating a facade](chapters/06-storage-facade/index.md#creating-a-facade).

## `StorageMetadataProtocol`

The storage protocol for querying a path without reading it: `get_metadata` returns a `StorageEntry`, `path_exists` returns `False` only for established absence, and `get_size` returns the size, or `None` when the store does not report one.

Related: [Metadata queries](#metadata-queries), [Storage protocol](#storage-protocol).

Explained in [Metadata](chapters/13-architecture/index.md#metadata).

## `StoragePath`

A stateless helper class whose class methods identify, normalise, join and match path strings without backend dispatch or I/O. `identify_scheme` returns the canonical scheme, and `normalize` canonicalises the scheme and rejects malformed input. It needs the `[http]` extra.

Related: [URL scheme](#url-scheme), [Scheme dispatch](#scheme-dispatch).

Explained in [StoragePath](chapters/04-paths-and-schemes/index.md#storagepath).

## `StorageProfileSpec`

The frozen dataclass that describes one storage provider: registry name, provider type, profile parameters, SDK package, backend location, capability flags, supported auth modes and the `implemented` flag. Profile classes, `resolve_storage` and the registry read from it.

Related: [Storage profile](#storage-profile), [`STORAGE_REGISTRY`](#storage_registry), [`implemented` flag](#implemented-flag).

Explained in [StorageProfileSpec](chapters/05-storage-profiles/index.md#storageprofilespec).

## `StorageReadProtocol`

The storage protocol for reading, with `read_to_bytes(path)` for a whole object and `read_to_stream(path)` for a caller-owned binary stream whose failures can surface on a later `read()` or `close()`. Every backend implements it.

Related: [`read` and `write`](#read-and-write), [Storage protocol](#storage-protocol).

Explained in [Read](chapters/13-architecture/index.md#read).

## `STORAGE_REGISTRY`

The `mountainash-settings` `Registry` that maps each provider spec name to its `StorageProfileSpec` and profile class. Its names are the `provider:` values in named-profile configuration. It indexes profile classes only and is separate from the backend registry.

Related: [`StorageProfileSpec`](#storageprofilespec), [Backend registry](#backend-registry).

Explained in [STORAGE_REGISTRY](chapters/05-storage-profiles/index.md#storage_registry).

## `StorageWriteProtocol`

The storage protocol for writing, with `write_from_bytes` and `write_from_stream`, both taking `create_parents=True`. Backends without directories accept and ignore the flag, and an error raised by the caller's input stream reaches the caller unchanged.

Related: [`read` and `write`](#read-and-write), [Parent creation](#parent-creation).

Explained in [Write](chapters/13-architecture/index.md#write).

## Stream ownership

The rule that the stream `read_stream()` returns belongs to the caller, and closing it closes every transform layer the facade built, in reverse order, and then the backend source. Closing a stream never closes its facade, which must stay open while remote streams are in use.

Related: [Deferred read error](#deferred-read-error), [`read_stream` and `write_stream`](#read_stream-and-write_stream).

Explained in [Stream ownership](chapters/09-read-access-modes/index.md#stream-ownership).

## `StreamTransform`

The runtime-checkable protocol for a reversible byte encoding, with `wrap(stream)` to encode and `unwrap(stream)` to decode, each taking and returning a readable binary stream. `Gzip` and `GPG` implement it, and custom transforms can too.

Related: [`Pipeline`](#pipeline), [`Gzip`](#gzip), [`GPG`](#gpg).

Explained in [The StreamTransform protocol](chapters/10-stream-transforms/index.md#the-streamtransform-protocol).

## Suffix chain

The sequence of trailing file-name suffixes, such as `.csv.gz.gpg`, that records how a file's bytes were layered. Transport reads it right to left and stops at the first unrecognised suffix, yielding a transform pipeline and the path without those suffixes.

Related: [Suffix inference](#suffix-inference), [`Pipeline`](#pipeline).

Explained in [Suffix chains](chapters/04-paths-and-schemes/index.md#suffix-chains).

## Suffix inference

The derivation of a read pipeline from a path's suffix chain, through `infer_pipeline` or `infer=True` on `read` and `read_stream`. `.gz` and `.gzip` map to `Gzip`, and `.gpg`, `.asc` and `.pgp` to `GPG`, which must be supplied as `gpg=`. Writes have no inference.

Related: [Suffix chain](#suffix-chain), [`Pipeline`](#pipeline).

Explained in [Suffix inference](chapters/10-stream-transforms/index.md#suffix-inference).

## Support matrix

The table of which storage protocols each registered backend class implements, derived by running `issubclass()` against every registered backend. The [support matrix and known limits](reference/support-matrix.md) page collects it with the documented behavioural limits.

Related: [Storage protocol](#storage-protocol), [Backend divergence](#backend-divergence).

Explained in [Support matrix](chapters/14-backends/index.md#support-matrix).

## Target family

A `TargetFamily` value from `mountainash-auth-client` that names the SDK a set of keyword arguments is for: `HTTP` (httpx), `BOTO` (boto3) or `PARAMIKO` (paramiko). Transport maps each provider type to one, so both profiles emit matching arguments.

Related: [Emission](#emission), [Auth profile](#auth-profile).

Explained in [Target families](chapters/11-connections/index.md#target-families).

## Transform direction

The order in which the facade applies a pipeline: reads unwrap from the outer layer inward in list order, and writes wrap from the inner layer outward in reverse order. Callers never reverse a pipeline themselves.

Related: [`Pipeline`](#pipeline), [`StreamTransform`](#streamtransform).

Explained in [Direction](chapters/10-stream-transforms/index.md#direction).

## `TransformError`

The `StorageError` subclass for stream transform failures. `Gzip` raises it, for example, when reading or seeking would decode more than `max_decompressed_bytes`.

Related: [`Gzip`](#gzip), [`StorageError`](#storageerror).

Explained in [Gzip](chapters/10-stream-transforms/index.md#gzip).

## `TransportConnectionError`

The root of the connection error family, raised for client construction, socket, DNS, SSH authentication, host-key and tunnel failures. Its subclasses in `mountainash_transport.connections.errors` include `ConnectionTimeoutError` and `UnsupportedAuthProfileError`.

Related: [Error families](#error-families), [`create_connection`](#create_connection).

Explained in [Connection errors](chapters/11-connections/index.md#connection-errors).

## `UnsupportedOperationError`

The `StorageError` subclass raised before any I/O when a facade's backend does not implement the operation called, naming the backend and the operation.

Related: [Capability check](#capability-check), [Storage protocol](#storage-protocol).

Explained in [Checking before you call](chapters/06-storage-facade/index.md#checking-before-you-call).

## URL scheme

The part of a path before `://` that selects the provider: none or `file` for local disk, `s3`, `s3express`, `r2`, `minio` and `b2` for the S3 family, `sftp`, and `http` or `https`. Schemes such as `gs`, `azure` and `ftp` are recognised but have no backend.

Related: [Scheme dispatch](#scheme-dispatch), [`SchemeSpec`](#schemespec).

Explained in [URL schemes and paths](chapters/01-what-transport-does/index.md#url-schemes-and-paths).
