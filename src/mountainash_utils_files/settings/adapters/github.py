"""fsspec GitHub adapter — builds ``GithubFileSystem`` kwargs from a profile.

Produces a dict suitable for
:class:`fsspec.implementations.github.GithubFileSystem`. Scope is
repository read access only (see
:class:`mountainash_utils_files.settings.providers.github_settings.GitHubRepoSettings`).

``fsspec`` is optional at construction time; the adapter never imports
it.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import AuthMode, JWTAuth, OAuth2Auth, TokenAuth

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _token_from_auth(auth: AuthMode | None) -> t.Optional[str]:
    """Extract a string bearer token from the discriminated auth union.

    - :class:`TokenAuth` / :class:`JWTAuth` → ``auth.token``
    - :class:`OAuth2Auth`                   → ``auth.token``
    - Anything else (incl. :class:`NoAuth`) → ``None``
    """
    if auth is None:
        return None
    if isinstance(auth, (TokenAuth, JWTAuth)):
        return _unwrap_secret(auth.TOKEN)
    if isinstance(auth, OAuth2Auth):
        return _unwrap_secret(auth.TOKEN)
    return None


def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
    """Build fsspec ``GithubFileSystem`` kwargs from a :class:`GitHubRepoSettings`.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[Profile], dict[str, Any]]``
    contract; callers always pass a :class:`GitHubRepoSettings`
    instance in practice.
    """
    org = getattr(profile, "ORG", None)
    repo = getattr(profile, "REPO", None)
    ref = getattr(profile, "REF", None)
    base_url = getattr(profile, "BASE_URL", None)
    timeout = getattr(profile, "TIMEOUT", None)

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

    token = _token_from_auth(auth)
    if token is not None:
        kwargs["token"] = token
        # For authenticated access fsspec also accepts ``username`` — if
        # the auth spec carries a username surface it. (TokenAuth doesn't
        # currently have one, but OAuth2Auth might.)
        username = getattr(auth, "USERNAME", None) if auth is not None else None
        if username:
            kwargs["username"] = username

    return kwargs
