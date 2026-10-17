"""S3WriteMixin — write operations for AWS S3."""

from __future__ import annotations

from typing import BinaryIO
import typing as t

from mountainash_transport._core.stream_errors import _CallerInput
from ._helpers import _mapped

from .s3_path import parse_s3_path

from mountainash_transport.storage.protocols import StorageWriteProtocol

class S3WriteMixin(StorageWriteProtocol):
    """Write mixin for AWS S3."""

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> None:
        """Upload bytes as an S3 object.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            data: Bytes to upload.
            create_parents: Ignored; object keys have no directory parents.
        """
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            self._client.put_object(Bucket=bucket, Key=key, Body=data)  # type: ignore[attr-defined]

    def write_from_stream(self, path: str, stream: BinaryIO, *, create_parents: bool = True) -> None:
        """Upload from a binary stream using boto3's multipart-aware upload_fileobj.

        Does NOT buffer the stream into memory. boto3 auto-multiparts large
        uploads and uses a single PUT for small ones.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            stream: Binary stream to read from.
            create_parents: Ignored; object keys have no directory parents.
        """
        bucket, key = parse_s3_path(path)
        guarded = _CallerInput(stream)
        try:
            with _mapped(path):
                self._client.upload_fileobj(t.cast(BinaryIO, guarded), bucket, key)  # type: ignore[attr-defined]
            return
        except BaseException as exc:
            original = guarded.original_in(exc)
            if original is None or original[0] is exc:
                raise
        raise original[0].with_traceback(original[1])
