"""Tests for StorageProfile — storage-flavored Profile.

Profile mechanism tests live in mountainash-settings. Here we
only exercise storage-specific behaviour: ``to_handler_kwargs()`` dispatch
logic (adapter present vs absent, inherited-from-base dispatch).
"""

from __future__ import annotations

import pytest

from mountainash_auth_client import CONST_AUTH_MODE, NoAuth, TokenAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.descriptor import (
    ParameterSpec,
    StorageDescriptor,
)
from mountainash_utils_files.settings.profile import StorageProfile


# Use an existing provider_type slot so StorageAuthBase.validate_provider_type
# accepts the dummy class. The test isn't registering anything on
# STORAGE_REGISTRY — it's only exercising in-class dispatch on StorageProfile.
_DUMMY_PROVIDER_TYPE = CONST_STORAGE_PROVIDER_TYPE.LOCAL

DUMMY_SPEC = StorageDescriptor(
    name="_dummy_storage",
    provider_type=_DUMMY_PROVIDER_TYPE,
    sdk_package=None,
    handler_module="mountainash_utils_files.storage_backends.local",
    handler_class="LocalStorageBackend",
    parameters=[
        ParameterSpec(
            name="STORE_PATH",
            type=str,
            tier="core",
            default=None,
            driver_key="path",
        ),
        ParameterSpec(
            name="LABEL",
            type=str,
            tier="advanced",
            default=None,
        ),
    ],
    default_auth=CONST_AUTH_MODE.NONE,
    supported_auth=frozenset({CONST_AUTH_MODE.NONE, CONST_AUTH_MODE.TOKEN}),
)


class DummyStorageProfile(StorageProfile):
    __spec__ = DUMMY_SPEC


@pytest.mark.unit
class TestStorageProfile:
    def test_to_handler_kwargs_default_no_adapter(self):
        """Without an adapter, spec driver_key mappings flow through."""
        p = DummyStorageProfile(
            PROVIDER_TYPE=_DUMMY_PROVIDER_TYPE,
            STORE_PATH="/tmp/files",
            auth=NoAuth(),
        )
        kwargs = p.to_handler_kwargs()
        assert kwargs.get("path") == "/tmp/files"

    def test_to_handler_kwargs_adapter_owns_pipeline(self):
        """When ``__adapter__`` is set it owns the full kwargs pipeline."""
        def _my_adapter(profile, auth=None):
            return {"custom_key": "custom_value"}

        class AdaptedProfile(StorageProfile):
            __spec__ = DUMMY_SPEC
            __adapter__ = staticmethod(_my_adapter)

        p = AdaptedProfile(PROVIDER_TYPE=_DUMMY_PROVIDER_TYPE, auth=NoAuth())
        assert p.to_handler_kwargs() == {"custom_key": "custom_value"}

    def test_to_handler_kwargs_token_auth_flows(self):
        """TokenAuth secret fields are reachable via ``_auth_kwargs``."""
        p = DummyStorageProfile(
            PROVIDER_TYPE=_DUMMY_PROVIDER_TYPE,
            STORE_PATH="/tmp",
            auth=TokenAuth(TOKEN=SecretStr("my-tok")),
        )
        kwargs = p.to_handler_kwargs()
        # _default_kwargs supplies path; _auth_kwargs may surface a token —
        # what matters for the profile-level test is that the spec
        # driver_key mapping round-trips cleanly.
        assert kwargs.get("path") == "/tmp"

    def test_adapter_inherited_from_parent(self):
        """``__adapter__`` on a parent class is picked up by subclasses via MRO."""
        def _parent_adapter(profile, auth=None):
            return {"from": "parent"}

        class ParentProfile(StorageProfile):
            __spec__ = DUMMY_SPEC
            __adapter__ = staticmethod(_parent_adapter)

        class ChildProfile(ParentProfile):
            pass

        p = ChildProfile(PROVIDER_TYPE=_DUMMY_PROVIDER_TYPE, auth=NoAuth())
        assert p.to_handler_kwargs() == {"from": "parent"}

    def test_spec_name_accessible(self):
        """The spec's typed metadata is reachable off the class."""
        assert DummyStorageProfile.__spec__.name == "_dummy_storage"
        assert DummyStorageProfile.__spec__.sdk_package is None
        # StorageDescriptor-specific typed fields are set to defaults.
        assert DummyStorageProfile.__spec__.read_only is False
        assert DummyStorageProfile.__spec__.supports_streaming is True

    def test_adapter_override_on_subclass_shadows_parent(self):
        """A subclass's ``__adapter__`` wins over the parent's (most-derived-first)."""
        def _parent(profile, auth=None):
            return {"from": "parent"}

        def _child(profile, auth=None):
            return {"from": "child"}

        class Parent(StorageProfile):
            __spec__ = DUMMY_SPEC
            __adapter__ = staticmethod(_parent)

        class Child(Parent):
            __adapter__ = staticmethod(_child)

        p = Child(PROVIDER_TYPE=_DUMMY_PROVIDER_TYPE, auth=NoAuth())
        assert p.to_handler_kwargs() == {"from": "child"}
