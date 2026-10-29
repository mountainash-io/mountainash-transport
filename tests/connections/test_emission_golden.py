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
class TestS3AssumeRoleEnvelope:
    """The L3 applier builds the Session-instruction envelope from the auth
    profile (ROLE_ARN/PROFILE_NAME). S3Connection consumes it (see
    tests/connections/test_s3_connection.py)."""

    def _profile(self, flavor="aws"):
        from mountainash_transport.settings.storage.profiles import S3StorageProfile
        return S3StorageProfile(FLAVOR=flavor, REGION="us-east-1",
                                **({"ACCOUNT_ID": "a"} if flavor == "r2" else {}),
                                **({"ENDPOINT_URL": "http://m:9000"} if flavor == "minio" else {}))

    def _emit(self, profile, auth):
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
        from mountainash_transport.connections import _emit_kwargs, _family_for_provider
        return _emit_kwargs(profile, auth, _family_for_provider(P.S3))

    def test_role_arn_builds_envelope(self):
        out = self._emit(self._profile(), IAMAuthProfile(
            ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk",
            ROLE_ARN="arn:aws:iam::123:role/r"))
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert out["session_name"] == "mountainash-transport"
        assert out["client_config"]["service_name"] == "s3"
        assert out["session"]["aws_access_key_id"] == "AKIA"
        assert out["session"]["region_name"] == "us-east-1"

    def test_keyless_role_arn_is_ambient(self):
        out = self._emit(self._profile(), IAMAuthProfile(ROLE_ARN="arn:aws:iam::123:role/r"))
        assert out["role_arn"] == "arn:aws:iam::123:role/r"
        assert "aws_access_key_id" not in out["session"]   # ambient bootstrap

    def test_profile_name_builds_envelope_without_role(self):
        out = self._emit(self._profile(), IAMAuthProfile(PROFILE_NAME="dev"))
        assert out["role_arn"] is None
        assert out["session"]["profile_name"] == "dev"

    def test_profile_name_allowed_on_r2(self):
        out = self._emit(self._profile("r2"), IAMAuthProfile(PROFILE_NAME="dev"))
        assert out["session"]["profile_name"] == "dev"   # NOT guarded

    def test_role_arn_on_r2_raises(self):
        with pytest.raises(ValueError, match="assume-role"):
            self._emit(self._profile("r2"), IAMAuthProfile(ROLE_ARN="arn:aws:iam::123:role/r"))

    def test_plain_iam_stays_flat(self):
        out = self._emit(self._profile(), IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="sk"))
        assert "client_config" not in out          # flat path
        assert out["aws_access_key_id"] == "AKIA"


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
