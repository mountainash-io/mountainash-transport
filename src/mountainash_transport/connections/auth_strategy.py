"""OAuth2 render adapter: bridges auth-client's OAuth2TokenManager to the HTTP
engine's RefreshableAuthStrategy seam. Transport CONFIGURES/renders; auth-client
owns acquire()/refresh()."""
from __future__ import annotations

import threading
import typing as t

if t.TYPE_CHECKING:
    from mountainash_auth_client.oauth.lifecycle.oauth2 import OAuth2TokenManager


class OAuth2RefreshableAuthStrategy:
    """RefreshableAuthStrategy over an OAuth2TokenManager (thread-safe)."""

    def __init__(self, manager: "OAuth2TokenManager") -> None:
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
