"""HTTPS reads with a client certificate (mTLS) through CertificateAuthProfile (#7).

A loopback HTTPS server requires a client certificate signed by a test CA; the
facade must present one, whatever trust setting the HTTP profile uses.
"""
from __future__ import annotations

import typing as t
from pathlib import Path

import pytest
from mountainash_auth_client import CertificateAuthProfile, TokenAuthProfile

from connections.tls_rig import TLSFiles, make_tls_files, mtls_server
from mountainash_transport import StorageConnectionError, StorageFacade
from mountainash_transport.settings.storage.profiles import HTTPStorageProfile

BODY = b"region,total\nnorth,120\n"


@pytest.fixture
def mtls(tmp_path: Path) -> t.Iterator[tuple[str, TLSFiles]]:
    files = make_tls_files(tmp_path)
    with mtls_server(files, BODY) as url:
        yield url, files


def test_a_certificate_and_key_by_path_read_through_a_private_ca(mtls: tuple[str, TLSFiles]) -> None:
    url, files = mtls
    auth = CertificateAuthProfile(CERTIFICATE_PATH=files.client_cert, PRIVATE_KEY_PATH=files.client_key)
    with StorageFacade.from_path(url, HTTPStorageProfile(CA_BUNDLE=str(files.ca)), auth_profile=auth) as web:
        assert web.read(url) == BODY


def test_a_certificate_and_key_held_in_memory(mtls: tuple[str, TLSFiles]) -> None:
    url, files = mtls
    auth = CertificateAuthProfile(CERTIFICATE=files.client_cert_pem, PRIVATE_KEY=files.client_key_pem)
    with StorageFacade.from_path(url, HTTPStorageProfile(CA_BUNDLE=str(files.ca)), auth_profile=auth) as web:
        assert web.read(url) == BODY


def test_a_combined_pem_with_verification_turned_off(mtls: tuple[str, TLSFiles]) -> None:
    url, files = mtls
    auth = CertificateAuthProfile(CERTIFICATE=files.client_cert_pem + files.client_key_pem)
    with StorageFacade.from_path(url, HTTPStorageProfile(VERIFY_SSL=False), auth_profile=auth) as web:
        assert web.read(url) == BODY


def test_default_trust_honours_ssl_cert_file(mtls: tuple[str, TLSFiles], monkeypatch: pytest.MonkeyPatch) -> None:
    url, files = mtls
    monkeypatch.setenv("SSL_CERT_FILE", str(files.ca))
    auth = CertificateAuthProfile(CERTIFICATE_PATH=files.client_cert, PRIVATE_KEY_PATH=files.client_key)
    with StorageFacade.from_path(url, HTTPStorageProfile(), auth_profile=auth) as web:
        assert web.read(url) == BODY


def test_without_a_client_certificate_the_server_refuses(mtls: tuple[str, TLSFiles]) -> None:
    """Other auth keeps trusting the server through CA_BUNDLE; only the missing certificate fails."""
    url, files = mtls
    profile = HTTPStorageProfile(CA_BUNDLE=str(files.ca), RETRY_MAX_ATTEMPTS=1)
    with StorageFacade.from_path(url, profile, auth_profile=TokenAuthProfile(TOKEN="t")) as web, \
            pytest.raises(StorageConnectionError):
        web.read(url)
