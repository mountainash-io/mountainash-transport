"""Shared S3 path parsing utility."""

from __future__ import annotations


def parse_s3_path(path: str) -> tuple[str, str]:
    """Parse an S3 path into (bucket, key).

    Accepts both ``s3://bucket/key`` and ``bucket/key`` forms.

    Args:
        path: S3 path string.

    Returns:
        A tuple of (bucket, key).  *key* is an empty string when the path
        refers to the bucket root.
    """
    if path.startswith("s3://"):
        path = path[5:]
    parts = path.split("/", 1)
    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""
    return bucket, key
