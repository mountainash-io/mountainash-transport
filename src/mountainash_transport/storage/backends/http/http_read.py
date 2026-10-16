"""HTTP sequential and identity-representation ranged reads."""
from __future__ import annotations

import contextlib
import io
import re
import typing as t

from mountainash_transport._core.exceptions import (
    RangeNotSupportedError, StorageError,
)
from mountainash_transport._core.http.errors import HttpClientError
from mountainash_transport._core.http.response import HttpStreamResponse
from mountainash_transport._core.ranged_io import RangedSource, strong_etag
from mountainash_transport._core.sequential_io import IterBytesReader
from mountainash_transport.storage.protocols import StorageReadProtocol
from ._helpers import _map_error, _mapped




def _range_headers(response: HttpStreamResponse) -> tuple[int, int, int]:
    headers = response.headers
    if response.status_code != 206:
        raise RangeNotSupportedError(f"Expected 206, received {response.status_code}")
    if headers.get("content-encoding", "identity").lower() not in ("", "identity"):
        raise RangeNotSupportedError("Encoded HTTP representation cannot provide identity byte ranges")
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", headers.get("content-range", ""))
    if not match:
        raise RangeNotSupportedError("Missing or invalid Content-Range with known size")
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


class HTTPReadMixin(StorageReadProtocol):
    """Read through the transport engine, retaining its auth and retry policy."""

    def read_to_bytes(self, path: str) -> bytes:
        engine = self._get_engine()  # type: ignore[attr-defined]
        with _mapped(path):
            return engine.request("GET", path).content

    def read_to_stream(self, path: str) -> t.BinaryIO:
        engine = self._get_engine()  # type: ignore[attr-defined]
        stack = contextlib.ExitStack()
        with _mapped(path):
            response = stack.enter_context(engine.stream("GET", path))
        try:
            raw = IterBytesReader(iter(response.iter_bytes()), stack.close, lambda exc: _map_error(exc, path))
            return t.cast(t.BinaryIO, io.BufferedReader(raw))
        except BaseException:
            stack.close()
            raise

    def open_ranged(self, path: str) -> RangedSource:
        """Probe range support without relying on HEAD or Accept-Ranges."""
        engine = self._get_engine()  # type: ignore[attr-defined]
        with _mapped(path):
            try:
                with engine.stream("GET", path, headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"}) as r:
                    start, end, size = _range_headers(r)
                    if (start, end) != (0, 0) or size <= 0:
                        raise RangeNotSupportedError("Invalid probe Content-Range")
                    etag = strong_etag(r.headers.get("etag"))
            except HttpClientError as exc:
                headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
                if exc.status_code == 416 and headers.get("content-range") == "bytes */0":
                    return RangedSource(0, lambda start, end: b"")
                raise

        def fetch(start: int, end: int) -> bytes:
            headers = {"Range": f"bytes={start}-{end-1}", "Accept-Encoding": "identity"}
            if etag:
                headers["If-Match"] = etag
            with _mapped(path):
                with engine.stream("GET", path, headers=headers) as r:
                    if _range_headers(r) != (start, end - 1, size):
                        raise StorageError("Content-Range does not match requested interval and object size")
                    data = bytearray()
                    for chunk in r.iter_bytes():
                        if len(data) + len(chunk) > end - start:
                            raise StorageError("Oversized HTTP range response")
                        data.extend(chunk)
                    if len(data) != end - start:
                        raise StorageError("Truncated HTTP range response")
                    return bytes(data)

        return RangedSource(size, fetch)
