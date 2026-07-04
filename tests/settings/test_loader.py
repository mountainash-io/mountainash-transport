"""Tests for resolve_storage — the load_storage successor."""
from __future__ import annotations

from mountainash_transport import (
    ProfileNotFoundError,
    ProfileResolutionError,
    StorageError,
)


class TestResolverExceptions:
    def test_hierarchy(self):
        err = ProfileNotFoundError("missing", available=["scratch", "lake"])
        assert isinstance(err, ProfileResolutionError)
        assert isinstance(err, StorageError)

    def test_not_found_message_names_profile_and_available(self):
        err = ProfileNotFoundError("missing", available=["scratch"])
        assert "missing" in str(err)
        assert "scratch" in str(err)
        assert err.name == "missing"
        assert err.available == ["scratch"]

    def test_resolution_error_carries_name_and_reason(self):
        err = ProfileResolutionError("lake", "unknown provider 'nosuch'")
        assert err.name == "lake"
        assert "nosuch" in str(err)
