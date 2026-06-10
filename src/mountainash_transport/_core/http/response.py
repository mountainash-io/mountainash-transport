"""HTTP response value types.

Provides two response types:

- ``HttpResponse`` — a frozen dataclass holding the fully-buffered response.
- ``HttpStreamResponse`` — a thin wrapper around an ``httpx.Response`` in
  streaming mode, exposing a consistent interface without loading the body.
"""

from __future__ import annotations

import json
import typing as t
from dataclasses import dataclass

from mountainash_transport._core.http.errors import HttpDecodeError

if t.TYPE_CHECKING:
    import httpx


@dataclass(frozen=True)
class HttpResponse:
    """A fully-buffered HTTP response.

    Parameters
    ----------
    status_code:
        The HTTP status code (e.g. 200, 404).
    headers:
        Response headers as a plain ``dict[str, str]``.
    content:
        Raw response body bytes.
    url:
        The final request URL (after any redirects).
    method:
        The HTTP method used (e.g. ``"GET"``, ``"POST"``).
    """

    status_code: int
    headers: dict[str, str]
    content: bytes
    url: str
    method: str

    @property
    def text(self) -> str:
        """Decode the response body as UTF-8 text."""
        return self.content.decode("utf-8")

    def json(self) -> t.Any:
        """Parse the response body as JSON.

        Returns
        -------
        Any
            The decoded JSON value (dict, list, str, int, float, bool, or None).

        Raises
        ------
        HttpDecodeError
            If the content cannot be decoded as UTF-8 or is not valid JSON.
        """
        try:
            return json.loads(self.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HttpDecodeError(
                f"Failed to decode response body as JSON: {exc}"
            ) from exc


class HttpStreamResponse:
    """Wraps an ``httpx.Response`` opened in streaming mode.

    The underlying response body is *not* loaded into memory; callers use
    :meth:`iter_bytes` or :meth:`iter_text` to consume it incrementally, or
    :meth:`read` to buffer it on demand.

    Parameters
    ----------
    response:
        An ``httpx.Response`` instance with streaming enabled (i.e. opened
        inside an ``httpx.Client.stream()`` context).
    """

    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    # ------------------------------------------------------------------
    # Response metadata
    # ------------------------------------------------------------------

    @property
    def status_code(self) -> int:
        """HTTP status code."""
        return self._response.status_code

    @property
    def headers(self) -> dict[str, str]:
        """Response headers as a plain dict."""
        return dict(self._response.headers)

    @property
    def url(self) -> str:
        """Final request URL as a string."""
        return str(self._response.url)

    @property
    def method(self) -> str:
        """HTTP method used for the request (e.g. ``"GET"``)."""
        return self._response.request.method

    # ------------------------------------------------------------------
    # Body consumption
    # ------------------------------------------------------------------

    def iter_bytes(self, chunk_size: int = 65536) -> t.Iterator[bytes]:
        """Iterate over the response body in raw byte chunks.

        Parameters
        ----------
        chunk_size:
            Number of bytes per chunk. Defaults to 65 536 (64 KiB).
        """
        return self._response.iter_bytes(chunk_size=chunk_size)

    def iter_text(self, chunk_size: int = 65536) -> t.Iterator[str]:
        """Iterate over the response body decoded as text chunks.

        Parameters
        ----------
        chunk_size:
            Number of bytes per chunk. Defaults to 65 536 (64 KiB).
        """
        return self._response.iter_text(chunk_size=chunk_size)

    def read(self) -> bytes:
        """Read and return the full response body as bytes.

        This buffers the entire body in memory.
        """
        return self._response.read()

    def close(self) -> None:
        """Close the streaming response and release underlying resources."""
        self._response.close()
