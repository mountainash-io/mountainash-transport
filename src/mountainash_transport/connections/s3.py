"""S3Connection — leaf connection creating an authenticated boto3 S3 client."""
from __future__ import annotations

import typing as t
from types import TracebackType

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError

from .._core.extras import raise_for_missing_extra
from .._core.protocols import ConnectionProtocol
from .._core.s3_capture import install_client_hooks
from .._core.safe_display import add_cleanup_note, raise_safe, safe_detail


class S3Connection(ConnectionProtocol):
    """Creates an authenticated boto3 S3 client from connect kwargs + auth strategy."""

    def __init__(self, connect_kwargs: dict[str, t.Any]) -> None:
        self._connect_kwargs = connect_kwargs
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import boto3
        except ImportError as exc:
            raise_for_missing_extra("S3 connections", "s3", exc)

        self.disconnect()
        session = self._connect_kwargs.get("session") if "client_config" in self._connect_kwargs else None
        if session and session.get("profile_name") and "aws_access_key_id" in session:
            raise ValueError(
                "Ambiguous S3 credentials: set either PROFILE_NAME or explicit "
                "keys on the IAMAuthProfile, not both."
            )
        try:
            if "client_config" in self._connect_kwargs:
                self._client = self._build_via_session(boto3)
            else:
                kwargs = dict(self._connect_kwargs)
                kwargs.pop("service_name", None)
                self._client = boto3.client("s3", **kwargs)
            install_client_hooks(self._client)  # before the client is shared
        except TransportConnectionError:
            raise
        except Exception as exc:
            raise_safe(TransportConnectionError(f"Failed to create S3 client ({safe_detail(exc)})"), exc)

        return self

    def _build_via_session(self, boto3: t.Any) -> t.Any:
        env = self._connect_kwargs
        session_inputs = dict(env["session"])
        client_config = dict(env["client_config"])
        client_config.pop("service_name", None)
        role_arn = env.get("role_arn")
        session_name = env.get("session_name", "mountainash-transport")

        profile_name = session_inputs.pop("profile_name", None)
        has_keys = "aws_access_key_id" in session_inputs
        region = session_inputs.get("region_name")

        if profile_name:
            source = boto3.Session(profile_name=profile_name, region_name=region)
        elif has_keys:
            source = boto3.Session(**session_inputs)
        else:
            source = boto3.Session(region_name=region)

        if not role_arn:
            return source.client("s3", **client_config)

        try:
            import botocore.session
            from botocore.credentials import (
                AssumeRoleCredentialFetcher,
                DeferredRefreshableCredentials,
            )
        except ImportError as exc:
            raise_for_missing_extra("assume-role S3 connections", "s3", exc)

        bc = source._session
        # No default: an absent verify lets botocore resolve AWS_CA_BUNDLE / ca_bundle.
        verify = client_config.get("verify")

        def _sts_creator(*a: t.Any, **k: t.Any) -> t.Any:
            if verify is not None:
                k.setdefault("verify", verify)
            return bc.create_client(*a, **k)

        src_creds = bc.get_credentials()
        if src_creds is None:
            raise TransportConnectionError(
                "assume-role requested but no source AWS credentials could be "
                "resolved (no explicit keys, named profile, or ambient credentials)."
            )

        fetcher = AssumeRoleCredentialFetcher(
            client_creator=_sts_creator,
            source_credentials=src_creds,
            role_arn=role_arn,
            extra_args={"RoleSessionName": session_name},
        )
        target = botocore.session.get_session()
        # botocore has no public setter for refreshable credentials; this is
        # the documented assume-role session recipe.
        target._credentials = DeferredRefreshableCredentials(  # type: ignore[attr-defined]
            fetcher.fetch_credentials, "assume-role"
        )
        if region:
            target.set_config_variable("region", region)
        return boto3.Session(botocore_session=target).client("s3", **client_config)

    def _assumes_role(self) -> bool:
        """True if connecting calls AWS STS: an explicit ROLE_ARN, or a named AWS
        profile whose config sets ``role_arn`` (botocore then assumes the role)."""
        env = self._connect_kwargs
        if "client_config" not in env:
            return False
        if env.get("role_arn"):
            return True
        profile_name = env["session"].get("profile_name")
        if not profile_name:
            return False
        try:
            import boto3
            import botocore.exceptions
        except ImportError as exc:
            raise_for_missing_extra("S3 connections", "s3", exc)

        try:
            config = boto3.Session(profile_name=profile_name)._session.full_config
        except botocore.exceptions.ProfileNotFound:
            return False  # connect() reports the missing profile
        return bool(config.get("profiles", {}).get(profile_name, {}).get("role_arn"))

    def disconnect(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                raise_safe(TransportConnectionError(f"Failed to close S3 client ({safe_detail(exc)})"), exc)

    @property
    def client(self) -> t.Any:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc_value: BaseException | None, traceback: TracebackType | None,
    ) -> None:
        try:
            self.disconnect()
        except BaseException as cleanup:
            if exc_value is None:
                raise
            add_cleanup_note(exc_value, "Connection cleanup also failed", cleanup)
