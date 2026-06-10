"""S3MetadataMixin — metadata operations for AWS S3."""
from __future__ import annotations

from mountainash_transport._core.dataclasses.storage_entry import StorageEntry
from mountainash_transport.storage.protocols import StorageMetadataProtocol

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


class S3MetadataMixin(StorageMetadataProtocol):
    """Metadata mixin for AWS S3."""

    def get_metadata(self, path: str) -> StorageEntry:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        name = key.rsplit("/", 1)[-1] if "/" in key else key
        checksum, checksum_algorithm = _pick_checksum(response)
        return StorageEntry(
            path=f"s3://{bucket}/{key}",
            name=name,
            size=response.get("ContentLength", 0),
            last_modified=response.get("LastModified"),
            etag=response.get("ETag", "").strip('"'),
            content_type=response.get("ContentType", ""),
            storage_class=response.get("StorageClass", ""),
            source="s3",
            version_id=response.get("VersionId", ""),
            checksum=checksum,
            checksum_algorithm=checksum_algorithm,
        )

    def path_exists(self, path: str) -> bool:
        bucket, key = parse_s3_path(path)
        if not key:
            response = self._client.list_objects_v2(Bucket=bucket, MaxKeys=1)  # type: ignore[attr-defined]
            return response.get("ResponseMetadata", {}).get("HTTPStatusCode", 404) == 200
        try:
            self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
            return True
        except Exception as exc:
            error_code = ""
            response_attr = getattr(exc, "response", None)
            if isinstance(response_attr, dict):
                error_code = response_attr.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            list_response = self._client.list_objects_v2(  # type: ignore[attr-defined]
                Bucket=bucket, Prefix=key, MaxKeys=1
            )
            return bool(list_response.get("Contents"))

    def get_size(self, path: str) -> int | None:
        bucket, key = parse_s3_path(path)
        response = self._client.head_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]
        return response.get("ContentLength")
