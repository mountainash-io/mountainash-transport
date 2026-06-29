"""S3Connection — leaf connection creating an authenticated boto3 S3 client."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError

from .._core.protocols import ConnectionProtocol

try:
    import botocore.session
    from botocore.credentials import (
        AssumeRoleCredentialFetcher,
        DeferredRefreshableCredentials,
    )
except ImportError:  # pragma: no cover - botocore ships with boto3
    botocore = None  # type: ignore[assignment]
    AssumeRoleCredentialFetcher = None  # type: ignore[assignment]
    DeferredRefreshableCredentials = None  # type: ignore[assignment]


class S3Connection(ConnectionProtocol):
    """Creates an authenticated boto3 S3 client from connect kwargs + auth strategy."""

    def __init__(self, connect_kwargs: dict[str, t.Any]) -> None:
        self._connect_kwargs = connect_kwargs
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise TransportConnectionError("boto3 is required for S3 connections") from exc

        try:
            if "client_config" in self._connect_kwargs:
                self._client = self._build_via_session(boto3)
            else:
                kwargs = dict(self._connect_kwargs)
                kwargs.pop("service_name", None)
                self._client = boto3.client("s3", **kwargs)
        except (ValueError, TransportConnectionError):
            raise
        except Exception as exc:
            raise TransportConnectionError(f"Failed to create S3 client: {exc}") from exc

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
        if profile_name and has_keys:
            raise ValueError(
                "Ambiguous S3 credentials: set either PROFILE_NAME or explicit "
                "keys on the IAMAuthProfile, not both."
            )
        region = session_inputs.get("region_name")

        if profile_name:
            source = boto3.Session(profile_name=profile_name, region_name=region)
        elif has_keys:
            source = boto3.Session(**session_inputs)
        else:
            source = boto3.Session(region_name=region)

        if not role_arn:
            return source.client("s3", **client_config)

        bc = source._session
        verify = client_config.get("verify", True)

        def _sts_creator(*a: t.Any, **k: t.Any) -> t.Any:
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
        target._credentials = DeferredRefreshableCredentials(
            fetcher.fetch_credentials, "assume-role"
        )
        if region:
            target.set_config_variable("region", region)
        return boto3.Session(botocore_session=target).client("s3", **client_config)

    def disconnect(self) -> None:
        self._client = None

    @property
    def client(self) -> t.Any:
        return self._client

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
