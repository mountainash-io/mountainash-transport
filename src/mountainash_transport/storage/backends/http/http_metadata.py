"""HTTPMetadataMixin — metadata operations for HTTP/HTTPS."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageError,
)
from mountainash_transport._core.http.errors import (
    HttpAuthenticationError,
    HttpForbiddenError,
    HttpNotFoundError,
    HttpTransportError,
)
from mountainash_transport.storage.protocols import StorageMetadataProtocol


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
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            engine.request("HEAD", path)
            return True
        except HttpNotFoundError:
            return False
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

    def get_metadata(self, path: str) -> StorageEntry:
        """Retrieve metadata for a resource via HTTP HEAD.

        Args:
            path: Full HTTP/HTTPS URL of the resource.

        Returns:
            A :class:`StorageEntry` populated from response headers.
        """
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("HEAD", path)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc

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
        engine = self._get_engine()  # type: ignore[attr-defined]
        try:
            response = engine.request("HEAD", path)
        except HttpNotFoundError as exc:
            raise PathNotFoundError(path) from exc
        except (HttpAuthenticationError, HttpForbiddenError) as exc:
            raise AuthenticationError(path) from exc
        except HttpTransportError as exc:
            raise StorageError(str(exc)) from exc
        size_str = response.headers.get("content-length")
        return int(size_str) if size_str else None
