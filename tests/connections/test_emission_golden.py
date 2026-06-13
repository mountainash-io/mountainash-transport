# tests/connections/test_emission_golden.py
"""Phase 3 golden tests.

``TestStrictParity`` asserts that ``Profile.emit`` reproduces the pre-refactor
``_core/auth`` resolver output captured before deletion (Task 1 baseline).
``TestIntentionalDivergence`` covers cases where Phase 2 deliberately changed
behaviour relative to the old resolver. ``TestS3RoleArnLayering`` and
``TestPerLeafEmission`` verify the factory's credential layering and per-leaf
emission. Exact key/value shape is asserted — no count-based assertions.
"""
from __future__ import annotations

import base64

import pytest

from mountainash_auth_client import (
    IAMAuthProfile,
    JWTAuthProfile,
    KerberosAuthProfile,
    PasswordAuthProfile,
    TokenAuthProfile,
)
from mountainash_auth_client.targets import TargetFamily


@pytest.mark.unit
class TestStrictParity:
    """emit() == the old resolver's merged output (captured pre-deletion)."""

    def test_http_bearer(self):
        out = TokenAuthProfile(TOKEN="t0k").emit(TargetFamily.HTTP, base={"timeout": 30})
        assert out == {"timeout": 30, "headers": {"Authorization": "Bearer t0k"}}

    def test_http_jwt_bearer(self):
        out = JWTAuthProfile(TOKEN="jw7").emit(TargetFamily.HTTP, base={"timeout": 30})
        assert out == {"timeout": 30, "headers": {"Authorization": "Bearer jw7"}}

    def test_http_basic(self):
        out = PasswordAuthProfile(USERNAME="u", PASSWORD="p").emit(
            TargetFamily.HTTP, base={"timeout": 30}
        )
        token = base64.b64encode(b"u:p").decode()  # == "dTpw"
        assert out == {"timeout": 30, "headers": {"Authorization": f"Basic {token}"}}

    def test_boto_iam_full(self):
        out = IAMAuthProfile(
            ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk", SESSION_TOKEN="st"
        ).emit(TargetFamily.BOTO, base={"service_name": "s3", "region_name": "us-east-1"})
        assert out == {
            "service_name": "s3",
            "region_name": "us-east-1",
            "aws_access_key_id": "AKIA",
            "aws_secret_access_key": "sk",
            "aws_session_token": "st",
        }

    def test_boto_iam_no_session(self):
        out = IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk").emit(
            TargetFamily.BOTO, base={"service_name": "s3"}
        )
        assert out == {
            "service_name": "s3",
            "aws_access_key_id": "AKIA",
            "aws_secret_access_key": "sk",
        }

    def test_paramiko_kerberos(self):
        out = KerberosAuthProfile(SERVICE_NAME="host.example.com").emit(
            TargetFamily.PARAMIKO, base={"hostname": "h"}
        )
        assert out == {"hostname": "h", "gss_auth": True, "gss_host": "host.example.com"}


@pytest.mark.unit
class TestIntentionalDivergence:
    """Cases where Phase 2 deliberately differs from the old resolver."""

    def test_sftp_password_now_emits_username(self):
        # OLD SSHPasswordStrategy emitted {"password": "p"} only (captured Task-1
        # baseline: {'hostname': 'h', 'password': 'p'}). Phase 2's
        # PasswordAuthProfile deliberately scopes BOTH username + password to
        # PARAMIKO so paramiko.connect receives a username. Documented divergence.
        out = PasswordAuthProfile(USERNAME="u", PASSWORD="p").emit(
            TargetFamily.PARAMIKO, base={"hostname": "h"}
        )
        assert out == {"hostname": "h", "username": "u", "password": "p"}


@pytest.mark.unit
class TestS3RoleArnLayering:
    """Credentials layer into the nested base_kwargs; the assume-role envelope is
    preserved.

    NOTE: ``S3Connection`` does NOT yet consume this envelope (no STS AssumeRole
    at connect time) — that is a pre-existing unimplemented gap, out of Phase 3
    scope. This test asserts only the credential layering the spec requires.
    """

    def test_credentials_land_in_base_kwargs(self):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
        from mountainash_transport.connections import _emit_kwargs, _family_for_provider

        class _Nested:
            class __spec__:
                provider_type = "s3"

            def to_handler_kwargs(self):
                return {
                    "base_kwargs": {"service_name": "s3", "region_name": "us-east-1"},
                    "role_arn": "arn:aws:iam::123:role/r",
                    "session_name": "mountainash-transport",
                }

            def emit(self, target=None, *, base=None):
                return {
                    **(base or {}),
                    "base_kwargs": {"service_name": "s3", "region_name": "us-east-1"},
                    "role_arn": "arn:aws:iam::123:role/r",
                    "session_name": "mountainash-transport",
                }

            def get_connection_url(self):
                return "s3://b/k"

        out = _emit_kwargs(
            _Nested(),
            IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"),
            _family_for_provider(P.S3),
        )
        # Outer assume-role envelope untouched.
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert out["session_name"] == "mountainash-transport"
        # Credentials landed inside base_kwargs, not at the top level.
        assert out["base_kwargs"]["aws_access_key_id"] == "AKIA"
        assert out["base_kwargs"]["aws_secret_access_key"] == "sk"
        assert "aws_access_key_id" not in out

    def test_layering_does_not_mutate_caller_base_kwargs(self):
        # Copy-on-write: the profile's returned base_kwargs dict is not mutated
        # in place by the credential emission.
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
        from mountainash_transport.connections import _emit_kwargs, _family_for_provider

        inner = {"service_name": "s3"}

        class _Nested:
            class __spec__:
                provider_type = "s3"

            def to_handler_kwargs(self):
                return {"base_kwargs": inner, "role_arn": "arn:x", "session_name": "s"}

            def emit(self, target=None, *, base=None):
                return {**(base or {}), "base_kwargs": inner, "role_arn": "arn:x", "session_name": "s"}

            def get_connection_url(self):
                return "s3://b/k"

        _emit_kwargs(
            _Nested(),
            IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"),
            _family_for_provider(P.S3),
        )
        assert "aws_access_key_id" not in inner


@pytest.mark.unit
class TestPerLeafEmission:
    """Each leaf of a composed chain emits with its own target family."""

    def test_sftp_chain_emits_paramiko_on_inner_ssh(self):
        from mountainash_transport.connections import create_connection
        from mountainash_transport.connections.sftp import SFTPConnection

        class _SFTP:
            class __spec__:
                provider_type = "sftp"

            def to_handler_kwargs(self):
                return {"hostname": "h"}

            def emit(self, target=None, *, base=None):
                return {**(base or {}), "hostname": "h"}

            def get_connection_url(self):
                return "sftp://h/p"

        conn = create_connection(_SFTP(), PasswordAuthProfile(USERNAME="u", PASSWORD="p"))
        assert isinstance(conn, SFTPConnection)
        # SFTPConnection stores its inner SSH leaf as `_ssh` (connections/sftp.py).
        assert conn._ssh._connect_kwargs["username"] == "u"
        assert conn._ssh._connect_kwargs["password"] == "p"
