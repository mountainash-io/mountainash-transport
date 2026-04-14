"""Tests for S3-family backends: R2, S3Express, and MinIO."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.exceptions import StorageConnectionError
from mountainash_utils_files.storage_protocols import (
    StorageConnectionProtocol,
    StorageCopyProtocol,
    StorageDeleteProtocol,
    StorageDirectoryProtocol,
    StorageListProtocol,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
)
from mountainash_utils_files.storage_registry import get_registered_backends

# Trigger backend registration
import mountainash_utils_files.storage_backends  # noqa: F401
from mountainash_utils_files.storage_backends.r2 import R2StorageBackend
from mountainash_utils_files.storage_backends.s3express import S3ExpressStorageBackend
from mountainash_utils_files.storage_backends.minio import MinIOStorageBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_r2(mock_client: MagicMock | None = None) -> R2StorageBackend:
    backend = R2StorageBackend(auth_params=None)
    backend._client = mock_client or MagicMock()
    return backend


def _make_s3express(mock_client: MagicMock | None = None) -> S3ExpressStorageBackend:
    backend = S3ExpressStorageBackend(auth_params=None)
    backend._client = mock_client or MagicMock()
    return backend


def _make_minio(mock_client: MagicMock | None = None) -> MinIOStorageBackend:
    backend = MinIOStorageBackend(auth_params=None)
    backend._client = mock_client or MagicMock()
    return backend


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_r2_registered(self):
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.R2 in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.R2] is R2StorageBackend

    def test_s3express_registered(self):
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS] is S3ExpressStorageBackend

    def test_minio_registered(self):
        backends = get_registered_backends()
        assert CONST_STORAGE_PROVIDER_TYPE.MINIO in backends
        assert backends[CONST_STORAGE_PROVIDER_TYPE.MINIO] is MinIOStorageBackend


# ---------------------------------------------------------------------------
# Protocol conformance — R2
# ---------------------------------------------------------------------------

class TestR2ProtocolConformance:
    @pytest.fixture()
    def backend(self):
        return _make_r2()

    def test_connection_protocol(self, backend):
        assert isinstance(backend, StorageConnectionProtocol)

    def test_read_protocol(self, backend):
        assert isinstance(backend, StorageReadProtocol)

    def test_write_protocol(self, backend):
        assert isinstance(backend, StorageWriteProtocol)

    def test_list_protocol(self, backend):
        assert isinstance(backend, StorageListProtocol)

    def test_delete_protocol(self, backend):
        assert isinstance(backend, StorageDeleteProtocol)

    def test_metadata_protocol(self, backend):
        assert isinstance(backend, StorageMetadataProtocol)

    def test_copy_protocol(self, backend):
        assert isinstance(backend, StorageCopyProtocol)

    def test_NOT_directory_protocol(self, backend):
        assert not isinstance(backend, StorageDirectoryProtocol)


# ---------------------------------------------------------------------------
# Protocol conformance — S3Express
# ---------------------------------------------------------------------------

class TestS3ExpressProtocolConformance:
    @pytest.fixture()
    def backend(self):
        return _make_s3express()

    def test_connection_protocol(self, backend):
        assert isinstance(backend, StorageConnectionProtocol)

    def test_read_protocol(self, backend):
        assert isinstance(backend, StorageReadProtocol)

    def test_write_protocol(self, backend):
        assert isinstance(backend, StorageWriteProtocol)

    def test_list_protocol(self, backend):
        assert isinstance(backend, StorageListProtocol)

    def test_delete_protocol(self, backend):
        assert isinstance(backend, StorageDeleteProtocol)

    def test_metadata_protocol(self, backend):
        assert isinstance(backend, StorageMetadataProtocol)

    def test_copy_protocol(self, backend):
        assert isinstance(backend, StorageCopyProtocol)

    def test_NOT_directory_protocol(self, backend):
        assert not isinstance(backend, StorageDirectoryProtocol)


# ---------------------------------------------------------------------------
# Protocol conformance — MinIO
# ---------------------------------------------------------------------------

class TestMinIOProtocolConformance:
    @pytest.fixture()
    def backend(self):
        return _make_minio()

    def test_connection_protocol(self, backend):
        assert isinstance(backend, StorageConnectionProtocol)

    def test_read_protocol(self, backend):
        assert isinstance(backend, StorageReadProtocol)

    def test_write_protocol(self, backend):
        assert isinstance(backend, StorageWriteProtocol)

    def test_list_protocol(self, backend):
        assert isinstance(backend, StorageListProtocol)

    def test_delete_protocol(self, backend):
        assert isinstance(backend, StorageDeleteProtocol)

    def test_metadata_protocol(self, backend):
        assert isinstance(backend, StorageMetadataProtocol)

    def test_copy_protocol(self, backend):
        assert isinstance(backend, StorageCopyProtocol)

    def test_NOT_directory_protocol(self, backend):
        assert not isinstance(backend, StorageDirectoryProtocol)


# ---------------------------------------------------------------------------
# R2 Connection
# ---------------------------------------------------------------------------

class TestR2Connection:
    def test_connect_builds_r2_endpoint_from_account_id(self):
        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = "secret"
        mock_settings.ACCESS_KEY_ID = "access"
        mock_settings.ACCOUNT_ID = "abc123"

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = R2StorageBackend(auth_params=mock_auth)
        assert not backend.is_connected()

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url="https://abc123.r2.cloudflarestorage.com",
            aws_access_key_id="access",
            aws_secret_access_key="secret",
            region_name="auto",
        )
        assert backend.is_connected()

    def test_connect_with_secret_str(self):
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "mysecret"

        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = mock_secret
        mock_settings.ACCESS_KEY_ID = "key"
        mock_settings.ACCOUNT_ID = "myaccount"

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = R2StorageBackend(auth_params=mock_auth)
        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        _, kwargs = mock_boto3_client.call_args
        assert kwargs["aws_secret_access_key"] == "mysecret"

    def test_connect_raises_storage_connection_error_on_failure(self):
        mock_auth = MagicMock()
        mock_auth.settings = MagicMock(
            SECRET_ACCESS_KEY="s",
            ACCESS_KEY_ID="a",
            ACCOUNT_ID="acct",
        )
        backend = R2StorageBackend(auth_params=mock_auth)
        with patch("boto3.client", side_effect=RuntimeError("boom")):
            with pytest.raises(StorageConnectionError, match="boom"):
                backend.connect()

    def test_disconnect_clears_client(self):
        backend = _make_r2()
        assert backend.is_connected()
        backend.disconnect()
        assert not backend.is_connected()

    def test_is_connected_false_initially(self):
        backend = R2StorageBackend(auth_params=None)
        assert not backend.is_connected()


# ---------------------------------------------------------------------------
# S3Express Connection
# ---------------------------------------------------------------------------

class TestS3ExpressConnection:
    def test_connect_creates_boto3_client(self):
        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = "secret"
        mock_settings.ENDPOINT_URL = None
        mock_settings.ACCESS_KEY_ID = "access"
        mock_settings.REGION = "us-east-1"

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = S3ExpressStorageBackend(auth_params=mock_auth)
        assert not backend.is_connected()

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url=None,
            aws_access_key_id="access",
            aws_secret_access_key="secret",
            region_name="us-east-1",
        )
        assert backend.is_connected()

    def test_connect_with_secret_str(self):
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "mysecret"

        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = mock_secret
        mock_settings.ENDPOINT_URL = None
        mock_settings.ACCESS_KEY_ID = "key"
        mock_settings.REGION = "us-east-1"

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = S3ExpressStorageBackend(auth_params=mock_auth)
        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        _, kwargs = mock_boto3_client.call_args
        assert kwargs["aws_secret_access_key"] == "mysecret"

    def test_connect_raises_storage_connection_error_on_failure(self):
        mock_auth = MagicMock()
        mock_auth.settings = MagicMock(
            SECRET_ACCESS_KEY="s",
            ENDPOINT_URL=None,
            ACCESS_KEY_ID="a",
            REGION="us-east-1",
        )
        backend = S3ExpressStorageBackend(auth_params=mock_auth)
        with patch("boto3.client", side_effect=RuntimeError("boom")):
            with pytest.raises(StorageConnectionError, match="boom"):
                backend.connect()

    def test_disconnect_clears_client(self):
        backend = _make_s3express()
        assert backend.is_connected()
        backend.disconnect()
        assert not backend.is_connected()

    def test_is_connected_false_initially(self):
        backend = S3ExpressStorageBackend(auth_params=None)
        assert not backend.is_connected()


# ---------------------------------------------------------------------------
# MinIO Connection
# ---------------------------------------------------------------------------

class TestMinIOConnection:
    def test_connect_creates_boto3_client_with_custom_endpoint(self):
        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = "secret"
        mock_settings.ENDPOINT_URL = "http://localhost:9000"
        mock_settings.ACCESS_KEY_ID = "minioadmin"
        mock_settings.REGION = "us-east-1"
        mock_settings.USE_SSL = False

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = MinIOStorageBackend(auth_params=mock_auth)
        assert not backend.is_connected()

        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        mock_boto3_client.assert_called_once_with(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="secret",
            region_name="us-east-1",
            use_ssl=False,
        )
        assert backend.is_connected()

    def test_connect_with_secret_str(self):
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "mysecret"

        mock_settings = MagicMock()
        mock_settings.SECRET_ACCESS_KEY = mock_secret
        mock_settings.ENDPOINT_URL = "http://minio:9000"
        mock_settings.ACCESS_KEY_ID = "key"
        mock_settings.REGION = "us-east-1"
        mock_settings.USE_SSL = False

        mock_auth = MagicMock()
        mock_auth.settings = mock_settings

        backend = MinIOStorageBackend(auth_params=mock_auth)
        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.return_value = MagicMock()
            backend.connect()

        _, kwargs = mock_boto3_client.call_args
        assert kwargs["aws_secret_access_key"] == "mysecret"

    def test_connect_raises_storage_connection_error_on_failure(self):
        mock_auth = MagicMock()
        mock_auth.settings = MagicMock(
            SECRET_ACCESS_KEY="s",
            ENDPOINT_URL="http://localhost:9000",
            ACCESS_KEY_ID="a",
            REGION="us-east-1",
            USE_SSL=False,
        )
        backend = MinIOStorageBackend(auth_params=mock_auth)
        with patch("boto3.client", side_effect=RuntimeError("boom")):
            with pytest.raises(StorageConnectionError, match="boom"):
                backend.connect()

    def test_disconnect_clears_client(self):
        backend = _make_minio()
        assert backend.is_connected()
        backend.disconnect()
        assert not backend.is_connected()

    def test_is_connected_false_initially(self):
        backend = MinIOStorageBackend(auth_params=None)
        assert not backend.is_connected()
