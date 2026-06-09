# SSH Absorption into mountainash-transport

## Context

The connection architecture alignment (PR #64) established three clean layers:
auth strategies, connections, and operations (backends). HTTP and S3 are
implemented. SSH support currently lives in a separate package
(`mountainash-utils-ssh`) with its own connection management (`SSH_Helper`),
settings (`SSHAuthSettings`), and reverse tunnel support. Transport already has
an `SSHStorageProfile` (descriptor-driven, 49 paramiko kwargs) but no
connection or backend.

This spec absorbs SSH into transport's connection architecture, deprecating
`mountainash-utils-ssh`.

## Problem

**Scattered SSH support:**
1. `mountainash-utils-ssh` has `SSH_Helper` (paramiko wrapper, reverse tunnel,
   context manager) and `SSHAuthSettings` (comprehensive validation).
2. `mountainash-transport` has `SSHStorageProfile` (descriptor-driven config)
   but no connection, no backend, no auth strategies.
3. No way to compose SSH tunnels with other connections (e.g., tunnel to a
   database or HTTP API through a bastion host).

**Auth resolver is HTTP-centric:**
`resolve_auth_strategy()` maps `PasswordAuth` to `BasicAuthStrategy` (HTTP
headers). SSH needs `PasswordAuth` to produce `{"password": secret}` for
paramiko. The resolver has no concept of SDK families.

## Design

### SDK-Family-Aware Auth Resolver

The resolver gains an optional `provider_type` parameter. The type is
`CONST_STORAGE_PROVIDER_TYPE | None` (the existing enum), not a raw string:

```python
def resolve_auth_strategy(
    auth_profile: AuthProfile | None,
    provider_type: CONST_STORAGE_PROVIDER_TYPE | None = None,
) -> AuthStrategy:
```

When `provider_type` is `CONST_STORAGE_PROVIDER_TYPE.SSH`, dispatch routes to
SSH-specific strategies. Default behaviour (no provider_type, or HTTP/S3
providers) is unchanged — fully backwards compatible.

`create_connection()` passes context from the profile:

```python
strategy = resolve_auth_strategy(auth_profile, provider_type=profile.provider_type)
```

The enum makes dispatch unambiguous — no string normalisation needed. Future
SDK families (FTP, SMB) add their own branches the same way.

### SSH Auth Strategies

Three new strategy classes in `_core/auth/strategies.py`:

| Strategy | Auth Profile | Paramiko kwargs produced |
|----------|-------------|------------------------|
| `SSHPasswordStrategy` | `PasswordAuth` | `{"password": secret}` |
| `SSHKeyStrategy` | `CertificateAuth` | `{"key_filename": path}` or `{"pkey": key_obj}` + `{"passphrase": ...}` |
| `SSHKerberosStrategy` | `KerberosAuth` | `{"gss_auth": True}` + optionally `{"gss_kex": True, "gss_host": host}` |

All follow the `AuthStrategy` protocol: `apply(kwargs) -> dict` returns a new
dict with credentials injected.

**SSHKeyStrategy detail:**
- If `CertificateAuth.PRIVATE_KEY_PATH` is set, injects `key_filename`.
- If `CertificateAuth.PRIVATE_KEY` is set (raw key string), parses it into a
  paramiko key object and injects `pkey`. The passphrase (if set) is passed
  to the parsing call itself — paramiko requires the passphrase during
  `from_private_key()`, not as a separate kwarg. Uses concrete key classes
  (`RSAKey`, `Ed25519Key`, `ECDSAKey`) with try/except fallthrough for type
  detection, since `PKey.from_private_key()` base-class auto-detection is
  version-sensitive.
- If `CertificateAuth.PRIVATE_KEY_PATH` is set with a passphrase, injects
  both `key_filename` and `passphrase` (paramiko's `connect()` accepts
  `passphrase` for file-based keys).

**SSHKerberosStrategy detail:**
- Always injects `gss_auth=True`.
- `gss_kex` defaults to `False` — many SSH servers support GSS auth but not
  GSS key exchange. Forcing `gss_kex=True` can cause hard connection failures.
  The strategy reads `gss_kex` from the profile's `_post_connect` envelope
  if present, allowing per-profile opt-in.
- If `KerberosAuth.SERVICE_NAME` is set, injects `gss_host` derived from the
  service name and the profile's hostname.

### SSHConnection (Leaf Connection)

General-purpose SSH connection exposing `paramiko.SSHClient`. Not limited to
storage — usable for tunnels, remote commands, SCP, or any SSH use case.

```
connections/ssh.py

class SSHConnection:
    __init__(profile, auth_strategy)
    connect() -> Self
    disconnect() -> None
    client -> paramiko.SSHClient | None
    is_connected -> bool
    __enter__ / __exit__
```

**Connect sequence:**
1. `import paramiko` (lazy — optional dependency `[sftp]` extra)
2. If already connected, disconnect first (idempotent — prevents leaked
   transports on repeated `connect()` calls)
3. `kwargs = profile.to_handler_kwargs()`
4. `kwargs = auth_strategy.apply(kwargs)` (inject credentials)
5. Pop `_post_connect` envelope from kwargs
6. Create `paramiko.SSHClient()`
7. Load system host keys via `client.load_system_host_keys()`
8. Apply host key policy from `_post_connect`:
   - `"reject"` → `paramiko.RejectPolicy()` (default — secure)
   - `"warn"` → `paramiko.WarningPolicy()`
   - `"auto_add"` → `paramiko.AutoAddPolicy()`
   - `"ignore"` → custom `_IgnorePolicy` (accepts any key, logs nothing)
   - Load `known_hosts_file` if provided (via `client.load_host_keys()`)
9. `client.connect(**kwargs)`
10. Store client

**Idempotency:** Calling `connect()` on an already-connected instance
disconnects first, then reconnects. This prevents leaked paramiko transports
and channels.

**Error wrapping (comprehensive):**
- `paramiko.AuthenticationException` → `TransportConnectionError`
- `paramiko.BadHostKeyException` → `TransportConnectionError`
- `paramiko.BadAuthenticationType` → `TransportConnectionError`
- `paramiko.PartialAuthentication` → `TransportConnectionError`
- `paramiko.SSHException` → `TransportConnectionError`
- `paramiko.ssh_exception.NoValidConnectionsError` → `TransportConnectionError`
- `socket.timeout` → `ConnectionTimeoutError`
- `socket.gaierror` (DNS resolution failure) → `TransportConnectionError`
- `OSError` (connection refused, network unreachable) → `TransportConnectionError`
- `ImportError` (paramiko not installed) → `TransportConnectionError`

**Ownership:** SSHConnection is designed for exclusive use by one decorator
(SFTPConnection or TunnelledConnection). Sharing an SSHConnection across
multiple decorators is not supported — each decorator must create its own.

**Thread safety:** `paramiko.SSHClient` is not safe for concurrent use without
external locking. SSHConnection is single-threaded by design. Concurrent
workflows should create separate SSHConnection instances.

### SFTPConnection (Decorator)

Wraps SSHConnection, opens an SFTP channel, exposes `paramiko.SFTPClient`.
This is the connection type wired to the SSH storage provider.

```
connections/sftp.py

class SFTPConnection:
    __init__(ssh_connection: SSHConnection)
    connect() -> Self
    disconnect() -> None
    client -> paramiko.SFTPClient | None
    is_connected -> bool
    __enter__ / __exit__
```

**Connect sequence:**
1. If already connected, disconnect first (idempotent)
2. If inner SSHConnection is not connected, connect it
3. `self._sftp = ssh_connection.client.open_sftp()`
4. Wrap `paramiko.SSHException` → `TransportConnectionError`

**Disconnect sequence:**
1. Close SFTP client
2. Disconnect SSH connection

**Ownership:** SFTPConnection has exclusive ownership of its SSHConnection.
`disconnect()` tears down both SFTP and SSH. Callers must not share the
inner SSHConnection with other decorators.

### TunnelledConnection (Decorator)

Wraps an SSHConnection (bastion) and any leaf connection (the target). Runs
a local TCP forwarding listener that tunnels traffic through the bastion via
paramiko `direct-tcpip` channels — like `ssh -L`.

A raw `direct-tcpip` channel is a single socket-like object. Inner SDK clients
(httpx, boto3) pool and reconnect — they need a real TCP endpoint, not a
paramiko channel. TunnelledConnection solves this by binding a local listener
on an ephemeral port. Each incoming TCP connection spawns a new `direct-tcpip`
channel to the remote target. The inner connection's profile is patched to
point at `localhost:forwarded_port`.

```
connections/tunnel.py

class TunnelledConnection:
    __init__(
        ssh_connection: SSHConnection,        # bastion host
        inner_connection_factory: Callable,    # builds inner connection (called after tunnel is up)
        remote_host: str,                      # target from bastion's perspective
        remote_port: int,
    )
    connect() -> Self
    disconnect() -> None
    client -> Any                             # inner connection's client
    is_connected -> bool
    local_port -> int                         # the ephemeral forwarded port
    __enter__ / __exit__
```

**Connect sequence:**
1. If already connected, disconnect first (idempotent)
2. If bastion SSHConnection is not connected, connect it
3. Bind a local TCP listener on `127.0.0.1:0` (OS-assigned ephemeral port)
4. Start a background daemon thread that accepts connections on the listener.
   For each accepted connection:
   a. Open `transport.open_channel("direct-tcpip", (remote_host, remote_port), ("127.0.0.1", local_port))`
   b. Bidirectionally forward data between the local socket and the channel
   c. Close both when either side disconnects
5. Record `self._local_port` from the bound socket
6. Call `inner_connection_factory(local_port)` to build the inner connection
   with its profile pointing at `localhost:local_port`
7. `inner_connection.connect()`

**Disconnect sequence (reverse order):**
1. Disconnect inner connection
2. Stop the listener thread (close the listener socket — the thread exits)
3. Close any active channels
4. Disconnect SSH connection

**`.client`** delegates to `inner_connection.client` — the backend is unaware
it's tunnelled.

**Inner connection factory:** Instead of receiving a pre-built inner
connection (whose profile would point at the wrong host/port), the constructor
takes a factory callable `(local_port: int) -> ConnectionProtocol`. This lets
the factory build the inner connection with the correct `localhost:local_port`
after the tunnel is up.

**Error wrapping:**
- `paramiko.ChannelException` → `TransportConnectionError`
- Channel open failure → `TransportConnectionError`
- Listener bind failure (`OSError`) → `TransportConnectionError`

**Ownership:** TunnelledConnection has exclusive ownership of its
SSHConnection. The inner connection is also exclusively owned.

### create_tunnelled_connection() Factory

Public factory in `connections/__init__.py`:

```python
def create_tunnelled_connection(
    bastion_profile: StorageProfileProtocol,
    bastion_auth: AuthProfile | None,
    target_profile: StorageProfileProtocol,
    target_auth: AuthProfile | None,
    remote_host: str,
    remote_port: int,
) -> TunnelledConnection:
    ssh_conn = SSHConnection(
        bastion_profile,
        resolve_auth_strategy(bastion_auth, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH),
    )

    def inner_factory(local_port: int) -> ConnectionProtocol:
        patched = _patch_profile_endpoint(target_profile, "127.0.0.1", local_port)
        return create_connection(patched, target_auth)

    return TunnelledConnection(ssh_conn, inner_factory, remote_host, remote_port)
```

`_PatchedEndpointProfile` is a wrapper class in `connections/tunnel.py` that
delegates to the original profile but overrides `to_handler_kwargs()` to
replace known endpoint keys with the tunnel address:
- `hostname` + `port` → `127.0.0.1` + `local_port` (SSH, paramiko)
- `base_url` → `http://127.0.0.1:local_port` (HTTP, httpx)
- `endpoint_url` → `http://127.0.0.1:local_port` (S3, boto3)

All other kwargs and attributes pass through via `__getattr__` delegation.

### SFTPStorageBackend

Stateless operation handler registered as the SSH storage provider. Receives
an SFTPConnection and delegates file operations to `paramiko.SFTPClient`.

```
storage/backends/ssh/__init__.py

@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SSH)
class SFTPStorageBackend:
    __init__(storage_profile, *, connection=None)
    _get_client() -> paramiko.SFTPClient
```

**Protocols implemented (5 of 8):**

| Protocol | Methods | SFTP mapping |
|----------|---------|-------------|
| Read | `read_to_bytes`, `read_to_stream` | `sftp.open(path, "rb")` |
| Write | `write_from_bytes`, `write_from_stream` | `sftp.open(path, "wb")` |
| List | `list_paths` | `sftp.listdir_attr(path)` |
| Delete | `delete_path` | `sftp.remove(path)` |
| Metadata | `path_exists`, `get_metadata`, `get_size` | `sftp.stat(path)` |

**Not implemented:**
- Copy: SFTP has no server-side copy. Use the facade's `copy_between`.
- Directory: `mkdir`/`rmdir` can be added later if needed.
- Connection: Managed by SFTPConnection, not the backend.

**Path semantics:** The backend receives remote filesystem paths, not URIs.
URI-to-remote-path stripping is handled by `StoragePath` in the facade layer
before the path reaches the backend. `StorageFacade.from_path("sftp://host/data/file.txt")`
extracts `/data/file.txt` as the remote path. The backend operates exclusively
on remote paths (e.g., `/data/file.txt`, `relative/path.txt`).

**Stream handling:** `read_to_stream` materialises the file content into a
`BytesIO` buffer before returning — not a raw `SFTPFile` handle. This ensures
the returned stream is independent of the SFTP connection lifecycle and safe
to use after the backend call returns.

**Error mapping:**
- `FileNotFoundError` / `IOError(errno=ENOENT)` → `PathNotFoundError`
- `IOError(errno=ENOTDIR)` / `IOError(errno=EISDIR)` → `StorageError`
- `PermissionError` / `IOError(errno=EACCES)` → `StorageError` (filesystem
  permission, not authentication failure — authentication errors surface at
  the connection layer)
- `paramiko.SFTPError` → `StorageError`
- `paramiko.SSHException` / `socket.error` during file ops (dropped
  connection) → `StorageConnectionError`

### Registration and Wiring

**`create_connection()` SSH branch:**
SFTPConnection has a different constructor signature than leaf connections
(it takes an SSHConnection, not a profile + strategy). The factory handles
this with an explicit branch, like the existing OAuth branches:

```python
# In create_connection():
if provider_type == CONST_STORAGE_PROVIDER_TYPE.SSH:
    strategy = resolve_auth_strategy(auth_profile, provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH)
    ssh_conn = SSHConnection(profile, strategy)
    return SFTPConnection(ssh_conn)
```

SSH is NOT added to `_PROVIDER_CONNECTION_MAP` — the explicit branch handles
the two-layer composition directly.

**Public API exports** (`__init__.py`):
- `SSHConnection`, `SFTPConnection`, `TunnelledConnection`
- `create_tunnelled_connection`
- `SSHPasswordStrategy`, `SSHKeyStrategy`, `SSHKerberosStrategy`

## File Layout

```
# New files
_core/auth/strategies.py            # + SSHPasswordStrategy, SSHKeyStrategy, SSHKerberosStrategy

connections/
  ssh.py                            # SSHConnection (leaf)
  sftp.py                           # SFTPConnection (decorator)
  tunnel.py                         # TunnelledConnection (decorator + local listener)

storage/backends/ssh/
  __init__.py                       # SFTPStorageBackend

# Modified files
_core/auth/resolver.py              # + provider_type param, SSH branches
_core/auth/__init__.py              # re-export new strategies
connections/__init__.py             # + SSH branch in create_connection(), create_tunnelled_connection()
__init__.py                         # + public API exports

# Test files
tests/_core/auth/test_ssh_strategies.py
tests/_core/auth/test_resolver_ssh.py
tests/connections/test_ssh_connection.py
tests/connections/test_sftp_connection.py
tests/connections/test_tunnel_connection.py
tests/connections/test_tunnel_factory.py
tests/storage/backends/test_sftp.py
```

## Deprecation of mountainash-utils-ssh

After this work lands, `mountainash-utils-ssh` provides no independent value:
- `SSH_Helper` connection management → `SSHConnection`
- `SSH_Helper._setup_reverse_tunnel()` → `TunnelledConnection`
- `SSHAuthSettings` validation → `SSHStorageProfile` + auth strategies

**Action:** Mark `mountainash-utils-ssh` as deprecated in its README. No
immediate deletion. Downstream consumers migrate to
`from mountainash_transport.connections import SSHConnection, SFTPConnection, TunnelledConnection`.

## Verification

After implementation:
1. `hatch run test:test-quick` — all tests pass, no regressions
2. `hatch run ruff:check` — lint clean
3. Existing HTTP and S3 paths unaffected (resolver default unchanged)
4. Public API imports unchanged (facade, read_bytes, etc.)
5. New SSH path: `StorageFacade.from_path("sftp://host/path")` works end-to-end
