"""S3CopyMixin — server-side copy operations for AWS S3."""

from __future__ import annotations

from .s3_path import parse_s3_path

from mountainash_transport.storage_protocols import StorageCopyProtocol

class S3CopyMixin(StorageCopyProtocol):
    """Copy mixin for AWS S3 using server-side copy."""

    def copy(self, source: str, destination: str) -> None:
        """Copy an S3 object to another location using server-side copy.

        Args:
            source: Source S3 path (``s3://bucket/key`` or ``bucket/key``).
            destination: Destination S3 path (``s3://bucket/key`` or
                ``bucket/key``).
        """
        src_bucket, src_key = parse_s3_path(source)
        dst_bucket, dst_key = parse_s3_path(destination)
        self._client.copy_object(  # type: ignore[attr-defined]
            Bucket=dst_bucket,
            Key=dst_key,
            CopySource={"Bucket": src_bucket, "Key": src_key},
        )
