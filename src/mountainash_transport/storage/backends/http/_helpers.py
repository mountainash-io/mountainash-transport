"""Shared helpers for the HTTP storage backend."""
from __future__ import annotations

import httpx

from mountainash_transport._core.exceptions import (
    AuthenticationError,
    PathNotFoundError,
    StorageError,
)


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
