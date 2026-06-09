"""StorageProfile — storage-flavored subclass of Profile.

Adds ``to_handler_kwargs()`` on top of the generic mechanism provided by
:class:`mountainash_settings.profiles.Profile`.
"""

from __future__ import annotations

import typing as t

from typing import Protocol


@t.runtime_checkable
class StorageProfileProtocol(Protocol):
    """Storage provider protocol."""

    def to_handler_kwargs(self) -> dict[str, t.Any]: ...

    def get_connection_url(self) -> str: ...
