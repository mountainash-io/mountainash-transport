---
title: FAQ
description: Questions people ask about installing, using, operating and extending mountainash-transport, with links to the sections that answer them in full.
---

# FAQ

Short answers to common questions about mountainash-transport. Each answer links to the section that explains the behaviour in full. Current limits are collected in the [support matrix and known limits](reference/support-matrix.md).

## Getting started

### What does mountainash-transport do?

It gives Python code one file API across local disk, the S3 family (AWS S3, S3 Express, Cloudflare R2, MinIO and Backblaze B2), SFTP servers and HTTP(S) endpoints. You open a `StorageFacade` and call `read`, `write`, `read_stream`, `write_stream`, `list_objects`, `copy`, `delete` and the other methods; the scheme of the path decides which backend does the work. Transport moves bytes and leaves their meaning to you. See [What transport does](chapters/01-what-transport-does/index.md#byte-storage-endpoints).

### Which Python version does it need?

Python 3.12 or later. See [Installation and the package surface](chapters/03-installation/index.md).

### What works on the base install?

The base install depends only on `typing-extensions`. It covers `StorageFacade` on local paths (bare paths and `file://` URLs) with every local operation, the `Gzip` transform, `Pipeline`, `infer_pipeline`, `LocationPolicy` from `mountainash_transport.location`, and the error and HTTP policy classes. Remote storage, storage profiles (including `LocalStorageProfile`), `resolve_storage`, connections, `StoragePath` and the HTTP request engine need at least the `[http]` extra. See [The base install](chapters/03-installation/index.md#the-base-install).

### Which extras should I install?

Choose extras by the endpoints your code reaches:

| Extra | Enables |
|---|---|
| `[http]` | HTTP(S) storage, storage profiles, named profiles, connections, `StoragePath`, the HTTP request engine |
| `[s3]` | The S3 backend for AWS S3, S3 Express, R2, MinIO and B2 |
| `[sftp]` | The SFTP backend, SSH connections and SSH tunnels |
| `[encryption]` | The `GPG` transform |
| `[oauth1]` | OAuth 1.0a request signing |
| `[gcs]`, `[azure]` | The vendor SDKs only; there is no GCS or Azure backend |
| `[all]` | All of the above |

Every backend extra includes `[http]`. `[encryption]` does not, because GPG works on local files without it. A tool that reads S3 and decrypts GPG files needs `[s3,encryption]`. See [Optional extras](chapters/03-installation/index.md#optional-extras).

### How do I install it next to the other Mountainash packages?

Version 0.1.0 is a development baseline. Until the sibling packages are published, install them from development checkouts placed side by side. With `uv`, from the parent directory of the checkouts:

```bash
uv pip install ./mountainash-settings ./mountainash-auth-client "./mountainash-transport[s3,sftp]"
```

Packages built on transport pass their extras through: `mountainash-files[s3]` installs `mountainash-transport[s3]`. See [Optional extras](chapters/03-installation/index.md#optional-extras).

### Why does `import mountainash_transport` succeed when an extra is missing?

The package root resolves its public names on first use (PEP 562). `import mountainash_transport` loads almost nothing, and local-only code never imports `httpx` or the cloud SDKs. A name that needs a missing extra fails when you first access it, for example `StoragePath` raises `MissingExtraError` on a base install. See [The lazy package root](chapters/03-installation/index.md#the-lazy-package-root).

### Why does `import mountainash_transport.storage.backends as backends` raise `ImportError`?

The package root binds `storage` to a factory function, so `mountainash_transport.storage` is that function and not the subpackage. Use `from` imports for submodules, for example `from mountainash_transport.storage.facade import StorageFacade`. See [The lazy package root](chapters/03-installation/index.md#the-lazy-package-root).

### What is the quickest way to open storage?

`StorageFacade.from_path(path, profile, auth_profile=...)` picks the backend from the path's scheme. `StorageFacade.for_local()` opens the local filesystem with no profile. The root `storage(provider_type, profile, auth_profile=...)` function builds a facade from a provider type and defaults to local, but it does not accept a location policy or the OAuth arguments. Use a facade as a context manager so its connection is released. See [Creating a facade](chapters/06-storage-facade/index.md#creating-a-facade).

### What does transport leave to other packages?

Credentials and OAuth token lifecycles belong to `mountainash-auth-client`. Loading configuration files, environment variables and secret references belongs to `mountainash-settings`. File formats, and the choice of access mode for a format, belong to consumers such as `mountainash-files` and `mountainash`. Transport owns backend selection, connections, byte movement, stream transforms, access modes, location policy and typed errors. See [What transport owns](chapters/01-what-transport-does/index.md#what-transport-owns) and [The Mountainash packages](chapters/02-mountainash-ecosystem/index.md#the-mountainash-packages).

## Backends and providers

### Which storage backends are there?

Four: local files, the S3 family, SFTP and HTTP(S). Each implements the storage protocols its store can honour. See the [support matrix](reference/support-matrix.md#backends-and-capabilities) and [Backends](chapters/14-backends/index.md#support-matrix).

### Do R2, MinIO, B2 and S3 Express need their own backends?

No. One `S3StorageBackend` class is registered for the `s3`, `s3express`, `r2`, `minio` and `b2` provider types. The `FLAVOR` field on `S3StorageProfile` (`aws`, `express`, `r2`, `minio` or `b2`) decides the endpoint, region and addressing style, and an explicit `ENDPOINT_URL` wins for every flavour. MinIO requires `ENDPOINT_URL`; R2 needs `ACCOUNT_ID` or `ENDPOINT_URL`. See [S3 flavours](chapters/05-storage-profiles/index.md#s3-flavours) and [One class, five provider types](chapters/14-backends/index.md#one-class-five-provider-types).

### Why can't I put the MinIO host and port in the path?

A path never carries an endpoint. In an S3-family path the host position is the bucket, so `minio://localhost:9000/reports/sales.csv` is not an addressable S3 path and the S3 path helpers return `None` for it. Put the endpoint on the storage profile's `ENDPOINT_URL` and name only the bucket and key in the path. See [S3 bucket and key parsing](chapters/04-paths-and-schemes/index.md#s3-bucket-and-key-parsing).

### Can I use Google Cloud Storage, Azure, FTP, SMB or GitHub repositories?

Not for storage operations. These are settings-only providers: their profile classes validate fields, appear in the registry and load by name with `resolve_storage`, but no backend exists. `StorageFacade.from_path("gs://...")` raises `BackendNotImplementedError`. Installing `[gcs]` or `[azure]` adds the vendor SDK and no backend. See [Settings-only providers](chapters/05-storage-profiles/index.md#settings-only-providers).

### Why does a GCS or FTP profile raise `TransportConnectionError` instead of `BackendNotImplementedError`?

When you pass a settings-only profile to `StorageFacade`, the facade builds the connection before it looks up the backend. `create_connection` has no connection class for these providers and falls back to an HTTP connection, which rejects the profile's arguments. When the provider comes from configuration, check `get_spec(name).implemented` before opening storage. See [BackendNotImplementedError](chapters/05-storage-profiles/index.md#backendnotimplementederror) and [create_connection](chapters/11-connections/index.md#create_connection).

### How do I check whether a store supports an operation?

Call `facade.supports(protocol)` with one of the eight protocol classes exported from the package root, such as `StorageDirectoryProtocol` or `StorageCopyProtocol`. Calling an operation the backend lacks raises `UnsupportedOperationError` before any I/O. HTTP cannot list, delete, copy or manage directories; the S3 family has no directories; SFTP has no `copy()`. See [Checking before you call](chapters/06-storage-facade/index.md#checking-before-you-call).

### Why can't I create directories on S3?

Object stores have keys, not directories. The slashes in `2026/q1/north.csv` are part of the key, and there is nothing to create first. The S3 backend does not implement the directory protocol, so `mkdir`, `rmdir` and `list_dir` raise `UnsupportedOperationError`, and `create_parents` on writes is accepted and ignored. Use `list_objects` with a prefix to see what is under a key prefix. See [Object storage has keys, not directories](chapters/01-what-transport-does/index.md#object-storage-has-keys-not-directories).

### Can a storage profile send an `s3://` path to a different backend?

No. Dispatch reads only the path's scheme. To choose the backend yourself, construct `StorageFacade` with a provider type instead of calling `from_path`. See [From path to backend](chapters/04-paths-and-schemes/index.md#from-path-to-backend).

### Why does `local` report no ranged-read support when random reads work?

Local storage does not implement `RangedReadProtocol`, so `supports(RangedReadProtocol)` is `False`. `read_stream(access="random")` still works on local paths because the facade returns a reader that wraps the operating system's native seekable file object and forwards its attributes. See [Native local handles](chapters/14-backends/index.md#native-local-handles).

## Profiles and credentials

### What is the difference between a storage profile and an auth profile?

A storage profile describes a store: endpoint, region, bucket or host, timeouts, TLS verification and addressing style. It never holds a password, key or token. An auth profile from `mountainash-auth-client` carries the credentials. Transport pairs them when it opens a connection, so the same storage profile can be used with different credentials in different environments and is safe to print. See [What a storage profile is](chapters/05-storage-profiles/index.md#what-a-storage-profile-is) and [How transport delegates credentials](chapters/02-mountainash-ecosystem/index.md#how-transport-delegates-credentials).

### Where do my S3 keys or SFTP password go?

In an auth profile passed as `auth_profile=`. Use `IAMAuthProfile` for AWS keys, a session token, a role or a named AWS profile, and `PasswordAuthProfile` (or a certificate or Kerberos profile) for SFTP. Do not put credentials in URLs: some errors quote the path as given. See [Auth profiles](chapters/05-storage-profiles/index.md#auth-profiles) and [Credential redaction](chapters/08-location-policy/index.md#credential-redaction).

### Why is my auth profile rejected with `UnsupportedAuthProfileError`?

Each provider declares the auth modes it accepts. S3 accepts `iam` and `none`; SFTP accepts `password`, `certificate`, `kerberos` and `none`; HTTP accepts `none`, `token`, `password` and `oauth2`; local accepts only `none`. Passing no auth profile counts as `none`. The check runs in `create_connection` before any network I/O. See [Auth profiles](chapters/05-storage-profiles/index.md#auth-profiles).

### Can I assume an IAM role for R2, MinIO or B2?

No. Assuming a role goes through AWS STS, which only the `aws` and `express` flavours reach. Pairing an `IAMAuthProfile` with `ROLE_ARN` and an R2, MinIO or B2 profile raises `ValueError` in `create_connection`. Setting both `PROFILE_NAME` and explicit keys raises `ValueError` at `connect()`. See [S3Connection](chapters/11-connections/index.md#s3connection).

### How do I keep store configuration and credentials out of code?

Use named profiles. A configuration file has a `storage_profiles:` section with one block per name, each giving a `provider`, its `parameters` and an optional `auth` block with a `mode` and its `parameters`. `resolve_storage(name, settings_parameters=...)` returns `(storage_profile, auth_profile)`. Without `settings_parameters`, it reads the file named by the `MOUNTAINASH_PROFILES_CONFIG` environment variable. See [resolve_storage](chapters/05-storage-profiles/index.md#resolve_storage).

### How are secrets in named-profile configuration resolved?

Write them as `"secret:<record>.<field>"`. `mountainash-settings` resolves the reference from the secret store you select in `SettingsParameters`, so the file holds references rather than secrets. A reference with no selected store, a missing record or a failed lookup is an error; there is no fallback to environment variables or provider defaults. See [Configuration comes from settings](chapters/02-mountainash-ecosystem/index.md#configuration-comes-from-settings).

### What does `resolve_storage` raise when configuration is wrong?

`ProfileNotFoundError` for a name that is not in the configuration, and its base class `ProfileResolutionError` for an unknown provider or auth mode or for parameters that fail validation. Both are `StorageError` subclasses. A pairing the provider does not accept raises `UnsupportedAuthProfileError`, which comes from the connection layer. See [resolve_storage](chapters/05-storage-profiles/index.md#resolve_storage).

### Does transport run OAuth flows?

No. `mountainash-auth-client` owns OAuth flows and token lifecycles. For managed OAuth2 over HTTP, pass an `OAuth2AuthProfile` with `oauth_provider=` and `token_store=` to `StorageFacade.from_path`. Transport adapts auth-client's token manager to the HTTP engine: each request takes its `Authorization` header from the manager, and a `401` triggers one refresh and a retry. The token store stays yours to open and close. See [Authentication strategies](chapters/12-http-engine/index.md#authentication-strategies).

## Reading and writing

### How do I read or write a file that does not fit in memory?

Use `read_stream(path)`, which returns a binary stream you read in chunks and close (preferably with `with`), and `write_stream(path, source)`, which consumes any readable binary stream. Remote sequential streams fetch data as you read. `read()` and `write()` hold the whole object in memory. SFTP is an exception on the write side; see [How much memory does writing a large stream to SFTP use?](#how-much-memory-does-writing-a-large-stream-to-sftp-use). See [Streaming reads and writes](chapters/07-file-operations/index.md#streaming-reads-and-writes).

### Why can't I seek on a stream from S3, SFTP or HTTP?

The default access mode is sequential, and remote sequential streams are forward-only. Ask for `access="random"` to get a seekable handle that fetches byte ranges, or `access="buffered"` to get a seekable in-memory buffer of the whole decoded object. Remote streams used to be downloaded before `read_stream()` returned; they no longer are, so code that seeks must request one of these modes. See [Choosing an access mode](chapters/09-read-access-modes/index.md#choosing-an-access-mode).

### Which access mode should I use for Parquet and other footer-first formats?

`access="random"`, which fetches only the byte ranges the reader asks for. Transport does not choose the mode from the file extension; the consumer does. For PyArrow's Parquet reader, a 64 KiB read-ahead (`RangePolicy("readahead", block_size=64 * 1024)`) fetched far fewer bytes than the 1 MiB default in the measured setup. See [Range tuning](chapters/09-read-access-modes/index.md#range-tuning).

### Why does `access="random"` raise `ValueError` on a `.gz` file?

Random access reads byte ranges of the stored object, and a compressed or encrypted object has no meaningful plaintext offsets, so the facade refuses any transform, explicit or inferred from the suffix. The refusal is a plain `ValueError`. Use sequential access to decode while streaming, or buffered access to seek in the decoded bytes. A consumer can check with `infer_pipeline(path)` before choosing the mode. See [Transforms and random access](chapters/10-stream-transforms/index.md#transforms-and-random-access).

### Why did `read_stream()` succeed and reading fail later?

Sequential transfers and lazy transforms produce their errors as you read. A malformed `.gz` file opens cleanly and raises `gzip.BadGzipFile` on `read()`. To get every transfer and decoding error inside one call, use `read()` or `access="buffered"`. See [Deferred read errors](chapters/09-read-access-modes/index.md#deferred-read-errors).

### Do I have to close streams before closing the facade?

Yes, for sequential and random streams from a remote store: the facade must stay open while they are in use. Closing a stream closes every transform layer on it and never closes the facade. Buffered results and the bytes from `read()` are independent of the facade and stay usable after it closes. See [Stream ownership](chapters/09-read-access-modes/index.md#stream-ownership).

### Can I reopen a closed facade?

No. Close is terminal: afterwards every storage operation, and re-entering the `with` block, raises `StorageConnectionError`. Create a new facade. Repeated `close()` is a no-op, and cleanup is not left to garbage collection. See [Facade lifecycle](chapters/06-storage-facade/index.md#facade-lifecycle).

### Can I trust `exists()` when it returns `False`?

Yes. `exists()` returns `False` only when the store establishes that the resource is absent. A denied request or an operational failure raises the matching storage error instead; a denied S3 `HEAD` raises `PermissionDeniedError`. `get_size()` returns `None` only when the resource exists without a reported size, and raises `PathNotFoundError` when it is missing. See [Metadata queries](chapters/07-file-operations/index.md#metadata-queries).

### Why does an S3 listing for `2026` also return `2026-draft.csv`?

On S3 the prefix is a literal key prefix, so `2026` matches any key that starts with those characters. End the prefix with `/` to select one folder's keys. On local and SFTP stores the prefix is an exact path. The facade's default `delimiter="/"` lists one level; `delimiter=None` lists recursively. See [Listing and metadata](chapters/07-file-operations/index.md#listing-and-metadata).

### Are writes atomic?

No. A write that fails part-way can leave partial data at the destination, and transport adds no rollback or retry. `create_parents` controls directory creation only. `copy_between` does no cleanup or atomic rename either. See [Reading and writing](chapters/07-file-operations/index.md#reading-and-writing).

### Does deleting a missing file raise an error?

On local and SFTP stores, yes: `PathNotFoundError`. On the S3 family, no: deleting a key that does not exist succeeds, as S3's `DeleteObject` does. Check `exists()` first if you need to know. HTTP stores do not support deletion. See [Deleting, directories and parent creation](chapters/07-file-operations/index.md#deleting-directories-and-parent-creation).

## Transforms and copying

### How do I compress or encrypt files as I write them?

Pass `pipeline=` with `Gzip()`, `GPG(...)` or a `Pipeline` of several to `write`, `write_stream`, `read` or `read_stream`. Writes encode and reads decode. Reads can also infer the pipeline from the file suffix with `infer=True`; writes cannot, so pass the pipeline explicitly when writing. See [Transforms and pipelines](chapters/10-stream-transforms/index.md#transforms-and-pipelines).

### In what order do I list transforms in a `Pipeline`?

Outermost first, which is the order of the file suffixes read from right to left. `sales.csv.gz.gpg` was gzipped and then encrypted, so it is `Pipeline(GPG(...), Gzip())`. You never reverse the list: the facade unwraps in list order on reads and wraps in reverse order on writes, so one pipeline value serves reads, writes and both sides of a copy. See [Pipelines](chapters/10-stream-transforms/index.md#pipelines) and [Direction](chapters/10-stream-transforms/index.md#direction).

### Why does `infer=True` fail on a `.gpg` file?

A GPG suffix needs key material, which transport never guesses. Pass `gpg=GPG(...)` alongside `infer=True`, or `infer_pipeline` raises `ValueError`. Inference also stops at the first unknown suffix, so `sales.csv.gz.bak` infers nothing. See [Suffix inference](chapters/10-stream-transforms/index.md#suffix-inference).

### Does GPG stream?

No. `python-gnupg` is not a streaming library, so `GPG` holds the whole encrypted or decrypted payload in memory in both directions, has no bound on decrypted size, and reports decryption failures when the stream is opened. It needs the `[encryption]` extra and a `gpg` binary, and keys live in the gpg keyring you point it at. See [GPG](chapters/10-stream-transforms/index.md#gpg).

### Why does reading a large gzip file raise `TransformError`?

`Gzip` bounds decoded output at `max_decompressed_bytes`, 1 GiB by default, and raises before allocating past it. For trusted data, raise the bound with `Gzip(max_decompressed_bytes=...)` or pass `None` to remove it. See [Gzip](chapters/10-stream-transforms/index.md#gzip).

### How do I copy a file from one store to another?

Use `copy_between(source_path, destination_path, source_facade, destination_facade)`. It streams the source into the destination and accepts `source_pipeline` and `destination_pipeline` to decode or encode on the way. Both facades must already be open, and `copy_between` never closes them. `copy()` copies only within one store, and SFTP and HTTP do not support it. See [Copying between backends](chapters/10-stream-transforms/index.md#copying-between-backends).

### Why did `copy_between` download and re-upload instead of copying server side?

The native copy is used only when no pipeline is given, both facades use the same backend class and equal location policies, they share the identical storage profile object (compared with `is`), and the backend supports copy. Two facades built from separate but equal profiles stream the bytes through your process. See [Copying between backends](chapters/10-stream-transforms/index.md#copying-between-backends).

### Why is my source stream closed after `write_stream()`?

Two cases close it. Writing through a `Gzip` layer closes the stream you supplied, including `copy_between` with a gzip `destination_pipeline`. A small single-request upload to an S3-family store also closes it, while a larger multipart upload leaves it open. Do not rely on the source stream's state after the call; pass a separate handle if you need it again. See [Who closes what](chapters/10-stream-transforms/index.md#who-closes-what) and [Streaming reads and writes](chapters/07-file-operations/index.md#streaming-reads-and-writes).

### Can I write my own transform?

Yes. Any object with `wrap(stream)` and `unwrap(stream)` methods, each taking and returning a readable binary stream, satisfies the `StreamTransform` protocol and can be passed wherever a pipeline is accepted. Implementations should stream lazily rather than drain the input when constructed. See [The StreamTransform protocol](chapters/10-stream-transforms/index.md#the-streamtransform-protocol).

## Location policy

### How do I stop code from reading or writing outside a directory?

Pass `policy=LocationPolicy(root=...)` to `StorageFacade.for_local`, `from_path` or the constructor. Local paths are joined to the root and resolved, following symbolic links and collapsing `..`, and anything that lands outside raises `LocationNotAllowed` with reason `outside root`. A `LocalStorageProfile` with `ROOT_PATH` sets the root even without a policy. `LocationPolicy` works on a base install; `LocalStorageProfile` needs `[http]`. See [Confining local paths](chapters/08-location-policy/index.md#confining-local-paths) and [The local profile](chapters/08-location-policy/index.md#the-local-profile).

### How do I limit which hosts or buckets a facade can reach?

Set `allowed_remote` to a mapping from canonical scheme to a `frozenset` of host names, or bucket names for the S3 family. `http` and `https` are separate keys, and ports are not compared. A scheme that is absent from the mapping refuses every host. The storage profile you pass also grants its own host or bucket. See [Allowing remote hosts](chapters/08-location-policy/index.md#allowing-remote-hosts).

### Why does `allowed_remote={"https": frozenset()}` allow every host?

An empty set means no restriction for that scheme. To allow no hosts for a scheme, leave the scheme out of `allowed_remote`. Take care when building the mapping from configuration that an empty list cannot stand in for "nothing allowed". See [Allowing remote hosts](chapters/08-location-policy/index.md#allowing-remote-hosts).

### Why can my S3 facade reach other buckets?

An S3-family profile without `BUCKET` grants every bucket at its endpoint, and the facade does not check bucket names. Set `BUCKET` on the profile to hold a facade to one bucket, and list any extra buckets in `allowed_remote["s3"]`. See [Hosts granted by a profile](chapters/08-location-policy/index.md#hosts-granted-by-a-profile).

### Are HTTP redirects checked against the policy?

Yes. For HTTP the facade hands the check to the HTTP request engine, which applies it to every request it sends, including redirects and requests made during an authentication flow. A redirect to an unlisted host is refused before it is followed. The check compares host names, so it does not defend against DNS rebinding, and managed OAuth2 token endpoints are not checked. See [Allowing remote hosts](chapters/08-location-policy/index.md#allowing-remote-hosts).

### Where do I import `LocationNotAllowed` from?

From `mountainash_transport.location`; it is not re-exported from the package root. It subclasses `StorageError` and has `location` (the refused path, with any user name and password removed) and `reason` attributes. See [LocationNotAllowed](chapters/08-location-policy/index.md#locationnotallowed).

## Connections, tunnels and HTTP

### How do I get the underlying boto3, paramiko or httpx client?

Call `create_connection(profile, auth_profile)`, then `with connection.connect() as conn:` and use `conn.client`. Entering a `with` block on a connection does not connect; `connect()` does, and returns the connection. `create_connection` validates the auth pairing and performs no network I/O. See [Opening and closing](chapters/06-storage-facade/index.md#opening-and-closing) and [create_connection](chapters/11-connections/index.md#create_connection).

### How do I reach a store behind an SSH bastion?

Use `create_tunnelled_connection(bastion_profile, bastion_auth, target_profile, target_auth, remote_host, remote_port)`. On `connect()` it opens SSH to the bastion, starts a listener on `127.0.0.1` at `local_port`, and builds the target connection pointed at that listener. `StorageFacade` has no tunnel option, so you use the tunnelled client directly. The local listener has no access control while it is open. See [Bastion tunnels](chapters/11-connections/index.md#bastion-tunnels).

### Can I reach an HTTPS service through a tunnel?

No. A tunnelled connection rewrites `endpoint_url` or `base_url` to `http://127.0.0.1:<port>`, dropping the original scheme, host name and path prefix. The SSH hop to the bastion is encrypted, but an HTTPS-only service receives plain HTTP and the request fails. Tunnel plain-HTTP or SSH targets only. An `HTTPStorageProfile` or `aws` flavour S3 profile is not rewritten at all, so build HTTP URLs from `local_port` yourself. See [How the target endpoint is rewritten](chapters/11-connections/index.md#how-the-target-endpoint-is-rewritten).

### Why does SFTP through a tunnel fail host-key checking?

The target's host key is looked up under the rewritten address, `[127.0.0.1]:<local_port>`, and the port changes on every connect, so a known-hosts entry for the real target never matches. The default `reject` policy refuses the connection. Only `HOST_KEY_POLICY="warn"` or `"auto_add"` connect, and neither verifies the target's identity. See [Bastion tunnels](chapters/11-connections/index.md#bastion-tunnels).

### Why does my SFTP connection fail with "not found in known_hosts"?

`HOST_KEY_POLICY` defaults to `reject`, which refuses a server whose key is unknown. Point `KNOWN_HOSTS_FILE` on the `SFTPStorageProfile` at a known-hosts file that holds the server's key. `warn` and `auto_add` connect to unknown hosts and allow a man-in-the-middle on first contact. See [SFTP profile](chapters/05-storage-profiles/index.md#sftp-profile) and [SSHConnection](chapters/11-connections/index.md#sshconnection).

### How do I retry failed HTTP requests?

Construct `HttpRequestEngine(client, RequestPolicy(retry=RetryPolicy(...)))`, or pass `policy=` per call. The default allows three attempts and retries statuses 429, 500, 502, 503 and 504 and connection and timeout errors. Methods outside `IDEMPOTENT_METHODS` are retried only on 429 unless `retry_unsafe_methods=True`. A 429 is retried for any method and any body; transport errors and other retryable statuses are not retried when the body was passed as a non-seekable stream. Waits sleep in the calling thread. See [Retries](chapters/12-http-engine/index.md#retries).

### Do the engine's retries apply to HTTP storage reads and writes?

Yes. The HTTP storage backend sends every request through `HttpRequestEngine`, so its retry, timeout, redirect and redaction behaviour and any auth strategy apply to facade calls. See [HTTP](chapters/14-backends/index.md#http).

### Why does a random read over HTTP raise `RangeNotSupportedError`?

The server ignored the range request (answered `200`), did not report a size, or applied a `Content-Encoding` other than identity. There is no silent fallback to a full download; use `access="buffered"` if that is what you want. See [Random access](chapters/09-read-access-modes/index.md#random-access).

## Errors and troubleshooting

### Which exceptions should I catch?

There are three families with no shared base class. `StorageError` covers the facade, backends, profiles and location policy. `TransportConnectionError` covers `create_connection` and the S3, SSH, SFTP and tunnel connections, and can surface while a facade is being constructed. `HttpTransportError` covers `HttpRequestEngine` used directly. Through a facade, HTTP failures arrive as storage errors, so a missing URL raises `PathNotFoundError`. Caller mistakes keep their native types such as `ValueError`. See [The error families](chapters/03-installation/index.md#the-error-families).

### Why didn't `except StorageError` catch a connection failure?

`TransportConnectionError` and its subclasses (`ConnectionTimeoutError`, `UnsupportedAuthProfileError`) are separate from the `StorageError` hierarchy. Errors raised while a facade builds and connects its connection reach you as connection errors; later backend I/O failures are translated into storage errors. See [Connection errors](chapters/11-connections/index.md#connection-errors).

### Why do I get `TransportConnectionError` instead of `MissingExtraError` when boto3 is missing?

`MissingExtraError` covers only the `[http]` stack. A missing `boto3` or `paramiko` raises `TransportConnectionError` when the S3 or SSH connection is created, and using `GPG` without `[encryption]` raises a plain `ImportError`. Each message names the extra to install. When probing for optional backends, catch all three. See [MissingExtraError](chapters/03-installation/index.md#missingextraerror).

### What is the difference between `BackendNotImplementedError` and `ValueError` from `from_path`?

`BackendNotImplementedError` means the scheme is recognised and the provider has a profile but no backend; its message lists the implemented providers. `ValueError` means the scheme is not in transport's scheme table at all. See [From path to backend](chapters/04-paths-and-schemes/index.md#from-path-to-backend).

### How do I tell an authentication failure from a permission denial?

`PermissionDeniedError` subclasses `AuthenticationError`, so catch `PermissionDeniedError` first. A denial does not prove that the credentials are valid. See [The error families](chapters/03-installation/index.md#the-error-families).

### What does `ObjectChangedError` mean?

The object was replaced while a random-access read was in progress. On S3 and HTTP, range requests are pinned to a strong ETag with `If-Match`, so a change raises this error instead of mixing bytes from two versions. SFTP has no pinning, and weak or missing ETags give no guarantee. See [Random access](chapters/09-read-access-modes/index.md#random-access).

### Can error messages expose credentials?

Some can. `LocationNotAllowed` strips user information from URLs, and HTTP engine errors replace it with `***` and drop the native cause when it contained credentials. Tokens in query strings, headers and response bodies (including `body_preview`) are not redacted, and exception context or traceback locals can still hold them. Without an active policy, a `ValueError` from scheme detection quotes the path as given. Keep credentials in auth profiles, not URLs. See [Error redaction](chapters/12-http-engine/index.md#error-redaction) and [Credential redaction](chapters/08-location-policy/index.md#credential-redaction).

## Known limits

### Where are the current limits listed?

The [support matrix and known limits](reference/support-matrix.md#known-limits) page collects them, and each one is also noted in the chapter section where it matters. Several are answered above: [empty host sets](#why-does-allowed_remotehttps-frozenset-allow-every-host), [HTTPS through tunnels](#can-i-reach-an-https-service-through-a-tunnel), [the scope of `MissingExtraError`](#why-do-i-get-transportconnectionerror-instead-of-missingextraerror-when-boto3-is-missing), [closed source streams](#why-is-my-source-stream-closed-after-write_stream), [native copy](#why-did-copy_between-download-and-re-upload-instead-of-copying-server-side) and [settings-only profiles](#why-does-a-gcs-or-ftp-profile-raise-transportconnectionerror-instead-of-backendnotimplementederror).

### Does `rmdir` behave the same on local storage and SFTP?

No. On local storage `rmdir()` removes the directory and everything inside it. On SFTP it removes only an empty directory and raises for a non-empty one. Code that must behave the same on both should delete the contents first and then remove the empty directory. See [Directory operations](chapters/07-file-operations/index.md#directory-operations).

### How much memory does writing a large stream to SFTP use?

The whole payload. The SFTP backend reads the entire source stream into memory before writing it, for `write_stream`, for `write` with a transform pipeline, and for `copy_between` into SFTP. See [Where backends differ](chapters/14-backends/index.md#where-backends-differ).

### Is there a size limit on S3 `copy()`?

Yes. An S3-family `copy()` is one `CopyObject` request with no multipart fallback, so it is bounded by the provider's single-request copy limit (5 GB on Amazon S3). To copy a larger object, stream it with `read_stream` and `write_stream`, which uploads through boto3's multipart-capable upload, or use `copy_between` with facades that do not share one profile object. See [Where backends differ](chapters/14-backends/index.md#where-backends-differ).

### Why is an S3 listing with `max_results` slow on a large prefix?

On the S3 family, `max_results` is applied after every page of the listing has been fetched, so the number of requests depends on the size of the prefix, not on the limit. The SFTP backend stops as soon as it has enough entries. See [Where backends differ](chapters/14-backends/index.md#where-backends-differ).

## Extending and internals

### How does the facade know what a backend can do?

Each capability is a `typing.Protocol` marked `runtime_checkable`. A backend conforms by having the protocol's methods; it does not need to inherit from it. Before every call the facade checks `isinstance(backend, protocol)` and raises `UnsupportedOperationError` when the check fails. The check confirms that method names exist and does not compare signatures or behaviour, which is left to mypy and the test suites. See [Protocols as contracts](chapters/13-architecture/index.md#protocols-as-contracts).

### How is a built-in backend put together?

Each backend class inherits one mixin per capability and adds a constructor and connection handling, so adding or dropping a capability means adding or dropping a mixin. Each backend package has a private helper that translates the SDK's exceptions into `StorageError` subclasses, keeping the native exception as `__cause__`. See [Composing backends from mixins](chapters/13-architecture/index.md#composing-backends-from-mixins) and [Backend error mapping](chapters/14-backends/index.md#backend-error-mapping).

### Can I register my own backend without changing the package?

Yes. Decorate a class with `register_storage_backend(provider_type)` from `mountainash_transport.storage.registry`. The registry calls it as `cls(storage_profile, connection=connection)`, so it needs a positional profile parameter and a `connection` keyword. A later registration for the same provider type replaces the earlier one, so yours wins over a built-in, and registration is process-wide. A backend for a remote store also needs a connection class. See [register_storage_backend](chapters/13-architecture/index.md#register_storage_backend).

### How do I add a new backend to the package?

Add the provider type and URL scheme, a storage profile and spec, a connection class mapped in the connection factory, and a backend package with one mixin per supported protocol and an error-mapping helper. Then add the new provider's host checks to the facade's location policy, and add conformance and behaviour tests. The settings-only providers already have the provider type, scheme and profile. See [Adding a backend](chapters/15-maintaining/index.md#adding-a-backend).

### Does a new remote backend get location policy checks automatically?

No. `StorageFacade` applies `allowed_remote` host checks per provider family, and a new remote provider needs its own branch there, or its hosts are not checked against the policy. A missing connection mapping is also silent: `create_connection` falls back to `HTTPConnection`. See [Adding a backend](chapters/15-maintaining/index.md#adding-a-backend).

### Why must a backend import its SDK inside functions?

The base install is a tested contract. `tests/test_slim_install.py` imports every backend package in a subprocess that blocks everything outside the standard library, `typing-extensions` and `mountainash_transport`, so a module-level SDK import fails the test. See [Slim install test](chapters/15-maintaining/index.md#slim-install-test).

### Which tests guard the backend contracts?

The conformance test checks each backend's expected and excluded protocols. The registry completeness test checks that each profile spec's `implemented` flag is `True` exactly when a backend is registered, and that every scheme with a provider resolves to a backend or `BackendNotImplementedError`. The slim install test checks the base install boundary. See [Tests that guard the contracts](chapters/15-maintaining/index.md#tests-that-guard-the-contracts).

### How do I run the test suite?

Clone `mountainash-settings` and `mountainash-auth-client` next to the transport checkout, then use the `hatch.toml` scripts: `hatch run test:test` for the full suite with coverage, `hatch run test:test-quick` without coverage, and `hatch run test:test-target-quick <path>` for one file, directory or test id. `hatch run mypy:check` and `hatch run ruff:check` run type checks and lint. See [Tests that guard the contracts](chapters/15-maintaining/index.md#tests-that-guard-the-contracts).

### What happens if I call `clear_registry()`?

The built-in backends do not come back in the same process, so every facade raises `BackendNotImplementedError` until backends are registered again by hand. Use it only in tests that save a snapshot from `get_registered_backends()` and re-register it afterwards. See [Registry completeness tests](chapters/15-maintaining/index.md#registry-completeness-tests).

### Does the fsspec version matter?

Yes for random reads. The random-access reader uses an internal method of fsspec's cache classes rather than a documented API, so an fsspec release that changes it would affect random reads on S3, SFTP and HTTP. The `[http]` extra constrains fsspec to `>=2026.6.0,<2027`. See [RangedReader](chapters/14-backends/index.md#rangedreader).
