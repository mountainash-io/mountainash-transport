"""HTTP/HTTPS provider settings.

A single :class:`HTTPStorageProfile` class for both ``http://`` and ``https://``
schemes. Uses httpx under the hood.
"""
from __future__ import annotations

import typing as t
import base64
import httpx


from mountainash_auth_client import CONST_AUTH_MODE
from mountainash_auth_client import AuthProfile, JWTAuth, NoAuth, OAuth2Auth, OAuth2AuthCodeAuth, PasswordAuth, TokenAuth

from ..profile_spec import ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE
from ..utils.secrets import _unwrap_secret

__all__ = ["HTTP_SPEC", "HTTPStorageProfile"]


HTTP_SPEC = StorageProfileSpec(
    name="http",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.HTTP,
    sdk_package="httpx",
    handler_module="mountainash_transport.storage_backends.http",
    handler_class="HTTPStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="TIMEOUT_CONNECT",
            type=float,
            tier="core",
            default=10.0,
            description="Connect timeout in seconds.",
        ),
        ParameterSpec(
            name="TIMEOUT_READ",
            type=float,
            tier="core",
            default=30.0,
            description="Read timeout in seconds.",
        ),
        ParameterSpec(
            name="TIMEOUT_WRITE",
            type=float,
            tier="advanced",
            default=60.0,
            description="Write timeout in seconds (for PUT requests).",
        ),
        ParameterSpec(
            name="FOLLOW_REDIRECTS",
            type=bool,
            tier="advanced",
            default=True,
            description="Whether to follow HTTP redirects.",
        ),
        ParameterSpec(
            name="MAX_REDIRECTS",
            type=int,
            tier="advanced",
            default=10,
            description="Maximum number of redirects to follow.",
        ),
        ParameterSpec(
            name="VERIFY_SSL",
            type=bool,
            tier="advanced",
            default=True,
            description="Whether to verify TLS certificates.",
        ),
        ParameterSpec(
            name="HEADERS",
            type=dict,
            tier="advanced",
            default=None,
            description="Custom request headers merged with auth headers.",
        ),
    ],
    default_auth=CONST_AUTH_MODE.NONE,
    supported_auth=frozenset({CONST_AUTH_MODE.NONE, CONST_AUTH_MODE.TOKEN, CONST_AUTH_MODE.PASSWORD}),
)


# def _adapter(profile: "HTTPStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.http import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class HTTPStorageProfile(Profile):
    """HTTP/HTTPS provider settings."""

    __spec__ = HTTP_SPEC

    def get_connection_url(self) -> str:
        """Return a placeholder connection URL for logging/inspection."""
        return "http(s)://<dynamic>"



    def _unwrap_secret(self, v: t.Any) -> t.Optional[str]:
        if v is None:
            return None
        if hasattr(v, "get_secret_value"):
            return v.get_secret_value()
        return str(v)


    def _resolve_auth_headers(self, auth_profile: AuthProfile | None) -> dict[str, str]:
        """Build Authorization header from an AuthSpec instance."""
        if auth_profile is None:
            return {}
        if isinstance(auth_profile, NoAuth):
            return {}
        if isinstance(auth_profile, (TokenAuth, JWTAuth)):
            token = _unwrap_secret(auth_profile.TOKEN)
            if token:
                return {"Authorization": f"Bearer {token}"}
        elif isinstance(auth_profile, PasswordAuth):
            username = auth_profile.USERNAME or ""
            password = _unwrap_secret(auth_profile.PASSWORD) or ""
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        elif isinstance(auth_profile, OAuth2Auth):
            token = _unwrap_secret(auth_profile.TOKEN)
            if token:
                return {"Authorization": f"Bearer {token}"}
        elif isinstance(auth_profile, OAuth2AuthCodeAuth):
            token = _unwrap_secret(auth_profile.ACCESS_TOKEN)
            if token:
                return {"Authorization": f"Bearer {token}"}
        return {}


    def to_handler_kwargs(self, auth_profile: AuthProfile | None = None) -> dict[str, t.Any]:
        """Build httpx.Client kwargs from an :class:`HTTPSettings` profile."""
        timeout_connect = getattr(self, "TIMEOUT_CONNECT", 10.0)
        timeout_read = getattr(self, "TIMEOUT_READ", 30.0)
        timeout_write = getattr(self, "TIMEOUT_WRITE", 60.0)
        follow_redirects = getattr(self, "FOLLOW_REDIRECTS", True)
        max_redirects = getattr(self, "MAX_REDIRECTS", 10)
        verify = getattr(self, "VERIFY_SSL", True)
        custom_headers = getattr(self, "HEADERS", None) or {}

        auth_headers = self._resolve_auth_headers(auth_profile)

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
