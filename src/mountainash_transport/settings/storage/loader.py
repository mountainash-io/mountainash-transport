"""Config-driven storage + auth materialisation — the load_storage successor.

``resolve_storage(name)`` locates a named block under ``storage_profiles:``
in the settings configuration, materialises the provider's storage Profile
and its paired AuthProfile, and validates the pairing against the provider
spec's ``supported_auth``. The facade and backends never see configuration —
they receive materialised Profile instances.

Config shape::

    storage_profiles:
      lake:
        provider: s3            # STORAGE_REGISTRY key
        parameters:             # fields of the provider's Profile class
          FLAVOR: aws
          REGION: ap-southeast-2
          BUCKET: my-lake
        auth:                   # optional; omitted -> spec default_auth
          mode: iam             # CONST_AUTH_PROFILES value
          parameters:
            ACCESS_KEY_ID: AKIA...
            SECRET_ACCESS_KEY: "secret:aws.secret_key"

When ``settings_parameters`` is omitted, ambient configuration is read from
the ``MOUNTAINASH_PROFILES_CONFIG`` (config file path) and
``MOUNTAINASH_SECRETS_PROVIDER`` (secrets backend name) environment variables.
"""

from __future__ import annotations

import dataclasses
import os
import typing as t

from pydantic import BaseModel, Field, ValidationError

from mountainash_auth_client import AUTH_REGISTRY, CONST_AUTH_PROFILES
from mountainash_settings import (
    MountainAshBaseSettings,
    SettingsParameters,
    get_secrets_backend,
    get_settings,
)
from mountainash_settings.resolve import resolve_references_in_dict

from mountainash_transport._core.exceptions import (
    ProfileNotFoundError,
    ProfileResolutionError,
)

from . import profiles  # noqa: F401 — populate STORAGE_REGISTRY
from .registry import get_settings_class, get_spec

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

    from ..profile_protocol import StorageProfileProtocol

__all__ = [
    "CONST_PROFILES_CONFIG_ENV",
    "CONST_SECRETS_PROVIDER_ENV",
    "AuthBlock",
    "StorageProfileBlock",
    "StorageProfilesSettings",
    "resolve_storage",
]

CONST_PROFILES_CONFIG_ENV = "MOUNTAINASH_PROFILES_CONFIG"
CONST_SECRETS_PROVIDER_ENV = "MOUNTAINASH_SECRETS_PROVIDER"


class AuthBlock(BaseModel):
    """Auth section of a named storage-profile block."""

    mode: str | None = None
    parameters: dict[str, t.Any] = Field(default_factory=dict)


class StorageProfileBlock(BaseModel):
    """One named block under ``storage_profiles:``."""

    provider: str
    parameters: dict[str, t.Any] = Field(default_factory=dict)
    auth: AuthBlock | None = None


class StorageProfilesSettings(MountainAshBaseSettings):
    """Settings model exposing the ``storage_profiles`` config section."""

    storage_profiles: dict[str, StorageProfileBlock] = Field(default_factory=dict)


def _build_params(
    name: str, settings_parameters: SettingsParameters | None
) -> SettingsParameters:
    if settings_parameters is None:
        config = os.environ.get(CONST_PROFILES_CONFIG_ENV)
        return SettingsParameters.create(
            settings_class=StorageProfilesSettings,
            config_files=[config] if config else None,
            secrets_provider=os.environ.get(CONST_SECRETS_PROVIDER_ENV),
        )
    if settings_parameters.settings_class is not None:
        raise ProfileResolutionError(
            name,
            "settings_parameters.settings_class must be unset — "
            "resolve_storage owns the settings class",
        )
    return dataclasses.replace(
        settings_parameters, settings_class=StorageProfilesSettings
    )


def resolve_storage(
    name: str,
    *,
    settings_parameters: SettingsParameters | None = None,
) -> tuple["StorageProfileProtocol", "AuthProfile"]:
    """Materialise ``(storage_profile, auth_profile)`` for a named profile.

    Raises:
        ProfileNotFoundError: *name* is absent from configuration.
        ProfileResolutionError: block invalid — unknown provider or auth
            mode, failed parameter validation, or caller-set settings_class.
        UnsupportedAuthProfileError: the storage/auth pairing is outside the
            provider spec's ``supported_auth``.
    """
    params = _build_params(name, settings_parameters)
    settings = t.cast(StorageProfilesSettings, get_settings(settings_parameters=params))

    block = settings.storage_profiles.get(name)
    if block is None:
        raise ProfileNotFoundError(name, available=list(settings.storage_profiles))

    backend = get_secrets_backend(params.secrets_provider)

    storage_params = dict(block.parameters)
    if backend is not None:
        storage_params = resolve_references_in_dict(storage_params, backend)

    try:
        storage_cls = get_settings_class(block.provider)
        spec = get_spec(block.provider)
    except KeyError as exc:
        raise ProfileResolutionError(
            name, f"unknown provider {block.provider!r}: {exc}"
        ) from exc

    try:
        storage_profile = storage_cls.model_validate(storage_params)
    except ValidationError as exc:
        raise ProfileResolutionError(
            name, f"invalid parameters for provider {block.provider!r}: {exc}"
        ) from exc

    auth_block = block.auth or AuthBlock()
    if auth_block.mode is None:
        effective_mode = spec.default_auth
    else:
        try:
            effective_mode = CONST_AUTH_PROFILES(auth_block.mode)
        except ValueError as exc:
            raise ProfileResolutionError(
                name, f"unknown auth mode {auth_block.mode!r}"
            ) from exc

    if effective_mode not in spec.supported_auth:
        from mountainash_transport.connections.errors import (
            UnsupportedAuthProfileError,
        )

        raise UnsupportedAuthProfileError(
            effective_mode.value,
            reason=(
                f"mode {effective_mode.value!r} not in supported_auth "
                f"{sorted(m.value for m in spec.supported_auth)} "
                f"for provider {block.provider!r} (profile {name!r})"
            ),
        )

    auth_params = dict(auth_block.parameters)
    if backend is not None:
        auth_params = resolve_references_in_dict(auth_params, backend)

    try:
        auth_cls = AUTH_REGISTRY.get_settings_class(effective_mode.value)
    except KeyError as exc:
        raise ProfileResolutionError(
            name, f"no auth profile class for mode {effective_mode.value!r}"
        ) from exc
    try:
        auth_profile = auth_cls.model_validate(auth_params)
    except ValidationError as exc:
        raise ProfileResolutionError(
            name,
            f"invalid auth parameters for mode {effective_mode.value!r}: {exc}",
        ) from exc

    return storage_profile, auth_profile
