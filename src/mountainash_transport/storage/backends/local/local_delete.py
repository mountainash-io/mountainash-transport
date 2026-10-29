"""LocalDeleteMixin — file deletion for local filesystem."""

from __future__ import annotations

import os

from ._helpers import _mapped


class LocalDeleteMixin:
    """Delete mixin for local filesystem."""

    def delete_file(self, path: str) -> None:
        """Delete the file at *path*.

        Raises:
            PathNotFoundError: if the path does not exist.
        """
        with _mapped(path):
            os.remove(path)
