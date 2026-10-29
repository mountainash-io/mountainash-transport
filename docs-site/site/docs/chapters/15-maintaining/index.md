---
title: Maintaining and extending transport
---

# Maintaining and extending transport

mountainash-transport keeps its backend contracts honest with tests rather than documentation: conformance tests check each backend's protocol set, registry tests check that profiles, schemes and backends agree, and a slim-install test checks that the base install never imports an optional SDK. A new backend has to pass all three.

It assumes the protocol and registry model in [Architecture: protocols and dispatch](../13-architecture/index.md), the [support matrix](../14-backends/index.md#support-matrix), the extras in [Base install and extras](../03-installation/index.md#base-install-and-extras) and the connection layer in [Leaf connections](../11-connections/index.md#leaf-connections).

## Tests that guard the contracts

The development environments are defined in `hatch.toml` and described in `TESTING.md` and `CONTRIBUTING.md`. The local environments install `mountainash-settings` and `mountainash-auth-client` from sibling checkouts next to this repository (`../mountainash-settings`, `../mountainash-auth-client`), so those must be cloned first. The commands below are scripts defined in `hatch.toml`:

| Command | What it runs |
|---|---|
| `hatch run test:test` | Full suite with coverage, then JSON, XML, HTML and terminal reports |
| `hatch run test:test-quick` | Full suite without coverage |
| `hatch run test:test-target-quick <path>` | One file, directory or test id, without coverage |
| `hatch run test:test-changed-quick` | Tests for changed files only (`pytest --picked`) |
| `hatch run test_github:test-cov` | The CI run used by `.github/workflows/python-run-pytest.yml` |
| `hatch run mypy:check` | mypy over `src/mountainash_transport` and `tests`, with the `[s3]`, `[sftp]` and `[encryption]` extras installed |
| `hatch run ruff:check` | Lint `src` (`ruff:fix` applies fixes) |

The `test` environment includes boto3, paramiko, python-gnupg and authlib, so backend tests run without extra setup. Tests use `unit`, `integration`, `performance` and `slow` markers, registered in `tests/conftest.py`, and `test:test-unit` and its siblings select by marker. The test tree mirrors `src/`. To run only the contract tests in this section:

```bash
hatch run test:test-target-quick tests/storage/protocols tests/test_slim_install.py
```

<!-- concept:221 -->
### Conformance tests

`tests/storage/protocols/test_backend_conformance.py` holds an `EXPECTED_PROTOCOLS` set and an `EXCLUDED_PROTOCOLS` set per provider type and asserts `issubclass(backend_cls, protocol)` for each against `get_registered_backends()`. A mixin added or removed by accident changes a backend's protocol set and fails here. The file covers the seven core protocols for `local`, `s3`, `r2`, `s3express`, `minio`, `sftp` and `http`; it has no `RangedReadProtocol` column and no `b2` row, so those cells of the support matrix rest on the structural check and on the behaviour tests below.

Shape and behaviour are tested separately:

- `tests/storage/protocols/test_protocol_shapes.py` checks each protocol against minimal conforming and non-conforming classes.
- `tests/storage/backends/test_ranged_conformance.py` runs the same random-read cases against S3, HTTP and SFTP with fakes that honour byte ranges, including object-change detection.
- `tests/storage/backends/test_directory_semantics.py` runs shared filesystem contracts (parent creation, `mkdir`, metadata, listing and enumeration) against local and SFTP.
- `tests/storage/backends/test_sequential_reads.py` and `test_read_initialization.py` cover lazy stream consumption, error translation and handle cleanup.
- `tests/storage/backends/test_local.py`, `test_s3.py`, `test_sftp.py`, `test_http.py` and `test_http_ranges.py` cover each backend's own calls and error mapping.

<!-- concept:222 -->
### Registry completeness tests

`tests/storage/protocols/test_registry_completeness.py` keeps three sources of truth in step. For every storage profile spec, `spec.implemented` must be `True` exactly when a backend is registered for its provider type. For every scheme with a provider, `get_storage_backend()` must either return a backend or raise `BackendNotImplementedError`, never an opaque `ValueError`. The settings-only providers in [Specs, the registry and settings-only providers](../05-storage-profiles/index.md#specs-the-registry-and-settings-only-providers) pass because their specs say `implemented=False`. `tests/storage/registry/` tests registration, override, lookup, scheme detection and the `auth_strategy` guard.

Registry tests mutate process-wide state. `clear_registry()` empties the mapping, and the built-ins do not come back: they register when the backends package is first imported, and later registry calls see that package as already loaded. A test that clears the registry must restore it itself. A snapshot from `get_registered_backends()` can be re-registered with the public decorator:

```python
from mountainash_transport import BackendNotImplementedError, StorageFacade
from mountainash_transport.storage.registry import (
    clear_registry, get_registered_backends, register_storage_backend,
)

saved = get_registered_backends()                     # a copy
clear_registry()
print(get_registered_backends())                      # -> {}

try:
    StorageFacade.for_local()
except BackendNotImplementedError as exc:
    print(exc)

for provider, cls in saved.items():                   # restore from the snapshot
    register_storage_backend(provider)(cls)
print(sorted(get_registered_backends()) == sorted(saved))   # -> True
```

Output:

```text
{}
The 'local' storage provider is not yet implemented. Implemented providers: []
True
```

!!! warning
    `clear_registry()` cannot restore the built-in backends in the same process. After it runs, every facade raises `BackendNotImplementedError` until the backends are registered again by hand. Use it only in tests that save and restore the registry.

<!-- concept:223 -->
### Slim install test

`tests/test_slim_install.py` runs code in a subprocess with an import blocker that allows only the standard library, `typing_extensions` and `mountainash_transport`. Anything outside the base install fails to import, and the blocker is derived from that rule rather than a list of SDK names, so a new backend that imports its SDK at module level fails without the test being edited. Inside the blocker the test checks that:

- a local facade can write, read (including random access and gzip), list and size files;
- every built-in backend package imports and registers;
- unimplemented schemes such as `gs://` and `ftp://` still raise `BackendNotImplementedError`;
- a caller's registration overrides a built-in;
- remote entry points raise `MissingExtraError` naming the `[http]` extra.

`tests/test_lazy_imports.py` checks that `import mountainash_transport` loads no heavy SDK, and `tests/test_installed_contract.py` checks the distribution metadata: a base install that requires only `typing-extensions`, and the `[http]` stack inside every remote extra.

## Adding a backend

<!-- concept:224 -->
A new backend touches the provider vocabulary, settings, connections, the backend package and the tests. The settings-only providers (GCS, Azure, FTP, SMB, GitHub) already have the first two.

1. Provider type and scheme. Add a member to `CONST_STORAGE_PROVIDER_TYPE` in `src/mountainash_transport/_core/constants.py` if none exists, and a `SchemeSpec` mapping the URL scheme to it in `src/mountainash_transport/_schemes.py` (see [How a path picks a backend](../04-paths-and-schemes/index.md#how-a-path-picks-a-backend)).
2. Storage profile. Add a profile class and spec under `src/mountainash_transport/settings/storage/profiles/`, as described in [Provider profiles](../05-storage-profiles/index.md#provider-profiles). Set `implemented=False` until the backend is registered, then remove it; the registry completeness test enforces the pairing.
3. Connection. Add a leaf connection class implementing `ConnectionProtocol` in `src/mountainash_transport/connections/` and map the provider type to it in the provider-to-connection table in `connections/__init__.py`. Raise `TransportConnectionError` subclasses for connection failures (see [Connection errors](../11-connections/index.md#connection-errors)). Credentials arrive from an auth profile owned by mountainash-auth-client; see [Credentials come from auth-client](../02-mountainash-ecosystem/index.md#credentials-come-from-auth-client).
4. Backend package. Create `src/mountainash_transport/storage/backends/<name>/` with one mixin per protocol the store can honour and a `_helpers.py` that maps the SDK's exceptions to `StorageError` subclasses with `raise ... from`. Give the backend class a `(storage_profile=None, *, connection=None)` constructor, decorate it with `@register_storage_backend(...)`, and import the package from `storage/backends/__init__.py`. Import the SDK inside functions, never at module level.
5. Facade policy. `StorageFacade` applies `allowed_remote` host checks per provider family in `src/mountainash_transport/storage/facade/facade.py`. A new remote provider needs a branch there, or its hosts are not checked against the policy.
6. Tests and documentation. Add the provider's expected and excluded protocols to the conformance test, write behaviour tests for its calls and error mapping, and update the root README's support matrix, which must match `get_registered_backends()`. A new example under `examples/` needs an index row in `examples/README.md`; `tests/examples/` runs every recipe.

!!! warning "Unmapped providers get an HTTP connection"
    `create_connection` falls back to `HTTPConnection` for a provider type with no entry in its connection table, without raising. A new backend whose connection mapping is missing receives an HTTP client instead of its own. See the [support matrix and known limits](../../reference/support-matrix.md).

A backend that accepts `auth_strategy` must name it in its constructor (or take `**kwargs`). Otherwise the registry raises `BackendNotImplementedError` when a facade with managed OAuth2 tries to build it.

The same contract applies to a backend kept outside the package. The class below is registered for GCS and tested the way the conformance test tests the built-ins:

```python
import io
import pytest
from mountainash_transport import (
    CONST_STORAGE_PROVIDER_TYPE, StorageCopyProtocol, StorageDirectoryProtocol,
    StorageFacade, StorageReadProtocol, StorageWriteProtocol,
)
from mountainash_transport.storage.registry import (
    get_registered_backends, register_storage_backend,
)


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS)
class MemoryBackend:
    def __init__(self, storage_profile=None, *, connection=None):
        self.storage_profile = storage_profile
        self.blobs = {}

    def read_to_bytes(self, path):
        return self.blobs[path]

    def read_to_stream(self, path):
        return io.BytesIO(self.blobs[path])

    def write_from_bytes(self, path, data, *, create_parents=True):
        self.blobs[path] = data

    def write_from_stream(self, path, stream, *, create_parents=True):
        self.blobs[path] = stream.read()


EXPECTED = {StorageReadProtocol, StorageWriteProtocol}
EXCLUDED = {StorageCopyProtocol, StorageDirectoryProtocol}


@pytest.fixture
def backend_cls():
    return get_registered_backends()[CONST_STORAGE_PROVIDER_TYPE.GCS]


def test_declared_protocols(backend_cls):
    assert all(issubclass(backend_cls, p) for p in EXPECTED)
    assert not any(issubclass(backend_cls, p) for p in EXCLUDED)


def test_round_trip_through_facade():
    with StorageFacade.from_path("gs://bucket/k") as facade:
        facade.write("gs://bucket/k", b"x")
        assert facade.read("gs://bucket/k") == b"x"
```

Running it with `pytest -q` reports `2 passed`. Registration happens at import, so the class stays registered for the rest of the test session.
