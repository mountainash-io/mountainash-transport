"""GitHub repository settings (scope-cut, read-only).

Descriptor-driven GitHub settings scoped to **repository mode only**.
The legacy ``GitHubStorageAuthSettings`` sprawled across three distinct
concerns (repository contents, releases, Packages), most of which are
API-call-site arguments rather than connection-level config. This
migration reduces the settings surface to what
:class:`fsspec.implementations.github.GithubFileSystem` actually needs:
``org`` / ``repo`` / ``sha`` / auth.

``read_only=True`` is set on the descriptor — fsspec's GithubFileSystem
only exposes a read surface; writes go through a separate API path
(PyGithub or raw REST) and would belong on a future ``GitHubAPISettings``
class if ever needed.

Adapter
(:func:`mountainash_transport.settings.adapters.github.build_handler_kwargs`)
produces :class:`fsspec.implementations.github.GithubFileSystem` kwargs.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_MODE

from ...profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["GITHUB_REPO_SPEC", "GitHubRepoStorageProfile"]


GITHUB_REPO_SPEC = StorageProfileSpec(
    name="github_repo",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.GITHUB,
    sdk_package="fsspec",
    handler_module="mountainash_transport.storage.backends.github",
    handler_class="GitHubRepoStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=True,
    parameters=[
        ParameterSpec(
            name="ORG",
            type=str,
            tier="core",
            default=MISSING,
            driver_key="org",
            description="GitHub organization or user that owns the repo.",
        ),
        ParameterSpec(
            name="REPO",
            type=str,
            tier="core",
            default=MISSING,
            driver_key="repo",
            description="Repository name.",
        ),
        ParameterSpec(
            name="REF",
            type=t.Optional[str],
            tier="core",
            default=None,
            driver_key="sha",
            description=(
                "Branch, tag, or commit SHA to resolve files against. "
                "``None`` → default branch."
            ),
        ),
        ParameterSpec(
            name="BASE_URL",
            type=str,
            tier="advanced",
            default="https://api.github.com",
            description=(
                "API base URL. Override for GitHub Enterprise "
                "(``https://<host>/api/v3``)."
            ),
        ),
        ParameterSpec(
            name="TIMEOUT",
            type=float,
            tier="advanced",
            default=30.0,
            description="HTTP request timeout in seconds.",
        ),
    ],
    default_auth=CONST_AUTH_MODE.TOKEN,
    supported_auth=frozenset({CONST_AUTH_MODE.TOKEN, CONST_AUTH_MODE.OAUTH2, CONST_AUTH_MODE.JWT, CONST_AUTH_MODE.NONE}),
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
# def _adapter(profile: "GitHubRepoStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.github import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class GitHubRepoStorageProfile(Profile):
    """GitHub repository (read-only) settings.

    Fields are installed from :data:`GITHUB_REPO_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.

    Auth maps onto fsspec/PyGithub kwargs:
        - :class:`TokenAuth`   → ``{"token": ...}`` (PAT or fine-grained
          token)
        - :class:`OAuth2Auth`  → ``{"token": <access_token>}`` (access
          token extracted from the auth spec)
        - :class:`JWTAuth`     → ``{"token": ...}`` (GitHub App
          installation token)
        - :class:`NoAuth`      → unauthenticated (rate-limited) access

    Legacy fields removed in the scope-cut: ``STORAGE_TYPE``,
    ``PACKAGE_TYPE``, ``PACKAGE_VISIBILITY``, ``BRANCH``, ``PATH``,
    ``CREATE_PATH``, ``API_VERSION``. Downstream code setting any of
    these should migrate — ``BRANCH`` maps to ``REF``, and everything
    else was either per-operation (PATH/CREATE_PATH) or in scope only
    for package/releases modes that this settings class no longer
    supports.
    """

    __spec__ = GITHUB_REPO_SPEC

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        base = getattr(self, "BASE_URL", "https://api.github.com")
        org = getattr(self, "ORG", "") or ""
        repo = getattr(self, "REPO", "") or ""
        return f"{base}/repos/{org}/{repo}"


    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build fsspec ``GithubFileSystem`` kwargs from a :class:`GitHubRepoSettings`.

        Returns SDK-level config only (org, repo, ref, base_url, timeout).
        Token injection is handled by the auth strategy layer.
        """
        org = getattr(self, "ORG", None)
        repo = getattr(self, "REPO", None)
        ref = getattr(self, "REF", None)
        base_url = getattr(self, "BASE_URL", None)
        timeout = getattr(self, "TIMEOUT", None)

        kwargs: dict[str, t.Any] = {
            "org": org,
            "repo": repo,
        }
        if ref is not None:
            kwargs["sha"] = ref
        if base_url:
            kwargs["base_url"] = base_url
        if timeout is not None:
            kwargs["timeout"] = timeout

        return kwargs
