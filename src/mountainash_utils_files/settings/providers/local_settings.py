"""Local filesystem settings (with NFS / CIFS mount fold-in).

Descriptor-driven settings class covering both direct local-filesystem
access and pre-mounted network filesystems (NFS, CIFS). The legacy
``NFSStorageAuthSettings`` is retired in favour of
``LocalSettings(MOUNT_SPEC={"mount_type": "nfs", ...})`` — the handler
issues an OS-level ``mount`` command if ``MOUNT_SPEC`` is populated
and then operates on the local path.

MOUNT_SPEC is an untyped ``dict`` for simplicity; the expected shape is:

.. code-block:: python

    {
        "mount_type":  "nfs" | "cifs" | "none",
        "server":      "host.example",
        "export_path": "/srv/shared",
        "options":     {"vers": "4.2", "sec": "sys"},
    }

Adapter
(:func:`mountainash_utils_files.settings.adapters.local.build_handler_kwargs`)
emits ``{"root_path": ..., "create_path": ...}`` plus ``mount_spec`` when
a non-``none`` mount type is configured.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.auth import NoAuth

from ..base import StorageAuthBase
from ..descriptor import MISSING, ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["LOCAL_DESCRIPTOR", "LocalSettings"]


LOCAL_DESCRIPTOR = StorageDescriptor(
    name="local",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    sdk_package=None,  # stdlib only
    handler_module="mountainash_utils_files.storage_backends.local",
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
                "Filesystem root. All paths resolve relative to this when "
                "set; otherwise paths are treated as absolute."
            ),
        ),
        ParameterSpec(
            name="CREATE_PATH",
            type=bool,
            tier="advanced",
            default=False,
            description="Create ``ROOT_PATH`` if it doesn't exist.",
        ),
        ParameterSpec(
            name="MOUNT_SPEC",
            type=t.Optional[dict[str, t.Any]],
            tier="advanced",
            default=None,
            description=(
                "Declarative mount metadata for NFS / CIFS fold-in. Expected "
                "keys: ``mount_type`` (``nfs`` | ``cifs`` | ``none``), "
                "``server``, ``export_path``, ``options`` (dict of "
                "mount-option strings). The handler decides whether to "
                "issue a pre-mount OS command."
            ),
        ),
    ],
    auth_modes=[NoAuth],
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
def _adapter(profile: "LocalSettings") -> dict[str, t.Any]:
    from ..adapters.local import build_handler_kwargs

    return build_handler_kwargs(profile)


@register(LOCAL_DESCRIPTOR)
class LocalSettings(StorageProfile, StorageAuthBase):
    """Local filesystem settings (also covers pre-mounted NFS / CIFS).

    Fields are installed from :data:`LOCAL_DESCRIPTOR` by the
    :class:`~mountainash_settings.profiles.DescriptorProfile` metaclass.
    Auth is always :class:`NoAuth` (local files have no connection-level
    auth); network-filesystem authentication is handled at mount time by
    the OS, driven by ``MOUNT_SPEC``.

    Legacy ``NFSStorageAuthSettings`` instances should migrate to

    .. code-block:: python

        LocalSettings(
            ROOT_PATH="/mnt/share",
            MOUNT_SPEC={
                "mount_type":  "nfs",
                "server":      "nfs.example",
                "export_path": "/srv/shared",
                "options":     {"vers": "4.2", "sec": "sys"},
            },
            auth=NoAuth(),
        )
    """

    __descriptor__ = LOCAL_DESCRIPTOR
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        root = getattr(self, "ROOT_PATH", None)
        mount_spec = getattr(self, "MOUNT_SPEC", None) or {}
        mount_type = mount_spec.get("mount_type") if mount_spec else None
        if mount_type in {"nfs", "cifs"}:
            server = mount_spec.get("server") or ""
            export = mount_spec.get("export_path") or ""
            scheme = "nfs" if mount_type == "nfs" else "cifs"
            return f"{scheme}://{server}{export}"
        if root:
            return f"file://{root}"
        return "file://"
