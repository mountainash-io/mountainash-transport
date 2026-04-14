"""R2ConnectionMixin — boto3 connection management for Cloudflare R2."""

from __future__ import annotations

import typing as t

from mountainash_utils_files.exceptions import StorageConnectionError


class R2ConnectionMixin:
    """Connection mixin for Cloudflare R2 using boto3.

    Expects ``self.auth_params`` to expose a ``settings`` attribute with:
    - ``ACCOUNT_ID`` — Cloudflare account ID (used to build the endpoint URL)
    - ``ACCESS_KEY_ID``
    - ``SECRET_ACCESS_KEY`` (may be a SecretStr)
    """

    _client: t.Any  # set by __init__ of the composed class or by connect()

    def connect(self) -> None:
        """Create and cache a boto3 S3 client pointed at the R2 endpoint.

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

            account_id = getattr(settings, "ACCOUNT_ID", None)
            endpoint_url = (
                f"https://{account_id}.r2.cloudflarestorage.com"
                if account_id
                else getattr(settings, "ENDPOINT_URL", None)
            )

            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=getattr(settings, "ACCESS_KEY_ID", None),
                aws_secret_access_key=secret_str,
                region_name="auto",
            )
        except Exception as exc:
            raise StorageConnectionError(
                f"Failed to create R2 client: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Release the cached boto3 client."""
        self._client = None  # type: ignore[assignment]

    def is_connected(self) -> bool:
        """Return True if a client has been created."""
        return self._client is not None
