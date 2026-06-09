"""Tests for StorageProfileProtocol — profile protocol contract.

Profile mechanism tests live in mountainash-settings. Here we
exercise that concrete profile classes satisfy the
``StorageProfileProtocol`` contract (``to_handler_kwargs`` +
``get_connection_url``) and that the spec metadata is accessible.
"""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuth

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol
from mountainash_transport.settings.storage.profiles import (
    LocalStorageProfile,
    LOCAL_SPEC,
    S3StorageProfile,
    S3_SPEC,
)


@pytest.mark.unit
class TestStorageProfile:
    def test_local_satisfies_protocol(self):
        """LocalStorageProfile is a runtime instance of StorageProfileProtocol."""
        p = LocalStorageProfile(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            ROOT_PATH="/tmp/files",
            auth=NoAuth(),
        )
        assert isinstance(p, StorageProfileProtocol)

    def test_to_handler_kwargs_returns_dict(self):
        """to_handler_kwargs returns a dict."""
        p = LocalStorageProfile(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            ROOT_PATH="/tmp/files",
            auth=NoAuth(),
        )
        kwargs = p.to_handler_kwargs()
        assert isinstance(kwargs, dict)

    def test_get_connection_url_returns_str(self):
        """get_connection_url returns a string."""
        p = LocalStorageProfile(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            ROOT_PATH="/tmp/files",
            auth=NoAuth(),
        )
        url = p.get_connection_url()
        assert isinstance(url, str)

    def test_spec_name_accessible(self):
        """The spec's typed metadata is reachable off the class."""
        assert LOCAL_SPEC.name == "local"
        assert LOCAL_SPEC.read_only is False
        assert LOCAL_SPEC.supports_streaming is True

    def test_s3_satisfies_protocol(self):
        """S3StorageProfile is a runtime instance of StorageProfileProtocol."""
        p = S3StorageProfile(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.S3,
            FLAVOR="aws",
            REGION="us-east-1",
            auth=NoAuth(),
        )
        assert isinstance(p, StorageProfileProtocol)
