"""HTTP/HTTPS provider settings.

A single :class:`HTTPSettings` class for both ``http://`` and ``https://``
schemes. Uses httpx under the hood.
"""
from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_MODE

from ..descriptor import ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["HTTP_SPEC", "HTTPSettings"]


HTTP_SPEC = StorageDescriptor(
    name="http",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.HTTP,
    sdk_package="httpx",
    handler_module="mountainash_utils_files.storage_backends.http",
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


def _adapter(profile: "HTTPSettings", auth=None) -> dict[str, t.Any]:
    from ..adapters.http import build_handler_kwargs

    return build_handler_kwargs(profile, auth)


@register
class HTTPSettings(StorageProfile):
    """HTTP/HTTPS provider settings."""

    __spec__ = HTTP_SPEC
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a placeholder connection URL for logging/inspection."""
        return "http(s)://<dynamic>"
