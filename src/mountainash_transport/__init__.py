"""mountainash-transport — unified storage and messaging operations across backends.

Public names are resolved lazily (PEP 562) so that stdlib-only submodules such as
``mountainash_transport.location`` can be imported without pulling in heavy dependencies.
"""

from __future__ import annotations

import importlib
import typing as t

from .__version__ import __version__
from ._core.constants import CONST_STORAGE_PROVIDER_TYPE

# Docstring-only subpackage; imported eagerly *before* the ``storage`` factory is
# defined so the factory (not the subpackage) is the final ``storage`` binding.
from . import storage as _storage_pkg  # noqa: F401

if t.TYPE_CHECKING:
    from .storage.facade import StorageFacade


def storage(provider_type: CONST_STORAGE_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            profile=None, *, auth_profile=None) -> "StorageFacade":
    """Convenience factory for creating a StorageFacade."""
    from .storage.facade import StorageFacade

    return StorageFacade(provider_type, profile, auth_profile=auth_profile)


_LAZY: dict[str, tuple[str, str]] = {
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
