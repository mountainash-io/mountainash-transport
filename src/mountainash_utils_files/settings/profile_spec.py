from __future__ import annotations

from dataclasses import dataclass, field
import typing as t
from typing import Protocol, Optional

from mountainash_auth_client import CONST_AUTH_MODE
from mountainash_settings.profiles import (
    MISSING,
    ParameterSpec,
    ProfileSpec,
    Profile
)




if t.TYPE_CHECKING:
    from mountainash_auth_client import AuthProfile


__all__ = ["MISSING", "ParameterSpec", "StorageProfileSpec"]

"""Storage-flavored ProfileSpec with typed metadata fields.

Retained in mountainash-utils-files (rather than lifted to mountainash-settings)
because these fields are domain-specific: handler_module, supports_streaming,
and read_only are meaningful only for storage providers.
"""



@dataclass(frozen=True, kw_only=True)
class StorageProfileSpec(ProfileSpec):
    """ProfileSpec with storage-provider-specific typed metadata.

    Extra fields:
        sdk_package: Canonical PyPI name of the SDK this provider uses
            (``"boto3"``, ``"google-cloud-storage"``, ``"paramiko"``, etc.).
            ``None`` for stdlib-only providers (``LocalSettings``, ``FTPSettings``).
        handler_module: Dotted module path where the storage backend lives
            (e.g. ``"mountainash_utils_files.storage_backends.s3"``).
        handler_class: Class name of the backend within handler_module
            (e.g. ``"S3StorageBackend"``).
        supports_streaming: Whether the backend supports streaming reads/writes.
        supports_multipart: Whether the backend supports multipart upload.
        read_only: Whether the backend is read-only (``GitHubRepoSettings`` = True).
        default_auth: Auth mode used by ``load_storage()`` when caller doesn't specify.
        supported_auth: Full set of valid auth modes for this provider.
    """

    sdk_package: str | None = None
    handler_module: str = ""
    handler_class: str = ""
    supports_streaming: bool = True
    supports_multipart: bool = True
    read_only: bool = False
    default_auth: CONST_AUTH_MODE = CONST_AUTH_MODE.NONE
    supported_auth: frozenset[CONST_AUTH_MODE] = field(
        default_factory=lambda: frozenset({CONST_AUTH_MODE.NONE})
    )
