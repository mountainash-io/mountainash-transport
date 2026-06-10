"""S3ListMixin — listing operations for AWS S3."""

from __future__ import annotations

from mountainash_transport._core.dataclasses.file_metadata import FileMetadata

from .s3_path import parse_s3_path
from mountainash_transport.storage.protocols.prtcl_list import StorageListProtocol


class S3ListMixin(StorageListProtocol):
    """List mixin for AWS S3."""

    def list_files(self, prefix: str) -> list[FileMetadata]:
        """Return :class:`FileMetadata` for every object directly under *prefix*.

        Uses ``list_objects_v2`` without a delimiter so that objects at any
        depth under the prefix are returned, matching the behaviour expected
        by the storage protocol.

        Args:
            prefix: S3 path prefix (``s3://bucket/key-prefix/`` or
                ``bucket/key-prefix/``).

        Returns:
            List of :class:`FileMetadata` objects, one per S3 object.
        """
        bucket, key_prefix = parse_s3_path(prefix)
        results: list[FileMetadata] = []

        paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[attr-defined]
        pages = paginator.paginate(Bucket=bucket, Prefix=key_prefix)

        for page in pages:
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                filename = key.split("/")[-1] if "/" in key else key
                directory = f"s3://{bucket}/{key_prefix}"
                full_path = f"s3://{bucket}/{key}"
                results.append(
                    FileMetadata(
                        filename=filename,
                        directory=directory,
                        full_path=full_path,
                        size=obj.get("Size", 0),
                        last_modified=obj.get("LastModified"),
                        etag=obj.get("ETag", "").strip('"'),
                        storage_class=obj.get("StorageClass", ""),
                        source="s3",
                    )
                )
        return results

    def list_directories(self, prefix: str) -> list[str]:
        """Return common prefixes (virtual directories) directly under *prefix*.

        Uses ``Delimiter="/"`` so that only the immediate level of hierarchy
        is returned.

        Args:
            prefix: S3 path prefix (``s3://bucket/key-prefix/`` or
                ``bucket/key-prefix/``).

        Returns:
            List of S3 path strings for each common prefix.
        """
        bucket, key_prefix = parse_s3_path(prefix)
        results: list[str] = []

        paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[attr-defined]
        pages = paginator.paginate(Bucket=bucket, Prefix=key_prefix, Delimiter="/")

        for page in pages:
            for cp in page.get("CommonPrefixes", []) or []:
                common_prefix: str = cp.get("Prefix", "")
                results.append(f"s3://{bucket}/{common_prefix}")
        return results
