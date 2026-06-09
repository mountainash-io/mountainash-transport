"""S3DeleteMixin — delete operations for AWS S3."""

from __future__ import annotations

from .s3_path import parse_s3_path

from mountainash_transport.storage.protocols import StorageDeleteProtocol

class S3DeleteMixin(StorageDeleteProtocol):
    """Delete mixin for AWS S3."""

    def delete_file(self, path: str) -> None:
        """Delete an S3 object.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
        """
        bucket, key = parse_s3_path(path)
        self._client.delete_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
