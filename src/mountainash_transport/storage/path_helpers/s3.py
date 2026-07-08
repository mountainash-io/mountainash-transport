"""S3-family path extractors.

Free functions, not classes. Both return None (not raise) when the input isn't an
addressable S3-family path, so callers can branch cheaply; malformed URLs raise
ValueError via StoragePath.normalize() (missing '//', mixed-case scheme).
"""
from __future__ import annotations

from typing import Optional, Union
from urllib.parse import urlparse

from upath import UPath

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from .scheme import SCHEMES
from .storage_path import StoragePath

# S3-compatible provider types; the family scheme set is DERIVED from SCHEMES so it
# cannot drift from the registry.
_S3_PROVIDERS = frozenset({
    CONST_STORAGE_PROVIDER_TYPE.S3,
    CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    CONST_STORAGE_PROVIDER_TYPE.R2,
    CONST_STORAGE_PROVIDER_TYPE.MINIO,
    CONST_STORAGE_PROVIDER_TYPE.B2,
})
_S3_FAMILY = frozenset(s for s, spec in SCHEMES.items() if spec.provider in _S3_PROVIDERS)


def _family_bucket_key(path: Union[str, UPath, None]) -> Optional[tuple[str, str]]:
    """Return (bucket, key) for an addressable S3-family path, else None.

    Validates via StoragePath.normalize() (raises ValueError on malformed/mixed-case),
    then reads netloc=bucket / path=key from the canonical string. Endpoints are a
    profile concern, never the path: a netloc carrying a port/host yields None.
    """
    if path is None:
        return None
    text = str(path)
    if StoragePath.identify_scheme(text) not in _S3_FAMILY:
        return None
    canonical = StoragePath.normalize(text)      # raises ValueError on malformed input
    parsed = urlparse(str(canonical))
    bucket = parsed.netloc
    if not bucket or ":" in bucket:              # empty netloc or host:port → not a bucket
        return None
    return bucket, parsed.path.lstrip("/")


def s3_bucket(path: Union[str, UPath, None], *, assume_s3: bool = False) -> Optional[str]:
    """Return the bucket from an S3-family path, or None if not addressable S3."""
    result = _family_bucket_key(path)
    if result is not None:
        return result[0]
    if assume_s3 and path is not None and StoragePath.identify_scheme(str(path)) == "":
        parts = str(path).split("/", 1)
        return parts[0] if parts[0] else None
    return None


def s3_key(path: Union[str, UPath, None], *, assume_s3: bool = False) -> Optional[str]:
    """Return the object key (path after the bucket, no leading slash), or None."""
    result = _family_bucket_key(path)
    if result is not None:
        return result[1]
    if assume_s3 and path is not None and StoragePath.identify_scheme(str(path)) == "":
        parts = str(path).split("/", 1)
        return parts[1] if len(parts) > 1 else ""
    return None
