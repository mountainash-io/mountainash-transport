"""Public native-read handoff: effective access selection without reading data.

The handoff resolves direct/named profiles, location policy and authentication
into an immutable ``NativeReadAccess`` or ``None`` (transport must read). These
tests exercise real profiles, real auth profiles, a real YAML config and real
files; the result is judged by values and by reading the returned location
through the public facade.
"""
from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
import textwrap

import pytest
from mountainash_auth_client import IAMAuthProfile, NoAuthProfile, TokenAuthProfile

from mountainash_transport import StorageFacade
from mountainash_transport.connections.errors import UnsupportedAuthProfileError
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.native_read import NativeReadAccess, resolve_native_read

from mountainash_transport.settings.storage.profiles import (
    HTTPStorageProfile,
    LocalStorageProfile,
    S3StorageProfile,
)


STATIC = IAMAuthProfile(ACCESS_KEY_ID="AKIASTATICKEY", SECRET_ACCESS_KEY="static-secret-value")


def minio(**extra):
    return S3StorageProfile(
        FLAVOR="minio", ENDPOINT_URL="http://127.0.0.1:9000", REGION="us-east-1",
        ADDRESSING_STYLE="path", USE_SSL=False, VERIFY_SSL=False,
        CONNECT_TIMEOUT=3.5, READ_TIMEOUT=7.0, **extra,
    )


def aws(**extra):
    return S3StorageProfile(FLAVOR="aws", REGION="ap-southeast-2", **extra)


@pytest.fixture
def dirs(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "f.csv").write_bytes(b"inside")
    (tmp_path / "outside.csv").write_bytes(b"outside")
    return root, tmp_path / "outside.csv"


def read(location: str) -> bytes:
    with StorageFacade.from_path(location) as facade:
        return facade.read(location)


# --- local ---------------------------------------------------------------------


class TestLocal:
    def test_unprofiled_local_location_reads_actual_bytes(self, dirs):
        root, _ = dirs
        access = resolve_native_read(str(root / "f.csv"))
        assert isinstance(access, NativeReadAccess)
        assert (access.provider, access.scheme, access.policy) == ("local", "file", None)
        assert dict(access.connection_options) == {}
        assert read(access.location) == b"inside"

    def test_default_does_not_confine_outside_declared_root(self, dirs):
        root, outside = dirs
        profile = LocalStorageProfile(ROOT_PATH=str(root))
        access = resolve_native_read(str(outside), storage_profile=profile)
        assert access.policy is None
        assert read(access.location) == b"outside"

    def test_declared_root_anchors_relative_path_without_confining(self, dirs):
        root, _ = dirs
        access = resolve_native_read("f.csv", storage_profile=LocalStorageProfile(ROOT_PATH=str(root)))
        assert access.policy is None
        assert os.path.realpath(access.location) == os.path.realpath(root / "f.csv")
        assert read(access.location) == b"inside"

    def test_profile_policy_is_inherited_and_denies_outside(self, dirs):
        root, outside = dirs
        profile = LocalStorageProfile(ROOT_PATH=str(root), LOCATION_POLICY={})
        access = resolve_native_read("f.csv", storage_profile=profile)
        assert access.policy is not None and access.policy.active
        assert os.path.realpath(access.policy.root) == os.path.realpath(root)
        with pytest.raises(LocationNotAllowed):
            resolve_native_read(str(outside), storage_profile=profile)
        off = resolve_native_read(str(outside), storage_profile=profile, policy=None)
        assert off.policy is None and read(off.location) == b"outside"
        wider = LocationPolicy(root=str(outside.parent))
        replaced = resolve_native_read(str(outside), storage_profile=profile, policy=wider)
        assert replaced.policy == wider and read(replaced.location) == b"outside"

    def test_explicit_policy_without_profile_confines_and_is_represented(self, dirs):
        root, outside = dirs
        policy = LocationPolicy(root=str(root))
        access = resolve_native_read(str(root / "f.csv"), policy=policy)
        assert access.policy == policy and read(access.location) == b"inside"
        with pytest.raises(LocationNotAllowed):
            resolve_native_read(str(outside), policy=policy)

    @pytest.mark.parametrize("profile_policy", [None, {}])
    def test_relative_profile_root_is_anchored_once(self, dirs, monkeypatch, profile_policy):
        root, _ = dirs
        monkeypatch.chdir(root.parent)
        profile = LocalStorageProfile(ROOT_PATH="root", LOCATION_POLICY=profile_policy)
        access = resolve_native_read("f.csv", storage_profile=profile)
        monkeypatch.chdir(root)
        assert read(access.location) == b"inside"


# --- S3 -----------------------------------------------------------------------


class TestS3Static:
    def test_static_credentials_and_options_are_canonical(self):
        access = resolve_native_read("s3://bkt/data/a.parquet", storage_profile=minio(), auth_profile=STATIC)
        assert (access.location, access.scheme, access.provider, access.policy) == (
            "s3://bkt/data/a.parquet", "s3", "s3", None,
        )
        assert dict(access.connection_options) == {
            "access_key_id": "AKIASTATICKEY",
            "secret_access_key": "static-secret-value",
            "region": "us-east-1",
            "endpoint_url": "http://127.0.0.1:9000",
            "use_ssl": False,
            "verify_tls": False,
            "addressing_style": "path",
            "connect_timeout": 3.5,
            "read_timeout": 7.0,
        }

    def test_aws_flavor_has_no_endpoint_and_carries_acceleration_flags(self):
        access = resolve_native_read(
            "s3://bkt/k.csv", storage_profile=aws(ACCELERATE_ENDPOINT=True, DUALSTACK_ENDPOINT=True),
            auth_profile=STATIC,
        )
        options = dict(access.connection_options)
        assert "endpoint_url" not in options and "connect_timeout" not in options
        assert options["region"] == "ap-southeast-2"
        assert options["accelerate_endpoint"] is True and options["dualstack_endpoint"] is True
        assert options["addressing_style"] == "auto" and options["verify_tls"] is True

    def test_result_and_option_snapshot_are_immutable(self):
        access = resolve_native_read("s3://bkt/k.csv", storage_profile=minio(), auth_profile=STATIC)
        with pytest.raises(TypeError):
            access.connection_options["secret_access_key"] = "x"
        with pytest.raises(dataclasses.FrozenInstanceError):
            access.location = "s3://other/k"

    def test_repr_and_str_exclude_credentials_and_options(self):
        access = resolve_native_read("s3://bkt/k.csv", storage_profile=minio(), auth_profile=STATIC)
        for text in (repr(access), str(access)):
            assert "static-secret-value" not in text and "AKIASTATICKEY" not in text
            assert "127.0.0.1" not in text

    def test_active_policy_is_represented_not_erased(self):
        policy = LocationPolicy(allowed_remote={"s3": frozenset()})
        access = resolve_native_read("s3://bkt/k.csv", storage_profile=minio(), auth_profile=STATIC, policy=policy)
        assert access.policy == policy
        with pytest.raises(LocationNotAllowed):  # a denial is an error, not a fallback signal
            resolve_native_read("s3://bkt/k.csv", policy=LocationPolicy())


class TestS3Fallback:
    """Configurations the native engine cannot represent faithfully: transport reads."""

    @pytest.mark.parametrize("auth", [
        None,
        NoAuthProfile(),
        IAMAuthProfile(),
        IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="s", SESSION_TOKEN="temporary"),
        IAMAuthProfile(ROLE_ARN="arn:aws:iam::123456789012:role/reader"),
        IAMAuthProfile(PROFILE_NAME="some-profile"),
        IAMAuthProfile(ACCESS_KEY_ID="AKIA", SECRET_ACCESS_KEY="s", PROFILE_NAME="some-profile"),
        IAMAuthProfile(ACCESS_KEY_ID="AKIA"),
        IAMAuthProfile(SECRET_ACCESS_KEY="s"),
    ], ids=["none", "noauth-ambient", "empty-iam-ambient", "session-token", "assume-role",
            "named-chain", "keys-and-chain", "partial-key", "partial-secret"])
    def test_non_static_or_ambient_auth_falls_back(self, auth):
        assert resolve_native_read("s3://bkt/k.csv", storage_profile=aws(), auth_profile=auth) is None

    def test_absent_auth_and_noauth_never_become_anonymous(self):
        for auth in (None, NoAuthProfile()):
            assert resolve_native_read("s3://bkt/k.csv", storage_profile=minio(), auth_profile=auth) is None

    def test_no_storage_profile_keeps_ambient_transport_route(self):
        assert resolve_native_read("s3://bkt/k.csv", auth_profile=STATIC) is None

    @pytest.mark.parametrize("url", ["sftp://host/p.csv", "gs://bkt/k.csv"])
    def test_other_providers_stay_on_transport(self, url):
        assert resolve_native_read(url) is None

    def test_unknown_scheme_is_left_to_transport_unless_confinement_is_active(self):
        assert resolve_native_read("weird://h/p") is None
        with pytest.raises(LocationNotAllowed):
            resolve_native_read("weird://h/p", policy=LocationPolicy())

    def test_session_and_role_inputs_do_not_resolve_credentials_or_use_network(self):
        script = textwrap.dedent('''
            import os, socket, sys
            for key in [k for k in os.environ if k.startswith("AWS_")]:
                del os.environ[key]
            os.environ["AWS_SHARED_CREDENTIALS_FILE"] = os.devnull
            os.environ["AWS_CONFIG_FILE"] = os.devnull

            def tripwire(*args, **kwargs):
                raise AssertionError("network used")
            socket.socket.connect = tripwire
            socket.create_connection = tripwire

            from mountainash_auth_client import IAMAuthProfile
            from mountainash_transport.native_read import resolve_native_read
            from mountainash_transport.settings.storage.profiles import S3StorageProfile

            profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1")
            for auth in (
                IAMAuthProfile(PROFILE_NAME="does-not-exist"),
                IAMAuthProfile(ROLE_ARN="arn:aws:iam::123456789012:role/r"),
                IAMAuthProfile(ACCESS_KEY_ID="a", SECRET_ACCESS_KEY="b", SESSION_TOKEN="t"),
                IAMAuthProfile(), None,
            ):
                assert resolve_native_read("s3://b/k", storage_profile=profile, auth_profile=auth) is None
            static = IAMAuthProfile(ACCESS_KEY_ID="a", SECRET_ACCESS_KEY="b")
            assert resolve_native_read("s3://b/k", storage_profile=profile, auth_profile=static) is not None
        ''')
        subprocess.run([sys.executable, "-c", script], check=True)

    def test_missing_s3_sdk_is_an_error_not_native_ineligibility(self):
        script = textwrap.dedent('''
            import importlib.abc, sys
            class NoBotocore(importlib.abc.MetaPathFinder):
                def find_spec(self, name, path=None, target=None):
                    if name.partition(".")[0] == "botocore":
                        raise ModuleNotFoundError(name=name)
            sys.meta_path.insert(0, NoBotocore())
            from mountainash_transport import resolve_native_read
            from mountainash_transport.connections.errors import TransportConnectionError
            from mountainash_transport.settings.storage.profiles import S3StorageProfile
            from mountainash_auth_client import IAMAuthProfile
            try:
                resolve_native_read("s3://bucket/key",
                    storage_profile=S3StorageProfile(REGION="us-east-1"),
                    auth_profile=IAMAuthProfile(ACCESS_KEY_ID="key", SECRET_ACCESS_KEY="secret"))
            except TransportConnectionError as exc:
                assert "[s3]" in str(exc)
            else:
                raise AssertionError("missing SDK became native ineligibility")
        ''')
        subprocess.run([sys.executable, "-c", script], check=True)


class TestS3InvalidAuth:
    def test_unsupported_auth_mode_keeps_existing_error(self):
        with pytest.raises(UnsupportedAuthProfileError):
            resolve_native_read("s3://bkt/k.csv", storage_profile=aws(), auth_profile=TokenAuthProfile(TOKEN="t"))

    def test_assume_role_on_non_sts_flavor_keeps_existing_error(self):
        with pytest.raises(ValueError, match="assume-role"):
            resolve_native_read(
                "s3://bkt/k.csv", storage_profile=minio(),
                auth_profile=IAMAuthProfile(ROLE_ARN="arn:aws:iam::123456789012:role/r"),
            )

# --- named profiles ----------------------------------------------------------


PROFILES_YAML = """
storage_profiles:
  lake:
    provider: s3
    parameters:
      FLAVOR: minio
      ENDPOINT_URL: http://127.0.0.1:9000
      REGION: us-east-1
      ADDRESSING_STYLE: path
    auth:
      mode: iam
      parameters:
        ACCESS_KEY_ID: NAMEDKEY
        SECRET_ACCESS_KEY: named-secret
  ambient-lake:
    provider: s3
    parameters:
      FLAVOR: aws
      REGION: us-east-1
  bad-pairing:
    provider: s3
    parameters:
      FLAVOR: aws
    auth:
      mode: token
      parameters:
        TOKEN: t
"""


@pytest.fixture
def named(tmp_path, monkeypatch):
    config = tmp_path / "profiles.yaml"
    config.write_text(PROFILES_YAML)
    monkeypatch.setenv("MOUNTAINASH_PROFILES_CONFIG", str(config))


class TestNamedProfiles:
    def test_named_profile_supplies_static_credentials_and_options(self, named):
        access = resolve_native_read("s3://bkt/k.parquet", storage_profile="lake")
        assert dict(access.connection_options) == {
            "access_key_id": "NAMEDKEY",
            "secret_access_key": "named-secret",
            "region": "us-east-1",
            "endpoint_url": "http://127.0.0.1:9000",
            "use_ssl": True,
            "verify_tls": True,
            "addressing_style": "path",
        }

    def test_explicit_auth_replaces_named_auth(self, named):
        other = IAMAuthProfile(ACCESS_KEY_ID="EXPLICITKEY", SECRET_ACCESS_KEY="explicit-secret")
        options = dict(resolve_native_read("s3://bkt/k.parquet", storage_profile="lake",
                                           auth_profile=other).connection_options)
        assert (options["access_key_id"], options["secret_access_key"]) == ("EXPLICITKEY", "explicit-secret")

    def test_explicit_noauth_replaces_named_credentials_with_ambient_fallback(self, named):
        assert resolve_native_read("s3://bkt/k.parquet", storage_profile="lake",
                                   auth_profile=NoAuthProfile()) is None

    def test_named_profile_without_credentials_is_ambient_fallback(self, named):
        assert resolve_native_read("s3://bkt/k.parquet", storage_profile="ambient-lake") is None

    def test_unknown_name_and_bad_pairing_keep_their_errors(self, named):
        from mountainash_transport import ProfileNotFoundError

        with pytest.raises(ProfileNotFoundError):
            resolve_native_read("s3://bkt/k", storage_profile="nope")
        with pytest.raises(UnsupportedAuthProfileError):
            resolve_native_read("s3://bkt/k", storage_profile="bad-pairing")


# --- HTTP ---------------------------------------------------------------------


class TestHttp:
    def test_default_http_is_anonymous_with_verified_tls(self):
        access = resolve_native_read("https://example.com/data.csv")
        assert (access.location, access.scheme, access.provider, access.policy) == (
            "https://example.com/data.csv", "https", "http", None,
        )
        assert dict(access.connection_options) == {"anonymous": True, "verify_tls": True}

    def test_noauth_http_with_explicit_options_carries_them_all(self):
        profile = HTTPStorageProfile(
            VERIFY_SSL=False, TIMEOUT_CONNECT=2.0, TIMEOUT_READ=5.0,
            FOLLOW_REDIRECTS=False, MAX_REDIRECTS=3, HEADERS={"X-Trace": "abc"},
        )
        access = resolve_native_read("http://example.com/d.csv", storage_profile=profile,
                                     auth_profile=NoAuthProfile())
        assert dict(access.connection_options) == {
            "anonymous": True, "verify_tls": False, "connect_timeout": 2.0, "read_timeout": 5.0,
            "follow_redirects": False, "max_redirects": 3, "headers": ((b"X-Trace", b"abc"),),
        }
        assert "abc" not in repr(access)

    def test_byte_headers_preserve_wire_values(self):
        profile = HTTPStorageProfile(HEADERS={b"X-Selection": b"\xffvalue"})
        access = resolve_native_read("https://example.com/data.csv", storage_profile=profile)
        assert access.connection_options["headers"] == ((b"X-Selection", b"\xffvalue"),)

    @pytest.mark.parametrize("auth", [None, NoAuthProfile(), TokenAuthProfile(TOKEN="t")])
    def test_url_userinfo_is_authenticated_input_and_falls_back(self, auth):
        assert resolve_native_read("https://user:pw@example.com/d.csv", auth_profile=auth) is None

    def test_authenticated_http_falls_back_to_transport(self):
        assert resolve_native_read("https://example.com/d.csv",
                                   auth_profile=TokenAuthProfile(TOKEN="secret-token")) is None

    def test_unsupported_auth_mode_for_http_is_an_error(self):
        with pytest.raises(UnsupportedAuthProfileError):
            resolve_native_read("https://example.com/d.csv", auth_profile=STATIC)

    def test_active_policy_is_enforced_and_represented(self):
        allowed = LocationPolicy(allowed_remote={"https": frozenset({"example.com"})})
        assert resolve_native_read("https://example.com/d.csv", policy=allowed).policy == allowed
        with pytest.raises(LocationNotAllowed):
            resolve_native_read("https://elsewhere.test/d.csv", policy=allowed)
