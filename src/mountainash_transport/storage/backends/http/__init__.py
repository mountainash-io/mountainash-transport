"""HTTP/HTTPS storage backend — read, write, and metadata via httpx."""
from __future__ import annotations

import io
import typing as t
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.file_metadata import FileMetadata
from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageConnectionError,
    StorageError,
)
from mountainash_transport.storage.registry import register_storage_backend
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


def _raise_for_status(response: httpx.Response, path: str) -> None:
    """Map HTTP error responses to storage exceptions."""
    code = response.status_code
    if 200 <= code < 300:
        return
    if code == 404:
        raise PathNotFoundError(f"Path not found: {path}")
    if code in (401, 403):
        raise AuthenticationError(
            f"Authentication failed ({code}) for {path}"
        )
    raise StorageError(
        f"HTTP {code} for {path}: {response.reason_phrase}"
    )


def _filename_from_url(url: str) -> str:
    """Extract filename from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return path.rsplit("/", 1)[-1] if "/" in path else path


def _directory_from_url(url: str) -> str:
    """Extract directory from a URL path."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if "/" in path:
        return path.rsplit("/", 1)[0]
    return "/"


@register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.HTTP)
class HTTPStorageBackend:
    """HTTP/HTTPS storage backend.

    Implements StorageReadProtocol, StorageWriteProtocol,
    and StorageMetadataProtocol using httpx.
    """

    def __init__(self, storage_profile: StorageProfileProtocol, *, auth_profile=None) -> None:
        self.storage_profile = storage_profile
        self.auth_profile = auth_profile
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            kwargs = self.storage_profile.to_handler_kwargs()
            self._client = httpx.Client(**kwargs)
        return self._client

    # -- StorageReadProtocol ------------------------------------------------

    def read_to_bytes(self, path: str) -> bytes:
        client = self._get_client()
        try:
            response = client.get(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout reading {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return response.content

    def read_to_stream(self, path: str) -> t.BinaryIO:
        client = self._get_client()
        try:
            response = client.get(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout reading {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return io.BytesIO(response.content)

    # -- StorageWriteProtocol -----------------------------------------------

    def write_from_bytes(self, path: str, data: bytes) -> None:
        client = self._get_client()
        try:
            response = client.put(path, content=data)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout writing {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

    def write_from_stream(self, path: str, stream: t.BinaryIO) -> None:
        client = self._get_client()
        try:
            response = client.put(path, content=stream.read())
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout writing {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

    # -- StorageMetadataProtocol --------------------------------------------

    def path_exists(self, path: str) -> bool:
        client = self._get_client()
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

    def get_metadata(self, path: str) -> FileMetadata:
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)

        headers = response.headers
        size = int(headers.get("content-length", "0"))
        etag = headers.get("etag", "")
        last_modified = None
        lm_header = headers.get("last-modified")
        if lm_header:
            try:
                last_modified = parsedate_to_datetime(lm_header)
            except (ValueError, TypeError):
                pass

        return FileMetadata(
            filename=_filename_from_url(path),
            directory=_directory_from_url(path),
            full_path=path,
            size=size,
            last_modified=last_modified,
            etag=etag,
            source="http",
        )

    def get_size(self, path: str) -> int:
        client = self._get_client()
        try:
            response = client.head(path)
        except httpx.TimeoutException as exc:
            raise StorageConnectionError(f"Timeout for {path}") from exc
        except httpx.ConnectError as exc:
            raise StorageConnectionError(f"Connection failed for {path}") from exc
        _raise_for_status(response, path)
        return int(response.headers.get("content-length", "0"))


__all__ = ["HTTPStorageBackend"]
