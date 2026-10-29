"""LocalDirectoryMixin — directory management for local filesystem."""

from __future__ import annotations

import os
import shutil

from ._helpers import _mapped


class LocalDirectoryMixin:
    """Directory management mixin for local filesystem."""

    def mkdir(self, path: str, parents: bool = True) -> None:
        """Create the directory at *path*.

        Args:
            path: Directory path to create.
            parents: If True, create intermediate parent directories (default True).
        """
        with _mapped(path):
            os.makedirs(path, exist_ok=True) if parents else os.mkdir(path)

    def rmdir(self, path: str) -> None:
        """Remove the directory at *path* and all its contents."""
        with _mapped(path):
            shutil.rmtree(path)
