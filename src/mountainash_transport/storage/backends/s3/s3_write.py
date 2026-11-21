"""S3WriteMixin — write operations for AWS S3."""

from __future__ import annotations

from typing import BinaryIO
import typing as t

from mountainash_transport._core.stream_errors import _CallerInput
from mountainash_transport._core.safe_display import raise_safe
from ._helpers import _map_error, _mapped

from .s3_path import parse_s3_path

from mountainash_transport.storage.protocols import StorageWriteProtocol

# Transport settings on S3StorageProfile -> boto3 TransferConfig arguments.
_TRANSFER_FIELDS = (
    ("MULTIPART_THRESHOLD", "multipart_threshold"),
    ("MULTIPART_CHUNKSIZE", "multipart_chunksize"),
    ("MAX_CONCURRENCY", "max_concurrency"),
)


def _upload_config(profile: t.Any) -> t.Any:
    """A TransferConfig from the profile's transfer fields, or None to keep boto3's defaults."""
    settings = {arg: value for field, arg in _TRANSFER_FIELDS
                if (value := getattr(profile, field, None)) is not None}
    if not settings:
        return None
    from boto3.s3.transfer import TransferConfig

    return TransferConfig(**settings)


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
        uploads and uses a single PUT for small ones; the profile's
        ``MULTIPART_THRESHOLD``, ``MULTIPART_CHUNKSIZE`` and ``MAX_CONCURRENCY``
        override boto3's transfer defaults when set.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            stream: Binary stream to read from.
            create_parents: Ignored; object keys have no directory parents.
        """
        bucket, key = parse_s3_path(path)
        config = _upload_config(getattr(self, "storage_profile", None))
        guarded = _CallerInput(stream)
        try:
            self._client.upload_fileobj(  # type: ignore[attr-defined]
                t.cast(BinaryIO, guarded), bucket, key, **({"Config": config} if config else {}),
            )
            return
        except BaseException as exc:
            # Look for the caller's error in the native chain: mapping drops it
            # from the chain it raises, so a caller error could not be found afterwards.
            original = guarded.original_in(exc)
            if original is None:
                mapped = _map_error(exc, path) if isinstance(exc, Exception) else None
                if mapped is None or mapped is exc:
                    raise
                raise_safe(mapped, exc)
        raise original[0].with_traceback(original[1])
