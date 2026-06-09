"""S3MetadataMixin — metadata operations for AWS S3."""

from __future__ import annotations

from mountainash_transport.dataclasses.file_metadata import FileMetadata

from .s3_path import parse_s3_path
from mountainash_transport.storage_protocols import StorageMetadataProtocol


class S3MetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for AWS S3."""

    def get_metadata(self, path: str) -> FileMetadata:
        """Return :class:`FileMetadata` for the S3 object at *path*.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.

        Returns:
            Populated :class:`FileMetadata` instance.
        """
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        filename = key.split("/")[-1] if "/" in key else key
        directory = f"s3://{bucket}/{'/'.join(key.split('/')[:-1])}" if "/" in key else f"s3://{bucket}/"
        return FileMetadata(
            filename=filename,
            directory=directory,
            full_path=f"s3://{bucket}/{key}",
            size=response.get("ContentLength", 0),
            last_modified=response.get("LastModified"),
            etag=response.get("ETag", "").strip('"'),
            storage_class=response.get("StorageClass", ""),
            source="s3",
        )

    def path_exists(self, path: str) -> bool:
        """Return True if an S3 object exists at *path*.

        Uses ``head_object`` first; falls back to ``list_objects_v2`` for
        bucket-level paths (empty key).

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.

        Returns:
            True if the object (or prefix) exists, False otherwise.
        """
        bucket, key = parse_s3_path(path)
        if not key:
            # Bucket-level existence check
            response = self._client.list_objects_v2(  # type: ignore[attr-defined]
                Bucket=bucket, MaxKeys=1
            )
            return response.get("ResponseMetadata", {}).get("HTTPStatusCode", 404) == 200

        try:
            self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
            return True
        except Exception as exc:
            # botocore.exceptions.ClientError with 404 → object not found
            error_code = ""
            response_attr = getattr(exc, "response", None)
            if isinstance(response_attr, dict):
                error_code = response_attr.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            # Fallback: prefix-based list for any other error
            list_response = self._client.list_objects_v2(  # type: ignore[attr-defined]
                Bucket=bucket, Prefix=key, MaxKeys=1
            )
            return bool(list_response.get("Contents"))

    def get_size(self, path: str) -> int:
        """Return the size in bytes of the S3 object at *path*.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.

        Returns:
            Object size in bytes.
        """
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return response.get("ContentLength", 0)
