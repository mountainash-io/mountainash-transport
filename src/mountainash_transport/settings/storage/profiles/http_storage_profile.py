"""HTTP/HTTPS provider settings.

A single :class:`HTTPStorageProfile` class for both ``http://`` and ``https://``
schemes. Uses httpx under the hood.
"""
from __future__ import annotations

import os
import ssl
import typing as t

import httpx

from mountainash_auth_client import CONST_AUTH_PROFILES
from mountainash_auth_client.targets import TargetFamily

from ...profile_spec import ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.safe_display import raise_safe, safe_detail

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
        ParameterSpec(name="RANGE_CACHE", type=t.Optional[str], default=None, tier="advanced",
                      description="Random-read cache: readahead, blockcache, bytes or none."),
        ParameterSpec(name="RANGE_BLOCK_SIZE", type=t.Optional[int], default=None, tier="advanced",
                      description="Random-read cache block/read-ahead size in bytes."),
        ParameterSpec(name="RANGE_MAX_BLOCKS", type=t.Optional[int], default=None, tier="advanced",
                      description="Maximum retained blocks for blockcache."),
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
            name="CA_BUNDLE",
            type=t.Optional[str],
            tier="advanced",
            default=None,
            description=(
                "Path to a CA bundle file or directory that signs the server's "
                "certificate. Unset: httpx defaults (SSL_CERT_FILE honoured). "
                "Ignored when VERIFY_SSL is False."
            ),
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
    supported_auth=frozenset({
        CONST_AUTH_PROFILES.NONE,
        CONST_AUTH_PROFILES.TOKEN,
        CONST_AUTH_PROFILES.PASSWORD,
        CONST_AUTH_PROFILES.OAUTH2,
    }),
)


def _http_httpx_kwargs(profile: Profile, kw: dict[str, t.Any]) -> dict[str, t.Any]:
    """Build httpx.Client kwargs (composing on kw, which is empty for HTTP)."""
    result: dict[str, t.Any] = dict(kw)
    result["timeout"] = httpx.Timeout(
        connect=getattr(profile, "TIMEOUT_CONNECT", 10.0),
        read=getattr(profile, "TIMEOUT_READ", 30.0),
        write=getattr(profile, "TIMEOUT_WRITE", 60.0),
        pool=5.0,
    )
    result["follow_redirects"] = getattr(profile, "FOLLOW_REDIRECTS", True)
    result["max_redirects"] = getattr(profile, "MAX_REDIRECTS", 10)
    result["verify"] = _verify(profile)
    custom_headers = getattr(profile, "HEADERS", None) or {}
    if custom_headers:
        result["headers"] = dict(custom_headers)
    return result


def _verify(profile: Profile) -> bool | ssl.SSLContext:
    """httpx ``verify``: False, a context loaded from CA_BUNDLE, or True."""
    if not getattr(profile, "VERIFY_SSL", True):
        return False
    ca_bundle = getattr(profile, "CA_BUNDLE", None)
    if not ca_bundle:
        return True
    # httpx 0.28 deprecates verify=<str>; this is the form it recommends.
    try:
        if os.path.isdir(ca_bundle):
            return ssl.create_default_context(capath=ca_bundle)
        return ssl.create_default_context(cafile=ca_bundle)
    except (OSError, ValueError) as exc:
        # W8: the native error may carry the bundle value (e.g. UnicodeEncodeError.object).
        raise_safe(ValueError(f"CA_BUNDLE could not be loaded ({safe_detail(exc)})"), exc)


@register
class HTTPStorageProfile(Profile):
    """HTTP/HTTPS provider settings."""

    if t.TYPE_CHECKING:
        RANGE_CACHE: str | None
        RANGE_BLOCK_SIZE: int | None
        RANGE_MAX_BLOCKS: int | None
        # Static view of the fields generated from __spec__ (kept in sync by tests).
        TIMEOUT_CONNECT: float
        TIMEOUT_READ: float
        TIMEOUT_WRITE: float
        FOLLOW_REDIRECTS: bool
        MAX_REDIRECTS: int
        VERIFY_SSL: bool
        CA_BUNDLE: str | None
        HEADERS: dict[str, t.Any] | None

    __spec__ = HTTP_SPEC
    __adapters__ = {TargetFamily.HTTP: _http_httpx_kwargs}

    def _sdk_family(self) -> TargetFamily:
        return TargetFamily.HTTP

    def get_connection_url(self) -> str:
        """Return a placeholder connection URL for logging/inspection."""
        return "http(s)://<dynamic>"

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Return the httpx kwargs ``emit(TargetFamily.HTTP)`` produces; required by ``ProfileProtocol``."""
        return self.emit(self._sdk_family())
