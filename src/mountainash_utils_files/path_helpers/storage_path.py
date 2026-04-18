"""StoragePath — parse and normalize storage paths.

Classmethod-only facade over upath.UPath + stdlib urlparse/urlunparse.
Does not dispatch to provider backends; callers own the scheme→provider
mapping (a single URL scheme can be served by multiple providers,
e.g. `s3://` → AWS S3 / MinIO / R2 / B2 / S3 Express).
"""
from __future__ import annotations

from typing import Optional, Union
from urllib.parse import urlparse

from upath import UPath

from .scheme import SCHEMES, _ALIAS_TO_CANONICAL


class StoragePath:
    """Stateless helper for parsing and normalizing storage paths."""

    @classmethod
    def identify_scheme(cls, path: Union[str, UPath, None]) -> Optional[str]:
        """Return the canonical scheme token, "" for bare/local, or None for unknown.

        Case-insensitive; aliases resolved. Returns None (not KeyError) for
        schemes not registered in SCHEMES.
        """
        if path is None:
            return ""
        text = str(path)
        if not text:
            return ""
        raw_scheme = urlparse(text).scheme.lower()
        if not raw_scheme:
            return ""
        if raw_scheme in SCHEMES:
            return raw_scheme
        if raw_scheme in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[raw_scheme]
        return None
