"""StorageProfile — storage-flavored subclass of DescriptorProfile.

Adds ``to_handler_kwargs()`` on top of the generic mechanism provided by
:class:`mountainash_settings.profiles.DescriptorProfile`.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.profiles import DescriptorProfile

__all__ = ["StorageProfile"]


class StorageProfile(DescriptorProfile):
    """Storage provider settings.

    Public API:
        - :meth:`to_handler_kwargs` — dict ready for the provider SDK client
          constructor (``boto3.client``, ``google.cloud.storage.Client``,
          ``BlobServiceClient``, ``paramiko.SSHClient.connect``, etc.).

    Subclasses set ``__descriptor__`` (a :class:`StorageDescriptor`) and
    optionally ``__adapter__``. Field installation, auth union, and template
    wiring are inherited from :class:`DescriptorProfile`.
    """

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build the final SDK-client kwargs dict.

        If ``__adapter__`` is set, adapter owns the full pipeline — typically
        it calls :meth:`_default_kwargs` and :meth:`_auth_kwargs` and layers
        provider-specific construction on top. Otherwise defaults to descriptor
        ``driver_key`` mappings + default auth dispatch.
        """
        adapter = type(self).__dict__.get("__adapter__")
        if adapter is None:
            for base in type(self).__mro__[1:]:
                candidate = base.__dict__.get("__adapter__")
                if candidate is not None:
                    adapter = candidate
                    break
        if adapter is not None:
            return adapter(self)
        kwargs = self._default_kwargs()
        kwargs.update(self._auth_kwargs())
        return kwargs
