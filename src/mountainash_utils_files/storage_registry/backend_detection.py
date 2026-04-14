# storage_registry/backend_detection.py

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE

_SCHEME_TO_PROVIDER: dict[str, CONST_STORAGE_PROVIDER_TYPE] = {
    "s3": CONST_STORAGE_PROVIDER_TYPE.S3,
    "gs": CONST_STORAGE_PROVIDER_TYPE.GCS,
    "az": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "sftp": CONST_STORAGE_PROVIDER_TYPE.SFTP,
    "ssh": CONST_STORAGE_PROVIDER_TYPE.SSH,
    "r2": CONST_STORAGE_PROVIDER_TYPE.R2,
    "b2": CONST_STORAGE_PROVIDER_TYPE.B2,
}


def detect_provider_from_path(path: str) -> CONST_STORAGE_PROVIDER_TYPE:
    """Detect the storage provider from a path string.

    Args:
        path: File path, optionally with a URL scheme (e.g. ``s3://bucket/key``).

    Returns:
        The matching :class:`CONST_STORAGE_PROVIDER_TYPE` enum member.

    Raises:
        ValueError: If the scheme is present but not recognised.
    """
    if "://" in path:
        scheme = path.split("://", 1)[0].lower()
        provider = _SCHEME_TO_PROVIDER.get(scheme)
        if provider is None:
            raise ValueError(f"Unknown scheme: {scheme!r} in path {path!r}")
        return provider
    return CONST_STORAGE_PROVIDER_TYPE.LOCAL
