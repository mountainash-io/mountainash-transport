"""S3-specific path extractors.

Free functions, not classes. Both return None (not raise) when the
input isn't an S3 path, so callers can branch cheaply.
"""
from __future__ import annotations

from typing import Optional, Union

from upath import UPath

from .storage_path import StoragePath


def s3_bucket(path: Union[str, UPath, None]) -> Optional[str]:
    """Return the bucket name from an S3 path, or None if `path` isn't S3."""
    if path is None:
        return None
    if StoragePath.identify_scheme(path) != "s3":
        return None
    parsed = StoragePath.normalize(path)
    if parsed is None:
        return None
    # UPath stores the bucket name in the drive property.
    # For "s3://bucket/key/...", drive is "bucket"
    drive = parsed.drive  # type: ignore[attr-defined]
    if not drive:
        return None
    return drive.rstrip("/")


def s3_key(path: Union[str, UPath, None]) -> Optional[str]:
    """Return the object key (path after the bucket, no leading slash), or None."""
    if path is None:
        return None
    if StoragePath.identify_scheme(path) != "s3":
        return None
    parsed = StoragePath.normalize(path)
    if parsed is None:
        return None
    # UPath parts for "s3://bucket/key/..." → ("bucket/", "key", ...)
    # Skip the first part (bucket/) and join the rest.
    parts = parsed.parts  # type: ignore[attr-defined]
    if len(parts) < 2:
        return ""
    return "/".join(parts[1:])
