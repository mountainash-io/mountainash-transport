# storage_facade/facade.py

"""StorageFacade — protocol-checked dispatch to registered storage backends."""

from __future__ import annotations

import io
from typing import BinaryIO

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult, StorageEntry
from mountainash_transport._core.exceptions import UnsupportedOperationError
from mountainash_transport.storage.protocols import (
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageEnumerateProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)
from mountainash_auth_client import AuthProfile
from mountainash_transport.storage.registry import (
    detect_provider_from_path,
    get_storage_backend,
)
from mountainash_transport.storage.path_helpers.suffixes import infer_pipeline as _infer_pipeline
from mountainash_transport._core.transforms import GPG, Gzip, Pipeline, StreamTransform

from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


class _PairedStream(io.RawIOBase):
    """BinaryIO wrapper that closes both a wrapped stream and its source on close().

    Used when a pipeline wraps a backend stream — closing must propagate to
    both so file descriptors are not leaked.
    """

    def __init__(self, wrapped: BinaryIO, source: BinaryIO) -> None:
        self._wrapped = wrapped
        self._source = source

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:  # type: ignore[override]
        chunk = self._wrapped.read(len(b))
        n = len(chunk)
        b[:n] = chunk
        return n

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self._wrapped.read(size)

    def close(self) -> None:  # type: ignore[override]
        try:
            if self._wrapped is not self._source:
                self._wrapped.close()
        finally:
            self._source.close()
            super().close()


class StorageFacade:
    """Unified user-facing API that dispatches to protocol-checked backends.

    Each operation checks that the underlying backend implements the required
    protocol before delegating, raising :class:`UnsupportedOperationError`
    if the backend does not support the operation.
    """

    def __init__(
        self,
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        auth_profile: AuthProfile | None = None,
    ) -> None:
        from mountainash_transport.connections import create_connection

        connection = None
        if storage_profile is not None:
            connection = create_connection(storage_profile, auth_profile)
            connection.connect()

        self._backend = get_storage_backend(
            provider_type, storage_profile,
            connection=connection,
        )

    # ------------------------------------------------------------------
    # Convenience factories
    # ------------------------------------------------------------------

    @classmethod
    def for_local(cls) -> StorageFacade:
        """Return a StorageFacade backed by the local filesystem."""
        return cls(CONST_STORAGE_PROVIDER_TYPE.LOCAL, storage_profile=None)

    @classmethod
    def from_path(
        cls,
        path: str,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        auth_profile: AuthProfile | None = None,
    ) -> StorageFacade:
        """Construct a facade whose provider is inferred from a path's URL scheme.

        Args:
            path: Path string, optionally with a URL scheme.
            profile: Optional storage profile forwarded to the backend.
            auth: Optional direct AuthProfile instance (e.g. TokenAuth, PasswordAuth).
                When provided, overrides any Authorization header set by *profile*.

        Returns:
            A StorageFacade wired to the provider that matches *path*.

        Raises:
            ValueError: If *path*'s scheme is unrecognised or has no backend.
        """
        provider = detect_provider_from_path(path)
        return cls(provider_type=provider, storage_profile=storage_profile, auth_profile=auth_profile)

    # ------------------------------------------------------------------
    # Protocol introspection
    # ------------------------------------------------------------------

    def supports(self, protocol: type) -> bool:
        """Return True if the backend implements *protocol*."""
        return isinstance(self._backend, protocol)

    def _require(self, protocol: type, operation: str) -> None:
        """Raise UnsupportedOperationError if the backend lacks *protocol*."""
        if not isinstance(self._backend, protocol):
            raise UnsupportedOperationError(
                f"{type(self._backend).__name__} does not support '{operation}'"
            )

    @staticmethod
    def _coerce_pipeline(
        pipeline: Pipeline | StreamTransform | None,
    ) -> Pipeline:
        if pipeline is None:
            return Pipeline()
        if isinstance(pipeline, Pipeline):
            return pipeline
        return Pipeline(pipeline)

    def _resolve_pipeline(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None,
        infer: bool,
        gpg: GPG | None,
        gzip: Gzip | None,
    ) -> Pipeline:
        """Resolve the effective pipeline from explicit or inferred sources."""
        if infer and pipeline is not None:
            raise ValueError(
                "Cannot pass both infer=True and an explicit pipeline"
            )
        if infer:
            inferred, _ = _infer_pipeline(path, gpg=gpg, gzip=gzip)
            if inferred is not None:
                return inferred
        return self._coerce_pipeline(pipeline)

    # ------------------------------------------------------------------
    # Read operations (StorageReadProtocol)
    # ------------------------------------------------------------------

    def read(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        infer: bool = False,
        gpg: GPG | None = None,
        gzip: Gzip | None = None,
    ) -> bytes:
        """Read file contents and return as bytes, optionally through *pipeline*.

        When *infer* is True, the path's suffix chain is parsed into a
        pipeline via :func:`infer_pipeline`. Raises ``ValueError`` if both
        *infer* and *pipeline* are provided.
        """
        self._require(StorageReadProtocol, "read")
        effective = self._resolve_pipeline(
            path, pipeline=pipeline, infer=infer, gpg=gpg, gzip=gzip,
        )
        source_stream = self._backend.read_to_stream(path)
        try:
            wrapped_stream = effective.apply_read(source_stream)
            try:
                return wrapped_stream.read()
            finally:
                if wrapped_stream is not source_stream:
                    wrapped_stream.close()
        finally:
            source_stream.close()

    def read_stream(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        infer: bool = False,
        gpg: GPG | None = None,
        gzip: Gzip | None = None,
    ) -> BinaryIO:
        """Read file contents and return as a binary stream, optionally through *pipeline*.

        When *infer* is True, the path's suffix chain is parsed into a
        pipeline via :func:`infer_pipeline`. Raises ``ValueError`` if both
        *infer* and *pipeline* are provided.

        The returned stream should be closed by the caller (context manager
        recommended). Closing propagates to both the pipeline wrapper and the
        underlying backend stream so file descriptors are not leaked.
        """
        self._require(StorageReadProtocol, "read_stream")
        effective = self._resolve_pipeline(
            path, pipeline=pipeline, infer=infer, gpg=gpg, gzip=gzip,
        )
        source_stream = self._backend.read_to_stream(path)
        wrapped_stream = effective.apply_read(source_stream)
        return _PairedStream(wrapped_stream, source_stream)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Write operations (StorageWriteProtocol)
    # ------------------------------------------------------------------

    def write(
        self,
        path: str,
        data: bytes,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
    ) -> None:
        """Write bytes data to a file at *path*, optionally through *pipeline*."""
        self._require(StorageWriteProtocol, "write")
        if pipeline is None:
            self._backend.write_from_bytes(path, data)
            return
        source = io.BytesIO(data)
        encoded = self._coerce_pipeline(pipeline).apply_write(source)
        self._backend.write_from_stream(path, encoded)

    def write_stream(
        self,
        path: str,
        stream: BinaryIO,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
    ) -> None:
        """Write data from a binary stream, optionally through *pipeline*."""
        self._require(StorageWriteProtocol, "write_stream")
        encoded = self._coerce_pipeline(pipeline).apply_write(stream)
        self._backend.write_from_stream(path, encoded)

    # ------------------------------------------------------------------
    # Enumerate operations (StorageEnumerateProtocol)
    # ------------------------------------------------------------------

    def list_objects(
        self,
        prefix: str,
        *,
        delimiter: str | None = "/",
        max_results: int | None = None,
    ) -> EnumerateResult:
        """Bucket-store listing. Requires StorageEnumerateProtocol."""
        self._require(StorageEnumerateProtocol, "list_objects")
        return self._backend.list_objects(prefix, delimiter=delimiter, max_results=max_results)

    # ------------------------------------------------------------------
    # Delete operations (StorageDeleteProtocol)
    # ------------------------------------------------------------------

    def delete(self, path: str) -> None:
        """Delete the file at *path*."""
        self._require(StorageDeleteProtocol, "delete")
        self._backend.delete_file(path)

    # ------------------------------------------------------------------
    # Metadata operations (StorageMetadataProtocol)
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return True if *path* exists on the backend."""
        self._require(StorageMetadataProtocol, "exists")
        return self._backend.path_exists(path)

    def metadata(self, path: str) -> StorageEntry:
        """Return metadata for the resource at *path*."""
        self._require(StorageMetadataProtocol, "metadata")
        return self._backend.get_metadata(path)

    def get_size(self, path: str) -> int | None:
        """Return the size in bytes of the file at *path*, or None if unknown."""
        self._require(StorageMetadataProtocol, "get_size")
        return self._backend.get_size(path)

    # ------------------------------------------------------------------
    # Copy operations (StorageCopyProtocol)
    # ------------------------------------------------------------------

    def copy(self, source: str, destination: str) -> None:
        """Copy file from *source* to *destination* within the same backend."""
        self._require(StorageCopyProtocol, "copy")
        self._backend.copy(source, destination)

    # ------------------------------------------------------------------
    # Directory operations (StorageDirectoryProtocol)
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[StorageEntry]:
        """Filesystem listing. Requires StorageDirectoryProtocol."""
        self._require(StorageDirectoryProtocol, "list_dir")
        return self._backend.list_dir(path)

    def mkdir(self, path: str, parents: bool = True) -> None:
        """Create a directory at *path*, optionally creating parent directories."""
        self._require(StorageDirectoryProtocol, "mkdir")
        self._backend.mkdir(path, parents=parents)

    def rmdir(self, path: str) -> None:
        """Remove the directory at *path*."""
        self._require(StorageDirectoryProtocol, "rmdir")
        self._backend.rmdir(path)
