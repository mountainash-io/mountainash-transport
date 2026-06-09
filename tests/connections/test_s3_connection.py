"""S3Connection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.auth.strategies import IAMCredentialStrategy, NoAuthStrategy
from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.s3 import S3Connection


class FakeS3Profile:
    def to_handler_kwargs(self) -> dict:
        return {"service_name": "s3", "region_name": "us-east-1"}

    def get_connection_url(self) -> str:
        return "https://s3.us-east-1.amazonaws.com"


class TestS3ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        assert isinstance(conn, ConnectionProtocol)


class TestS3ConnectionLifecycle:
    @patch("boto3.client")
    def test_connect_creates_client(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        result = conn.connect()
        mock_client_fn.assert_called_once()
        assert mock_client_fn.call_args[0][0] == "s3"
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("boto3.client")
    def test_connect_with_iam_credentials(self, mock_client_fn):
        strategy = IAMCredentialStrategy(
            access_key_id="AKIA123", secret_access_key="secret"
        )
        conn = S3Connection(FakeS3Profile(), strategy)
        conn.connect()
        call_kwargs = mock_client_fn.call_args[1]
        assert call_kwargs["aws_access_key_id"] == "AKIA123"
        assert call_kwargs["aws_secret_access_key"] == "secret"

    @patch("boto3.client")
    def test_disconnect(self, mock_client_fn):
        mock_client_fn.return_value = MagicMock()
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        conn.connect()
        conn.disconnect()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        assert conn.client is None
        assert conn.is_connected is False

    @patch("boto3.client")
    def test_context_manager(self, mock_client_fn):
        mock_client_fn.return_value = MagicMock()
        with S3Connection(FakeS3Profile(), NoAuthStrategy()) as conn:
            conn.connect()
            assert conn.is_connected is True
        assert conn.is_connected is False

    @patch("boto3.client")
    def test_service_name_stripped_from_kwargs(self, mock_client_fn):
        conn = S3Connection(FakeS3Profile(), NoAuthStrategy())
        conn.connect()
        call_kwargs = mock_client_fn.call_args[1]
        assert "service_name" not in call_kwargs
