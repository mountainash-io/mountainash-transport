"""SFTP backend helpers — shared utilities used across all SFTP mixins."""
from __future__ import annotations

import errno
import contextlib
import io
import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError, PathNotFoundError, PermissionDeniedError,
    StorageConnectionError, StorageError,
)


def _is_not_found(exc: BaseException) -> bool:
    if isinstance(exc, FileNotFoundError):
        return True
    if isinstance(exc, IOError) and getattr(exc, "errno", None) == errno.ENOENT:
        return True
    return False


def _wrap_sftp_error(exc: BaseException, path: str) -> StorageError | None:
    if isinstance(exc, (StorageError, io.UnsupportedOperation)):
        return None
    if _is_not_found(exc):
        return PathNotFoundError(path)
    if isinstance(exc, PermissionError) or (
        isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EPERM)
    ):
        return PermissionDeniedError(path)
    from paramiko import AuthenticationException, SFTPError, SSHException
    from paramiko.ssh_exception import NoValidConnectionsError
    if isinstance(exc, AuthenticationException):
        return AuthenticationError(path)
    if isinstance(exc, (ConnectionError, TimeoutError, EOFError, SSHException, NoValidConnectionsError)):
        return StorageConnectionError(f"{path}: {exc}")
    if isinstance(exc, (OSError, SFTPError)):
        return StorageError(f"{path}: {exc}")
    return None


@contextlib.contextmanager
def _mapped(path: str) -> t.Iterator[None]:
    try:
        yield
    except Exception as exc:
        mapped = _wrap_sftp_error(exc, path)
        if mapped is None or mapped is exc:
            raise
        raise mapped from exc
