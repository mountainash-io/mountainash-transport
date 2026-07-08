"""OAuth2 render adapter: bridges auth-client's OAuth2TokenManager to the HTTP
engine's RefreshableAuthStrategy seam. Transport CONFIGURES/renders; auth-client
owns acquire()/refresh()."""
from __future__ import annotations

import threading
import typing as t

from mountainash_auth_client.oauth.lifecycle.oauth2 import OAuth2TokenManager


class OAuth2RefreshableAuthStrategy:
    """RefreshableAuthStrategy over an OAuth2TokenManager (thread-safe)."""

    def __init__(self, manager: OAuth2TokenManager) -> None:
        self._mgr = manager
        self._cred: t.Any = None
        self._lock = threading.Lock()

    def get_headers(self) -> dict[str, str]:
        with self._lock:
            if self._cred is None:
                self._cred = self._mgr.acquire()      # refresh-if-stale (auth-client)
            return {"Authorization": f"{self._cred.token_type} {self._cred.access_token}"}

    def refresh(self) -> bool:
        with self._lock:
            self._cred = self._mgr.refresh()          # force-refresh (auth-client)
            return True

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return kwargs                                 # engine injects via get_headers()


def create_auth_strategy(
    auth_profile: t.Any,
    *,
    oauth_provider: t.Any = None,
    secret_resolver: t.Any = None,
) -> OAuth2RefreshableAuthStrategy | None:
    """Build the managed OAuth2 strategy, or None for the static-token path.

    None when no oauth_provider (static-token path). Raises on a provider without a
    resolver, or an oauth_provider paired with a non-OAuth2 auth profile (a
    misconfiguration surfaced fail-closed rather than silently ignoring the provider).
    """
    from mountainash_auth_client import OAuth2AuthProfile

    if oauth_provider is None:
        return None
    if not isinstance(auth_profile, OAuth2AuthProfile):
        raise ValueError(
            "oauth_provider supplied with a non-OAuth2 auth profile "
            f"({type(auth_profile).__name__})."
        )
    if secret_resolver is None:
        raise ValueError(
            "OAuth2 managed flow requires secret_resolver (no default — "
            "pass the SecretStoreResolver for the token store)."
        )
    manager = OAuth2TokenManager(oauth_provider, auth_profile, resolver=secret_resolver)
    return OAuth2RefreshableAuthStrategy(manager)
