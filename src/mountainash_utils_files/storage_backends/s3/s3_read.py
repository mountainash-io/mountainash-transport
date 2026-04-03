"""S3ReadMixin — read operations for AWS S3."""

from __future__ import annotations

import io
from typing import BinaryIO

from .s3_path import parse_s3_path


class S3ReadMixin:
    """Read mixin for AWS S3."""

    def read_to_bytes(self, path: str) -> bytes:
        """Download an S3 object and return its contents as bytes.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.

        Returns:
            Object body as bytes.
        """
        bucket, key = parse_s3_path(path)
        response = self._client.get_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return response["Body"].read()

    def read_to_stream(self, path: str) -> BinaryIO:
        """Download an S3 object and return a seekable in-memory binary stream.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.

        Returns:
            A :class:`io.BytesIO` stream containing the object body.
        """
        data = self.read_to_bytes(path)
        return io.BytesIO(data)
