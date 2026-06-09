"""S3Connection — leaf connection creating an authenticated boto3 S3 client."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

from mountainash_transport._core.auth.strategies import AuthStrategy
from mountainash_transport.connections.errors import TransportConnectionError
from mountainash_transport.settings.profile_protocol import StorageProfileProtocol


class S3Connection:
    """Creates an authenticated boto3 S3 client from profile config + auth strategy."""

    def __init__(
        self,
        profile: StorageProfileProtocol,
        auth_strategy: AuthStrategy,
    ) -> None:
        self._profile = profile
        self._auth_strategy = auth_strategy
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise TransportConnectionError(
                "boto3 is required for S3 connections"
            ) from exc

        kwargs = self._profile.to_handler_kwargs()
        kwargs = self._auth_strategy.apply(kwargs)

        # Strip the profile's service_name (boto3.client takes it positionally).
        kwargs.pop("service_name", None)

        try:
            self._client = boto3.client("s3", **kwargs)
        except Exception as exc:
            raise TransportConnectionError(
                f"Failed to create S3 client: {exc}"
            ) from exc

        return self

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
