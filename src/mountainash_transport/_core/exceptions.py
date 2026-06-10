# exceptions.py

"""Custom exception hierarchy for mountainash-transport storage operations."""


class StorageError(Exception):
    """Base exception for all storage-related errors."""


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
    """Raised when authentication with a storage backend fails."""


class TransformError(StorageError):
    """Raised when a stream transform fails to encode or decode."""


class BackendNotImplementedError(StorageError):
    """Raised when a storage provider has no backend implementation yet."""
