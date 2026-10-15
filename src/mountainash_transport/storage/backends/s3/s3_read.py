"""S3ReadMixin — read operations for AWS S3."""

from __future__ import annotations

import io
import typing as t
from typing import BinaryIO

from .s3_path import parse_s3_path

from mountainash_transport.storage.protocols import StorageReadProtocol
from mountainash_transport._core.exceptions import (
    AuthenticationError, ObjectChangedError, PathNotFoundError, StorageError,
)
from mountainash_transport._core.ranged_io import RangedSource, strong_etag
from mountainash_transport._core.sequential_io import ForwardOnlyReader


def _map_error(exc: Exception, path: str) -> StorageError:
    response = getattr(exc, "response", {})
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    code = response.get("Error", {}).get("Code")
    if status == 404 or code in ("404", "NoSuchKey", "NotFound"):
        return PathNotFoundError(path)
    if status in (401, 403) or code == "AccessDenied":
        return AuthenticationError(path)
    if status == 412 or code == "PreconditionFailed":
        return ObjectChangedError(path)
    return StorageError(f"{path}: {exc}")


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
        response = self._client.get_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return response["Body"].read()

    def read_to_stream(self, path: str) -> BinaryIO:
        """Return a forward-only native object stream; caller closes it."""
        bucket, key = parse_s3_path(path)
        try:
            body = self._client.get_object(Bucket=bucket, Key=key)["Body"]  # type: ignore[attr-defined]
        except Exception as exc:
            raise _map_error(exc, path) from exc
        return t.cast(BinaryIO, io.BufferedReader(ForwardOnlyReader(
            body.read, body.close, lambda exc: _map_error(exc, path),
        )))

    def open_ranged(self, path: str) -> RangedSource:
        """Read ranges pinned to the initial strong ETag, when available."""
        bucket, key = parse_s3_path(path)
        try:
            head = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        except Exception as exc:
            raise _map_error(exc, path) from exc
        size = int(head["ContentLength"])
        etag = strong_etag(head.get("ETag"))

        def fetch(start: int, end: int) -> bytes:
            kwargs: dict[str, t.Any] = dict(Bucket=bucket, Key=key, Range=f"bytes={start}-{end-1}")
            if etag:
                kwargs["IfMatch"] = etag
            try:
                response = self._client.get_object(**kwargs)  # type: ignore[attr-defined]
                body = response["Body"]
                try:
                    data = body.read(end - start + 1)
                    if len(data) != end - start:
                        raise StorageError("S3 range response length mismatch")
                    return data
                finally:
                    body.close()
            except StorageError:
                raise
            except Exception as exc:
                raise _map_error(exc, path) from exc

        return RangedSource(size, fetch)
