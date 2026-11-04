"""S3CopyMixin — server-side copy operations for the S3 family."""

from __future__ import annotations

import typing as t

from .s3_path import parse_s3_path
from ._helpers import _mapped

from mountainash_transport.storage.protocols import StorageCopyProtocol

# Single-request CopyObject limits: AWS S3 and S3 Express 5 GB, Backblaze B2 5 GB
# (standard files), Cloudflare R2 5 GiB less 5 MiB; MinIO documents none. Objects
# at or above this size are copied with multipart UploadPartCopy instead.
_COPY_MULTIPART_THRESHOLD = 4 * 1024**3
# Within every provider's part-size range (5 MiB to 5 GB/GiB).
_COPY_PART_SIZE = 256 * 1024**2


def _copy_config() -> t.Any:
    from boto3.s3.transfer import TransferConfig

    return TransferConfig(multipart_threshold=_COPY_MULTIPART_THRESHOLD, multipart_chunksize=_COPY_PART_SIZE)


class S3CopyMixin(StorageCopyProtocol):
    """Copy mixin for the S3 family using server-side copy."""

    def copy(self, source: str, destination: str) -> None:
        """Copy an S3 object server side, for any object size.

        Objects below 4 GiB are copied with one ``CopyObject``; larger ones with
        multipart ``UploadPartCopy`` (boto3's managed copy), keeping the source's
        content type and metadata.

        Args:
            source: Source S3 path (``s3://bucket/key`` or ``bucket/key``).
            destination: Destination S3 path (``s3://bucket/key`` or
                ``bucket/key``).
        """
        src_bucket, src_key = parse_s3_path(source)
        dst_bucket, dst_key = parse_s3_path(destination)
        with _mapped(destination):
            self._client.copy(  # type: ignore[attr-defined]
                {"Bucket": src_bucket, "Key": src_key}, dst_bucket, dst_key, Config=_copy_config(),
            )
