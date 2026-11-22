"""S3WriteMixin — write operations for AWS S3."""

from __future__ import annotations

from typing import BinaryIO
import typing as t

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport._core.stream_errors import _CallerInput, seekable_extent
from mountainash_transport._core.safe_display import raise_safe
from mountainash_transport._core.s3_capture import install_client_hooks
from ._helpers import _map_error, _mapped

from .s3_metadata import entry_from_response
from .s3_path import parse_s3_path

from mountainash_transport.storage.protocols import StorageWriteProtocol

# Transport settings on S3StorageProfile -> boto3 TransferConfig arguments.
_TRANSFER_FIELDS = (
    ("MULTIPART_THRESHOLD", "multipart_threshold"),
    ("MULTIPART_CHUNKSIZE", "multipart_chunksize"),
    ("MAX_CONCURRENCY", "max_concurrency"),
)


def _upload_config(profile: t.Any) -> t.Any:
    """A TransferConfig from the profile's transfer fields, always on the classic transfer manager.

    The CRT transfer manager, which boto3 can choose by itself, sends requests
    outside the client, so its responses would never reach the client's
    response capture. boto3 versions without ``preferred_transfer_client``
    have no CRT manager to avoid.
    """
    from boto3.s3.transfer import TransferConfig

    settings = {arg: value for field, arg in _TRANSFER_FIELDS
                if (value := getattr(profile, field, None)) is not None}
    config = TransferConfig(**settings)
    if hasattr(config, "preferred_transfer_client"):
        setattr(config, "preferred_transfer_client", "classic")  # noqa: B010 — stubs type it as int
    return config


class S3WriteMixin(StorageWriteProtocol):
    """Write mixin for AWS S3."""

    def write_from_bytes(self, path: str, data: bytes, *, create_parents: bool = True) -> StorageEntry:
        """Upload bytes as an S3 object and return the PutObject response's entry.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            data: Bytes to upload.
            create_parents: Ignored; object keys have no directory parents.
        """
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            response = self._client.put_object(Bucket=bucket, Key=key, Body=data)  # type: ignore[attr-defined]
        return entry_from_response(bucket, key, response, len(data))

    def write_from_stream(self, path: str, stream: BinaryIO, *, create_parents: bool = True) -> StorageEntry:
        """Upload from a binary stream using boto3's multipart-aware upload_fileobj.

        Does NOT buffer the stream into memory. boto3 auto-multiparts large
        uploads and uses a single PUT for small ones; the profile's
        ``MULTIPART_THRESHOLD``, ``MULTIPART_CHUNKSIZE`` and ``MAX_CONCURRENCY``
        override boto3's transfer defaults when set.

        The returned entry carries the ETag/VersionId of this upload's own
        PutObject or CompleteMultipartUpload response, captured from the client.
        If another write to the same key ran through the same client at the same
        time, the two responses cannot be told apart and those fields stay empty.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
            stream: Binary stream to read from.
            create_parents: Ignored; object keys have no directory parents.
        """
        bucket, key = parse_s3_path(path)
        config = _upload_config(getattr(self, "storage_profile", None))
        guarded = _CallerInput(stream)
        capture = install_client_hooks(self._client)  # type: ignore[attr-defined]
        try:
            # Through the guard: a decoding source can fail while seeking, and that error is the caller's.
            extent = seekable_extent(t.cast(BinaryIO, guarded))  # botocore may reread a seekable body
            with capture.collect(bucket, key) as seen:
                self._client.upload_fileobj(  # type: ignore[attr-defined]
                    t.cast(BinaryIO, guarded), bucket, key, Config=config,
                )
            return entry_from_response(bucket, key, seen[0] if len(seen) == 1 else None,
                                       guarded.bytes_read if extent is None else extent)
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
