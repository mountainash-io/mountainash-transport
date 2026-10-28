# storage_facade/facade.py

"""StorageFacade — protocol-checked dispatch to registered storage backends."""

from __future__ import annotations

import contextlib
import io
import os
import typing as t
from types import TracebackType
from typing import BinaryIO

from mountainash_settings.secrets import ClearableSecretStore

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import EnumerateResult, StorageEntry
from mountainash_transport._core.exceptions import StorageConnectionError, UnsupportedOperationError
from mountainash_transport._core.protocols import ConnectionProtocol
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
from mountainash_transport._core.ranged_io import RangePolicy, RangedReader
from mountainash_transport._core.transforms.util import materialize
from mountainash_transport._core.transforms.pipeline import _ReadStream, _close_if_open
from mountainash_transport.storage.protocols.prtcl_ranged_read import RangedReadProtocol

from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_transport.location import LocationNotAllowed, LocationPolicy, confine_local

_S3_FAMILY = frozenset({
    CONST_STORAGE_PROVIDER_TYPE.S3, CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    CONST_STORAGE_PROVIDER_TYPE.MINIO, CONST_STORAGE_PROVIDER_TYPE.R2,
    CONST_STORAGE_PROVIDER_TYPE.B2,
})


def _has_static_token(auth_profile: t.Any) -> bool:
    """Return True if *auth_profile* carries a non-empty static ACCESS_TOKEN."""
    tok = getattr(auth_profile, "ACCESS_TOKEN", None)
    return bool(tok.get_secret_value()) if tok is not None else False


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
        oauth_provider: t.Any = None,
        token_store: ClearableSecretStore | None = None,
        policy: LocationPolicy | None = None,
    ) -> None:
        from mountainash_transport.connections import create_connection, create_auth_strategy
        from mountainash_auth_client import OAuth2AuthProfile
        self._provider_type = provider_type
        self._storage_profile = storage_profile

        declared = None
        if provider_type == CONST_STORAGE_PROVIDER_TYPE.LOCAL and storage_profile is not None:
            declared = getattr(storage_profile, "ROOT_PATH", None)
            if declared and getattr(storage_profile, "CREATE_PATH", False):
                os.makedirs(declared, exist_ok=True)
        self._policy = (policy or LocationPolicy()).with_declared_root(declared) if declared else policy

        # Profile permission comes only from a caller-supplied profile.
        self._profile_host: str | None = None
        self._profile_any = False
        if storage_profile is not None:
            if provider_type == CONST_STORAGE_PROVIDER_TYPE.SFTP:
                self._profile_host = getattr(storage_profile, "HOST", None)
            elif provider_type in _S3_FAMILY:
                bucket = getattr(storage_profile, "BUCKET", None)
                if bucket:
                    self._profile_host = bucket
                else:
                    self._profile_any = True

        if storage_profile is None and provider_type == CONST_STORAGE_PROVIDER_TYPE.HTTP:
            from mountainash_transport.settings.storage.profiles import HTTPStorageProfile

            storage_profile = HTTPStorageProfile()

        self._closed = False
        self._connection: ConnectionProtocol[t.Any] | None = None
        strategy = None
        try:
            if storage_profile is not None:
                self._connection = create_connection(storage_profile, auth_profile)
                strategy = create_auth_strategy(
                    auth_profile, oauth_provider=oauth_provider, token_store=token_store,
                )
                # Validate managed OAuth before opening the connection.
                if (
                    isinstance(auth_profile, OAuth2AuthProfile)
                    and strategy is None
                    and not _has_static_token(auth_profile)
                ):
                    raise ValueError(
                        "OAuth2 profile has no static ACCESS_TOKEN and no oauth_provider; "
                        "supply oauth_provider + token_store for the managed flow, "
                        "or set a static ACCESS_TOKEN."
                    )
                self._connection.connect()

            backend_kwargs: dict[str, t.Any] = {"connection": self._connection}
            if strategy is not None:
                backend_kwargs["auth_strategy"] = strategy
            self._backend = get_storage_backend(provider_type, storage_profile, **backend_kwargs)
        except BaseException as primary:
            try:
                self.close()
            except BaseException as cleanup:
                primary.add_note(f"Facade cleanup also failed: {cleanup!r}")
                for note in getattr(cleanup, "__notes__", ()):
                    primary.add_note(note)
            raise

    def _check(self, path: str) -> str:
        """Return the path the backend must use, enforcing the location policy."""
        if self._provider_type == CONST_STORAGE_PROVIDER_TYPE.LOCAL:
            return confine_local(path, self._policy)
        return path

    def _ensure_open(self) -> None:
        if self._closed:
            raise StorageConnectionError("StorageFacade is closed")

    def close(self) -> None:
        """Disconnect the owned connection; further I/O is forbidden.

        All returned streams remain caller-owned. Close remote sequential and
        random streams before their facade. Repeated close is a no-op, even
        when the first cleanup attempt failed.
        """
        if self._closed:
            return
        self._closed = True
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.disconnect()

    def __enter__(self) -> t.Self:
        self._ensure_open()
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except BaseException as cleanup:
            if exc_value is None:
                raise
            exc_value.add_note(f"Facade cleanup also failed: {cleanup!r}")
            for note in getattr(cleanup, "__notes__", ()):
                exc_value.add_note(note)

    # ------------------------------------------------------------------
    # Convenience factories
    # ------------------------------------------------------------------

    @classmethod
    def for_local(cls, *, policy: LocationPolicy | None = None) -> StorageFacade:
        """Return a StorageFacade backed by the local filesystem."""
        return cls(CONST_STORAGE_PROVIDER_TYPE.LOCAL, storage_profile=None, policy=policy)

    @classmethod
    def from_path(
        cls,
        path: str,
        storage_profile: StorageProfileProtocol | None = None,
        *,
        auth_profile: AuthProfile | None = None,
        oauth_provider: t.Any = None,
        token_store: ClearableSecretStore | None = None,
        policy: LocationPolicy | None = None,
    ) -> StorageFacade:
        """Construct a facade whose provider is inferred from a path's URL scheme.

        Args:
            path: Path string, optionally with a URL scheme.
            profile: Optional storage profile forwarded to the backend.
            auth: Optional direct AuthProfile instance (e.g. TokenAuth, PasswordAuth).
                When provided, overrides any Authorization header set by *profile*.
            oauth_provider: Optional OAuth2 provider profile for the managed token flow.
            token_store: Raw ClearableSecretStore for managed tokens, distinct from
                the config reader. The caller owns its lifetime.

        Returns:
            A StorageFacade wired to the provider that matches *path*.

        Raises:
            ValueError: If *path*'s scheme is unrecognised or has no backend.
        """
        provider = detect_provider_from_path(path)
        return cls(
            provider_type=provider, storage_profile=storage_profile, auth_profile=auth_profile,
            oauth_provider=oauth_provider, token_store=token_store, policy=policy,
        )

    # ------------------------------------------------------------------
    # Protocol introspection
    # ------------------------------------------------------------------

    def supports(self, protocol: type) -> bool:
        """Return True if the backend implements *protocol*."""
        return isinstance(self._backend, protocol)

    def _require(self, protocol: type, operation: str) -> None:
        """Raise UnsupportedOperationError if the backend lacks *protocol*."""
        self._ensure_open()
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
        with self.read_stream(
            path, pipeline=pipeline, infer=infer, gpg=gpg, gzip=gzip,
        ) as stream:
            return stream.read()

    def read_stream(
        self,
        path: str,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        infer: bool = False,
        gpg: GPG | None = None,
        gzip: Gzip | None = None,
        access: t.Literal["sequential", "random", "buffered"] = "sequential",
        range_policy: RangePolicy | None = None,
    ) -> BinaryIO:
        """Read file contents and return as a binary stream, optionally through *pipeline*.

        When *infer* is True, the path's suffix chain is parsed into a
        pipeline via :func:`infer_pipeline`. Raises ``ValueError`` if both
        *infer* and *pipeline* are provided.

        Errors can occur at two points:

        - **Opening** (this call): backend open failures and transform
          construction failures. On a construction failure the source and any
          already-built transform layers are closed before the original error
          propagates.
        - **Consumption** (``read()`` on the returned stream): lazy transforms
          decode as you read, so e.g. a malformed ``.gz`` opens successfully and
          raises ``gzip.BadGzipFile`` on read. A successful return does not
          certify the payload is valid or fully available. Error timing depends
          on the effective transform/backend: GPG currently buffers internally,
          so its failures surface while opening. Use :meth:`read` to have all
          decoding errors raised within one call.

        The caller owns the returned stream and must keep it open for the whole
        read, ideally with a context manager::

            with facade.read_stream(path, infer=True) as s:
                data = s.read()

        Closing (including on a consumer exception) unwinds every constructed
        transform layer in reverse construction order, then the backend stream.
        All closes are attempted even if one raises; repeated close is a no-op.

        ``access="sequential"`` streams without whole-object buffering; remote
        handles are forward-only. ``"random"`` fetches stored byte ranges and
        rejects transforms. ``"buffered"`` materializes decoded bytes in memory.
        Local sequential/random handles retain native seekability. Random
        reads use call policy, then profile RANGE_* settings, then library defaults.
        See ``docs/read-access-modes.md`` for migration and format tuning.
        """
        self._require(StorageReadProtocol, "read_stream")
        if access not in ("sequential", "random", "buffered"):
            raise ValueError(f"Unknown access mode: {access!r}")
        if range_policy is not None and access != "random":
            raise ValueError("range_policy requires access='random'")
        effective = self._resolve_pipeline(
            path, pipeline=pipeline, infer=infer, gpg=gpg, gzip=gzip,
        )
        path = self._check(path)
        if access == "random":
            if not effective.is_empty():
                raise ValueError("access='random' cannot be combined with transforms")
            if self._provider_type == CONST_STORAGE_PROVIDER_TYPE.LOCAL:
                return self._backend.read_to_stream(path)
            self._require(RangedReadProtocol, "random reads")
            policy = range_policy or RangePolicy.from_profile(getattr(self._backend, "storage_profile", None))
            source = self._backend.open_ranged(path)
            try:
                return t.cast(BinaryIO, RangedReader(source, policy))
            except BaseException:
                if source.on_close is not None:
                    source.on_close()
                raise
        source_stream = self._backend.read_to_stream(path)
        cleanup = contextlib.ExitStack()
        cleanup.callback(_close_if_open, source_stream)
        try:
            wrapped_stream = effective.apply_read(source_stream)
            if wrapped_stream is not source_stream:
                cleanup.callback(_close_if_open, wrapped_stream)
            owned = _ReadStream(wrapped_stream, cleanup)
        except BaseException:
            try:
                cleanup.close()
            except Exception:
                pass
            raise
        if access == "buffered":
            with owned:
                result, _ = materialize(t.cast(BinaryIO, owned))
                return result
        return t.cast(BinaryIO, owned)

    # ------------------------------------------------------------------
    # Write operations (StorageWriteProtocol)
    # ------------------------------------------------------------------

    def write(
        self,
        path: str,
        data: bytes,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        create_parents: bool = True,
    ) -> None:
        """Write bytes, optionally transformed, creating directory parents by default.

        With ``create_parents=False``, Local/SFTP open the destination without
        creating or pre-checking parents; a missing parent raises PathNotFoundError.
        S3 and HTTP ignore this option. This does not make file writes atomic.
        """
        self._require(StorageWriteProtocol, "write")
        path = self._check(path)
        if pipeline is None:
            self._backend.write_from_bytes(path, data, create_parents=create_parents)
            return
        source = io.BytesIO(data)
        encoded = self._coerce_pipeline(pipeline).apply_write(source)
        self._backend.write_from_stream(path, encoded, create_parents=create_parents)

    def write_stream(
        self,
        path: str,
        stream: BinaryIO,
        *,
        pipeline: Pipeline | StreamTransform | None = None,
        create_parents: bool = True,
    ) -> None:
        """Write a stream with the same parent-creation policy as :meth:`write`."""
        self._require(StorageWriteProtocol, "write_stream")
        path = self._check(path)
        encoded = self._coerce_pipeline(pipeline).apply_write(stream)
        self._backend.write_from_stream(path, encoded, create_parents=create_parents)

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
        """Enumerate an exact Local/SFTP path or literal S3 key prefix.

        The default "/" delimiter groups immediate children; None recurses.
        Requires StorageEnumerateProtocol.
        """
        self._require(StorageEnumerateProtocol, "list_objects")
        prefix = self._check(prefix)
        return self._backend.list_objects(prefix, delimiter=delimiter, max_results=max_results)

    # ------------------------------------------------------------------
    # Delete operations (StorageDeleteProtocol)
    # ------------------------------------------------------------------

    def delete(self, path: str) -> None:
        """Delete the file at *path*."""
        self._require(StorageDeleteProtocol, "delete")
        path = self._check(path)
        self._backend.delete_file(path)

    # ------------------------------------------------------------------
    # Metadata operations (StorageMetadataProtocol)
    # ------------------------------------------------------------------

    def exists(self, path: str) -> bool:
        """Return False only for established absence; backend failures raise."""
        self._require(StorageMetadataProtocol, "exists")
        path = self._check(path)
        return self._backend.path_exists(path)

    def metadata(self, path: str) -> StorageEntry:
        """Return metadata for the resource at *path*."""
        self._require(StorageMetadataProtocol, "metadata")
        path = self._check(path)
        return self._backend.get_metadata(path)

    def get_size(self, path: str) -> int | None:
        """Return size or None for present-but-unknown size; missing raises.

        Operational failures raise typed storage errors, never None.
        """
        self._require(StorageMetadataProtocol, "get_size")
        path = self._check(path)
        return self._backend.get_size(path)

    # ------------------------------------------------------------------
    # Copy operations (StorageCopyProtocol)
    # ------------------------------------------------------------------

    def copy(self, source: str, destination: str) -> None:
        """Copy file from *source* to *destination* within the same backend."""
        self._require(StorageCopyProtocol, "copy")
        src = self._check(source)
        dst = self._check(destination)
        if self._provider_type == CONST_STORAGE_PROVIDER_TYPE.LOCAL and os.path.isdir(dst):
            final = self._check(os.path.join(dst, os.path.basename(src)))
            if os.path.isdir(final):
                raise LocationNotAllowed(destination, "copy destination is a directory")
            dst = final
        self._backend.copy(src, dst)

    # ------------------------------------------------------------------
    # Directory operations (StorageDirectoryProtocol)
    # ------------------------------------------------------------------

    def list_dir(self, path: str) -> list[StorageEntry]:
        """Filesystem listing. Requires StorageDirectoryProtocol."""
        self._require(StorageDirectoryProtocol, "list_dir")
        path = self._check(path)
        return self._backend.list_dir(path)

    def mkdir(self, path: str, parents: bool = True) -> None:
        """Create a directory at *path*, optionally creating parent directories."""
        self._require(StorageDirectoryProtocol, "mkdir")
        path = self._check(path)
        self._backend.mkdir(path, parents=parents)

    def rmdir(self, path: str) -> None:
        """Remove the directory at *path*."""
        self._require(StorageDirectoryProtocol, "rmdir")
        path = self._check(path)
        self._backend.rmdir(path)
