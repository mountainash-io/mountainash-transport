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

## Publication controls

| Trigger | GitHub release and wheels PR | PyPI |
| --- | --- | --- |
| Open or updated PR | No; build and verify only | No |
| Merged PR | Yes | No |
| Manual, default inputs | No; build and verify only | No |
| Manual, `release=true` | Yes | Only if separately enabled |
| Manual on `main`, `publish=true` | Only if `release=true` | Yes, after approval |

Merges to `main` use the reviewed source version. Merges to `develop` produce
`rc<run_number>` versions; merges to other configured branches produce
`b<run_number>` versions. Manual MountainAsh releases select `release_type`
(`production`, `rc`, or `beta`). Suffixes change only the build checkout, never source commits.

GitHub releases contain the verified wheel, sdist, and SBOMs. Wheel distribution
opens a release-branch PR targeting `mountainash-wheels/develop`; it does not push
directly to `develop` or `main`.

To publish to both destinations in one run, dispatch on `main` with `release=true`,
`publish=true`, and `release_type=production`. Both publishers download exact
same-run artifact IDs and verify hashes without rebuilding or overwriting existing
releases. If GitHub already carries this version, leave `release=false` for a
PyPI-only run.

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
`skip-existing`. It confirms public transport file hashes and performs a fresh
install/import with the exact approved sibling wheels. Consumers likewise need
compatible sibling packages through MountainAsh distribution or checkout setup;
this does not claim a standalone public-PyPI-only installation works.

## Failure handling

Missing sibling checkouts, incompatible metadata, install/import failures, changed
hashes, or missing environment protection block publication. Collisions and partial
uploads require explicit reconciliation; upload success alone is not confirmation.

Do not relax safe sdist extraction to accept repository-local tooling links.
Source archives contain portable package/build inputs rather than the development
checkout. Source/version changes require a new candidate and approval.

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and [first-publication setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
