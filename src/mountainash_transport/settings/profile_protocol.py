"""Profile protocols — base contract and storage-specific refinement.

``ProfileProtocol`` is the universal contract: every profile — storage,
messaging, connection — can produce SDK-ready kwargs via
``to_handler_kwargs()``.

``StorageProfileProtocol`` refines the base with ``get_connection_url()``
for diagnostics and logging.
"""

from __future__ import annotations

import typing as t

from typing import Protocol


@t.runtime_checkable
class ProfileProtocol(Protocol):
    """Base contract for any profile in mountainash-transport.

    Every profile — storage, messaging, connection — can produce SDK-ready
    kwargs. Family-specific protocols refine this with additional methods.
    """

    def to_handler_kwargs(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class StorageProfileProtocol(ProfileProtocol, Protocol):
    """Storage-specific refinement.

    Adds ``get_connection_url()`` for diagnostics and logging. Only storage
    profiles implement this — connection and messaging profiles do not.
    """

    def get_connection_url(self) -> str: ...
