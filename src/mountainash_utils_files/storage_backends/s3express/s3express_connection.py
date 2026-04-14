"""S3ExpressConnectionMixin — boto3 connection management for AWS S3 Express."""

from __future__ import annotations

import typing as t

from mountainash_utils_files.exceptions import StorageConnectionError


class S3ExpressConnectionMixin:
    """Connection mixin for AWS S3 Express One Zone using boto3.

    Expects ``self.auth_params`` to expose a ``settings`` attribute with:
    - ``ENDPOINT_URL``
    - ``ACCESS_KEY_ID``
    - ``SECRET_ACCESS_KEY`` (may be a SecretStr)
    - ``REGION``
    """

    _client: t.Any  # set by __init__ of the composed class or by connect()

    def connect(self) -> None:
        """Create and cache a boto3 S3 client for S3 Express One Zone.

        Raises:
            StorageConnectionError: if the boto3 client cannot be created.
        """
        try:
            import boto3  # type: ignore[import-untyped]

            settings = self.auth_params.settings  # type: ignore[attr-defined]

            secret = settings.SECRET_ACCESS_KEY
            secret_str: t.Optional[str] = (
                secret.get_secret_value() if hasattr(secret, "get_secret_value") else secret
            )

            self._client = boto3.client(
                "s3",
                endpoint_url=getattr(settings, "ENDPOINT_URL", None),
                aws_access_key_id=getattr(settings, "ACCESS_KEY_ID", None),
                aws_secret_access_key=secret_str,
                region_name=getattr(settings, "REGION", None),
            )
        except Exception as exc:
            raise StorageConnectionError(
                f"Failed to create S3 Express client: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Release the cached boto3 client."""
        self._client = None  # type: ignore[assignment]

    def is_connected(self) -> bool:
        """Return True if a client has been created."""
        return self._client is not None
