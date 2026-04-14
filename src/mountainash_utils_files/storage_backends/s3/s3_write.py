"""S3WriteMixin — write operations for AWS S3."""

from __future__ import annotations

from typing import BinaryIO

from .s3_path import parse_s3_path


class S3WriteMixin:
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
        """Upload data from a binary stream as an S3 object.

        The entire stream is read into memory before uploading.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            stream: Binary stream to read from.
        """
        data = stream.read()
        self.write_from_bytes(path, data)
