"""Shared S3 path parsing utility."""

from __future__ import annotations
from ...path_helpers.s3 import s3_bucket, s3_key

def parse_s3_path(path: str) -> tuple[str, str]:
    """Parse an S3 path into (bucket, key).

    Accepts both ``s3://bucket/key`` and ``bucket/key`` forms.

    Args:
        path: S3 path string.

    Returns:
        A tuple of (bucket, key).  *key* is an empty string when the path
        refers to the bucket root.
    """

    bucket = s3_bucket(path, assume_s3=True)
    key = s3_key(path, assume_s3=True)

    if bucket is None or key is None:
        raise ValueError(f"Invalid S3 path: {path}")
    return bucket, key
