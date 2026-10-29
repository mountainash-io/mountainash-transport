# storage_registry/backend_detection.py

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._schemes import SCHEMES
from mountainash_transport import location


def detect_provider_from_path(path: str) -> CONST_STORAGE_PROVIDER_TYPE:
    """Detect the storage provider from a path string.

    Args:
        path: File path, optionally with a URL scheme (e.g. ``s3://bucket/key``).

    Returns:
        The matching :class:`CONST_STORAGE_PROVIDER_TYPE` enum member.

    Raises:
        ValueError: If the scheme is present but not registered in SCHEMES,
            or if the scheme is registered but has no backend provider.
    """
    scheme = location.identify_scheme(str(path)) if path else ""
    if scheme is None:
        raise ValueError(f"Unrecognised scheme in path {path!r}")
    spec = SCHEMES[scheme]
    if spec.provider is None:
        raise ValueError(
            f"Scheme {scheme!r} is recognised but has no registered backend"
        )
    return spec.provider
