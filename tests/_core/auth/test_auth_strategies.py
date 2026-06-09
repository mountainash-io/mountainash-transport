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
