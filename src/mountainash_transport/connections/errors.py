"""Connection-specific exceptions."""
from __future__ import annotations


class TransportConnectionError(Exception):
    """Base exception for all connection operations."""


# Backwards-compatible alias during transition.
ConnectionError = TransportConnectionError


class ConnectionTimeoutError(TransportConnectionError):
    """Connection or request timed out."""


class TokenExchangeError(TransportConnectionError):
    """OAuth token endpoint returned an error during code exchange."""

    def __init__(self, *, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Token exchange failed: HTTP {status_code} POST {url} — {body[:200]}")


class TokenRefreshError(TransportConnectionError):
    """OAuth token refresh failed."""

    def __init__(self, *, url: str, status_code: int, body: str) -> None:
        self.url = url
        self.status_code = status_code
        self.body = body
        super().__init__(f"Token refresh failed: HTTP {status_code} POST {url} — {body[:200]}")


class AuthorizationRequired(TransportConnectionError):
    """No valid token exists and auto_authorize is False."""

    def __init__(self, *, provider: str, user: str) -> None:
        self.provider = provider
        self.user = user
        super().__init__(f"Authorization required for {provider}/{user}")


class UnsupportedAuthProfileError(TransportConnectionError):
    """The connection factory was given an auth profile it does not handle.

    Transport's ``create_connection`` builds storage connections; OAuth
    *authorization* flows are not a transport concern. Construct
    ``mountainash_auth_client``'s ``OAuth2Connection``/``OAuth1Connection`` with
    an ``OAuth2ProviderProfile``/``OAuth1ProviderProfile`` (which carry the
    OAuth-server coordinates) instead.
    """

    def __init__(self, profile_name: str, *, reason: str | None = None) -> None:
        self.profile_name = profile_name
        if reason is not None:
            super().__init__(f"{profile_name} is not supported: {reason}")
        else:
            super().__init__(
                f"{profile_name} is not supported by transport's create_connection; "
                "use mountainash-auth-client's OAuth2Connection/OAuth1Connection with "
                "an OAuth2ProviderProfile/OAuth1ProviderProfile instead."
            )
