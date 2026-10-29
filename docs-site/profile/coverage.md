# Profile coverage — mountainash-transport

- Source: `src/mountainash_transport` @ `8a979e2` (develop); previous profile `65bc90f` (`src/mountainash_utils_files`).
- Behavior: **full refresh** — package root renamed and module topology changed; the previous profile also failed the current schema.
- Discovered 43 module units from 111 files: 36 profiled, 7 ignored. 4 facets.
- Working tree: `docs-site/profile/README.md` deleted (out-of-contract artifact, superseded by the root README; user-approved).

## Missing

None. Every included source file maps to a profiled module or an ignored path.

## Stale

None. All module records carry `source_hash` 8a979e2 (full refresh).

## Orphaned (retired from previous profile)

The 25 `mountainash_utils_files.*` records were retired; their source no longer exists. All their `manual` objects were empty defaults, so no editorial data was lost. Retired IDs are listed in `manifest.changed_scopes.retired_module_ids`.

## Ignored paths

- `src/mountainash_transport/__version__.py` — Single version constant (__version__ = "0.1.0"); re-exported and documented through the root module profile
- `src/mountainash_transport/_core/__init__.py` — Docstring-only namespace package marker for the _core foundation
- `src/mountainash_transport/messaging/__init__.py` — Docstring-only placeholder for the future messaging family; no implementation yet
- `src/mountainash_transport/settings/messaging/__init__.py` — Docstring-only placeholder for future messaging profiles; no implementation yet
- `src/mountainash_transport/settings/storage/__init__.py` — Docstring-only namespace package marker for storage settings
- `src/mountainash_transport/settings/utils/__init__.py` — Empty package marker
- `src/mountainash_transport/storage/__init__.py` — Docstring-only namespace package marker for the storage family

## Low / medium confidence

No low-confidence records. Medium confidence:

- `mountainash_transport.connections.tunnel` — Is the forced http:// scheme for tunnelled base_url/endpoint_url intentional, and how should HTTPS targets be tunnelled?
- `mountainash_transport.settings.storage.registry` — Is this module part of the documented public surface? It is not exported from the package root, but the user-facing storage_profiles example imports get_spec/get_settings_class from it directly.

## Audience coverage

- **users** — 27 member modules, 9 concepts; members not placed in a concept: `mountainash_transport._core.protocols`, `mountainash_transport.storage.backends.http`, `mountainash_transport.storage.backends.local`, `mountainash_transport.storage.backends.s3`, `mountainash_transport.storage.backends.sftp`
- **maintainers** — 36 member modules, 8 concepts; members not placed in a concept: `mountainash_transport._core.dataclasses`, `mountainash_transport._core.exceptions`, `mountainash_transport._core.transforms`, `mountainash_transport._core.transforms.pipeline`, `mountainash_transport.connections.s3`, `mountainash_transport.connections.sftp`, `mountainash_transport.storage.backends.http`, `mountainash_transport.storage.backends.local`, `mountainash_transport.storage.backends.s3`, `mountainash_transport.storage.backends.sftp`, `mountainash_transport.storage.facade.cross_backend`
- **backend-architecture** — 29 member modules, 6 concepts; members not placed in a concept: `mountainash_transport`, `mountainash_transport._core.constants`, `mountainash_transport._core.dataclasses`, `mountainash_transport._core.exceptions`, `mountainash_transport._core.extras`, `mountainash_transport._core.transforms`, `mountainash_transport.location`, `mountainash_transport.settings`
- **broader-hype** — 4 member modules, 3 concepts; members not placed in a concept: none

## Documentation gaps and drift (evidence in module records)

- AGENTS.md is stale: names `GitHubStorageProfile` (actual `GitHubRepoStorageProfile` / `github_repo`); says local implements 'all but enumerate' and omits Enumerate for SFTP — code, README and conformance tests show both implement it.
- README support table lacks a RangedRead column; HTTP, S3 and SFTP implement `open_ranged` (protocol satisfied by method shape, no explicit subclassing).
- Settings-only providers (no backend, `implemented=False`): GCS, Azure, FTP, SMB, GitHub. Docs must not imply backends exist.
- `location`: an empty `frozenset()` allow-list means 'allow any host' for that scheme — undocumented; no runnable example for `LocationPolicy`.
- `connections.tunnel`: endpoint rewrite to `http://127.0.0.1:<port>` (connections/tunnel.py:201) drops scheme, host and path prefix — HTTPS targets through a tunnel are effectively unsupported; no tunnel example.
- `MissingExtraError` only translates `[http]`-stack imports; missing boto3/paramiko/gnupg surface as plain ImportError/TransportConnectionError.
- `create_connection` silently falls back to `HTTPConnection` for unknown provider types and ignores `auto_authorize`.
- Backend divergences: local `rmdir` is recursive, SFTP `rmdir` empty-only; SFTP `write_from_stream` buffers the whole payload; S3 copy is a single `copy_object` call (no multipart fallback); S3 enumerate lists all pages before applying `max_results`.
- `copy_between` uses native copy only when source and destination share the identical profile object (`is`), and reads private `StorageFacade` attributes.
- Gzip compressing reader closes the caller's source stream, contrary to the documented transform rule; GPG buffers the whole payload and holds the passphrase as a plain attribute.
- `RangedReader` depends on the private fsspec `cache._fetch` API.
- Docstring drift: `from_path` documents `profile`/`auth` (actual `storage_profile`/`auth_profile`); profile docstrings cite non-existent `settings.adapters.*`; `to_handler_kwargs` labelled a deprecated shim though `ProfileProtocol` requires it; `get_descriptor` warns of removal 'before 26.6.0' while the package version is 0.1.0.
- `import mountainash_transport.storage.backends as b` raises ImportError because the root rebinds `storage` to the factory function.
- `clear_registry()` is irreversible: `ensure_backends_loaded()` is a no-op after first import.
- Dead code: `settings/utils/secrets.py`; five unreferenced enums in `_core/constants.py`; `NFS`/`AZURE_FILES` provider types have no scheme.
- Missing examples: LocationPolicy, random-access reads, SFTP recipe, tunnel.

## Boundary questions (not restructured)

- `connections` bundles factory, errors, NullConnection and the OAuth2 auth-strategy bridge; `auth_strategy.py` may merit its own module.
- `_core.ranged_io` mixes public `RangePolicy` with backend-author `RangedSource`/`RangedReader`.
- `settings.storage.registry` and `settings.storage.profiles` are mutually importing and could be one unit.
- `storage.facade.cross_backend` (one function) could fold into `storage.facade`.
- Scheme identification is split across `_schemes`, `location` and `StoragePath.identify_scheme`.
