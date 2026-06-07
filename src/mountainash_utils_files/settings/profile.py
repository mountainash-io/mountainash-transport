"""StorageProfile — storage-flavored subclass of Profile.

Adds ``to_handler_kwargs()`` on top of the generic mechanism provided by
:class:`mountainash_settings.profiles.Profile`.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.profiles import Profile, lookup_class_var

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthMode

__all__ = ["StorageProfile"]


class StorageProfile(Profile):
    """Storage provider settings.

    Public API:
        - :meth:`to_handler_kwargs` — dict ready for the provider SDK client
          constructor (``boto3.client``, ``google.cloud.storage.Client``,
          ``BlobServiceClient``, ``paramiko.SSHClient.connect``, etc.).

    Subclasses set ``__spec__`` (a :class:`StorageDescriptor`) and
    optionally ``__adapter__``. Field installation, template wiring,
    and validation are inherited from :class:`Profile`.
    """

    def to_handler_kwargs(
        self, auth: AuthMode | None = None,
    ) -> dict[str, t.Any]:
        """Build the final SDK-client kwargs dict.

        If ``__adapter__`` is set, adapter owns the full pipeline — it
        receives the profile and auth, and layers provider-specific
        construction on top. Otherwise defaults to spec ``driver_key``
        mappings via ``_default_kwargs()``.
        """
        adapter = lookup_class_var(type(self), "__adapter__")
        if adapter is not None:
            return adapter(self, auth)
        return self._default_kwargs()
