"""httpx adapter — builds client kwargs from an HTTPSettings profile."""
from __future__ import annotations

import base64
import typing as t

import httpx
from mountainash_auth_client import AuthMode, JWTAuth, NoAuth, OAuth2Auth, OAuth2AuthCodeAuth, PasswordAuth, TokenAuth

if t.TYPE_CHECKING:
    from ..profile import StorageProfile

__all__ = ["build_handler_kwargs"]


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _resolve_auth_headers(auth: AuthMode | None) -> dict[str, str]:
    """Build Authorization header from an AuthSpec instance."""
    if auth is None:
        return {}
    if isinstance(auth, NoAuth):
        return {}
    if isinstance(auth, (TokenAuth, JWTAuth)):
        token = _unwrap_secret(auth.TOKEN)
        if token:
            return {"Authorization": f"Bearer {token}"}
    elif isinstance(auth, PasswordAuth):
        username = auth.USERNAME or ""
        password = _unwrap_secret(auth.PASSWORD) or ""
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    elif isinstance(auth, OAuth2Auth):
        token = _unwrap_secret(auth.TOKEN)
        if token:
            return {"Authorization": f"Bearer {token}"}
    elif isinstance(auth, OAuth2AuthCodeAuth):
        token = _unwrap_secret(auth.ACCESS_TOKEN)
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
    """Build httpx.Client kwargs from an :class:`HTTPSettings` profile."""
    timeout_connect = getattr(profile, "TIMEOUT_CONNECT", 10.0)
    timeout_read = getattr(profile, "TIMEOUT_READ", 30.0)
    timeout_write = getattr(profile, "TIMEOUT_WRITE", 60.0)
    follow_redirects = getattr(profile, "FOLLOW_REDIRECTS", True)
    max_redirects = getattr(profile, "MAX_REDIRECTS", 10)
    verify = getattr(profile, "VERIFY_SSL", True)
    custom_headers = getattr(profile, "HEADERS", None) or {}

    auth_headers = _resolve_auth_headers(auth)

    headers = {**custom_headers, **auth_headers}

    kwargs: dict[str, t.Any] = {
        "timeout": httpx.Timeout(
            connect=timeout_connect,
            read=timeout_read,
            write=timeout_write,
            pool=5.0,
        ),
        "follow_redirects": follow_redirects,
        "max_redirects": max_redirects,
        "verify": verify,
    }
    if headers:
        kwargs["headers"] = headers

    return kwargs
