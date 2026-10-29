"""SFTP backend helpers — shared utilities used across all SFTP mixins."""
from __future__ import annotations

import errno
import contextlib
import io
import posixpath
import stat
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


def _remote_path(profile: t.Any, path: str) -> str:
    """Return the remote path for *path*, converting ``sftp://HOST[:PORT]/p`` to ``/p``.

    The URL's host and port must match the connected profile's ``HOST`` and
    ``PORT``; otherwise the URL names another server and is rejected.
    """
    if not path[:7].lower().startswith("sftp://"):
        return path
    from urllib.parse import unquote, urlsplit

    from mountainash_transport.location import LocationNotAllowed, _norm_host, url_host
    host = url_host(path)
    try:
        parts = urlsplit(path)
        port = parts.port if parts.port is not None else 22
    except ValueError:
        raise LocationNotAllowed(path, "invalid location") from None
    if parts.query or parts.fragment:
        raise LocationNotAllowed(path, "invalid location")
    profile_host = getattr(profile, "HOST", None)
    if not profile_host or host != _norm_host(profile_host) or port != getattr(profile, "PORT", 22):
        raise LocationNotAllowed(path, "profile host mismatch")
    return unquote(parts.path) or "/"


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


def _require_file_type(mode: int | None, path: str) -> int:
    """Keep unavailable type distinct from known special-file types."""
    kind = stat.S_IFMT(mode) if mode is not None else 0
    if not kind:
        raise StorageError(f"{path}: SFTP server did not supply file type information")
    return kind


def _check_not_directory(client: t.Any, path: str) -> None:
    """Recover ENOTDIR after SFTP v3 reports ambiguous NO_SUCH_FILE."""
    candidate = path.rstrip("/") or ("/" if path.startswith("/") else ".")
    while True:
        try:
            attrs = client.stat(candidate)
        except OSError as error:
            if not _is_not_found(error):
                raise
        else:
            if _require_file_type(attrs.st_mode, candidate) != stat.S_IFDIR:
                raise NotADirectoryError(errno.ENOTDIR, "Not a directory", candidate)
            return
        parent = posixpath.dirname(candidate)
        if not parent or parent == candidate:
            return
        candidate = parent
