"""OAuth2 render adapter: bridges auth-client's OAuth2TokenManager to the HTTP
engine's RefreshableAuthStrategy seam. Transport CONFIGURES/renders; auth-client
owns acquire()/refresh()."""
from __future__ import annotations

import threading
import typing as t

from mountainash_auth_client.oauth.lifecycle.oauth2 import OAuth2TokenManager
from mountainash_settings.secrets import ClearableSecretStore


class OAuth2RefreshableAuthStrategy:
    """RefreshableAuthStrategy over an OAuth2TokenManager (thread-safe)."""

    def __init__(self, manager: OAuth2TokenManager) -> None:
        self._mgr = manager
        self._lock = threading.Lock()

    def get_headers(self) -> dict[str, str]:
        with self._lock:
            credential = self._mgr.acquire()      # refresh-if-stale (auth-client)
            return {"Authorization": f"{credential.token_type} {credential.access_token}"}

    def refresh(self) -> bool:
        with self._lock:
            self._mgr.refresh()          # force-refresh (auth-client)
            return True

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        # Engine injects auth via get_headers(); apply() is a no-op for this
        # strategy but still honours the protocol's "returns a NEW dict" contract
        # so a caller can safely reuse its own kwargs without aliasing.
        return dict(kwargs)


def create_auth_strategy(
    auth_profile: t.Any,
    *,
    oauth_provider: t.Any = None,
    token_store: ClearableSecretStore | None = None,
) -> OAuth2RefreshableAuthStrategy | None:
    """Build the managed OAuth2 strategy, or None for the static-token path.

    None when no oauth_provider (static-token path). Raises on a provider without a
    token store, or an oauth_provider paired with a non-OAuth2 auth profile (a
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
    if token_store is None:
        raise ValueError(
            "OAuth2 managed flow requires token_store (no default — "
            "pass a raw ClearableSecretStore, distinct from the config reader)."
        )
    manager = OAuth2TokenManager(oauth_provider, auth_profile, token_store=token_store)
    return OAuth2RefreshableAuthStrategy(manager)
