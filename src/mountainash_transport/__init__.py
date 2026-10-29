"""mountainash-transport — unified storage and messaging operations across backends.

Public names are resolved lazily (PEP 562) so that stdlib-only submodules such as
``mountainash_transport.location`` can be imported without pulling in heavy dependencies.
"""

from __future__ import annotations

import importlib
import typing as t

from .__version__ import __version__
from ._core.constants import CONST_STORAGE_PROVIDER_TYPE
from .location import POLICY_UNSET, PolicyOverride

# Docstring-only subpackage; imported eagerly *before* the ``storage`` factory is
# defined so the factory (not the subpackage) is the final ``storage`` binding.
from . import storage as _storage_pkg  # noqa: F401

if t.TYPE_CHECKING:
    # Static view of the lazy exports below; runtime stays lazy (PEP 562).
    from .storage.facade import (
        StorageFacade as StorageFacade,
        copy_between as copy_between,
    )
    from ._core.ranged_io import RangePolicy as RangePolicy
    from ._core.exceptions import (
        RangeNotSupportedError as RangeNotSupportedError,
        ObjectChangedError as ObjectChangedError,
        StorageError as StorageError,
        UnsupportedOperationError as UnsupportedOperationError,
        StorageConnectionError as StorageConnectionError,
        PathNotFoundError as PathNotFoundError,
        AuthenticationError as AuthenticationError,
        PermissionDeniedError as PermissionDeniedError,
        TransformError as TransformError,
        BackendNotImplementedError as BackendNotImplementedError,
        MissingExtraError as MissingExtraError,
        ProfileResolutionError as ProfileResolutionError,
        ProfileNotFoundError as ProfileNotFoundError,
    )
    from .storage.protocols.prtcl_ranged_read import RangedReadProtocol as RangedReadProtocol
    from .storage.registry import (
        get_storage_backend as get_storage_backend,
        detect_provider_from_path as detect_provider_from_path,
    )
    from .storage.protocols import (
        StorageReadProtocol as StorageReadProtocol,
        StorageWriteProtocol as StorageWriteProtocol,
        StorageEnumerateProtocol as StorageEnumerateProtocol,
        StorageDeleteProtocol as StorageDeleteProtocol,
        StorageMetadataProtocol as StorageMetadataProtocol,
        StorageCopyProtocol as StorageCopyProtocol,
        StorageDirectoryProtocol as StorageDirectoryProtocol,
    )
    from ._core.protocols import ConnectionProtocol as ConnectionProtocol
    from .settings.profile_protocol import (
        ProfileProtocol as ProfileProtocol,
        StorageProfileProtocol as StorageProfileProtocol,
    )
    from .settings import (
        AuthBlock as AuthBlock,
        StorageProfileBlock as StorageProfileBlock,
        StorageProfilesSettings as StorageProfilesSettings,
        resolve_storage as resolve_storage,
    )
    from .connections.errors import TransportConnectionError as TransportConnectionError
    from .connections import (
        SSHConnection as SSHConnection,
        SFTPConnection as SFTPConnection,
        TunnelledConnection as TunnelledConnection,
        create_connection as create_connection,
        create_tunnelled_connection as create_tunnelled_connection,
    )
    from ._core.dataclasses.storage_entry import (
        EntryType as EntryType,
        EnumerateResult as EnumerateResult,
        StorageEntry as StorageEntry,
    )
    from ._core.transforms import (
        Pipeline as Pipeline,
        StreamTransform as StreamTransform,
        Gzip as Gzip,
        GPG as GPG,
    )
    from ._core.http import (
        HttpRequestEngine as HttpRequestEngine,
        RequestPolicy as RequestPolicy,
        RetryPolicy as RetryPolicy,
        TimeoutPolicy as TimeoutPolicy,
        RedirectPolicy as RedirectPolicy,
        HttpResponse as HttpResponse,
        HttpStreamResponse as HttpStreamResponse,
        SAFE_METHODS as SAFE_METHODS,
        IDEMPOTENT_METHODS as IDEMPOTENT_METHODS,
        HttpTransportError as HttpTransportError,
        HttpResponseError as HttpResponseError,
        HttpClientError as HttpClientError,
        HttpServerError as HttpServerError,
        HttpNotFoundError as HttpNotFoundError,
        HttpAuthenticationError as HttpAuthenticationError,
        HttpForbiddenError as HttpForbiddenError,
        HttpRateLimitError as HttpRateLimitError,
        HttpConflictError as HttpConflictError,
        HttpBadGatewayError as HttpBadGatewayError,
        HttpServiceUnavailableError as HttpServiceUnavailableError,
        HttpGatewayTimeoutError as HttpGatewayTimeoutError,
        HttpConnectionError as HttpConnectionError,
        HttpTimeoutError as HttpTimeoutError,
        HttpRedirectError as HttpRedirectError,
        HttpProtocolError as HttpProtocolError,
        HttpRequestError as HttpRequestError,
        HttpDecodeError as HttpDecodeError,
    )
    from .storage.path_helpers import (
        StoragePath as StoragePath,
        infer_pipeline as infer_pipeline,
    )


def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            profile=None, *, auth_profile=None, policy: PolicyOverride = POLICY_UNSET) -> "StorageFacade":
    """Convenience factory for creating a StorageFacade."""
    from .storage.facade import StorageFacade

    return StorageFacade(provider_type, profile, auth_profile=auth_profile, policy=policy)


_LAZY: dict[str, tuple[str, str]] = {
    'NativeReadAccess': ('.native_read', 'NativeReadAccess'),
    'resolve_native_read': ('.native_read', 'resolve_native_read'),
    'StorageFacade': ('.storage.facade', 'StorageFacade'),
    'copy_between': ('.storage.facade', 'copy_between'),
    'RangePolicy': ('._core.ranged_io', 'RangePolicy'),
    'RangeNotSupportedError': ('._core.exceptions', 'RangeNotSupportedError'),
    'ObjectChangedError': ('._core.exceptions', 'ObjectChangedError'),
    'RangedReadProtocol': ('.storage.protocols.prtcl_ranged_read', 'RangedReadProtocol'),
    'get_storage_backend': ('.storage.registry', 'get_storage_backend'),
    'detect_provider_from_path': ('.storage.registry', 'detect_provider_from_path'),
    'StorageReadProtocol': ('.storage.protocols', 'StorageReadProtocol'),
    'StorageWriteProtocol': ('.storage.protocols', 'StorageWriteProtocol'),
    'StorageEnumerateProtocol': ('.storage.protocols', 'StorageEnumerateProtocol'),
    'StorageDeleteProtocol': ('.storage.protocols', 'StorageDeleteProtocol'),
    'StorageMetadataProtocol': ('.storage.protocols', 'StorageMetadataProtocol'),
    'StorageCopyProtocol': ('.storage.protocols', 'StorageCopyProtocol'),
    'StorageDirectoryProtocol': ('.storage.protocols', 'StorageDirectoryProtocol'),
    'ConnectionProtocol': ('._core.protocols', 'ConnectionProtocol'),
    'ProfileProtocol': ('.settings.profile_protocol', 'ProfileProtocol'),
    'StorageProfileProtocol': ('.settings.profile_protocol', 'StorageProfileProtocol'),
    'AuthBlock': ('.settings', 'AuthBlock'),
    'StorageProfileBlock': ('.settings', 'StorageProfileBlock'),
    'StorageProfilesSettings': ('.settings', 'StorageProfilesSettings'),
    'resolve_storage': ('.settings', 'resolve_storage'),
    'TransportConnectionError': ('.connections.errors', 'TransportConnectionError'),
    'SSHConnection': ('.connections', 'SSHConnection'),
    'SFTPConnection': ('.connections', 'SFTPConnection'),
    'TunnelledConnection': ('.connections', 'TunnelledConnection'),
    'create_connection': ('.connections', 'create_connection'),
    'create_tunnelled_connection': ('.connections', 'create_tunnelled_connection'),
    'EntryType': ('._core.dataclasses.storage_entry', 'EntryType'),
    'EnumerateResult': ('._core.dataclasses.storage_entry', 'EnumerateResult'),
    'StorageEntry': ('._core.dataclasses.storage_entry', 'StorageEntry'),
    'StorageError': ('._core.exceptions', 'StorageError'),
    'UnsupportedOperationError': ('._core.exceptions', 'UnsupportedOperationError'),
    'StorageConnectionError': ('._core.exceptions', 'StorageConnectionError'),
    'PathNotFoundError': ('._core.exceptions', 'PathNotFoundError'),
    'AuthenticationError': ('._core.exceptions', 'AuthenticationError'),
    'PermissionDeniedError': ('._core.exceptions', 'PermissionDeniedError'),
    'TransformError': ('._core.exceptions', 'TransformError'),
    'BackendNotImplementedError': ('._core.exceptions', 'BackendNotImplementedError'),
    'MissingExtraError': ('._core.exceptions', 'MissingExtraError'),
    'ProfileResolutionError': ('._core.exceptions', 'ProfileResolutionError'),
    'ProfileNotFoundError': ('._core.exceptions', 'ProfileNotFoundError'),
    'Pipeline': ('._core.transforms', 'Pipeline'),
    'StreamTransform': ('._core.transforms', 'StreamTransform'),
    'Gzip': ('._core.transforms', 'Gzip'),
    'GPG': ('._core.transforms', 'GPG'),
    'HttpRequestEngine': ('._core.http', 'HttpRequestEngine'),
    'RequestPolicy': ('._core.http', 'RequestPolicy'),
    'RetryPolicy': ('._core.http', 'RetryPolicy'),
    'TimeoutPolicy': ('._core.http', 'TimeoutPolicy'),
    'RedirectPolicy': ('._core.http', 'RedirectPolicy'),
    'HttpResponse': ('._core.http', 'HttpResponse'),
    'HttpStreamResponse': ('._core.http', 'HttpStreamResponse'),
    'SAFE_METHODS': ('._core.http', 'SAFE_METHODS'),
    'IDEMPOTENT_METHODS': ('._core.http', 'IDEMPOTENT_METHODS'),
    'HttpTransportError': ('._core.http', 'HttpTransportError'),
    'HttpResponseError': ('._core.http', 'HttpResponseError'),
    'HttpClientError': ('._core.http', 'HttpClientError'),
    'HttpServerError': ('._core.http', 'HttpServerError'),
    'HttpNotFoundError': ('._core.http', 'HttpNotFoundError'),
    'HttpAuthenticationError': ('._core.http', 'HttpAuthenticationError'),
    'HttpForbiddenError': ('._core.http', 'HttpForbiddenError'),
    'HttpRateLimitError': ('._core.http', 'HttpRateLimitError'),
    'HttpConflictError': ('._core.http', 'HttpConflictError'),
    'HttpBadGatewayError': ('._core.http', 'HttpBadGatewayError'),
    'HttpServiceUnavailableError': ('._core.http', 'HttpServiceUnavailableError'),
    'HttpGatewayTimeoutError': ('._core.http', 'HttpGatewayTimeoutError'),
    'HttpConnectionError': ('._core.http', 'HttpConnectionError'),
    'HttpTimeoutError': ('._core.http', 'HttpTimeoutError'),
    'HttpRedirectError': ('._core.http', 'HttpRedirectError'),
    'HttpProtocolError': ('._core.http', 'HttpProtocolError'),
    'HttpRequestError': ('._core.http', 'HttpRequestError'),
    'HttpDecodeError': ('._core.http', 'HttpDecodeError'),
    'StoragePath': ('.storage.path_helpers', 'StoragePath'),
    'infer_pipeline': ('.storage.path_helpers', 'infer_pipeline'),
}


def __getattr__(name: str) -> t.Any:
    try:
        module, attr = _LAZY[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(module, __package__), attr)
    globals()[name] = value
    return value


__all__ = [
    "RangePolicy", "RangeNotSupportedError", "ObjectChangedError", "RangedReadProtocol",
    "__version__",
    "StorageFacade", "copy_between", "storage",
    "POLICY_UNSET", "PolicyOverride", "NativeReadAccess", "resolve_native_read",
    "get_storage_backend", "detect_provider_from_path",
    "ConnectionProtocol", "TransportConnectionError",
    "SSHConnection", "SFTPConnection", "TunnelledConnection",
    "create_connection", "create_tunnelled_connection",
    "StorageReadProtocol", "StorageWriteProtocol",
    "StorageEnumerateProtocol", "StorageDeleteProtocol", "StorageMetadataProtocol",
    "StorageCopyProtocol", "StorageDirectoryProtocol",
    "ProfileProtocol", "StorageProfileProtocol",
    "resolve_storage", "StorageProfilesSettings", "StorageProfileBlock", "AuthBlock",
    "CONST_STORAGE_PROVIDER_TYPE", "StorageEntry", "EntryType", "EnumerateResult",
    "StorageError", "UnsupportedOperationError", "StorageConnectionError",
    "PathNotFoundError", "AuthenticationError", "TransformError", "BackendNotImplementedError",
    "MissingExtraError",
    "PermissionDeniedError",
    "ProfileResolutionError", "ProfileNotFoundError",
    "StoragePath", "infer_pipeline",
    "Pipeline", "StreamTransform", "Gzip", "GPG",
    # HTTP transport foundation
    "HttpRequestEngine",
    "RequestPolicy", "RetryPolicy", "TimeoutPolicy", "RedirectPolicy",
    "HttpResponse", "HttpStreamResponse",
    "SAFE_METHODS", "IDEMPOTENT_METHODS",
    "HttpTransportError", "HttpResponseError",
    "HttpClientError", "HttpServerError",
    "HttpNotFoundError", "HttpAuthenticationError", "HttpForbiddenError",
    "HttpRateLimitError", "HttpConflictError",
    "HttpBadGatewayError", "HttpServiceUnavailableError", "HttpGatewayTimeoutError",
    "HttpConnectionError", "HttpTimeoutError",
    "HttpRedirectError", "HttpProtocolError", "HttpRequestError", "HttpDecodeError",
]
