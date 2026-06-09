"""IAMCredentialStrategy tests."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.strategies import AuthStrategy, IAMCredentialStrategy


class TestIAMCredentialStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(
            IAMCredentialStrategy(access_key_id="AK", secret_access_key="SK"),
            AuthStrategy,
        )

    def test_injects_credentials(self):
        strategy = IAMCredentialStrategy(
            access_key_id="AKIA123", secret_access_key="secret"
        )
        result = strategy.apply({"region_name": "us-east-1"})
        assert result["aws_access_key_id"] == "AKIA123"
        assert result["aws_secret_access_key"] == "secret"
        assert result["region_name"] == "us-east-1"

    def test_returns_new_dict(self):
        original = {"region_name": "us-east-1"}
        strategy = IAMCredentialStrategy(access_key_id="AK", secret_access_key="SK")
        result = strategy.apply(original)
        assert result is not original
        assert "aws_access_key_id" not in original

    def test_with_session_token(self):
        strategy = IAMCredentialStrategy(
            access_key_id="AK", secret_access_key="SK", session_token="SESS"
        )
        result = strategy.apply({})
        assert result["aws_session_token"] == "SESS"

    def test_without_session_token(self):
        strategy = IAMCredentialStrategy(access_key_id="AK", secret_access_key="SK")
        result = strategy.apply({})
        assert "aws_session_token" not in result

    def test_none_credentials_omitted(self):
        strategy = IAMCredentialStrategy()
        result = strategy.apply({"region_name": "us-east-1"})
        assert "aws_access_key_id" not in result
        assert "aws_secret_access_key" not in result
