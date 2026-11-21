"""LocalMoveMixin — rename for the local filesystem."""

from __future__ import annotations

import os

from ._helpers import _mapped, _native


class LocalMoveMixin:
    """Move mixin for the local filesystem."""

    def move(self, source: str, destination: str, *, create_parents: bool = True) -> None:
        """Rename with ``os.replace``: atomic within one filesystem, replacing an existing destination.

        A move to another filesystem raises ``StorageError`` (``EXDEV``) and
        leaves the source in place.
        """
        source, destination = _native(source), _native(destination)
        parent = os.path.dirname(os.path.abspath(destination))
        if create_parents:
            with _mapped(parent):
                os.makedirs(parent, exist_ok=True)
        else:
            with _mapped(parent):
                os.stat(parent)  # a missing parent is reported as itself, not as the source
        with _mapped(source):
            os.replace(source, destination)
