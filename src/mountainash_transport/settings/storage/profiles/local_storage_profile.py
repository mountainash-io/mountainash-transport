"""Local filesystem settings.

Descriptor-driven settings for direct local-filesystem access. ``ROOT_PATH``
confines every path the facade handles to that directory; ``CREATE_PATH``
creates ``ROOT_PATH`` if missing. Network filesystems must be mounted by the
operating system; the library never issues mount commands.

Adapter
(:func:`mountainash_transport.settings.adapters.local.build_handler_kwargs`)
emits ``{"root_path": ..., "create_path": ...}``.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_PROFILES

from ...profile_spec import ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["LOCAL_SPEC", "LocalStorageProfile"]


LOCAL_SPEC = StorageProfileSpec(
    name="local",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    sdk_package=None,  # stdlib only
    handler_module="mountainash_transport.storage.backends.local",
    handler_class="LocalStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="ROOT_PATH",
            type=t.Optional[str],
            tier="core",
            default=None,
            description=(
                "Filesystem root. When set, the facade confines every path to "
                "this directory; relative paths resolve beneath it."
            ),
        ),
        ParameterSpec(
            name="CREATE_PATH",
            type=bool,
            tier="advanced",
            default=False,
            description="Create ``ROOT_PATH`` if it doesn't exist.",
        ),
    ],
    default_auth=CONST_AUTH_PROFILES.NONE,
    supported_auth=frozenset({CONST_AUTH_PROFILES.NONE}),
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
# def _adapter(profile: "LocalStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.local import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class LocalStorageProfile(Profile):
    """Local filesystem settings.

    Fields are installed from :data:`LOCAL_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is always :class:`NoAuth` (local files have no connection-level
    auth). ``ROOT_PATH`` confines the facade to that directory.
    """

    if t.TYPE_CHECKING:
        # Static view of the fields generated from __spec__ (kept in sync by tests).
        ROOT_PATH: str | None
        CREATE_PATH: bool

    __spec__ = LOCAL_SPEC

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        root = getattr(self, "ROOT_PATH", None)
        if root:
            return f"file://{root}"
        return "file://"





    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build LocalStorageBackend kwargs from this profile.

        This transport hook returns SDK config directly. Settings emission
        adapters belong in the target-specific ``__adapters__`` mapping;
        each adapter receives ``(profile, merged)`` for its selected target.
        """
        kwargs: dict[str, t.Any] = {
            "root_path": getattr(self, "ROOT_PATH", None),
            "create_path": bool(getattr(self, "CREATE_PATH", False)),
        }

        return kwargs
