"""LocalCopyMixin — file copy operations for local filesystem."""

from __future__ import annotations

import os
import shutil


class LocalCopyMixin:
    """Copy mixin for local filesystem."""

    def copy(self, source: str, destination: str) -> None:
        """Copy *source* to *destination*, creating parent directories as needed."""
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        shutil.copy2(source, destination)
