"""S3-specific path extractors.

Free functions, not classes. Both return None (not raise) when the
input isn't an S3 path, so callers can branch cheaply.
"""
from __future__ import annotations

from typing import Optional, Union

from upath import UPath

from .storage_path import StoragePath


def s3_bucket(
    path: Union[str, UPath, None],
    *,
    assume_s3: bool = False,
) -> Optional[str]:
    """Return the bucket name from an S3 path, or None if `path` isn't S3.

    When *assume_s3* is True, bare paths without an ``s3://`` scheme are
    treated as S3 paths (``bucket/key`` form).
    """
    if path is None:
        return None
    text = str(path)
    scheme = StoragePath.identify_scheme(text)
    if scheme == "s3":
        parsed = StoragePath.normalize(text)
        if parsed is None:
            return None
        drive = parsed.drive  # type: ignore[attr-defined]
        if not drive:
            return None
        return drive.rstrip("/")
    if assume_s3 and scheme == "":
        parts = text.split("/", 1)
        return parts[0] if parts[0] else None
    return None


def s3_key(
    path: Union[str, UPath, None],
    *,
    assume_s3: bool = False,
) -> Optional[str]:
    """Return the object key (path after the bucket, no leading slash), or None.

    When *assume_s3* is True, bare paths without an ``s3://`` scheme are
    treated as S3 paths (``bucket/key`` form).
    """
    if path is None:
        return None
    text = str(path)
    scheme = StoragePath.identify_scheme(text)
    if scheme == "s3":
        parsed = StoragePath.normalize(text)
        if parsed is None:
            return None
        parts = parsed.parts  # type: ignore[attr-defined]
        if len(parts) < 2:
            return ""
        return "/".join(parts[1:])
    if assume_s3 and scheme == "":
        parts = text.split("/", 1)
        return parts[1] if len(parts) > 1 else ""
    return None
