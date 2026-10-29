---
title: Location policy
---

# Location policy

A location policy limits where a `StorageFacade` may reach. It confines local paths to a root directory, lists the remote hosts or S3 buckets each URL scheme may contact, and accepts the host or bucket named by the storage profile you supplied. Every facade operation checks its path against the policy before any I/O, and a refused path raises `LocationNotAllowed` with credentials removed from the message. Use it when paths come from configuration, user input or another system and should not be able to leave a known area.

The policy lives in `mountainash_transport.location`, a standard-library-only module that works on a base install. This page assumes you can open a facade (see [creating a facade](../06-storage-facade/index.md#creating-a-facade)) and know what a storage profile holds (see [what a storage profile is](../05-storage-profiles/index.md#what-a-storage-profile-is)).

## LocationPolicy

<!-- concept:123 -->

`LocationPolicy` is a frozen dataclass with three fields:

| Field | Default | Meaning |
|---|---|---|
| `root` | `None` | A directory that local paths must stay inside. Relative paths resolve beneath it. |
| `allowed_remote` | `{}` | A mapping from canonical URL scheme (`"http"`, `"https"`, `"s3"`, `"sftp"` and so on) to a `frozenset` of host names or S3 bucket names that scheme may reach. |
| `allow_unconfined` | `False` | An explicit opt-out. When `True`, the policy is inactive and checks nothing. |

You pass a policy as `policy=` to `StorageFacade(...)`, `StorageFacade.from_path(...)` or `StorageFacade.for_local(...)`. A facade with no policy behaves as if confinement did not exist: no path is checked. A facade with an active policy checks every path, and refuses any URL whose scheme is not in transport's scheme registry (see [how a path picks a backend](../04-paths-and-schemes/index.md#how-a-path-picks-a-backend)).

The checks that apply depend on the facade's backend:

```mermaid
flowchart TD
    P["path given to a facade operation"] --> A{"active policy?"}
    A -->|"no policy, or allow_unconfined"| OK["operation runs"]
    A -->|yes| K{"known scheme?"}
    K -->|no| X["LocationNotAllowed"]
    K -->|yes| B{"backend"}
    B -->|local| R{"root set?"}
    R -->|no| OK
    R -->|yes| IN{"resolved path<br/>inside root?"}
    IN -->|yes| OK
    IN -->|no| X
    B -->|"S3 family, SFTP, HTTP"| PH{"host or bucket matches<br/>caller's profile?"}
    PH -->|yes| OK
    PH -->|no| AL{"listed in<br/>allowed_remote[scheme]?"}
    AL -->|yes| OK
    AL -->|no| X
```

An active policy with no `root` leaves local paths unconfined but still restricts remote hosts. A policy with only a `root` refuses every remote host that the profile does not grant. The two halves are independent, so one policy can serve both a local facade and a remote one.

<!-- concept:127 -->

### LocationNotAllowed

`LocationNotAllowed` is the error a refused path raises. It subclasses `StorageError`, so handlers written for storage failures catch it, and you import it from `mountainash_transport.location` (it is not re-exported from the package root). It has two attributes: `location`, the refused path with any user name and password removed, and `reason`, a short code. The message combines them:

```text
location not allowed: ../secrets.txt (outside root)
```

That line is real output from the example in [confining local paths](#confining-local-paths). The reasons you will see are `outside root`, `remote not allowed`, `profile host mismatch`, `unknown scheme`, `invalid location` (a URL that cannot be parsed), `invalid file URI` and `copy destination is a directory`. The check runs before the backend is called, so a refused path is never opened, written or deleted.

## Confining local paths

<!-- concept:124 -->

With `root` set, a local path is joined to the root, resolved, and compared with the resolved root. Resolution follows symbolic links and collapses `..`, so the check is on where the path really points, not on how it is spelled. The facade then uses the resolved path. Paths that do not exist yet, such as a file about to be written, are resolved as far as they exist and accepted if they would land inside the root. `file://` URIs are decoded and treated as local paths.

```python
import os
import tempfile

from mountainash_transport import StorageError, StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy

with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, "reports")
    os.makedirs(root)
    with open(os.path.join(tmp, "secrets.txt"), "wb") as fh:
        fh.write(b"keep out")
    os.symlink(os.path.join(tmp, "secrets.txt"), os.path.join(root, "shortcut.txt"))

    with StorageFacade.for_local(policy=LocationPolicy(root=root)) as storage:
        storage.write("2026/sales.csv", b"region,total\nnorth,120\n")
        print(storage.read("2026/sales.csv"))
        print(os.path.exists(os.path.join(root, "2026", "sales.csv")))

        attempts = {
            "dot-dot": "../secrets.txt",
            "absolute": os.path.join(tmp, "secrets.txt"),
            "symlink": "shortcut.txt",
        }
        for label, path in attempts.items():
            try:
                storage.read(path)
            except LocationNotAllowed as exc:
                print(f"{label}: {exc.reason}")

        try:
            storage.read("../secrets.txt")
        except StorageError as exc:
            print(exc)
```

Output:

```text
b'region,total\nnorth,120\n'
True
dot-dot: outside root
absolute: outside root
symlink: outside root
location not allowed: ../secrets.txt (outside root)
```

The relative path `2026/sales.csv` was written beneath the root, with its parent directory created. The symbolic link `shortcut.txt` sits inside the root but points outside it, so reading it is refused. Copies get one extra check: when the destination of `copy` is an existing directory, the file path inside it is checked too, and the copy is refused if that path is itself a directory.

<!-- concept:139 -->

### The local profile

`LocalStorageProfile` has two fields. `ROOT_PATH` names a directory, and `CREATE_PATH` asks the facade to create it if it is missing. When you open a local facade with a profile that sets `ROOT_PATH`, that directory becomes the policy root, even if you passed no policy at all. If you pass a policy that already has a `root`, yours wins, and `CREATE_PATH` only creates the profile's directory when it lies inside your root. A policy that sets only `allowed_remote` keeps the profile's root. To use a profile without confinement, pass `LocationPolicy(allow_unconfined=True)`.

```python
import os
import tempfile

from mountainash_transport import CONST_STORAGE_PROVIDER_TYPE, StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.settings.storage.profiles import LocalStorageProfile

with tempfile.TemporaryDirectory() as tmp:
    root = os.path.join(tmp, "archive")
    profile = LocalStorageProfile(ROOT_PATH=root, CREATE_PATH=True)

    with StorageFacade(CONST_STORAGE_PROVIDER_TYPE.LOCAL, profile) as storage:
        print(os.path.isdir(root))
        storage.write("sales.csv", b"region,total\n")
        print(sorted(os.listdir(root)))
        try:
            storage.write("../escape.csv", b"x")
        except LocationNotAllowed as exc:
            print(exc)

    with StorageFacade(CONST_STORAGE_PROVIDER_TYPE.LOCAL, profile,
                       policy=LocationPolicy(allow_unconfined=True)) as storage:
        storage.write(os.path.join(tmp, "outside.csv"), b"x")
        print(sorted(os.listdir(tmp)))
```

Output:

```text
True
['sales.csv']
location not allowed: ../escape.csv (outside root)
['archive', 'outside.csv']
```

`LocalStorageProfile` is a settings profile and needs the `[http]` extra. On a base install, confine a local facade with `LocationPolicy(root=...)` instead. Network filesystems are confined the same way once the operating system has mounted them; transport does not mount anything.

## Allowing remote hosts

<!-- concept:125 -->

`allowed_remote` lists, per scheme, the hosts a facade may contact. Keys are canonical scheme names, so `http` and `https` are separate entries. Host names are compared after lowercasing and IDNA encoding; ports are not part of the comparison. For the S3 family the "host" is the bucket name, because the bucket is what an S3 path names (see [S3 bucket and key parsing](../04-paths-and-schemes/index.md#s3-bucket-and-key-parsing)).

For HTTP, the facade passes the check to the HTTP request engine, which calls it on every request it sends, including redirects and requests made during an authentication flow. A redirect to an unlisted host is refused before it is followed. The engine accepts the same check directly through its `location_check` argument (see [making requests](../12-http-engine/index.md#making-requests)).

The example below runs against a local HTTP server on `127.0.0.1`, where `/moved.csv` redirects to the same server under the name `localhost`. The server bootstrap line is omitted; `port` is the server's port.

```python
from mountainash_transport import StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy

by_ip = f"http://127.0.0.1:{port}/sales.csv"
by_name = f"http://localhost:{port}/sales.csv"
redirected = f"http://127.0.0.1:{port}/moved.csv"

policies = {
    "listed host": LocationPolicy(allowed_remote={"http": frozenset({"127.0.0.1"})}),
    "empty set": LocationPolicy(allowed_remote={"http": frozenset()}),
    "https only": LocationPolicy(allowed_remote={"https": frozenset({"127.0.0.1"})}),
    "no entries": LocationPolicy(),
}

for label, policy in policies.items():
    with StorageFacade.from_path(by_ip, policy=policy) as storage:
        for url in (by_ip, by_name, redirected):
            try:
                outcome = f"read {len(storage.read(url))} bytes"
            except LocationNotAllowed as exc:
                outcome = f"refused ({exc.reason})"
            print(f"{label:12} {url.split('/')[2].split(':')[0]:9} "
                  f"{url.rsplit('/', 1)[1]:10} {outcome}")
```

Output:

```text
listed host  127.0.0.1 sales.csv  read 23 bytes
listed host  localhost sales.csv  refused (remote not allowed)
listed host  127.0.0.1 moved.csv  refused (remote not allowed)
empty set    127.0.0.1 sales.csv  read 23 bytes
empty set    localhost sales.csv  read 23 bytes
empty set    127.0.0.1 moved.csv  read 23 bytes
https only   127.0.0.1 sales.csv  refused (remote not allowed)
https only   localhost sales.csv  refused (remote not allowed)
https only   127.0.0.1 moved.csv  refused (remote not allowed)
no entries   127.0.0.1 sales.csv  refused (remote not allowed)
no entries   localhost sales.csv  refused (remote not allowed)
no entries   127.0.0.1 moved.csv  refused (remote not allowed)
```

With `127.0.0.1` listed, the same server is refused under the name `localhost`, and the redirect to `localhost` is refused before it is followed. A scheme with no entry refuses every host, which is why the `https`-only policy blocks plain `http`.

!!! warning "An empty set allows every host"
    `allowed_remote={"http": frozenset()}` does not block `http`; it allows any host for that scheme, as the "empty set" rows above show. This is the current behaviour of `allow_remote` in `src/mountainash_transport/location.py`: a scheme that is absent from the mapping is refused, while a scheme mapped to an empty set is unrestricted. To block a scheme, leave it out of `allowed_remote`. Do not build an allow-list from configuration in a way that can produce an empty set when you mean "nothing allowed". See the [support matrix and known limits](../../reference/support-matrix.md).

!!! note "DNS resolution and token endpoints after the host check"
    The check compares host names, so it does not defend against DNS rebinding, where an allowed name resolves to an unexpected address. Token endpoints used by managed OAuth2 are not checked by the policy.

<!-- concept:126 -->

### Hosts granted by a profile

A storage profile you pass to the facade grants its own host without an `allowed_remote` entry. An SFTP profile grants its `HOST`: an `sftp://` URL for another host is refused with `profile host mismatch`, while plain paths go to the profile's host and need no host check. An S3-family profile with a `BUCKET` grants that bucket only. An S3-family profile without a `BUCKET` grants every bucket at its endpoint, and the facade does not check bucket names at all. `allowed_remote` can add hosts beyond the profile's own, but a profile never grants anything other than its own host or bucket.

The example below runs against an in-process S3 service with buckets `reports`, `archive` and `payroll`, each holding `sales.csv`. The bootstrap line that starts it is omitted.

```python
from mountainash_auth_client import IAMAuthProfile
from mountainash_transport import CONST_STORAGE_PROVIDER_TYPE, StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.settings.storage.profiles import S3StorageProfile

keys = IAMAuthProfile(ACCESS_KEY_ID="example-access-key", SECRET_ACCESS_KEY="example-secret")
cases = {
    "BUCKET=reports": (S3StorageProfile(BUCKET="reports"), LocationPolicy()),
    "BUCKET=reports, archive listed": (
        S3StorageProfile(BUCKET="reports"),
        LocationPolicy(allowed_remote={"s3": frozenset({"archive"})}),
    ),
    "no BUCKET": (S3StorageProfile(), LocationPolicy()),
}

for label, (profile, policy) in cases.items():
    with StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, profile,
                       auth_profile=keys, policy=policy) as storage:
        results = []
        for bucket in ("reports", "archive", "payroll"):
            try:
                storage.read(f"s3://{bucket}/sales.csv")
                results.append(f"{bucket}=ok")
            except LocationNotAllowed as exc:
                results.append(f"{bucket}: {exc.reason}")
        print(f"{label}: {', '.join(results)}")
```

Output:

```text
BUCKET=reports: reports=ok, archive: profile host mismatch, payroll: profile host mismatch
BUCKET=reports, archive listed: reports=ok, archive=ok, payroll: profile host mismatch
no BUCKET: reports=ok, archive=ok, payroll=ok
```

Set `BUCKET` on S3 profiles whenever a facade should be held to one bucket. The SFTP rules are exercised in `tests/test_location.py`.

## Policy on the facade

<!-- concept:158 -->

The facade applies the policy in one place: every operation that takes a path checks it before calling the backend. That covers `read`, `read_stream`, `write`, `write_stream`, `list_objects`, `delete`, `exists`, `metadata`, `get_size`, `list_dir`, `mkdir`, `rmdir`, and both ends of `copy`. `from_path` also refuses an unknown scheme before it constructs anything. `supports()` does not take a path and is unaffected. Operation behaviour itself is described in [file operations](../07-file-operations/index.md).

`copy_between` uses each facade's own policy: the source facade checks the source path and the destination facade checks the destination path (see [copying between backends](../10-stream-transforms/index.md#copying-between-backends)). The policy is fixed when the facade is created; open a new facade to change it. Maintainers will find the dispatch in `StorageFacade._check` in `src/mountainash_transport/storage/facade/facade.py` and the rules in `src/mountainash_transport/location.py`, with tests in `tests/test_location.py` and `tests/storage/facade/test_facade_location_policy.py`.

<!-- concept:128 -->

### Credential redaction

URLs sometimes carry credentials in their user-info part, as in `https://user:password@host/path`. `LocationNotAllowed` strips that part before storing `location` or building its message, and a URL that cannot be parsed is reported as `invalid location` without chaining the parser's exception, which could quote the input. The redaction applies to policy errors. Without an active policy, other errors may still quote the path as given:

```python
from mountainash_transport import StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy

policy = LocationPolicy(allowed_remote={"https": frozenset({"data.example.com"})})

try:
    StorageFacade.from_path("nfs://admin:hunter2@files.example.com/share", policy=policy)
except LocationNotAllowed as exc:
    print(exc)
    print(exc.location)

with StorageFacade.from_path("https://data.example.com/", policy=policy) as storage:
    try:
        storage.read("https://admin:hunter2@files.example.com/sales.csv")
    except LocationNotAllowed as exc:
        print(exc)

try:
    StorageFacade.from_path("nfs://admin:hunter2@files.example.com/share")
except ValueError as exc:
    print(f"{type(exc).__name__}: {exc}")
```

Output:

```text
location not allowed: nfs://files.example.com/share (unknown scheme)
nfs://files.example.com/share
location not allowed: https://files.example.com (remote not allowed)
ValueError: Unrecognised scheme in path 'nfs://admin:hunter2@files.example.com/share'
```

The last call had no policy, and the `ValueError` from scheme detection quotes the path, password included. Keep credentials in auth profiles rather than URLs (see [credentials come from auth-client](../02-mountainash-ecosystem/index.md#credentials-come-from-auth-client)). HTTP errors have their own redaction, described in [error redaction](../12-http-engine/index.md#error-redaction).
