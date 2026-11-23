"""LocalCopyMixin — file copy operations for local filesystem."""

from __future__ import annotations

import os
import shutil

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry

from ._helpers import _mapped, _native
from .local_metadata import entry_from_stat


class LocalCopyMixin:
    """Copy mixin for local filesystem."""

    def copy(self, source: str, destination: str) -> StorageEntry:
        """Copy *source* to *destination*, creating parent directories as needed.

        Returns the copied file's entry; a directory *destination* receives the
        file under its own name, and that file is described.
        """
        source, destination = _native(source), _native(destination)
        with _mapped(destination):
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
            target = shutil.copy2(source, destination)
            return entry_from_stat(target, os.stat(target))
