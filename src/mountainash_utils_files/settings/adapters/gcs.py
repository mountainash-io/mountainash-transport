"""google-cloud-storage adapter — builds Client kwargs from a profile.

Produces a dict suitable for ``google.cloud.storage.Client(**kwargs)``.
Resolves credentials from the discriminated ``auth`` union on the
profile; forwards ``API_ENDPOINT`` / ``USER_PROJECT`` through
``client_options``.

All ``google.*`` imports are lazy to avoid a hard dependency on
google-cloud-storage for pure-settings usage.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import AuthMode, IAMAuth, NoAuth, OAuth2Auth, ServiceAccountAuth, TokenAuth

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]

_GCS_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/devstorage.read_write",
)


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _resolve_credentials(auth: AuthMode | None) -> t.Any:
    """Resolve a google-auth ``Credentials`` instance (or ``None``) from auth.

    - ``ServiceAccountAuth`` with ``file``  → ``from_service_account_file``
    - ``ServiceAccountAuth`` with ``info``  → ``from_service_account_info``
    - ``TokenAuth``                         → ``google.oauth2.credentials.Credentials(token=...)``
    - ``OAuth2Auth``                        → token-based Credentials with refresh data
    - ``IAMAuth`` / ``NoAuth`` / missing    → ``None`` (SDK falls back to ADC or anonymous)
    """
    if auth is None:
        return None

    if isinstance(auth, ServiceAccountAuth):
        sa_file = auth.FILE
        sa_info = auth.INFO
        if sa_file:
            from google.oauth2 import service_account  # type: ignore[import-untyped]

            return service_account.Credentials.from_service_account_file(
                str(sa_file), scopes=list(_GCS_SCOPES)
            )
        if sa_info:
            from google.oauth2 import service_account  # type: ignore[import-untyped]

            return service_account.Credentials.from_service_account_info(
                sa_info, scopes=list(_GCS_SCOPES)
            )
        return None

    if isinstance(auth, TokenAuth):
        token = _unwrap_secret(auth.TOKEN)
        if not token:
            return None
        from google.oauth2.credentials import (  # type: ignore[import-untyped]
            Credentials,
        )

        return Credentials(token=token)

    if isinstance(auth, OAuth2Auth):
        access_token = _unwrap_secret(auth.TOKEN)
        refresh_token = _unwrap_secret(auth.REFRESH_TOKEN)
        client_id = auth.CLIENT_ID
        client_secret = _unwrap_secret(auth.CLIENT_SECRET)
        token_uri = auth.SERVER_URI or "https://oauth2.googleapis.com/token"
        if not access_token and not refresh_token:
            return None
        from google.oauth2.credentials import (  # type: ignore[import-untyped]
            Credentials,
        )

        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=list(_GCS_SCOPES),
        )

    # IAMAuth / NoAuth / anything else: let the SDK's ambient resolution
    # (google.auth.default() / anonymous client) take over.
    return None


def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
    """Build ``google.cloud.storage.Client`` kwargs from a :class:`GCSSettings` profile.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[Profile], dict[str, Any]]``
    contract; callers always pass a :class:`GCSSettings` instance in
    practice.
    """
    project = getattr(profile, "PROJECT", None)
    api_endpoint = getattr(profile, "API_ENDPOINT", None)
    user_project = getattr(profile, "USER_PROJECT", None)

    credentials = _resolve_credentials(auth)

    kwargs: dict[str, t.Any] = {
        "project": project,
        "credentials": credentials,
    }

    # NoAuth signals that the caller wants an anonymous client. Pass a
    # hint the handler can act on; google-cloud-storage exposes
    # ``Client.create_anonymous_client()`` rather than a constructor flag.
    if isinstance(auth, NoAuth):
        kwargs["anonymous"] = True

    client_options_kwargs: dict[str, t.Any] = {}
    if api_endpoint:
        client_options_kwargs["api_endpoint"] = api_endpoint
    if user_project:
        client_options_kwargs["quota_project_id"] = user_project

    if client_options_kwargs:
        try:
            from google.api_core.client_options import (  # type: ignore[import-untyped]
                ClientOptions,
            )

            kwargs["client_options"] = ClientOptions(**client_options_kwargs)
        except ImportError:
            # google-api-core not installed — pass the raw dict; the
            # handler can lazily wrap it.
            kwargs["client_options"] = client_options_kwargs

    return kwargs
