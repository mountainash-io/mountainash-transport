"""SFTP backend helpers — shared utilities used across all SFTP mixins."""
from __future__ import annotations

import errno

from mountainash_transport._core.exceptions import PathNotFoundError, StorageError


def _is_not_found(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.ENOENT:
        return True
    return False


def _wrap_sftp_error(exc: BaseException, path: str) -> StorageError:
    if _is_not_found(exc):
        return PathNotFoundError(f"Path not found: {path}")
    if isinstance(exc, PermissionError) or (
        isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.EACCES
    ):
        return StorageError(f"Permission denied: {path}")
    if isinstance(exc, IOError) and getattr(exc, "errno", None) in (
        errno.ENOTDIR,
        errno.EISDIR,
    ):
        return StorageError(f"Invalid path type: {path}")
    return StorageError(f"SFTP error for {path}: {exc}")


__all__ = ["_is_not_found", "_wrap_sftp_error"]
