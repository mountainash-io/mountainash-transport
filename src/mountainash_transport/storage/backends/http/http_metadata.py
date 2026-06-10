"""HTTPMetadataMixin — metadata operations for HTTP/HTTPS."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.exceptions import StorageConnectionError
from mountainash_transport.storage.protocols import StorageMetadataProtocol

from ._helpers import _raise_for_status


def _filename_from_url(url: str) -> str:
    """Extract filename from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.rsplit("/", 1)[-1] if "/" in path else path


class HTTPMetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for HTTP/HTTPS storage."""

    def path_exists(self, path: str) -> bool:
        """Check whether a resource exists via HTTP HEAD.

        Args:
            path: Full HTTP/HTTPS URL to check.

        Returns:
            True if the server responds with a 2xx status.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout checking {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        if response.status_code == 404:
            return False
        if 200 <= response.status_code < 300:
            return True
        _raise_for_status(response, path)
        return False

    def get_metadata(self, path: str) -> StorageEntry:
        """Retrieve metadata for a resource via HTTP HEAD.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            A :class:`StorageEntry` populated from response headers.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

        headers = response.headers
        size_str = headers.get("content-length")
        size = int(size_str) if size_str else None
        etag = headers.get("etag", "")
        content_type = headers.get("content-type", "")
        content_md5 = headers.get("content-md5", "")

        last_modified = None
        lm_header = headers.get("last-modified")
        if lm_header:
            try:
                last_modified = parsedate_to_datetime(lm_header)
            except (ValueError, TypeError):
                pass

        return StorageEntry(
            path=path,
            name=_filename_from_url(path),
            size=size,
            last_modified=last_modified,
            etag=etag,
            content_type=content_type,
            source="http",
            checksum=content_md5,
            checksum_algorithm="MD5" if content_md5 else "",
        )

    def get_size(self, path: str) -> int | None:
        """Return the content-length of a resource via HTTP HEAD.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            File size in bytes, or None if the header is absent.
        """
        client = self._get_client()  # type: ignore[attr-defined]
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        size_str = response.headers.get("content-length")
        return int(size_str) if size_str else None
