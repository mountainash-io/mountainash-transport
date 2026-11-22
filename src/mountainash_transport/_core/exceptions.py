# exceptions.py

"""Custom exception hierarchy for mountainash-transport storage operations."""

from __future__ import annotations

from mountainash_transport._core.safe_display import safe_location

_SHOWN_FAILURES = 5


class StorageError(Exception):
    """Base exception for all storage-related errors."""


class RangeNotSupportedError(StorageError):
    """The resource cannot provide byte-range reads."""


class ObjectChangedError(StorageError):
    """A pinned object changed during ranged reading."""


class RandomAccessUnavailableError(StorageError, ValueError):
    """Random access was requested but the resolved pipeline has transforms.

    Byte ranges of an encoded object do not map to its decoded bytes, so
    ``read_stream(access="random")`` refuses a non-empty pipeline, whether passed
    or inferred from the suffix. Fall back to ``access="buffered"`` or
    ``"sequential"``. Subclasses ``ValueError`` so existing handlers still catch it.
    """


class UnsupportedOperationError(StorageError):
    """Raised when a storage backend does not support a requested operation."""


class BulkDeleteError(StorageError):
    """Raised once at the end of ``delete_many`` when any path could not be deleted.

    Every path was attempted; those listed in ``failures`` (input order, with
    the error each raised) remain, and every other path is gone. Missing paths
    count as deleted and are never listed.
    """

    def __init__(self, failures: tuple[tuple[str, StorageError], ...]) -> None:
        self.failures = failures
        shown = ", ".join(safe_location(path) for path, _ in failures[:_SHOWN_FAILURES])
        more = f" (+{len(failures) - _SHOWN_FAILURES} more)" if len(failures) > _SHOWN_FAILURES else ""
        super().__init__(f"{len(failures)} path(s) could not be deleted: {shown}{more}")


class StorageConnectionError(StorageError):
    """Raised when a connection to a storage backend fails.

    Note: intentionally does NOT inherit from the builtin ConnectionError
    to avoid shadowing it.
    """


class PathNotFoundError(StorageError):
    """Raised when a path does not exist on the storage backend."""


class AuthenticationError(StorageError):
    """Missing, invalid or expired credentials; also the base for access denial."""


class PermissionDeniedError(AuthenticationError):
    """Access was denied; this does not establish valid credentials."""


class TransformError(StorageError):
    """Raised when a stream transform fails to encode or decode."""


class MissingExtraError(StorageError, ImportError):
    """A storage feature needs an optional extra that is not installed.

    Attributes:
        extra: Name of the ``mountainash-transport`` extra to install.
        feature: The feature that needed it.
    """

    extra: str
    feature: str


class BackendNotImplementedError(StorageError):
    """Raised when a storage provider has no backend implementation yet."""


class ProfileResolutionError(StorageError):
    """A named storage profile could not be materialised from configuration."""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self.reason = reason
        super().__init__(f"Cannot resolve storage profile {name!r}: {reason}")


class ProfileNotFoundError(ProfileResolutionError):
    """The named storage profile is absent from configuration."""

    def __init__(self, name: str, available: list[str]) -> None:
        self.available = available
        super().__init__(
            name,
            f"not found in configuration. Available: {sorted(available) or '(none)'}",
        )
