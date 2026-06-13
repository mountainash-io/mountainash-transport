"""HTTP/HTTPS provider settings.

A single :class:`HTTPStorageProfile` class for both ``http://`` and ``https://``
schemes. Uses httpx under the hood.
"""
from __future__ import annotations

import typing as t

import httpx


from mountainash_auth_client import CONST_AUTH_PROFILES

from ...profile_spec import ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["HTTP_SPEC", "HTTPStorageProfile"]


HTTP_SPEC = StorageProfileSpec(
    name="http",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.HTTP,
    sdk_package="httpx",
    handler_module="mountainash_transport.storage.backends.http",
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
    default_auth=CONST_AUTH_PROFILES.NONE,
    supported_auth=frozenset({CONST_AUTH_PROFILES.NONE, CONST_AUTH_PROFILES.TOKEN, CONST_AUTH_PROFILES.PASSWORD}),
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



    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build httpx.Client kwargs from an :class:`HTTPSettings` profile.

        Returns SDK-level config only (timeouts, redirects, TLS, custom
        headers). Auth headers are injected by the auth strategy layer, not
        here.
        """
        timeout_connect = getattr(self, "TIMEOUT_CONNECT", 10.0)
        timeout_read = getattr(self, "TIMEOUT_READ", 30.0)
        timeout_write = getattr(self, "TIMEOUT_WRITE", 60.0)
        follow_redirects = getattr(self, "FOLLOW_REDIRECTS", True)
        max_redirects = getattr(self, "MAX_REDIRECTS", 10)
        verify = getattr(self, "VERIFY_SSL", True)
        custom_headers = getattr(self, "HEADERS", None) or {}

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
        if custom_headers:
            kwargs["headers"] = dict(custom_headers)

        return kwargs
