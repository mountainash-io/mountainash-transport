# Phase 4: mountainash-utils-files profiles migration — execution plan

**Spec:** `docs/superpowers/specs/2026-04-17-profiles-migration-design.md`
**Branch:** `feat/profiles-migration` (branched from `develop` tip `237fede`)
**Base dependency:** mountainash-settings v26.4.0 (released)
**Target:** PR to `develop`

## Task cadence

Tasks T1, T2 self-executed (trivial/short). T3+T4 bundled to one implementer. T5+T6 bundled. T7 bundled. T8 separate implementer. T9, T10 self.

## T1 (self): branch + dep pin

1. `git checkout -b feat/profiles-migration` from `develop`
2. Verify `hatch.toml [envs.test]` already pins `mountainash_settings @ {root:uri}/../mountainash-settings` (from scoping report).
3. `hatch env prune && hatch env create test`
4. `hatch run test:test-quick` to capture baseline.

**Commit:** `chore(settings): branch + baseline`

## T2 (self): mechanism files

Write three short files to `src/mountainash_utils_files/settings/`:
- `descriptor.py` — `StorageDescriptor(ProfileDescriptor)` with `sdk_package`, `handler_module`, `handler_class`, `supports_streaming`, `supports_multipart`, `read_only`
- `profile.py` — `StorageProfile(DescriptorProfile)` with `to_handler_kwargs()` (MRO-walking adapter lookup, mirrors Phase 3's `SecretsProfile`)
- `registry.py` — `STORAGE_REGISTRY = Registry("storage")` + `register = SECRETS_REGISTRY.decorator()` + `get_descriptor` / `get_settings_class` wrappers

Test that `from mountainash_utils_files.settings import StorageDescriptor, StorageProfile, STORAGE_REGISTRY` imports cleanly.

**Commit:** `feat(settings): add descriptor + profile + registry mechanism`

## T3+T4 bundled (implementer): S3-family consolidation

**One implementer subagent.** Bundled because settings + backend collapse are tightly coupled.

### T3: S3Settings (5 → 1 class)
- Create `settings/providers/s3_settings.py` with `S3Settings(StorageProfile, StorageAuthBase)` + `S3_DESCRIPTOR` (StorageDescriptor literal).
- Declare all S3/S3Express/R2/MinIO/B2 parameters using `ParameterSpec` (see spec for full shape).
- `FLAVOR: Literal["aws","express","r2","minio","b2"]` as the discriminator.
- Typed `auth: Union[IAMAuth, TokenAuth, NoAuth]` discriminated union.
- **Fix known bugs:** `USE_SSL` default `True` (was `False`); drop `PATH_STYLE` (redundant with `ADDRESSING_STYLE`); drop `ACCOUNT_ID` as required (keep optional for R2 endpoint templating); drop S3Express fake `zone_id`; drop B2 `CAPABILITIES` / `API_ENDPOINT` (SDK returns them); drop MinIO `PORT` (fold into endpoint); drop R2 duplicate `ENDPOINT` field; drop pydantic-v1 `const=False`.
- Create `settings/adapters/s3.py` — `build_kwargs(settings: S3Settings) -> dict` that dispatches on `flavor` for endpoint URL, addressing style, session-auth toggles. boto3 contract.
- Add class aliases: `S3StorageAuthSettings = S3Settings` (+ R2/S3Express/MinIO/B2 aliases) in `providers/__init__.py` for backward compat.
- `@register(S3_DESCRIPTOR)` to populate `STORAGE_REGISTRY`.

### T4: S3 backend consolidation (5 → 1)
- Keep `storage_backends/s3/` (with all mixins: connection, read, write, list, delete, copy, metadata, path).
- Delete `storage_backends/{r2,s3express,minio}/` directories.
- `S3StorageBackend.__init__(auth_params: S3Settings)` dispatches on `auth_params.FLAVOR` for any flavor-specific construction (mostly just endpoint_url selection).
- Update `storage_backends/__init__.py`: single `from . import s3` + `from . import local`.
- Update registry to resolve R2/S3EXPRESS/MINIO/B2 provider_type enums all to `S3StorageBackend`.

### Testing (per-task, not T8)
- After T3: field-shape smoke test per flavor (`S3Settings(FLAVOR="r2", ACCOUNT_ID=..., auth=IAMAuth(...))`).
- After T4: existing `tests/backends/test_s3_family.py` should continue to pass.

**Commits (suggested):**
- `refactor(settings): consolidate S3-family into S3Settings with flavor discriminator`
- `feat(settings): add boto3 adapter with per-flavor dispatch`
- `refactor(backends): collapse S3/R2/S3Express/MinIO backends to flavor-dispatched s3 backend`
- `feat(settings): register S3Settings in STORAGE_REGISTRY with provider-type aliases`
- `chore(settings): add class aliases for S3StorageAuthSettings, R2StorageAuthSettings, etc.`

## T5+T6 bundled (implementer): GCS + AzureStorage migration

**One implementer subagent.** Both are settings-only (no backend implementations yet).

### T5: GCSSettings
- Create `settings/providers/gcs_settings.py` with `GCSSettings(StorageProfile, StorageAuthBase)` + `GCS_DESCRIPTOR`.
- **Fix bug:** declare `API_VERSION` (or drop it from get_connection_args).
- Drop dead `OAUTH_CREDENTIALS` field.
- `auth: Union[ServiceAccountAuth, IAMAuth, OAuth2Auth, TokenAuth, NoAuth]` discriminated union.
- Create `settings/adapters/gcs.py` — builds `google.cloud.storage.Client` kwargs: `project`, `credentials` (resolved from auth type), `client_options={"api_endpoint": ...}`.
- Class alias: `GCSStorageAuthSettings = GCSSettings`.

### T6: AzureStorageSettings (merge Blob + Files)
- Create `settings/providers/azure_settings.py` with `AzureStorageSettings(StorageProfile, StorageAuthBase)` + `AZURE_STORAGE_DESCRIPTOR`.
- `service_type: Literal["blob","files"]` discriminator.
- **Fix bugs:** rename `MANAGED_IDENTITY` auth mode — it's actually service principal (requires CLIENT_ID + TENANT_ID + CLIENT_SECRET). True managed identity is a separate `AzureADAuth` variant.
- Pass plain string (not `SecretStr` object) to SDK.
- Add `token_intent: Optional[str]` (required for Azure Files with AAD).
- `auth: Union[AzureADAuth, TokenAuth, PasswordAuth, NoAuth]` discriminated union.
- Create `settings/adapters/azure.py` — builds `BlobServiceClient` or `ShareServiceClient` kwargs based on `service_type`; resolves credential from auth type.
- `ACCOUNT_URL` template: `"https://{ACCOUNT_NAME}.{SERVICE_TYPE}.{ENDPOINT_SUFFIX}"` using ParameterSpec.template.
- Class aliases: `AzureBlobStorageAuthSettings = AzureStorageSettings` (default `service_type="blob"`), `AzureFilesStorageAuthSettings = AzureStorageSettings` (default `service_type="files"`). Aliases may need factory-function shape rather than pure class alias.

**Commits:**
- `feat(settings): migrate GCSSettings to DescriptorProfile`
- `refactor(settings): merge AzureBlob + AzureFiles into AzureStorageSettings`
- `feat(settings): add GCS + Azure adapters`

## T7 bundled (implementer): SSH/SFTP merge + FTP + SMB + Local + GitHub + NFS deletion

**One implementer subagent.**

### SSH/SFTP merge
- Create `settings/providers/ssh_settings.py` with `SSHSettings(StorageProfile, StorageAuthBase)` + `SSH_DESCRIPTOR`.
- **Drop fake fields:** `host_keys_filename`, `COMPRESSION_LEVEL`, `PREFERRED_AUTH_METHODS`, `PRIVATE_KEY_TYPE`, `CIPHERS`/`KEX_ALGORITHMS`/`MAC_ALGORITHMS`/`HOST_KEY_ALGORITHMS` (not `connect()` kwargs).
- Keep `KNOWN_HOSTS_FILE` + `HOST_KEY_POLICY` as metadata (applied to `SSHClient` post-construction, not in kwargs).
- `auth: Union[PasswordAuth, CertificateAuth, KerberosAuth]` discriminated union.
- Create `settings/adapters/ssh.py` — builds paramiko `SSHClient.connect()` kwargs.
- Class aliases: `SFTPStorageAuthSettings = SSHSettings`, `SSHStorageAuthSettings = SSHSettings`.

### FTPSettings
- Create `settings/providers/ftp_settings.py`.
- **Fix bug:** declare `USE_TLS` field (currently referenced but commented out in class body).
- Drop `AUTH_METHOD` enum; use `Union[PasswordAuth, NoAuth]` (anonymous = NoAuth).
- Drop `PORT` from constructor kwargs (ftplib takes port via `connect()`, not `__init__`).
- Create `settings/adapters/ftp.py`.
- Class alias: `FTPStorageAuthSettings = FTPSettings`.

### SMBSettings
- Create `settings/providers/smb_settings.py`.
- **Drop fake fields:** `VERSION`, `MIN_VERSION`, `MAX_VERSION`, `PREFERRED_DIALECT`, `FALLBACK_VERSIONS` (not smbprotocol params).
- `auth: Union[PasswordAuth, KerberosAuth]` discriminated union (replace `USE_KERBEROS` flag).
- Fold `DOMAIN` into adapter (encode as `DOMAIN\\username` per smbprotocol convention).
- Drop `SHARE` from client-init; it's per-operation.
- Create `settings/adapters/smb.py`.

### LocalSettings (+ NFS fold-in)
- Extend `settings/providers/local_settings.py` with optional `mount_spec: Optional[MountSpec] = None`.
- `MountSpec` = small pydantic model with `mount_type: Literal["nfs","cifs","none"]`, `server`, `export_path`, `options: dict[str, str]` — declarative mount metadata, resolved by adapter to a pre-mount command (or ignored for `mount_type="none"`).
- **Delete `settings/providers/nfs.py`** entirely.
- Class alias: `LocalStorageAuthSettings = LocalSettings`, `NFSStorageAuthSettings = LocalSettings` (NFS users get a LocalSettings with mount_spec).

### GitHubRepoSettings (scope-cut)
- Create `settings/providers/github_settings.py` with `GitHubRepoSettings`.
- **Scope-cut:** only repository mode. Fields: `ORG`, `REPO`, `REF` (branch/tag/sha), auth.
- **Fix bug:** declare `TIMEOUT` field (currently referenced but missing).
- Drop `STORAGE_TYPE` / `PACKAGE_TYPE` / `PACKAGE_VISIBILITY` / `BRANCH` / `PATH` / `CREATE_PATH` / `API_VERSION` (not connection config).
- `auth: Union[TokenAuth, OAuth2Auth, JWTAuth, NoAuth]` discriminated union.
- Mark `read_only=True` in descriptor metadata.
- Create `settings/adapters/github.py` — builds `fsspec.implementations.github.GithubFileSystem` kwargs: `org`, `repo`, `sha`, `token` (from auth).
- Class alias: `GitHubStorageAuthSettings = GitHubRepoSettings` (with shim for legacy fields that become no-ops + deprecation warning).

**Commits:**
- `refactor(settings): merge SSH + SFTP into SSHSettings`
- `feat(settings): migrate FTPSettings with bug fixes`
- `refactor(settings): strip fake SMBSettings fields`
- `refactor(settings): fold NFSSettings into LocalSettings via mount_spec`
- `refactor(settings): scope-cut GitHub to read-only GitHubRepoSettings`
- `feat(settings): add ssh/ftp/smb/local/github adapters`

## T8 (separate implementer): descriptor invariants + tests

**Fresh implementer subagent** (avoids carrying stale assumptions from T3-7).

- Create `tests/test_unit/settings/test_descriptor_invariants.py` using `descriptor_invariants_for(STORAGE_REGISTRY)`.
- Per-provider tests: `tests/test_unit/settings/providers/test_{s3,gcs,azure,ssh,ftp,smb,local,github}_settings.py`.
  - S3: flavor matrix (5 flavors × core fields).
  - Azure: service_type matrix (blob vs files).
  - SSH: auth-spec dispatch (password vs key vs kerberos).
  - Others: standard field validation + adapter kwargs smoke tests.
- Class-alias tests: `assert S3StorageAuthSettings is S3Settings`, etc.
- Factory dispatch tests: `get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.R2, S3Settings(FLAVOR="r2", ...))` resolves to S3StorageBackend.
- Fix any pre-existing migration-broken tests (expected: some tests in `tests/` reference old class names via imports — update to new names or rely on aliases).

**Commit:** `test(settings): descriptor invariants + per-provider tests + migration-broken fixes`

## T9 (self): CLAUDE.md update

Mirror Phase 3's CLAUDE.md edits. Key additions:
- Descriptor-driven architecture section.
- Provider Pattern (two-line shell with `__descriptor__` + `__adapter__`).
- `STORAGE_REGISTRY` + `@register(DESCRIPTOR)`.
- Typed `AuthSpec` discriminated union.
- Pattern B template examples (Azure `ACCOUNT_URL`, R2 `ENDPOINT_URL`).
- Removed: references to flat `AUTH_METHOD` enum + conditional secret fields.
- Note backwards-compat: old class names aliased for a release cycle.

**Commit:** `docs(claude): update for descriptor-driven storage architecture`

## T10 (self): push + PR

`git push -u origin feat/profiles-migration`
`gh pr create --base develop --title "feat(profiles): migrate settings to DescriptorProfile + consolidate 15→8 providers — Phase 4"` with body covering:
- Summary (consolidation 15→8, pattern migration, bug fixes)
- Spec + plan links
- Commit walkthrough by task
- Test state (baseline vs post-migration counts)
- Explicit list of bugs fixed
- Backwards-compat note (class aliases)
- Non-goals (unimplemented backends, MinIO/B2 native SDK classes, NFS as Python SDK)
- Test plan checklist
