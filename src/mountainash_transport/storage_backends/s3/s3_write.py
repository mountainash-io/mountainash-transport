"""S3WriteMixin — write operations for AWS S3."""

from __future__ import annotations

from typing import BinaryIO

from .s3_path import parse_s3_path

from mountainash_transport.storage_protocols import StorageWriteProtocol

class S3WriteMixin(StorageWriteProtocol):
    """Write mixin for AWS S3."""

    def write_from_bytes(self, path: str, data: bytes) -> None:
        """Upload bytes as an S3 object.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            data: Bytes to upload.
        """
        bucket, key = parse_s3_path(path)
        self._client.put_object(Bucket=bucket, Key=key, Body=data)  # type: ignore[attr-defined]

    def write_from_stream(self, path: str, stream: BinaryIO) -> None:
        """Upload from a binary stream using boto3's multipart-aware upload_fileobj.

        Does NOT buffer the stream into memory. boto3 auto-multiparts large
        uploads and uses a single PUT for small ones.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            stream: Binary stream to read from.
        """
        bucket, key = parse_s3_path(path)
        self._client.upload_fileobj(stream, bucket, key)  # type: ignore[attr-defined]
