"""LocalDeleteMixin — file deletion for local filesystem."""

from __future__ import annotations

import os

from mountainash_transport.exceptions import PathNotFoundError


class LocalDeleteMixin:
    """Delete mixin for local filesystem."""

    def delete_file(self, path: str) -> None:
        """Delete the file at *path*.

        Raises:
            PathNotFoundError: if the path does not exist.
        """
        if not os.path.exists(path):
            raise PathNotFoundError(f"Path not found: {path!r}")
        os.remove(path)
