"""Verify the new public API exports are correct."""
import pytest


class TestPublicAPI:

    def test_facade_importable(self):
        from mountainash_transport import StorageFacade, copy_between
        assert callable(StorageFacade)
        assert callable(copy_between)

    def test_protocols_importable(self):
        from mountainash_transport import (
            StorageReadProtocol, StorageWriteProtocol, StorageEnumerateProtocol,
            StorageDeleteProtocol, StorageMetadataProtocol, StorageCopyProtocol,
            StorageDirectoryProtocol, ConnectionProtocol, TransportConnectionError,
        )

    def test_dataclasses_importable(self):
        from mountainash_transport import StorageEntry, EntryType, EnumerateResult
        assert EntryType.FILE == "file"

    def test_registry_importable(self):
        from mountainash_transport import get_storage_backend, detect_provider_from_path

    def test_constants_importable(self):
        from mountainash_transport import CONST_STORAGE_PROVIDER_TYPE

    def test_exceptions_importable(self):
        from mountainash_transport import (
            StorageError, UnsupportedOperationError,
            PathNotFoundError, AuthenticationError, MissingExtraError,
        )

    def test_storage_path_importable(self):
        from mountainash_transport import StoragePath
        assert callable(StoragePath.identify_scheme)

    def test_storage_subpackage_import_forms(self):
        """The root's `storage` attribute is the subpackage, so dotted imports work (#46)."""
        import importlib

        import mountainash_transport
        import mountainash_transport.storage.backends as backends

        assert backends is importlib.import_module("mountainash_transport.storage.backends")
        from mountainash_transport import storage
        assert storage is importlib.import_module("mountainash_transport.storage")
        assert "storage" not in mountainash_transport.__all__

    def test_transform_exports_are_top_level(self):
        """Pipeline, Gzip, GPG, StreamTransform, TransformError import from package root."""
        from mountainash_transport import (
            GPG,
            Gzip,
            Pipeline,
            StreamTransform,
            TransformError,
        )
        # Construction smoke checks
        assert isinstance(Pipeline(Gzip()).apply_read, type(Pipeline().apply_read))
        assert issubclass(TransformError, Exception)
        assert isinstance(Gzip(), StreamTransform)

    def test_materialize_is_public(self):
        """`materialize` imports from the root and the transforms package (#56)."""
        import io

        import mountainash_transport
        from mountainash_transport import materialize
        from mountainash_transport._core.transforms import materialize as from_transforms

        assert materialize is from_transforms
        assert "materialize" in mountainash_transport.__all__
        buffer, length = materialize(io.BytesIO(b"abc"))
        assert (length, buffer.read()) == (3, b"abc")


class TestHttpTransportPublicApi:

    def test_engine_importable(self):
        from mountainash_transport import HttpRequestEngine
        assert callable(HttpRequestEngine)

    def test_policy_types_importable(self):
        from mountainash_transport import (
            RequestPolicy,
            RetryPolicy,
            TimeoutPolicy,
            RedirectPolicy,
        )
        assert callable(RetryPolicy)
        assert callable(TimeoutPolicy)
        assert callable(RedirectPolicy)
        assert callable(RequestPolicy)

    def test_response_types_importable(self):
        from mountainash_transport import HttpResponse, HttpStreamResponse
        assert callable(HttpResponse)
        assert callable(HttpStreamResponse)

    def test_method_constants_importable(self):
        from mountainash_transport import SAFE_METHODS, IDEMPOTENT_METHODS
        assert "GET" in SAFE_METHODS
        assert "PUT" in IDEMPOTENT_METHODS
        assert "POST" not in IDEMPOTENT_METHODS

    def test_error_base_classes_importable(self):
        from mountainash_transport import (
            HttpTransportError,
            HttpResponseError,
            HttpClientError,
            HttpServerError,
        )
        assert issubclass(HttpResponseError, HttpTransportError)
        assert issubclass(HttpClientError, HttpResponseError)
        assert issubclass(HttpServerError, HttpResponseError)

    def test_client_error_subclasses_importable(self):
        from mountainash_transport import (
            HttpNotFoundError,
            HttpAuthenticationError,
            HttpForbiddenError,
            HttpRateLimitError,
            HttpConflictError,
        )
        from mountainash_transport import HttpClientError
        for cls in (
            HttpNotFoundError,
            HttpAuthenticationError,
            HttpForbiddenError,
            HttpRateLimitError,
            HttpConflictError,
        ):
            assert issubclass(cls, HttpClientError)

    def test_server_error_subclasses_importable(self):
        from mountainash_transport import (
            HttpBadGatewayError,
            HttpServiceUnavailableError,
            HttpGatewayTimeoutError,
        )
        from mountainash_transport import HttpServerError
        for cls in (HttpBadGatewayError, HttpServiceUnavailableError, HttpGatewayTimeoutError):
            assert issubclass(cls, HttpServerError)

    def test_transport_error_subclasses_importable(self):
        from mountainash_transport import (
            HttpConnectionError,
            HttpTimeoutError,
            HttpRedirectError,
            HttpProtocolError,
            HttpRequestError,
            HttpDecodeError,
        )
        from mountainash_transport import HttpTransportError
        for cls in (
            HttpConnectionError,
            HttpTimeoutError,
            HttpRedirectError,
            HttpProtocolError,
            HttpRequestError,
            HttpDecodeError,
        ):
            assert issubclass(cls, HttpTransportError)

    def test_all_http_names_in_dunder_all(self):
        import mountainash_transport
        http_names = [
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
        for name in http_names:
            assert name in mountainash_transport.__all__, f"{name!r} missing from __all__"


def test_resolver_public_api():
    import mountainash_transport as mt

    assert callable(mt.resolve_storage)
    for name in ("StorageProfilesSettings", "StorageProfileBlock", "AuthBlock",
                 "ProfileResolutionError", "ProfileNotFoundError"):
        assert hasattr(mt, name), name


def test_legacy_settings_surface_removed():
    import mountainash_transport.settings as s

    assert not hasattr(s, "StorageAuthTemplates")
    assert not hasattr(s, "StorageAuthError")
    assert not hasattr(s, "load_storage")
