"""HTTPMetadataMixin — metadata operations for HTTP/HTTPS."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import typing as t

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.exceptions import PathNotFoundError, StorageError
from mountainash_transport._core.http.redact import redact_userinfo

from ._helpers import _mapped
from mountainash_transport.storage.protocols import StorageMetadataProtocol


def _filename_from_url(url: str) -> str:
    """Extract filename from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.rsplit("/", 1)[-1] if "/" in path else path


def _size(headers: t.Mapping[str, str], path: str) -> int | None:
    value = headers.get("content-length")
    try:
        return int(value) if value else None
    except ValueError as exc:
        raise StorageError(f"Invalid Content-Length for {redact_userinfo(path)}") from exc


class HTTPMetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for HTTP/HTTPS storage."""

    def path_exists(self, path: str) -> bool:
        """Check whether a resource exists via HTTP HEAD.

        Args:
            path: Full HTTP/HTTPS URL to check.

        Returns:
            True if the server responds with a 2xx status.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            with _mapped(path):
                engine.request("HEAD", path)
            return True
        except PathNotFoundError:
            return False

    def get_metadata(self, path: str) -> StorageEntry:
        """Retrieve metadata for a resource via HTTP HEAD.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            A :class:`StorageEntry` populated from response headers.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        with _mapped(path):
            response = engine.request("HEAD", path)

        headers = response.headers
        size = _size(headers, path)
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
            path=redact_userinfo(path),
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
        engine = self._get_engine()  # type: ignore[attr-defined]
        with _mapped(path):
            response = engine.request("HEAD", path)
        return _size(response.headers, path)
