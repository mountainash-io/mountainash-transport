# Release Procedure

mountainash-transport requires Python 3.12+. MountainAsh distribution and optional
PyPI publishing consume the same verified artifacts when enabled together. Source
changes or candidate builds alone do not establish publication.

## Prepare and verify

1. Prepare an unused version in `src/mountainash_transport/__version__.py` through
   reviewed `release/*` or `hotfix/*` changes. Never push directly to protected branches.
2. CI reads `.github/config/mountainash_dependencies.yml` and checks out settings,
   secrets, and auth-client under `temp/`. It selects a matching source branch,
   falling back to the PR base branch or manual `fallback_branch` input.
3. Hatch installs all three siblings before installing transport. Runtime version
   bounds remain enforced; local paths do not bypass compatibility checks.
4. `build-and-release-package.yml` builds one transport wheel and sdist plus sibling
   wheels. It verifies the transport wheel and independently sdist-derived wheel
   in fresh external Python 3.12 environments using those sibling wheels and
   public PyPI for other dependencies.
5. Install reports, `pip check`, module origins, metadata agreement, artifact hashes,
   sibling revisions, and full/direct JSON SBOMs are recorded as verification evidence.

The distribution artifact contains only transport's wheel and sdist. Sibling wheels
travel in the separate evidence artifact, with hashes checked before PyPI publication.

This is a **development rehearsal**, not public-PyPI readiness: its sibling
wheels are deliberately allowed only inside the rehearsal environments.

## Public-only readiness rehearsal

Dispatch `build-and-release-package.yml` with `verify_public=true`,
`release=false`, and `publish=false` to test public-only resolution without any
release, wheels, or PyPI publication. It may run on an allowed feature or
development branch:
```sh
gh workflow run build-and-release-package.yml --repo mountainash-io/mountainash-transport \
  --ref develop -f verify_public=true -f release=false -f publish=false \
  -f release_type=production -f fallback_branch=develop
```

The `verify-public` job downloads the exact rehearsal wheel/sdist and `release.json`
artifact IDs, revalidates their filenames/hashes, and verifies both the original
wheel and a new wheel built from the sdist. Fresh temporary environments obtain
dependencies and build tools only from public PyPI; static and backend-reported
dynamic build requirements are source-checked and installed with retained
provenance reports. The selected candidate or sdist-derived wheel is the sole
permitted local distribution. Install reports must be present and name only that
candidate or public PyPI sources. The rebuilt wheel is evidence only and is never
published.

Public verification requires compatible PyPI wheels for dependencies and build tools. Source-only dependencies cannot pass and are not built implicitly; the candidate's own sdist is still rebuilt through the controlled path.

Until every runtime sibling is publicly available, a missing dependency is a
correct readiness failure. These packages remain unready and unpublished; neither
this rehearsal nor the development rehearsal claims an end-to-end public-PyPI
installation has succeeded.

## Publication controls

| Trigger | GitHub release and wheels PR | PyPI |
| --- | --- | --- |
| Open or updated PR | No; build and verify only | No |
| Merged PR | Yes | No |
| Manual, default inputs | No; development rehearsal only | No |
| Manual, `verify_public=true`, `release=false`, `publish=false` | No; public-only readiness rehearsal | No |
| Manual, `release=true` | Yes | Only if separately enabled |
| Manual on `main`, `publish=true` | Only if `release=true` | Yes, after public-only verification and approval |

Merges to `main` use the reviewed source version. Merges to `develop` produce
`rc<run_number>` versions; merges to other configured branches produce
`b<run_number>` versions. Manual MountainAsh releases select `release_type`
(`production`, `rc`, or `beta`). Suffixes change only the build checkout, never source commits.

GitHub releases contain the verified wheel, sdist, and SBOMs. Wheel distribution
opens a release-branch PR targeting `mountainash-wheels/develop`; it does not push
directly to `develop` or `main`.

To publish to both destinations in one run, dispatch on `main` with `release=true`,
`publish=true`, and `release_type=production`. Publication requires both a
successful `verify-public` job and the protected-environment preflight. The
publishers then download exact same-run artifact IDs and verify hashes without
rebuilding or overwriting existing releases. If GitHub already carries this
version, leave `release=false` for a PyPI-only run.

## Credentials and PyPI protection

- `CI_APP_ID` and `CI_APP_PRIVATE_KEY`: sibling read access and contents/pull-request
  write access to `mountainash-wheels`.
- `CODECOV_TOKEN`: coverage and test-result uploads.
- Establish PyPI ownership or a pending publisher for `mountainash-transport`.
  Pending publishers do not reserve names.
- Configure the `pypi` GitHub environment with human reviewers and exactly one
  custom deployment policy allowing the `main` branch.
- Configure PyPI Trusted Publishing for this repository, workflow filename
  `build-and-release-package.yml`, and environment `pypi`. The preflight fails
  closed if protection is missing or cannot be verified.

After approval, PyPI publishing uses short-lived OIDC authority and never uses
`skip-existing`. It confirms public transport file hashes and then installs only
`distribution==version` from public PyPI; the post-publication provenance check
rejects every local or non-public dependency source. A successful public install
is not claimed before the dependency chain is actually published.

## Failure handling

Missing sibling checkouts, incompatible metadata, install/import failures, changed
hashes, or missing environment protection block publication. Collisions and partial
uploads require explicit reconciliation; upload success alone is not confirmation.

Do not relax safe sdist extraction to accept repository-local tooling links.
Source archives contain portable package/build inputs rather than the development
checkout. Source/version changes require a new candidate and approval.

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [first-publication setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

See the [shared release procedures](https://github.com/mountainash-io/mountainash-central/blob/main/05.devops/releases/shared/README.md)
for the release-routing and rehearsal definitions shared by MountainAsh packages.
