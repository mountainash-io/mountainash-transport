# tests/test_constants_and_exceptions.py

import pytest
from enum import StrEnum


class TestConstStorageProviderType:
    """Tests for CONST_STORAGE_PROVIDER_TYPE enum."""

    def test_is_str_enum(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        assert issubclass(CONST_STORAGE_PROVIDER_TYPE, StrEnum)

    def test_has_all_required_members(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        expected = {"LOCAL", "S3", "S3EXPRESS", "R2", "MINIO", "GCS", "AZURE_BLOB", "SFTP", "SSH", "B2"}
        actual = {member.name for member in CONST_STORAGE_PROVIDER_TYPE}
        assert expected.issubset(actual), f"Missing members: {expected - actual}"

    def test_member_values_are_lowercase_strings(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        for member in CONST_STORAGE_PROVIDER_TYPE:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower(), f"{member.name} value '{member.value}' is not lowercase"

    def test_local_value(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        assert CONST_STORAGE_PROVIDER_TYPE.LOCAL == "local"

    def test_s3_value(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        assert CONST_STORAGE_PROVIDER_TYPE.S3 == "s3"

    def test_members_are_strings(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
        assert CONST_STORAGE_PROVIDER_TYPE.LOCAL == "local"
        assert isinstance(CONST_STORAGE_PROVIDER_TYPE.LOCAL, str)


class TestRemovedEnums:
    """Verify that old enums have been removed from constants."""

    def test_const_storagesystem_removed(self):
        import mountainash_transport._core.constants as constants
        assert not hasattr(constants, "CONST_STORAGESYSTEM"), (
            "CONST_STORAGESYSTEM should have been removed from constants.py"
        )

    def test_const_storagesystem_prefix_removed(self):
        import mountainash_transport._core.constants as constants
        assert not hasattr(constants, "CONST_STORAGESYSTEM_PREFIX"), (
            "CONST_STORAGESYSTEM_PREFIX should have been removed from constants.py"
        )

    def test_const_datafileformat_removed(self):
        import mountainash_transport._core.constants as constants
        assert not hasattr(constants, "CONST_DATAFILEFORMAT"), (
            "CONST_DATAFILEFORMAT should have been removed from constants.py"
        )


class TestExceptionHierarchy:
    """Tests for custom exception hierarchy."""

    def test_storage_error_inherits_exception(self):
        from mountainash_transport._core.exceptions import StorageError
        assert issubclass(StorageError, Exception)

    def test_unsupported_operation_error_inherits_storage_error(self):
        from mountainash_transport._core.exceptions import UnsupportedOperationError, StorageError
        assert issubclass(UnsupportedOperationError, StorageError)

    def test_storage_connection_error_inherits_storage_error(self):
        from mountainash_transport._core.exceptions import StorageConnectionError, StorageError
        assert issubclass(StorageConnectionError, StorageError)

    def test_path_not_found_error_inherits_storage_error(self):
        from mountainash_transport._core.exceptions import PathNotFoundError, StorageError
        assert issubclass(PathNotFoundError, StorageError)

    def test_authentication_error_inherits_storage_error(self):
        from mountainash_transport._core.exceptions import AuthenticationError, StorageError
        assert issubclass(AuthenticationError, StorageError)

    def test_all_exceptions_inherit_storage_error(self):
        from mountainash_transport._core.exceptions import (
            StorageError,
            UnsupportedOperationError,
            StorageConnectionError,
            PathNotFoundError,
            AuthenticationError,
        )
        for exc_class in (UnsupportedOperationError, StorageConnectionError, PathNotFoundError, AuthenticationError):
            assert issubclass(exc_class, StorageError), f"{exc_class.__name__} does not inherit from StorageError"


class TestExceptionMessages:
    """Tests that exception messages propagate correctly."""

    def test_storage_error_message(self):
        from mountainash_transport._core.exceptions import StorageError
        msg = "base storage error"
        exc = StorageError(msg)
        assert str(exc) == msg

    def test_unsupported_operation_error_message(self):
        from mountainash_transport._core.exceptions import UnsupportedOperationError
        msg = "operation not supported"
        exc = UnsupportedOperationError(msg)
        assert str(exc) == msg

    def test_storage_connection_error_message(self):
        from mountainash_transport._core.exceptions import StorageConnectionError
        msg = "connection failed"
        exc = StorageConnectionError(msg)
        assert str(exc) == msg

    def test_path_not_found_error_message(self):
        from mountainash_transport._core.exceptions import PathNotFoundError
        msg = "/some/path/not/found"
        exc = PathNotFoundError(msg)
        assert str(exc) == msg

    def test_authentication_error_message(self):
        from mountainash_transport._core.exceptions import AuthenticationError
        msg = "invalid credentials"
        exc = AuthenticationError(msg)
        assert str(exc) == msg


class TestStorageConnectionErrorNotBuiltin:
    """Verify StorageConnectionError doesn't shadow the builtin ConnectionError."""

    def test_does_not_inherit_builtin_connection_error(self):
        from mountainash_transport._core.exceptions import StorageConnectionError
        assert not issubclass(StorageConnectionError, ConnectionError), (
            "StorageConnectionError must not shadow the builtin ConnectionError"
        )

    def test_builtin_connection_error_still_accessible(self):
        # Ensure importing our module doesn't shadow the builtin
        from mountainash_transport._core.exceptions import StorageConnectionError  # noqa: F401
        assert ConnectionError is not StorageConnectionError


class TestExceptionsRaisable:
    """Verify exceptions can be raised and caught."""

    def test_raise_and_catch_storage_error(self):
        from mountainash_transport._core.exceptions import StorageError
        with pytest.raises(StorageError):
            raise StorageError("test")

    def test_catch_subclass_as_storage_error(self):
        from mountainash_transport._core.exceptions import PathNotFoundError, StorageError
        with pytest.raises(StorageError):
            raise PathNotFoundError("not found")

    def test_catch_as_exception(self):
        from mountainash_transport._core.exceptions import AuthenticationError
        with pytest.raises(Exception):
            raise AuthenticationError("auth failed")


def test_transform_error_inherits_storage_error():
    from mountainash_transport._core.exceptions import StorageError, TransformError
    assert issubclass(TransformError, StorageError)
    err = TransformError("boom")
    assert isinstance(err, StorageError)
    assert str(err) == "boom"


def test_backend_not_implemented_error_is_storage_error():
    from mountainash_transport._core.exceptions import BackendNotImplementedError, StorageError
    exc = BackendNotImplementedError("GCS backend not yet implemented")
    assert isinstance(exc, StorageError)
    assert "GCS" in str(exc)
