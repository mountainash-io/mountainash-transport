"""Public read-access handoff for engines that read storage natively.

Normalizes a location, storage/auth profiles and location policy into an
immutable :class:`NativeReadAccess`, or ``None`` when only transport can read
the location faithfully. Nothing is opened, fetched or authenticated here.

Module level imports are stdlib-safe; settings, auth-client and profile classes
are imported only in the branches that need them, so unprofiled local access
works on the base install.

``connection_options`` uses transport-owned names:

* S3 family: ``access_key_id``, ``secret_access_key`` (static credentials only),
  ``region``, ``endpoint_url`` (when set), ``use_ssl``, ``verify_tls``,
  ``addressing_style``, ``accelerate_endpoint`` / ``dualstack_endpoint`` (when
  enabled), ``connect_timeout`` / ``read_timeout`` (when configured).
* HTTP: ``anonymous`` and ``verify_tls``, plus ``connect_timeout``,
  ``read_timeout``, ``follow_redirects``, ``max_redirects`` and ``headers``
  (tuple of pairs) when they differ from the profile defaults.

Configurations that cannot be represented (ambient/session/role/profile-chain
credentials, unknown emitter options, authenticated HTTP, userinfo URLs,
SFTP and other providers) return ``None``; transport keeps reading them.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._schemes import SCHEMES
from mountainash_transport.location import (
    POLICY_UNSET,
    LocationPolicy,
    _S3_FAMILY,
    check_location,
    local_path,
    require_known_scheme,
    resolve_policy,
)

__all__ = ["NativeReadAccess", "resolve_native_read"]


_S3_EMITTED = frozenset({
    "service_name", "region_name", "use_ssl", "verify", "endpoint_url", "config",
    "aws_access_key_id", "aws_secret_access_key",
})
_HTTP_EMITTED = frozenset({"timeout", "follow_redirects", "max_redirects", "verify", "headers"})


@dataclass(frozen=True)
class NativeReadAccess:
    """Effective, non-reading access description for one location."""

    location: str = field(repr=False)
    scheme: str
    provider: str
    policy: LocationPolicy | None
    connection_options: Mapping[str, object] = field(repr=False)



def _same_family(a: CONST_STORAGE_PROVIDER_TYPE | None, b: CONST_STORAGE_PROVIDER_TYPE | None) -> bool:
    return a == b or (a in _S3_FAMILY and b in _S3_FAMILY)


def resolve_native_read(
    path: str | os.PathLike[str],
    *,
    storage_profile: Any = None,
    auth_profile: Any = None,
    policy: Any = POLICY_UNSET,
) -> NativeReadAccess | None:
    """Return the access for *path*, or ``None`` when transport must read it.

    ``storage_profile`` is a profile object or a configured profile name; an
    explicit ``auth_profile`` replaces a named profile's auth. Permission denial
    and invalid profile/auth combinations raise; they never become ``None``.
    """
    location = os.fspath(path)

    profile_provider = None
    if isinstance(storage_profile, str):
        from mountainash_transport.settings import resolve_storage

        storage_profile, named_auth = resolve_storage(storage_profile)
        if auth_profile is None:
            auth_profile = named_auth
    if storage_profile is not None:
        from mountainash_transport.connections import _provider_type_from_profile

        profile_provider = _provider_type_from_profile(storage_profile)

    declared_root = None
    if profile_provider == CONST_STORAGE_PROVIDER_TYPE.LOCAL:
        declared_root = getattr(storage_profile, "ROOT_PATH", None)
        declared_root = os.path.join(os.getcwd(), os.fspath(declared_root)) if declared_root else None
    selected = resolve_policy(policy, storage_profile, declared_root=declared_root)

    scheme = require_known_scheme(location, selected)
    if scheme is None:
        return None
    provider = SCHEMES[scheme].provider
    if provider is None:
        return None

    if provider == CONST_STORAGE_PROVIDER_TYPE.HTTP and storage_profile is None:
        from mountainash_transport.connections import _provider_type_from_profile
        from mountainash_transport.settings.storage.profiles import HTTPStorageProfile

        storage_profile = HTTPStorageProfile()
        profile_provider = _provider_type_from_profile(storage_profile)
    if storage_profile is not None:
        from mountainash_transport.connections import _require_supported_auth

        _require_supported_auth(storage_profile, auth_profile)

    base = declared_root if provider == CONST_STORAGE_PROVIDER_TYPE.LOCAL else None
    checked = check_location(location, provider, storage_profile, selected, base=base)

    if storage_profile is not None and not _same_family(profile_provider, provider):
        return None

    if provider == CONST_STORAGE_PROVIDER_TYPE.LOCAL:
        return NativeReadAccess(local_path(checked), "file", provider.value, selected, MappingProxyType({}))

    if provider in _S3_FAMILY:
        options = _s3_options(storage_profile, auth_profile) if storage_profile is not None else None
    elif provider == CONST_STORAGE_PROVIDER_TYPE.HTTP:
        options = _http_options(checked, storage_profile, auth_profile)
    else:
        options = None
    if options is None:
        return None
    return NativeReadAccess(checked, scheme, provider.value, selected, MappingProxyType(options))


def _s3_options(profile: Any, auth_profile: Any) -> dict[str, object] | None:
    from mountainash_auth_client.targets import TargetFamily

    from mountainash_transport.connections import _emit_kwargs

    emitted = _emit_kwargs(profile, auth_profile, TargetFamily.BOTO)
    if "client_config" in emitted or not set(emitted) <= _S3_EMITTED:
        return None  # session/role/profile chain or an option this handoff cannot name
    key, secret = emitted.get("aws_access_key_id"), emitted.get("aws_secret_access_key")
    if not key or not secret:
        return None  # ambient or partial credentials: transport owns selection and errors
    config = emitted.get("config")
    if config is None:
        from importlib import import_module
        from mountainash_transport.connections.errors import TransportConnectionError

        try:
            import_module("botocore.config")
        except ImportError as exc:
            raise TransportConnectionError(
                "botocore is required for S3 native access — install mountainash-transport[s3]"
            ) from exc
        return None  # an emitter without representable configuration
    s3 = dict(getattr(config, "s3", None) or {})

    options: dict[str, object] = {
        "access_key_id": key,
        "secret_access_key": secret,
        "region": emitted.get("region_name"),
        "use_ssl": emitted.get("use_ssl", True),
        "verify_tls": emitted.get("verify", True),
        "addressing_style": s3.get("addressing_style", "auto"),
    }
    if emitted.get("endpoint_url"):
        options["endpoint_url"] = emitted["endpoint_url"]
    if s3.get("use_accelerate_endpoint"):
        options["accelerate_endpoint"] = True
    if s3.get("use_dualstack_endpoint"):
        options["dualstack_endpoint"] = True
    for option, field_name in (("connect_timeout", "CONNECT_TIMEOUT"), ("read_timeout", "READ_TIMEOUT")):
        value = getattr(profile, field_name, None)
        if value is not None:
            options[option] = value
    return options


def _has_userinfo(location: str) -> bool:
    from urllib.parse import urlsplit

    try:
        return "@" in urlsplit(location).netloc
    except ValueError:
        return True


def _http_options(location: str, profile: Any, auth_profile: Any) -> dict[str, object] | None:
    from mountainash_auth_client import NoAuthProfile
    from mountainash_auth_client.targets import TargetFamily

    from mountainash_transport.connections import _emit_kwargs

    if auth_profile is not None and not isinstance(auth_profile, NoAuthProfile):
        return None
    if _has_userinfo(location):
        return None
    emitted = _emit_kwargs(profile, None, TargetFamily.HTTP)
    if not set(emitted) <= _HTTP_EMITTED:
        return None

    defaults = {p.name: p.default for p in profile.__spec__.parameters}
    options: dict[str, object] = {"anonymous": True, "verify_tls": emitted.get("verify", True)}
    timeout = emitted.get("timeout")
    if timeout is not None:
        if timeout.connect != defaults["TIMEOUT_CONNECT"]:
            options["connect_timeout"] = timeout.connect
        if timeout.read != defaults["TIMEOUT_READ"]:
            options["read_timeout"] = timeout.read
    if emitted.get("follow_redirects", True) != defaults["FOLLOW_REDIRECTS"]:
        options["follow_redirects"] = emitted["follow_redirects"]
    if emitted.get("max_redirects", defaults["MAX_REDIRECTS"]) != defaults["MAX_REDIRECTS"]:
        options["max_redirects"] = emitted["max_redirects"]
    if emitted.get("headers"):
        from httpx import Headers

        options["headers"] = tuple(Headers(emitted["headers"]).raw)
    return options
