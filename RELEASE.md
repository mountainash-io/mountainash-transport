# Release Procedure

mountainash-transport requires Python 3.12+. Source changes and candidate builds do not establish public publication. Settings and auth-client, including auth-client's secrets dependency, must have compatible public PyPI releases first.

## Prepare and verify

1. Prepare the final unused version in `src/mountainash_transport/__version__.py` under this repository's version policy. Use reviewed `release/*` or `hotfix/*` changes and existing branch/CI rules; do not push directly to protected branches.
2. `build-and-release-package.yml` builds candidates for PRs targeting `main`/`develop` and for manual dispatch. Default manual input is `publish=false`.
3. The workflow builds exactly one wheel and one sdist with public build requirements, checks metadata and records hashes/source/run identity. It installs the wheel and an independently sdist-derived wheel in fresh external Python 3.12 environments, using only public PyPI dependencies.
4. Installation reports, `pip check`, imported-module origins and wheel/sdist metadata agreement must pass. A sibling checkout or private wheelhouse is not final release evidence.

## Publishing setup requires separate authorization

- Establish PyPI ownership or a pending publisher for `mountainash-transport`. Pending publishers do not reserve names.
- Configure the GitHub environment **`pypi`** with required human reviewers and exactly one custom deployment policy allowing the **`main` branch**.
- Configure PyPI Trusted Publishing for this repository's exact owner/name, workflow filename **`build-and-release-package.yml`**, and environment **`pypi`**.
- No token, unprotected environment, fallback branch or alternate index substitutes for missing setup. Preflight fails closed if protection is missing or cannot be verified.

## Approve, publish, confirm

After authorization, dispatch on `main` with `publish=true`. Review the exact source/version, wheel/sdist hashes and verification evidence before approving the `pypi` environment.

The publisher downloads the exact same-run distribution/evidence artifact IDs, checks identity and hashes, and uploads with short-lived OIDC authority. It never rebuilds, rewrites the version or uses `skip-existing`. It then checks the public PyPI file set/hashes and performs a fresh public-index install/import.

Evidence artifacts are named `release-dist-<run>-<attempt>`, `release-evidence-<run>-<attempt>` and, after successful confirmation, `publication-evidence-<run>-<attempt>`. The old automatic GitHub/SBOM/wheels-repository release path is replaced; historical releases remain untouched.

## Failure handling

Missing public dependencies, incompatible metadata, install/import failures, changed hashes or missing environment protection block publication. Collisions, partial uploads and unexpected public files require explicit reconciliation before a new attempt; upload success alone is not confirmation.

Do not relax safe sdist extraction to accept repository-local tooling links. Source archives contain portable package/build inputs rather than the development checkout. Source/version changes require a new candidate and approval.

See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/) and [first-publication setup](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
