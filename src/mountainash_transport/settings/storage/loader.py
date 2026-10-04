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
the ``MOUNTAINASH_PROFILES_CONFIG`` (config file path) environment variable.
Secret references use only the reader selected through ``SettingsParameters``.
"""

from __future__ import annotations

import dataclasses
import os
import typing as t

from pydantic import BaseModel, Field, SecretStr, ValidationError

from mountainash_auth_client import AUTH_REGISTRY, CONST_AUTH_PROFILES
from mountainash_settings import (
    CacheableSettingsSource,
    MountainAshBaseSettings,
    SettingsParameters,
    get_settings,
)

from mountainash_transport._core.exceptions import (
    ProfileNotFoundError,
    ProfileResolutionError,
)

from . import profiles  # noqa: F401 — populate STORAGE_REGISTRY
from .registry import STORAGE_REGISTRY, get_spec

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

    from ..profile_protocol import StorageProfileProtocol

__all__ = [
    "CONST_PROFILES_CONFIG_ENV",
    "AuthBlock",
    "StorageProfileBlock",
    "StorageProfilesSettings",
    "resolve_storage",
]

CONST_PROFILES_CONFIG_ENV = "MOUNTAINASH_PROFILES_CONFIG"


class AuthBlock(BaseModel):
    """Auth section of a named storage-profile block."""

    mode: str | None = None
    parameters: dict[str, t.Any] = Field(default_factory=dict)


class StorageProfileBlock(BaseModel):
    """One named block under ``storage_profiles:``."""

    provider: str
    parameters: dict[str, t.Any] = Field(default_factory=dict)
    auth: AuthBlock | None = None


def _reference_shape(value: t.Any) -> t.Any:
    """Keep only reference locations, never reference text or resolved values."""
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        return {key: _reference_shape(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_reference_shape(item) for item in value]
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    return isinstance(value, str) and value.startswith("secret:")


def _has_reference(shape: t.Any) -> bool:
    if isinstance(shape, dict):
        return any(_has_reference(value) for value in shape.values())
    if isinstance(shape, list):
        return any(_has_reference(value) for value in shape)
    return shape is True


def _sensitive_validation(error: ValidationError, shape: t.Any) -> bool:
    for entry in error.errors(include_url=False):
        location = entry["loc"]
        # Missing fields and model validators can include the complete input
        # mapping in their diagnostic, including otherwise valid secrets.
        if not location or entry["type"] == "missing":
            if _has_reference(shape):
                return True
            continue
        implicated = shape
        for part in location:
            if isinstance(implicated, dict):
                implicated = implicated.get(part, False)
            elif (
                isinstance(implicated, list)
                and isinstance(part, int)
                and 0 <= part < len(implicated)
            ):
                implicated = implicated[part]
            else:
                break
        if _has_reference(implicated):
            return True
    return False


class _ReferenceLocationsSource(CacheableSettingsSource):
    """Observe the captured source tree without extra I/O or reader calls."""

    def get_field_value(self, field: t.Any, field_name: str) -> t.Any:
        return None, field_name, False

    def __call__(self) -> dict[str, t.Any]:
        return self.capture()

    def capture(self) -> dict[str, t.Any]:
        if "reference_inputs" in self.current_state:
            raise ValueError("reference_inputs is reserved for loader metadata")
        return {
            "reference_inputs": _reference_shape(
                self.current_state.get("storage_profiles", {})
            )
        }

    @staticmethod
    def project(
        owned_resolved_snapshot: dict[str, t.Any],
        owned_current_state: dict[str, t.Any],
        owned_sources_data: dict[str, dict[str, t.Any]],
    ) -> dict[str, t.Any]:
        return owned_resolved_snapshot


class StorageProfilesSettings(MountainAshBaseSettings):
    """Settings model exposing the ``storage_profiles`` config section."""

    storage_profiles: dict[str, StorageProfileBlock] = Field(default_factory=dict)
    reference_inputs: dict[str, t.Any] = Field(
        default_factory=dict, exclude=True, repr=False
    )

    @classmethod
    def settings_capture_sources(cls, sources: tuple) -> tuple:
        return (*sources, _ReferenceLocationsSource(cls))


def _build_params(
    name: str, settings_parameters: SettingsParameters | None
) -> SettingsParameters:
    if settings_parameters is None:
        config = os.environ.get(CONST_PROFILES_CONFIG_ENV)
        return SettingsParameters.create(
            settings_class=StorageProfilesSettings,
            config_files=[config] if config else None,
        )
    if settings_parameters.settings_class is not None:
        raise ProfileResolutionError(
            name,
            "settings_parameters.settings_class must be unset — "
            "resolve_storage owns the settings class",
        )
    kwargs = dict(settings_parameters.kwargs or {})
    # Runtime fields replace captured fields; metadata follows that precedence.
    kwargs.pop("reference_inputs", None)
    if "storage_profiles" in kwargs:
        kwargs["reference_inputs"] = _reference_shape(kwargs["storage_profiles"])
    return dataclasses.replace(
        settings_parameters, settings_class=StorageProfilesSettings, kwargs=kwargs
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

    # Settings owns reference resolution; do not add a transport resolver pass.
    storage_params = dict(block.parameters)
    reference_inputs = settings.reference_inputs.get(name, {})

    try:
        storage_cls = STORAGE_REGISTRY.get_settings_class(block.provider)
        spec = get_spec(block.provider)
    except KeyError as exc:
        raise ProfileResolutionError(
            name, f"unknown provider {block.provider!r}: {exc}"
        ) from exc

    try:
        storage_profile = storage_cls.model_validate(storage_params)
    except ValidationError as exc:
        if not _sensitive_validation(exc, reference_inputs.get("parameters", {})):
            raise ProfileResolutionError(
                name, f"invalid parameters for provider {block.provider!r}: {exc}"
            ) from exc
        storage_profile = None
    if storage_profile is None:
        # Leave the handler: `from None` alone still retains a secret-bearing
        # ValidationError in __context__.
        raise ProfileResolutionError(name, "invalid resolved storage parameters")

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

    try:
        auth_cls = AUTH_REGISTRY.get_settings_class(effective_mode.value)
    except KeyError as exc:
        raise ProfileResolutionError(
            name, f"no auth profile class for mode {effective_mode.value!r}"
        ) from exc
    try:
        auth_profile = auth_cls.model_validate(auth_params)
    except ValidationError as exc:
        if not _sensitive_validation(
            exc, reference_inputs.get("auth", {}).get("parameters", {})
        ):
            summary = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                for e in exc.errors(include_url=False)
            )
            raise ProfileResolutionError(
                name,
                f"invalid auth parameters for mode {effective_mode.value!r}: {summary}",
            ) from exc
        auth_profile = None
    if auth_profile is None:
        raise ProfileResolutionError(name, "invalid resolved auth parameters")

    # Both registries enforce their protocol/base class at registration, so the
    # validated instances satisfy the declared return types.
    return (
        t.cast("StorageProfileProtocol", storage_profile),
        t.cast("AuthProfile", auth_profile),
    )
