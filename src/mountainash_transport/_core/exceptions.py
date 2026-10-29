# exceptions.py

"""Custom exception hierarchy for mountainash-transport storage operations."""


class StorageError(Exception):
    """Base exception for all storage-related errors."""


class RangeNotSupportedError(StorageError):
    """The resource cannot provide byte-range reads."""


class ObjectChangedError(StorageError):
    """A pinned object changed during ranged reading."""


class UnsupportedOperationError(StorageError):
    """Raised when a storage backend does not support a requested operation."""


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
