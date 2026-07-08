"""Tests for OAuth2 auth profiles flowing through create_connection().

Design invariant: auth-client OWNS the OAuth lifecycle; transport
CONFIGURES/renders only. Removing the blanket OAuth refusal in
create_connection() lets the supported_auth gate govern OAuth2 admission
per-profile, and lets a static-token OAuth2 profile authenticate over HTTP
via the existing bearer emit adapter (_bearer_from_access_token).
"""
from __future__ import annotations

import pytest

from mountainash_auth_client import OAuth2AuthProfile
from mountainash_transport.connections import create_connection
from mountainash_transport.connections.errors import UnsupportedAuthProfileError
from mountainash_transport.settings.storage.profiles import HTTPStorageProfile
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile


def test_oauth2_static_token_over_http_renders_bearer():
    conn = create_connection(HTTPStorageProfile(), OAuth2AuthProfile(ACCESS_TOKEN="tkn"))
    # _bearer_from_access_token renders the static token into the connection's kwargs
    assert conn._connect_kwargs["headers"]["Authorization"] == "Bearer tkn"


def test_oauth2_rejected_on_s3_by_gate():
    prof = S3StorageProfile(BUCKET="b", FLAVOR="aws")
    with pytest.raises(UnsupportedAuthProfileError):
        create_connection(prof, OAuth2AuthProfile(ACCESS_TOKEN="tkn"))
