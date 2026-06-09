# """Config-driven storage + auth materialisation.

# Application-layer convenience that creates SettingsParameters for both
# the storage profile and the auth mode, calls get_settings(), and returns
# materialised instances. The facade and backends never see
# SettingsParameters — they receive materialised Profile instances.
# """

# from __future__ import annotations

# from mountainash_auth_client import AUTH_REGISTRY, AuthMode, CONST_AUTH_MODE
# from mountainash_settings import SettingsParameters, get_settings

# from .profile import StorageProfile
# from .registry import STORAGE_REGISTRY

# __all__ = ["load_storage"]


# def load_storage(
#     provider: str,
#     *,
#     config_file: str | None = None,
#     secrets_provider: str | None = None,
#     auth_mode: CONST_AUTH_MODE | None = None,
# ) -> tuple[StorageProfile, AuthMode]:
#     """Materialise a storage profile and auth instance from config.

#     Args:
#         provider: Storage provider name (e.g. ``"s3"``, ``"gcs"``).
#         config_file: Path to a YAML/TOML config file. Both the profile
#             and auth classes load from the same file (each picks its own
#             fields via ``extra="ignore"``).
#         secrets_provider: Secrets provider name for secret resolution.
#         auth_mode: Override the provider's default auth mode.

#     Returns:
#         A ``(profile, auth)`` tuple of materialised settings instances.

#     Raises:
#         ValueError: If *auth_mode* is not in the provider's
#             ``supported_auth`` set.
#     """
#     spec = STORAGE_REGISTRY.get_descriptor(provider)
#     profile_cls = STORAGE_REGISTRY.get_settings_class(provider)

#     effective_auth = auth_mode or spec.default_auth
#     if effective_auth not in spec.supported_auth:
#         raise ValueError(
#             f"Auth mode {effective_auth!r} is not supported for provider "
#             f"{provider!r}. Supported: {sorted(spec.supported_auth)}"
#         )
#     auth_cls = AUTH_REGISTRY.get_settings_class(effective_auth)

#     config_files = [config_file] if config_file else []

#     profile = get_settings(settings_parameters=SettingsParameters.create(
#         settings_class=profile_cls,
#         config_files=config_files,
#         secrets_provider=secrets_provider,
#     ))
#     auth = get_settings(settings_parameters=SettingsParameters.create(
#         settings_class=auth_cls,
#         config_files=config_files,
#         secrets_provider=secrets_provider,
#     ))
#     return profile, auth
