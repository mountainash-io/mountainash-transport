"""Tests for HTTPStorageBackend — auth and profile integration."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import httpx
import pytest

from mountainash_utils_files.storage_backends.http import HTTPStorageBackend


@pytest.mark.unit
class TestHTTPBackendClientCreation:
    def test_bare_client_when_no_auth_params(self):
        backend = HTTPStorageBackend(auth_params=None)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            backend._get_client()
            mock_client.assert_called_once_with()

    def test_profile_kwargs_forwarded_to_client(self):
        profile = MagicMock()
        expected_kwargs = {
            "timeout": httpx.Timeout(connect=5.0, read=15.0, write=60.0, pool=5.0),
            "follow_redirects": True,
            "max_redirects": 10,
            "verify": True,
            "headers": {"Authorization": "Bearer tok123"},
        }
        profile.to_handler_kwargs.return_value = expected_kwargs
        backend = HTTPStorageBackend(auth_params=profile)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            backend._get_client()
            mock_client.assert_called_once_with(**expected_kwargs)

    def test_client_cached_after_first_call(self):
        backend = HTTPStorageBackend(auth_params=None)
        with patch("mountainash_utils_files.storage_backends.http.httpx.Client") as mock_client:
            c1 = backend._get_client()
            c2 = backend._get_client()
            assert c1 is c2
            mock_client.assert_called_once()
