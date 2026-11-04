"""Local filesystem error classification, at native operation boundaries only."""
from __future__ import annotations

import contextlib
import io
import shutil
import typing as t

from mountainash_transport._core.exceptions import (
    PathNotFoundError, PermissionDeniedError, StorageConnectionError, StorageError,
)
from mountainash_transport.location import local_path


def _native(path: str) -> str:
    """Return the filesystem path for *path*: ``file://`` URLs decoded, bare paths unchanged.

    Runs on every operation regardless of location policy (a policy only judges);
    a ``file://`` URL with a non-local host, userinfo, query or fragment raises a
    redacted ``LocationNotAllowed``.
    """
    return local_path(path)


def _map_local_error(exc: Exception, path: str) -> StorageError | None:
    if isinstance(exc, (StorageError, io.UnsupportedOperation, shutil.SameFileError)):
        return None
    if isinstance(exc, FileNotFoundError):
        return PathNotFoundError(path)
    if isinstance(exc, PermissionError):
        return PermissionDeniedError(path)
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return StorageConnectionError(f"{path}: {exc}")
    if isinstance(exc, OSError):
        return StorageError(f"{path}: {exc}")
    return None


@contextlib.contextmanager
def _mapped(path: str) -> t.Iterator[None]:
    try:
        yield
    except OSError as exc:
        mapped = _map_local_error(exc, path)
        if mapped is None:
            raise
        raise mapped from exc
