"""Tests for FTPStorageProfile — FTP / FTPS (ftplib) settings."""

from __future__ import annotations

import pytest

from mountainash_auth_client import NoAuth

from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.settings.storage.profiles import (
    FTP_SPEC,
    FTPStorageProfile,
)


def _make(*, auth=None, host: str = "ftp.example", **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.FTP,
        "HOST": host,
        "auth": auth if auth is not None else NoAuth(),
    }
    kwargs.update(extra)
    return FTPStorageProfile(**kwargs)


@pytest.mark.unit
class TestFTPAnonymous:
    def test_anonymous_default_username(self):
        s = _make(USERNAME="anonymous", auth=NoAuth())
        assert s.USERNAME == "anonymous"
        # ftplib class should be the plain (non-TLS) one.
        kw = s.to_handler_kwargs()
        assert kw["ftp_class_path"] == "ftplib.FTP"

    def test_anonymous_init_kwargs_carry_user(self):
        s = _make(USERNAME="anonymous", auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["init_kwargs"]["user"] == "anonymous"


@pytest.mark.unit
class TestFTPHandlerKwargs:
    """to_handler_kwargs returns SDK-level config only (no auth)."""

    def test_no_auth_keys_in_init_kwargs(self):
        """Auth credentials are injected by the strategy layer, not the profile."""
        s = _make()
        kw = s.to_handler_kwargs()
        init = kw["init_kwargs"]
        assert "passwd" not in init


@pytest.mark.unit
class TestFTPTlsSwitch:
    def test_use_tls_false_selects_plain_ftp(self):
        s = _make(USERNAME="u", USE_TLS=False, auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["ftp_class_path"] == "ftplib.FTP"

    def test_use_tls_true_selects_ftp_tls(self):
        s = _make(USERNAME="u", USE_TLS=True, auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["ftp_class_path"] == "ftplib.FTP_TLS"


@pytest.mark.unit
class TestFTPEnvelopeLayout:
    def test_port_carried_in_connect_kwargs_not_init(self):
        s = _make(USERNAME="u", PORT=2121, auth=NoAuth())
        kw = s.to_handler_kwargs()
        # Port is for ftp.connect(host, port) — not the __init__ signature.
        assert kw["_connect_kwargs"]["port"] == 2121
        assert "port" not in kw["init_kwargs"]

    def test_passive_mode_default_true(self):
        s = _make(USERNAME="u", auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["_post_connect"]["passive"] is True

    def test_passive_mode_off_explicit(self):
        s = _make(USERNAME="u", PASSIVE_MODE=False, auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["_post_connect"]["passive"] is False

    def test_envelope_has_all_four_keys(self):
        s = _make(USERNAME="u", auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert set(kw.keys()) == {
            "ftp_class_path",
            "init_kwargs",
            "_connect_kwargs",
            "_post_connect",
        }

    def test_host_flows_through_init_kwargs(self):
        s = _make(USERNAME="u", auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["init_kwargs"]["host"] == "ftp.example"


@pytest.mark.unit
class TestFTPDescriptor:
    def test_descriptor_name(self):
        assert FTP_SPEC.name == "ftp"

    def test_descriptor_sdk_package_is_none(self):
        """stdlib ftplib — no SDK dependency."""
        assert FTP_SPEC.sdk_package is None

    def test_descriptor_not_read_only(self):
        assert FTP_SPEC.read_only is False

    def test_descriptor_no_multipart(self):
        assert FTP_SPEC.supports_multipart is False
