"""S3Connection behavioral tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.s3 import S3Connection


FAKE_S3_KWARGS: dict = {"service_name": "s3", "region_name": "us-east-1"}


class TestS3ConnectionProtocol:
    def test_conforms_to_connection_protocol(self):
        conn = S3Connection(FAKE_S3_KWARGS)
        assert isinstance(conn, ConnectionProtocol)


class TestS3ConnectionLifecycle:
    @patch("boto3.client")
    def test_connect_creates_client(self, mock_client_fn):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        conn = S3Connection(FAKE_S3_KWARGS)
        result = conn.connect()
        mock_client_fn.assert_called_once()
        assert mock_client_fn.call_args[0][0] == "s3"
        assert conn.client is mock_client
        assert conn.is_connected is True
        assert result is conn

    @patch("boto3.client")
    def test_connect_passes_merged_credentials_to_boto3(self, mock_client_fn):
        kwargs = {**FAKE_S3_KWARGS, "aws_access_key_id": "AKIA", "aws_secret_access_key": "sk"}
        conn = S3Connection(kwargs)
        conn.connect()
        _, called = mock_client_fn.call_args
        assert called["aws_access_key_id"] == "AKIA"
        assert "service_name" not in called

    @patch("boto3.client")
    def test_disconnect(self, mock_client_fn):
        mock_client_fn.return_value = MagicMock()
        conn = S3Connection(FAKE_S3_KWARGS)
        conn.connect()
        conn.disconnect()
        assert conn.client is None
        assert conn.is_connected is False

    def test_not_connected_initially(self):
        conn = S3Connection(FAKE_S3_KWARGS)
        assert conn.client is None
        assert conn.is_connected is False

    @patch("boto3.client")
    def test_context_manager(self, mock_client_fn):
        mock_client_fn.return_value = MagicMock()
        with S3Connection(FAKE_S3_KWARGS) as conn:
            conn.connect()
            assert conn.is_connected is True
        assert conn.is_connected is False

    @patch("boto3.client")
    def test_service_name_stripped_from_kwargs(self, mock_client_fn):
        conn = S3Connection(FAKE_S3_KWARGS)
        conn.connect()
        call_kwargs = mock_client_fn.call_args[1]
        assert "service_name" not in call_kwargs


from mountainash_transport.connections.errors import TransportConnectionError  # noqa: E402


def _envelope(*, session=None, role_arn=None):
    return {
        "client_config": {"service_name": "s3", "region_name": "us-east-1",
                          "use_ssl": True, "verify": True},
        "session": session if session is not None else {"region_name": "us-east-1"},
        "role_arn": role_arn,
        "session_name": "mountainash-transport",
    }


@pytest.mark.unit
class TestS3ConnectionFlatPath:
    def test_flat_dict_builds_plain_client(self):
        with patch("boto3.client") as mk:
            S3Connection({"service_name": "s3", "region_name": "us-east-1",
                          "aws_access_key_id": "AKIA"}).connect()
            # service_name is popped; passed positionally as "s3".
            args, kwargs = mk.call_args
            assert args[0] == "s3"
            assert "service_name" not in kwargs
            assert kwargs["aws_access_key_id"] == "AKIA"


@pytest.mark.unit
class TestS3ConnectionProfileName:
    def test_profile_name_routes_to_session(self):
        with patch("boto3.Session") as MkSession:
            sess = MkSession.return_value
            S3Connection(_envelope(session={"profile_name": "dev", "region_name": "us-east-1"})).connect()
            MkSession.assert_called_once_with(profile_name="dev", region_name="us-east-1")
            sess.client.assert_called_once()
            assert sess.client.call_args[0][0] == "s3"

    def test_profile_name_and_keys_is_ambiguous(self):
        env = _envelope(session={"profile_name": "dev", "aws_access_key_id": "AKIA",
                                 "aws_secret_access_key": "sk", "region_name": "us-east-1"})
        with pytest.raises(ValueError, match="[Aa]mbiguous"):
            S3Connection(env).connect()


@pytest.mark.unit
class TestS3ConnectionAssumeRole:
    def test_assume_role_builds_refreshable_client(self):
        with patch("boto3.Session") as MkSession, \
             patch("botocore.session.get_session") as mk_get, \
             patch("mountainash_transport.connections.s3.AssumeRoleCredentialFetcher") as MkFetcher, \
             patch("mountainash_transport.connections.s3.DeferredRefreshableCredentials") as MkCreds:
            source = MkSession.return_value
            source._session.get_credentials.return_value = MagicMock()  # ambient present
            target = mk_get.return_value
            S3Connection(_envelope(role_arn="arn:aws:iam::123:role/r")).connect()
            # fetcher built with the role + session name
            _, fkwargs = MkFetcher.call_args
            assert fkwargs["role_arn"] == "arn:aws:iam::123:role/r"
            assert fkwargs["extra_args"] == {"RoleSessionName": "mountainash-transport"}
            # refreshable creds attached to the target botocore session
            assert target._credentials is MkCreds.return_value

    def test_assume_role_without_source_creds_raises(self):
        with patch("boto3.Session") as MkSession, \
             patch("botocore.session.get_session"):
            MkSession.return_value._session.get_credentials.return_value = None
            with pytest.raises(TransportConnectionError, match="credentials"):
                S3Connection(_envelope(role_arn="arn:aws:iam::123:role/r")).connect()
