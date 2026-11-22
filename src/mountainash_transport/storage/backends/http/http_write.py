"""HTTPWriteMixin — write operations for HTTP/HTTPS."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.safe_display import raise_safe
from mountainash_transport._core.stream_errors import _CallerInput, seekable_extent
from ._helpers import _map_error, _mapped
from .http_metadata import entry_from_headers
from mountainash_transport.storage.protocols import StorageWriteProtocol


class HTTPWriteMixin(StorageWriteProtocol):
    """Write mixin for HTTP/HTTPS storage.

    Writes return the PUT response's ``ETag``/``Last-Modified`` when the server
    sends them; ``size`` is the number of bytes sent once (the response's own
    ``Content-Length`` describes the response, not the resource).
    """

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> StorageEntry:
        """Upload bytes to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            data: Bytes to upload.
            create_parents: Ignored; HTTP resources have no directory parents.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        with _mapped(path):
            response = engine.request("PUT", path, content=data)
        return entry_from_headers(path, response.headers, len(data))

    def write_from_stream(self, path: str, stream: t.BinaryIO, *, create_parents: bool = True) -> StorageEntry:
        """Upload a binary stream to a resource via HTTP PUT.

        Args:
            path: Full HTTP/HTTPS URL of the target resource.
            stream: Binary stream to read and upload.
            create_parents: Ignored; HTTP resources have no directory parents.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        guarded = _CallerInput(stream)
        try:
            # Through the guard: a decoding source can fail while seeking, and that error is the caller's.
            extent = seekable_extent(t.cast(t.BinaryIO, guarded))  # a seekable body may be sent more than once
            response = engine.request("PUT", path, stream=t.cast(t.BinaryIO, guarded))
            return entry_from_headers(path, response.headers, guarded.bytes_read if extent is None else extent)
        except BaseException as exc:
            # Look for the caller's error in the native chain: mapping drops it
            # from the chain it raises, so a caller error could not be found afterwards.
            original = guarded.original_in(exc)
            if original is None:
                mapped = _map_error(exc, path) if isinstance(exc, Exception) else None
                if mapped is None or mapped is exc:
                    raise
                raise_safe(mapped, exc)
        raise original[0].with_traceback(original[1])
