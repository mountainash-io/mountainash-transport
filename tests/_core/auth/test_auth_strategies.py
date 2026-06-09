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
