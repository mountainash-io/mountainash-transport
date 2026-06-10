"""Auth strategy protocol conformance and behavioral tests."""
from __future__ import annotations

import pytest

from mountainash_transport._core.auth.strategies import AuthStrategy, NoAuthStrategy


class GoodStrategy:
    def apply(self, kwargs: dict) -> dict:
        return kwargs


class BadStrategy:
    pass


class TestAuthStrategyProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodStrategy(), AuthStrategy)

    def test_negative_conformance(self):
        assert not isinstance(BadStrategy(), AuthStrategy)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), AuthStrategy)


class TestNoAuthStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(NoAuthStrategy(), AuthStrategy)

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = NoAuthStrategy().apply(original)
        assert result == {"timeout": 30}
        assert result is not original

    def test_preserves_existing_keys(self):
        original = {"headers": {"X-Custom": "val"}, "timeout": 30}
        result = NoAuthStrategy().apply(original)
        assert result == {"headers": {"X-Custom": "val"}, "timeout": 30}

    def test_empty_kwargs(self):
        result = NoAuthStrategy().apply({})
        assert result == {}


import base64

from mountainash_transport._core.auth.strategies import BearerTokenStrategy, BasicAuthStrategy


class TestBearerTokenStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(BearerTokenStrategy("tok"), AuthStrategy)

    def test_injects_bearer_header(self):
        result = BearerTokenStrategy("my-token").apply({"timeout": 30})
        assert result["headers"]["Authorization"] == "Bearer my-token"
        assert result["timeout"] == 30

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = BearerTokenStrategy("tok").apply(original)
        assert result is not original
        assert "headers" not in original

    def test_merges_with_existing_headers(self):
        original = {"headers": {"X-Custom": "val"}}
        result = BearerTokenStrategy("tok").apply(original)
        assert result["headers"]["Authorization"] == "Bearer tok"
        assert result["headers"]["X-Custom"] == "val"

    def test_does_not_mutate_original_headers(self):
        original_headers = {"X-Custom": "val"}
        original = {"headers": original_headers}
        BearerTokenStrategy("tok").apply(original)
        assert "Authorization" not in original_headers


class TestBasicAuthStrategy:
    def test_conforms_to_protocol(self):
        assert isinstance(BasicAuthStrategy("user", "pass"), AuthStrategy)

    def test_injects_basic_header(self):
        result = BasicAuthStrategy("user", "pass").apply({"timeout": 30})
        expected = base64.b64encode(b"user:pass").decode()
        assert result["headers"]["Authorization"] == f"Basic {expected}"
        assert result["timeout"] == 30

    def test_returns_new_dict(self):
        original = {"timeout": 30}
        result = BasicAuthStrategy("u", "p").apply(original)
        assert result is not original

    def test_merges_with_existing_headers(self):
        original = {"headers": {"X-Custom": "val"}}
        result = BasicAuthStrategy("u", "p").apply(original)
        assert result["headers"]["X-Custom"] == "val"
        assert "Authorization" in result["headers"]

    def test_does_not_mutate_original_headers(self):
        original_headers = {"X-Custom": "val"}
        original = {"headers": original_headers}
        BasicAuthStrategy("u", "p").apply(original)
        assert "Authorization" not in original_headers


from mountainash_transport._core.auth.strategies import RefreshableAuthStrategy


class _ConcreteRefreshable:
    """Minimal concrete class satisfying the RefreshableAuthStrategy protocol."""

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, kwargs: dict) -> dict:
        result = {**kwargs}
        result.setdefault("headers", {})["Authorization"] = f"Bearer {self._token}"
        return result

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def refresh(self) -> bool:
        self._token = "refreshed-token"
        return True


class TestRefreshableAuthStrategy:
    def test_regular_strategy_is_not_refreshable(self):
        # BearerTokenStrategy only has apply(); it should NOT satisfy RefreshableAuthStrategy
        assert not isinstance(BearerTokenStrategy("tok"), RefreshableAuthStrategy)

    def test_concrete_refreshable_detected(self):
        # A class implementing apply(), get_headers(), refresh() IS detected
        obj = _ConcreteRefreshable("initial")
        assert isinstance(obj, RefreshableAuthStrategy)

    def test_get_headers_contract(self):
        # After refresh(), get_headers() must reflect the new credentials
        obj = _ConcreteRefreshable("initial")
        assert obj.get_headers()["Authorization"] == "Bearer initial"
        refreshed = obj.refresh()
        assert refreshed is True
        assert obj.get_headers()["Authorization"] == "Bearer refreshed-token"

    def test_is_also_auth_strategy(self):
        # RefreshableAuthStrategy extends AuthStrategy — instances satisfy both
        obj = _ConcreteRefreshable("tok")
        assert isinstance(obj, AuthStrategy)
        assert isinstance(obj, RefreshableAuthStrategy)

    def test_missing_get_headers_is_not_refreshable(self):
        class _NoGetHeaders:
            def apply(self, kwargs: dict) -> dict:
                return kwargs

            def refresh(self) -> bool:
                return True

        assert not isinstance(_NoGetHeaders(), RefreshableAuthStrategy)

    def test_missing_refresh_is_not_refreshable(self):
        class _NoRefresh:
            def apply(self, kwargs: dict) -> dict:
                return kwargs

            def get_headers(self) -> dict[str, str]:
                return {}

        assert not isinstance(_NoRefresh(), RefreshableAuthStrategy)
