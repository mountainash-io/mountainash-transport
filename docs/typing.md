# Installed typing

Transport ships inline annotations and a PEP 561 `py.typed` marker. The
qualification gate checks a direct wheel, sdist, and sdist-rebuilt wheel using
mypy **1.10.1** on Python **3.12 and 3.13**, installed together with typed
`mountainash-settings` and `mountainash-auth-client` wheels. Source checking
covers all of `src/mountainash_transport` and `tests`; no test exclusions apply.

## Public contracts

- `StorageFacade` operations are precisely typed: `read()` returns `bytes`,
  `read_stream()` a `BinaryIO`, `metadata()` a `StorageEntry`, `list_dir()` a
  `list[StorageEntry]`, `list_objects()` an `EnumerateResult`. Wrong argument
  types (a non-`str` path, `str` data, a non-transform pipeline) are rejected.
- `Pipeline`, `Gzip`, `GPG`, `infer_pipeline()` and `copy_between()` are typed;
  `infer_pipeline()` returns `tuple[Pipeline | None, str]`.
- `resolve_storage()` returns `tuple[StorageProfileProtocol, AuthProfile]`,
  using auth-client's typed `AuthProfile` union.
- Storage profiles declare their spec-generated fields for type checkers, so
  `S3StorageProfile(...).FLAVOR` is `str` and `.BUCKET` is `str | None`.
  Assigning a wrong type or reading an undeclared field is reported.
  A field whose spec default is `None` is declared optional, matching its
  runtime value. A test keeps these declarations in step with each `__spec__`.
- `HttpRequestEngine.request()` returns `HttpResponse`; HTTP errors form the
  typed `HttpTransportError` hierarchy.

## Dynamic boundaries

- `StorageProfileProtocol` exposes only `to_handler_kwargs()` and
  `get_connection_url()`. Narrow to a concrete profile class (for example with
  `isinstance`) to read its fields.
- `create_connection()` returns `ConnectionProtocol[Any]`: the SDK client type
  depends on the runtime provider. Emitted handler kwargs are `dict[str, Any]`.
- Profile constructor keywords are validated at runtime by the profile schema,
  not statically.
- Optional SDKs (boto3, paramiko, python-gnupg) are imported lazily and are not
  needed to import or type-check the package. python-gnupg publishes no type
  information; transport's own check ignores only that module's missing stubs.

## Commands

With sibling checkouts of `mountainash-settings` and `mountainash-auth-client`:

```sh
hatch run mypy:check
hatch run mypy:check-src
hatch run mypy:check-tests
hatch run mypy:check-src-untyped
hatch run mypy:check-tests-untyped
hatch run mypy:qualify --output /tmp/transport-typing-evidence
```

`check` runs mypy with `--warn-unused-ignores` over `src` and `tests` in an
environment that installs the S3, SFTP and encryption extras plus pinned stubs.
`check-src` and `check-tests` select source and test targets independently;
both accept extra mypy flags without replacing their targets. Checking tests
still follows source imports, so that run can also report source errors.
`--check-untyped-defs` is opt-in and checks bodies of unannotated functions.
`check-src-untyped` and `check-tests-untyped` are shortcuts for the respective
targeted checks with that flag enabled; they also accept extra mypy flags.

`qualify` builds the wheel and sdist, rebuilds a wheel from the sdist, and checks
each wheel from its own fresh environment outside the checkout: marker presence,
public exports, positive `assert_type` contracts, every expected-invalid call
(each must fail with its exact error code), and an installed runtime smoke.
Pass `--settings-source` / `--auth-client-source` to use other checkouts.
`--output` must be a new directory outside all source checkouts; the command
writes logs, artifacts and a SHA-256 `receipt.json` there. CI runs both commands
on Python 3.12 and 3.13 and uploads the evidence. Typing qualification is
separate from release authorization.
