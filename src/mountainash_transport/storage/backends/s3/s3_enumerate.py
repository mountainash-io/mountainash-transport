"""S3EnumerateMixin — object enumeration for S3-family backends."""
from __future__ import annotations

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)
from mountainash_transport.storage.protocols import StorageEnumerateProtocol

from .s3_path import parse_s3_path


class S3EnumerateMixin(StorageEnumerateProtocol):
    """Enumerate mixin for AWS S3."""

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = None,
        max_results: int | None = None,
    ) -> EnumerateResult:
        bucket, key_prefix = parse_s3_path(prefix)
        objects: list[StorageEntry] = []
        common_prefixes: list[StorageEntry] = []

        paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[attr-defined]
        paginate_kwargs: dict = {"Bucket": bucket, "Prefix": key_prefix}
        if delimiter is not None:
            paginate_kwargs["Delimiter"] = delimiter

        for page in paginator.paginate(**paginate_kwargs):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                name = key.rsplit("/", 1)[-1] if "/" in key else key
                objects.append(
                    StorageEntry(
                        path=f"s3://{bucket}/{key}",
                        name=name,
                        size=obj.get("Size", 0),
                        last_modified=obj.get("LastModified"),
                        etag=obj.get("ETag", "").strip('"'),
                        storage_class=obj.get("StorageClass", ""),
                        source="s3",
                    )
                )
            for cp in page.get("CommonPrefixes", []) or []:
                raw_prefix: str = cp.get("Prefix", "")
                stripped = raw_prefix.rstrip("/")
                name = stripped.rsplit("/", 1)[-1] if "/" in stripped else stripped
                common_prefixes.append(
                    StorageEntry(
                        path=f"s3://{bucket}/{raw_prefix}",
                        name=name,
                        entry_type=EntryType.PREFIX,
                        source="s3",
                    )
                )

        all_entries = objects + common_prefixes
        if max_results is not None and len(all_entries) > max_results:
            objects = objects[:max_results]
            remaining = max_results - len(objects)
            common_prefixes = common_prefixes[:max(0, remaining)]

        return EnumerateResult(
            objects=tuple(objects),
            common_prefixes=tuple(common_prefixes),
        )
