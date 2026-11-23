"""LocalDeleteMixin — file deletion for local filesystem."""

from __future__ import annotations

import os
import typing as t

from .._delete_many import delete_each
from ._helpers import _mapped, _native


class LocalDeleteMixin:
    """Delete mixin for local filesystem."""

    def delete_file(self, path: str) -> None:
        """Delete the file at *path*.

        Raises:
            PathNotFoundError: if the path does not exist.
        """
        path = _native(path)
        with _mapped(path):
            os.remove(path)

    def delete_many(self, paths: t.Iterable[str]) -> None:
        """Delete every path, one ``os.remove`` each; missing paths count as deleted."""
        delete_each(self.delete_file, paths)
