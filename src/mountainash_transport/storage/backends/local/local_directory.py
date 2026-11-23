"""LocalDirectoryMixin — directory management for local filesystem."""

from __future__ import annotations

import errno
import os
import shutil
import stat

from ._helpers import _mapped, _native


class LocalDirectoryMixin:
    """Directory management mixin for local filesystem."""

    def mkdir(self, path: str, parents: bool = True) -> None:
        """Create the directory at *path*.

        Args:
            path: Directory path to create.
            parents: If True, create intermediate parent directories (default True).
        """
        path = _native(path)
        with _mapped(path):
            os.makedirs(path, exist_ok=True) if parents else os.mkdir(path)

    def rmdir(self, path: str, *, recursive: bool = False) -> None:
        """Remove a directory: empty-only by default, the whole tree with ``recursive=True``."""
        path = _native(path)
        with _mapped(path):
            if not recursive:
                os.rmdir(path)
                return
            if not stat.S_ISDIR(os.lstat(path).st_mode):
                raise NotADirectoryError(errno.ENOTDIR, "Not a directory", path)
            shutil.rmtree(path)
