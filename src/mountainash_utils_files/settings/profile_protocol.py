"""StorageProfile — storage-flavored subclass of Profile.

Adds ``to_handler_kwargs()`` on top of the generic mechanism provided by
:class:`mountainash_settings.profiles.Profile`.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.profiles import Profile, lookup_class_var
from typing import Protocol, Optional

# from.types import StorageProfileT

if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile

# __all__ = ["StorageProfileProtocol"]

@t.runtime_checkable
class StorageProfileProtocol(Protocol):
    """Storage provider protocol.
    """

    # def to_handler_kwargs(
    #     self, auth_profile: AuthProfile | None = None ) -> dict[str, t.Any]:

    def to_handler_kwargs(self, auth_profile: AuthProfile | None = None) -> dict[str, t.Any]: ...

    def get_connection_url(self) -> str: ...
