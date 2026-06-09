"""Tests for OAuthFlow (OAuth2 authorization code flow)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mountainash_transport.connections.errors import TokenExchangeError, TokenRefreshError
from mountainash_transport.connections.oauth2.flow import OAuthFlow


class TestBuildAuthorizeUrl:
    def test_returns_url_with_client_id(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert "client_id=my_client" in url
        assert "https://auth.example.com/authorize" in url

    def test_returns_url_with_state(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, state = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert state in url
        assert len(state) > 0

    def test_no_pkce_by_default(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, _ = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert "code_challenge" not in url

    def test_pkce_adds_code_challenge_and_s256(self):
        from tests.connections.conftest import FakeOAuth2Spec
        spec = FakeOAuth2Spec(metadata={
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "use_pkce": True,
        })
        flow = OAuthFlow(spec)
        url, _ = flow.build_authorize_url(
            client_id="pkce_client",
            redirect_uri="http://localhost:8080/callback",
        )
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url

    def test_scope_included_when_provided(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        url, _ = flow.build_authorize_url(
            client_id="my_client",
            redirect_uri="http://localhost/cb",
            scope="read write",
        )
        assert "scope=" in url


class TestExchangeCode:
    def test_raises_token_exchange_error_on_http_error(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("mountainash_transport.connections.oauth2.flow.httpx.Client") as MockClient:
            mock_client_instance = MockClient.return_value.__enter__.return_value
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_response
            )
            with pytest.raises(TokenExchangeError) as exc_info:
                flow.exchange_code(
                    code="authcode",
                    redirect_uri="http://localhost/cb",
                    client_id="cid",
                    client_secret="csec",
                )
            assert exc_info.value.status_code == 400

    def test_returns_token_dict_on_success(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "access_tok",
            "refresh_token": "refresh_tok",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("mountainash_transport.connections.oauth2.flow.httpx.Client") as MockClient:
            mock_client_instance = MockClient.return_value.__enter__.return_value
            mock_client_instance.post.return_value = mock_response
            result = flow.exchange_code(
                code="code123",
                redirect_uri="http://localhost/cb",
                client_id="cid",
                client_secret="csec",
            )
        assert result["access_token"] == "access_tok"
        assert result["refresh_token"] == "refresh_tok"
        assert result["token_expires_at"] is not None


class TestRefresh:
    def test_raises_token_refresh_error_on_http_error(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("mountainash_transport.connections.oauth2.flow.httpx.Client") as MockClient:
            mock_client_instance = MockClient.return_value.__enter__.return_value
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=mock_response
            )
            with pytest.raises(TokenRefreshError) as exc_info:
                flow.refresh(
                    refresh_token="old_refresh",
                    client_id="cid",
                    client_secret="csec",
                )
            assert exc_info.value.status_code == 401


class TestIsExpired:
    def test_none_returns_false(self):
        assert OAuthFlow.is_expired(None) is False

    def test_past_timestamp_returns_true(self):
        assert OAuthFlow.is_expired(int(time.time()) - 1000) is True

    def test_far_future_returns_false(self):
        assert OAuthFlow.is_expired(int(time.time()) + 10000) is False

    def test_near_future_returns_true_due_to_buffer(self):
        assert OAuthFlow.is_expired(int(time.time()) + 100) is True


class TestCsrfStateValidation:
    def test_missing_state_in_callback_raises(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        flow.build_authorize_url("cid", "http://localhost/cb")
        with pytest.raises(ValueError, match="[Ss]tate"):
            flow._validate_callback_state({}, "expected_state")

    def test_mismatched_state_raises(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        flow.build_authorize_url("cid", "http://localhost/cb")
        with pytest.raises(ValueError, match="[Ss]tate"):
            flow._validate_callback_state({"state": "wrong"}, "expected_state")

    def test_correct_state_passes(self, fake_oauth2_spec):
        flow = OAuthFlow(fake_oauth2_spec)
        _, state = flow.build_authorize_url("cid", "http://localhost/cb")
        flow._validate_callback_state({"state": state}, state)


class TestPkceVerifierByState:
    def test_sequential_authorize_exchange(self):
        from tests.connections.conftest import FakeOAuth2Spec
        spec = FakeOAuth2Spec(metadata={
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "use_pkce": True,
        })
        flow = OAuthFlow(spec)
        _, state1 = flow.build_authorize_url("cid", "http://localhost/cb")
        assert flow._pending_verifiers.get(state1) is not None

    def test_concurrent_authorize_urls_have_independent_verifiers(self):
        from tests.connections.conftest import FakeOAuth2Spec
        spec = FakeOAuth2Spec(metadata={
            "authorize_url": "https://auth.example.com/authorize",
            "token_url": "https://auth.example.com/token",
            "use_pkce": True,
        })
        flow = OAuthFlow(spec)
        _, state1 = flow.build_authorize_url("cid", "http://localhost/cb")
        _, state2 = flow.build_authorize_url("cid", "http://localhost/cb")
        assert state1 != state2
        assert flow._pending_verifiers[state1] != flow._pending_verifiers[state2]
