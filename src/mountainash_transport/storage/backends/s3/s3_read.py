"""S3ReadMixin — read operations for AWS S3."""

from __future__ import annotations

import io
import typing as t
from typing import BinaryIO

from .s3_path import parse_s3_path

from mountainash_transport.storage.protocols import StorageReadProtocol
from mountainash_transport._core.exceptions import StorageError
from mountainash_transport._core.ranged_io import RangedSource, strong_etag
from mountainash_transport._core.sequential_io import ForwardOnlyReader
from ._helpers import _map_error, _mapped




class S3ReadMixin(StorageReadProtocol):
    """Read mixin for AWS S3."""

    def read_to_bytes(self, path: str) -> bytes:
        """Download an S3 object and return its contents as bytes.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.

        Returns:
            Object body as bytes.
        """
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            response = self._client.get_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
            try:
                return response["Body"].read()
            finally:
                response["Body"].close()

    def read_to_stream(self, path: str) -> BinaryIO:
        """Return a forward-only native object stream; caller closes it."""
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            body = self._client.get_object(Bucket=bucket, Key=key)["Body"]  # type: ignore[attr-defined]
        return t.cast(BinaryIO, io.BufferedReader(ForwardOnlyReader(
            body.read, body.close, lambda exc: _map_error(exc, path),
        )))

    def open_ranged(self, path: str) -> RangedSource:
        """Read ranges pinned to the initial strong ETag, when available."""
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            head = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        size = int(head["ContentLength"])
        etag = strong_etag(head.get("ETag"))

        def fetch(start: int, end: int) -> bytes:
            kwargs: dict[str, t.Any] = dict(Bucket=bucket, Key=key, Range=f"bytes={start}-{end-1}")
            if etag:
                kwargs["IfMatch"] = etag
            with _mapped(path):
                response = self._client.get_object(**kwargs)  # type: ignore[attr-defined]
                body = response["Body"]
                try:
                    data = body.read(end - start + 1)
                    if len(data) != end - start:
                        raise StorageError("S3 range response length mismatch")
                    return data
                finally:
                    body.close()

        return RangedSource(size, fetch)
