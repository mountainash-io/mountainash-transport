"""S3Connection — leaf connection creating an authenticated boto3 S3 client."""
from __future__ import annotations

import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError

from .._core.protocols import ConnectionProtocol

class S3Connection(ConnectionProtocol):
    """Creates an authenticated boto3 S3 client from connect kwargs + auth strategy."""

    def __init__(self, connect_kwargs: dict[str, t.Any]) -> None:
        self._connect_kwargs = connect_kwargs
        self._client: t.Any = None

    def connect(self) -> Self:
        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError as exc:
            raise TransportConnectionError(
                "boto3 is required for S3 connections"
            ) from exc

        kwargs = dict(self._connect_kwargs)

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
