"""Storage-flavored ProfileDescriptor with typed metadata fields.

Retained in mountainash-utils-files (rather than lifted to mountainash-settings)
because these fields are domain-specific: handler_module, supports_streaming,
and read_only are meaningful only for storage providers.
"""

from __future__ import annotations

from dataclasses import dataclass

from mountainash_settings.profiles import (
    MISSING,
    ParameterSpec,
    ProfileDescriptor,
)

__all__ = ["MISSING", "ParameterSpec", "StorageDescriptor"]


@dataclass(frozen=True, kw_only=True)
class StorageDescriptor(ProfileDescriptor):
    """ProfileDescriptor with storage-provider-specific typed metadata.

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
    """

    sdk_package: str | None = None
    handler_module: str = ""
    handler_class: str = ""
    supports_streaming: bool = True
    supports_multipart: bool = True
    read_only: bool = False
