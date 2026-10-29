"""ConnectionProtocol conformance tests."""
from __future__ import annotations

import typing as t

import pytest

from mountainash_transport._core.protocols import ConnectionProtocol


class GoodConnection:
    def connect(self):
        return self

    def disconnect(self) -> None:
        pass

    @property
    def client(self):
        return None

    @property
    def is_connected(self) -> bool:
        return False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MissingClient:
    def connect(self):
        return self

    def disconnect(self) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return False


class TestConnectionProtocol:
    def test_positive_conformance(self):
        assert isinstance(GoodConnection(), ConnectionProtocol)

    def test_negative_conformance(self):
        assert not isinstance(MissingClient(), ConnectionProtocol)

    def test_empty_class_does_not_conform(self):
        assert not isinstance(object(), ConnectionProtocol)
