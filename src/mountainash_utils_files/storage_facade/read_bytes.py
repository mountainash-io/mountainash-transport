"""Top-level read helper that dispatches by URL scheme.

For http/https, uses urllib directly as a temporary bridge until the HTTP
backend follow-up spec ships.
"""
from __future__ import annotations

import typing
import urllib.request

from mountainash_utils_files.path_helpers.storage_path import StoragePath
from mountainash_utils_files.storage_facade.facade import StorageFacade


def read_bytes(path: str, auth_params: typing.Any = None) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    Local paths and recognised storage schemes route through
    :meth:`StorageFacade.from_path`. ``http://`` and ``https://`` paths use
    ``urllib.request.urlopen`` directly; this branch is removed when the
    HTTP backend follow-up spec ships.

    Args:
        path: Path or URL.
        auth_params: Optional auth params forwarded to the storage facade.

    Returns:
        The full content of *path* as ``bytes``.

    Raises:
        ValueError: If the scheme is unrecognised or describes a backend that
            is not registered.
    """
    scheme = StoragePath.identify_scheme(path)
    if scheme in ("http", "https"):
        with urllib.request.urlopen(path) as response:  # noqa: S310
            return response.read()
    return StorageFacade.from_path(path, auth_params).read(path)
