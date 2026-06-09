"""S3ConnectionMixin — boto3 connection management for the S3 family.

Flavor dispatch lives here: ``auth_params.settings.FLAVOR`` selects
between AWS S3, S3 Express, Cloudflare R2, MinIO, and Backblaze B2.
Legacy ``auth_params.settings`` shapes (without FLAVOR) fall back to the
pre-consolidation AWS S3 behaviour for backwards compatibility.

Preferred path is ``auth_params.to_handler_kwargs()`` on an
:class:`~mountainash_transport.settings.providers.s3_settings.S3Settings`
profile; the adapter (``settings.adapters.s3``) resolves flavor-specific
endpoints up front and returns boto3 kwargs directly.
"""

from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import StorageConnectionError

from mountainash_transport.storage.protocols import StorageConnectionProtocol

class S3ConnectionMixin(StorageConnectionProtocol):
    """Connection mixin wrapping ``boto3.client("s3", ...)``.

    The mixin accepts three ``auth_params`` shapes for compatibility:

    1. An :class:`S3Settings` profile with ``to_handler_kwargs()`` — the
       adapter resolves flavor-specific kwargs and returns them directly.
    2. A legacy wrapper exposing a ``.settings`` attribute with
       ``ENDPOINT_URL`` / ``ACCESS_KEY_ID`` / ``SECRET_ACCESS_KEY`` /
       ``REGION`` fields (optionally ``FLAVOR``, ``ACCOUNT_ID``,
       ``USE_SSL``). Used by the existing unit-test mocks.
    3. ``None`` — caller will set ``_client`` manually (test shim).
    """

    _client: t.Any  # set by __init__ of the composed class or by connect()

    def connect(self) -> None:
        """Create and cache a boto3 S3 client.

        Raises:
            StorageConnectionError: if the boto3 client cannot be created.
        """
        try:
            import boto3  # type: ignore[import-untyped]

            storage_profile = self.storage_profile  # type: ignore[attr-defined]

            kwargs = storage_profile.to_handler_kwargs()

            # Strip the adapter's service_name (boto3.client takes it
            # positionally) so the call is always ``boto3.client("s3", ...)``.
            kwargs.pop("service_name", None)
            self._client = boto3.client("s3", **kwargs)
        except StorageConnectionError:
            raise
        except Exception as exc:
            raise StorageConnectionError(
                f"Failed to create S3 client: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Release the cached boto3 client."""
        self._client = None  # type: ignore[assignment]

    def is_connected(self) -> bool:
        """Return True if a client has been created."""
        return self._client is not None


    # def _resolve_kwargs(self) -> dict[str, t.Any]:
    #     """Return boto3 client kwargs for the wrapped auth_params shape."""
    #     storage_profile = self.storage_profile  # type: ignore[attr-defined]
    #     auth_profile = self.auth_profile  # type: ignore[attr-defined]


    #     # Shape 1: S3Settings profile (preferred). Use the class-level
    #     # descriptor check rather than ``hasattr`` — MagicMock auto-generates
    #     # ``to_handler_kwargs`` on access, which would otherwise match.
    #     cls = type(storage_profile)
    #     is_profile = (
    #         any("to_handler_kwargs" in b.__dict__ for b in cls.__mro__)
    #         and not hasattr(storage_profile, "_mock_name")
    #     )
    #     if is_profile:
    #         kwargs = storage_profile.to_handler_kwargs(auth_profile)
    #         if isinstance(kwargs, dict) and "base_kwargs" in kwargs:
    #             # STS assume-role dispatch — not implemented at this layer.
    #             raise StorageConnectionError(
    #                 "ROLE_ARN dispatch (STS assume-role) is not yet "
    #                 "implemented in S3ConnectionMixin; call "
    #                 "profile.to_handler_kwargs() and perform STS before "
    #                 "instantiating the backend."
    #             )
    #         return kwargs

        # # Shape 2: legacy ``.settings`` wrapper.
        # settings = getattr(storage_profile, "settings", None)
        # if settings is None:
        #     raise StorageConnectionError(
        #         "auth_params must be an S3Settings profile or expose a "
        #         "`settings` attribute."
        #     )

        # flavor = getattr(settings, "FLAVOR", None) or "aws"
        # endpoint_url = getattr(settings, "ENDPOINT_URL", None)
        # account_id = getattr(settings, "ACCOUNT_ID", None)

        # # Flavor-specific endpoint URL resolution for legacy mocks.
        # if flavor == "r2":
        #     endpoint_url = endpoint_url or (
        #         f"https://{account_id}.r2.cloudflarestorage.com"
        #         if account_id
        #         else None
        #     )
        #     region = "auto"
        # else:
        #     region = getattr(settings, "REGION", None)

        # secret = getattr(settings, "SECRET_ACCESS_KEY", None)
        # secret_str: t.Optional[str]
        # if secret is None:
        #     secret_str = None
        # elif hasattr(secret, "get_secret_value"):
        #     secret_str = secret.get_secret_value()
        # else:
        #     secret_str = secret

        # kwargs: dict[str, t.Any] = {
        #     "endpoint_url": endpoint_url,
        #     "aws_access_key_id": getattr(settings, "ACCESS_KEY_ID", None),
        #     "aws_secret_access_key": secret_str,
        #     "region_name": region,
        # }

        # # Only pass use_ssl when explicitly set on legacy settings objects;
        # # keeps the pre-consolidation AWS S3 call signature intact for tests
        # # that don't set USE_SSL on the mock.
        # if "USE_SSL" in getattr(settings, "__dict__", {}) or (
        #     hasattr(settings, "USE_SSL") and not _is_magicmock_default(settings, "USE_SSL")
        # ):
        #     use_ssl = getattr(settings, "USE_SSL", None)
        #     if isinstance(use_ssl, bool):
        #         kwargs["use_ssl"] = use_ssl

        # return kwargs



# def _is_magicmock_default(obj: t.Any, attr: str) -> bool:
#     """Return True if ``obj.attr`` is an auto-generated MagicMock attribute.

#     MagicMock auto-creates attributes on access, yielding a non-bool value
#     for ``USE_SSL``. Tests that don't set USE_SSL on their mock settings
#     should not have ``use_ssl`` appear in the boto3 call.
#     """
#     # Heuristic: MagicMock attributes have a ``_mock_name`` attribute; plain
#     # bools / Nones do not.
#     val = getattr(obj, attr, None)
#     return hasattr(val, "_mock_name") and not isinstance(val, bool)
