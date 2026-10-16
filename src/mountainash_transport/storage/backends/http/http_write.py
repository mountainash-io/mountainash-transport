"""HTTPWriteMixin — write operations for HTTP/HTTPS."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.stream_errors import _CallerInput
from ._helpers import _mapped
from mountainash_transport.storage.protocols import StorageWriteProtocol


class HTTPWriteMixin(StorageWriteProtocol):
    """Write mixin for HTTP/HTTPS storage."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Upload bytes to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            data: Bytes to upload.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        with _mapped(path):
            engine.request("PUT", path, content=data)

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        """Upload a binary stream to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            stream: Binary stream to read and upload.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        guarded = _CallerInput(stream)
        try:
            with _mapped(path):
                engine.request("PUT", path, stream=t.cast(t.BinaryIO, guarded))
            return
        except BaseException as exc:
            original = guarded.original_in(exc)
            if original is None or original[0] is exc:
                raise
        raise original[0].with_traceback(original[1])
