"""S3DeleteMixin — delete operations for AWS S3."""

from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import BulkDeleteError, PathNotFoundError, StorageError

from .s3_path import parse_s3_path
from ._helpers import _map_error, _mapped

from mountainash_transport.storage.protocols import StorageDeleteProtocol

# DeleteObjects accepts at most 1,000 keys per request.
_BATCH = 1000


class S3DeleteMixin(StorageDeleteProtocol):
    """Delete mixin for AWS S3."""

    def delete_file(self, path: str) -> None:
        """Delete an S3 object.

        Args:
            path: S3 path in the form ``s3://bucket/key`` or ``bucket/key``.
        """
        bucket, key = parse_s3_path(path)
        with _mapped(path):
            self._client.delete_object(Bucket=bucket, Key=key)  # type: ignore[attr-defined]

    def delete_many(self, paths: t.Iterable[str]) -> None:
        """Delete every path with ``DeleteObjects``, one request per bucket per 1,000 keys.

        Every path is attempted; a key repeated in the input is sent once.
        Missing keys and buckets count as deleted. Per-key errors, and a whole
        request's error for each of its keys, are mapped to storage errors and
        raised together as one ``BulkDeleteError`` in input order. botocore owns
        retries and the request checksum.
        """
        by_bucket: dict[str, dict[str, tuple[int, str]]] = {}
        for index, path in enumerate(paths):
            bucket, key = parse_s3_path(path)
            by_bucket.setdefault(bucket, {}).setdefault(key, (index, path))

        failures: list[tuple[int, str, StorageError]] = []
        for bucket, keyed in by_bucket.items():
            entries = [(index, path, key) for key, (index, path) in keyed.items()]
            for start in range(0, len(entries), _BATCH):
                failures.extend(self._delete_batch(bucket, entries[start:start + _BATCH]))
        failures = [failure for failure in failures if not isinstance(failure[2], PathNotFoundError)]
        if failures:
            failures.sort(key=lambda failure: failure[0])
            raise BulkDeleteError(tuple((path, error) for _, path, error in failures))

    def _delete_batch(
        self, bucket: str, entries: list[tuple[int, str, str]],
    ) -> list[tuple[int, str, StorageError]]:
        """One DeleteObjects request; returns (input index, path, mapped error) for each failed key."""
        from botocore.exceptions import ClientError

        try:
            response = self._client.delete_objects(  # type: ignore[attr-defined]
                Bucket=bucket, Delete={"Objects": [{"Key": key} for _, _, key in entries], "Quiet": True},
            )
        except Exception as exc:
            mapped = [(index, path, _map_error(exc, path)) for index, path, _ in entries]
            if any(error is None for _, _, error in mapped):
                raise  # not a storage failure (e.g. invalid parameters): the caller's error
            return t.cast(list[tuple[int, str, StorageError]], mapped)

        by_key = {key: (index, path) for index, path, key in entries}
        failed = []
        for item in response.get("Errors", ()):
            index, path = by_key[item["Key"]]
            error = ClientError({"Error": {"Code": item.get("Code", ""), "Message": item.get("Message", "")}},
                                "DeleteObjects")
            failed.append((index, path, _map_error(error, path) or StorageError(path)))
        return failed
