"""S3MetadataMixin — metadata operations for AWS S3."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport.storage.protocols import StorageMetadataProtocol
from mountainash_transport._core.exceptions import PathNotFoundError

from ._helpers import _mapped

from .s3_path import parse_s3_path

_CHECKSUM_PREFERENCE = (
    ("ChecksumSHA256", "SHA256"),
    ("ChecksumCRC32C", "CRC32C"),
    ("ChecksumCRC32", "CRC32"),
    ("ChecksumSHA1", "SHA1"),
)


def _pick_checksum(response: dict) -> tuple[str, str]:
    for key, algorithm in _CHECKSUM_PREFERENCE:
        value = response.get(key)
        if value:
            return value, algorithm
    return "", ""


def entry_from_response(
    bucket: str, key: str, response: t.Mapping[str, t.Any] | None, size: int | None,
) -> StorageEntry:
    """The StorageEntry for ``s3://bucket/key`` from an S3 response already in hand.

    Accepts HeadObject, PutObject, CompleteMultipartUpload and CopyObject
    responses (whose ETag and LastModified sit under ``CopyObjectResult``).
    *size* is supplied by the caller; a None *response* gives path, name and size only.
    """
    response = response or {}
    result = response.get("CopyObjectResult") or response
    checksum, checksum_algorithm = _pick_checksum(t.cast(dict, result))
    return StorageEntry(
        path=f"s3://{bucket}/{key}",
        name=key.rsplit("/", 1)[-1] if "/" in key else key,
        size=size,
        last_modified=result.get("LastModified"),
        etag=result.get("ETag", "").strip('"'),
        content_type=response.get("ContentType", ""),
        storage_class=response.get("StorageClass", ""),
        source="s3",
        version_id=response.get("VersionId", ""),
        checksum=checksum,
        checksum_algorithm=checksum_algorithm,
    )


class S3MetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for AWS S3."""

    def get_metadata(self, path: str) -> StorageEntry:
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return entry_from_response(bucket, key, response, response.get("ContentLength", 0))

    def path_exists(self, path: str) -> bool:
        bucket, key = parse_s3_path(path)
        try:
            with _mapped(path):
                if not key:
                    response = self._client.list_objects_v2(Bucket=bucket, MaxKeys=1)  # type: ignore[attr-defined]
                    return response.get("ResponseMetadata", {}).get("HTTPStatusCode", 404) == 200
                self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
            return True
        except PathNotFoundError:
            return False

    def get_size(self, path: str) -> int | None:
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return response.get("ContentLength")
