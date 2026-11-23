"""SFTPWriteMixin — write operations for SFTP storage backend."""
from __future__ import annotations

import io
import posixpath
import typing as t

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.stream_errors import _CallerInput

from ._helpers import _mapped, _remote_path
from .sftp_metadata import entry_from_attrs


class SFTPWriteMixin:
    """Write mixin for SFTP storage backend.

    Both writes go through paramiko ``putfo``, whose size-confirming ``stat``
    supplies the returned entry (the one request a write adds for its result).
    """

    def _prepare_write(self, path: str, create_parents: bool) -> tuple[str, t.Any]:
        path = _remote_path(self.storage_profile, path)  # type: ignore[attr-defined]
        parent = posixpath.dirname(path)
        if create_parents and parent:
            self.mkdir(parent, parents=True)  # type: ignore[attr-defined]
        return path, self._get_client()  # type: ignore[attr-defined]

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> StorageEntry:
        """Write bytes, optionally creating remote parent directories."""
        path, sftp = self._prepare_write(path, create_parents)
        with _mapped(path), io.BytesIO(data) as source:
            return entry_from_attrs(path, sftp.putfo(source, path))  # confirm=True by default

    def write_from_stream(self, path: str, stream: t.BinaryIO, *, create_parents: bool = True) -> StorageEntry:
        """Upload a stream in chunks (paramiko ``putfo``), never holding the whole payload.

        The caller's stream is left open, and an error raised by the caller's
        stream propagates unchanged rather than as a storage error.
        """
        path, sftp = self._prepare_write(path, create_parents)
        guarded = _CallerInput(stream)
        try:
            return entry_from_attrs(path, sftp.putfo(guarded, path))
        except BaseException as exc:
            original = guarded.original_in(exc)
            if original is None:
                with _mapped(path):
                    raise
        raise original[0].with_traceback(original[1])
