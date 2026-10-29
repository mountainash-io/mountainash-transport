"""Tests for LocalStorageProfile."""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuthProfile

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.storage.profiles import (
    LOCAL_SPEC,
    LocalStorageProfile,
)


def _make(**extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.LOCAL,
        "auth": NoAuthProfile(),
    }
    kwargs.update(extra)
    return LocalStorageProfile(**kwargs)


@pytest.mark.unit
class TestLocalBasic:
    def test_construct_with_just_root_path(self):
        s = _make(ROOT_PATH="/tmp/files")
        assert s.ROOT_PATH == "/tmp/files"

    def test_no_root_path_allowed(self):
        s = _make()
        assert s.ROOT_PATH is None

    def test_to_handler_kwargs_shape(self):
        s = _make(ROOT_PATH="/tmp/files")
        kw = s.to_handler_kwargs()
        assert kw == {"root_path": "/tmp/files", "create_path": False}

    def test_create_path_flag_surfaced(self):
        s = _make(ROOT_PATH="/tmp/new", CREATE_PATH=True)
        kw = s.to_handler_kwargs()
        assert kw["create_path"] is True


@pytest.mark.unit
class TestLocalDescriptor:
    def test_descriptor_name(self):
        assert LOCAL_SPEC.name == "local"

    def test_descriptor_sdk_package_is_none(self):
        """Stdlib only — no SDK."""
        assert LOCAL_SPEC.sdk_package is None

    def test_descriptor_not_read_only(self):
        assert LOCAL_SPEC.read_only is False

    def test_descriptor_no_multipart(self):
        assert LOCAL_SPEC.supports_multipart is False
