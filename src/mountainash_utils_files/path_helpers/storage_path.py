"""StoragePath — parse and normalize storage paths.

Classmethod-only facade over upath.UPath + stdlib urlparse/urlunparse.
Does not dispatch to provider backends; callers own the scheme→provider
mapping (a single URL scheme can be served by multiple providers,
e.g. `s3://` → AWS S3 / MinIO / R2 / B2 / S3 Express).
"""
from __future__ import annotations

import fnmatch
from typing import Optional, Union
from urllib.parse import urlparse, urlunparse

from upath import UPath

from .scheme import SCHEMES, _ALIAS_TO_CANONICAL

# Return type for normalize: UPath for schemes fsspec supports,
# _GenericSchemePath (str subclass) for schemes that only the registry
# knows about. Callers should treat the result as path-like via str().
_NormalizedPath = Union[UPath, "_GenericSchemePath"]


class _GenericSchemePath(str):
    """Fallback path wrapper for schemes in SCHEMES that UPath cannot construct.

    UPath raises ValueError for schemes without an fsspec implementation
    (e.g. "azure", "b2", "smb"). The hygiene spec keeps those schemes in
    the registry because path parsing is decoupled from backend support.
    For those schemes, normalize() returns this string subclass — stringifies
    to the canonical URL, carries no filesystem behavior.
    """

    def __new__(cls, url: str) -> _GenericSchemePath:
        return str.__new__(cls, url)


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

    @classmethod
    def to_str(cls, path: Union[str, UPath, None]) -> Optional[str]:
        """None passthrough; otherwise `str(path)`. No normalization."""
        if path is None:
            return None
        return str(path)

    @classmethod
    def matches(cls, pattern: str, name: str) -> bool:
        """Wildcard match via fnmatch. Supports `*` and `?`."""
        return fnmatch.fnmatch(name, pattern)

    @classmethod
    def normalize(cls, path: Union[str, UPath, None]) -> Optional[_NormalizedPath]:
        """Normalize a path.

        - None or empty string → None.
        - Bare/local paths: expanduser, strip trailing slash unless length 1.
        - Schemed paths: validated + canonicalised via urlunparse (Task 5).
        - Raises ValueError on invalid schemed input (Task 6).
        """
        if path is None:
            return None
        text = str(path)
        if not text:
            return None
        scheme = cls.identify_scheme(text)
        if scheme == "":
            return cls._normalize_bare(text)
        if scheme is None:
            raise ValueError(f"Unknown scheme in path: {text!r}")
        return cls._normalize_schemed(text, scheme)

    @staticmethod
    def _normalize_bare(text: str) -> UPath:
        stripped = text.rstrip("/\\") if len(text) > 1 else text
        return UPath(stripped).expanduser()

    @staticmethod
    def _normalize_schemed(text: str, canonical_scheme: str) -> _NormalizedPath:
        parsed = urlparse(text)
        # Rebuild with the canonical scheme (lowercased/alias-resolved).
        # Preserve netloc, path, params, query, fragment verbatim.
        rebuilt_path = parsed.path.rstrip("/") if len(parsed.path) > 1 else parsed.path
        rebuilt = urlunparse((
            canonical_scheme,
            parsed.netloc,
            rebuilt_path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        ))
        try:
            return UPath(rebuilt)
        except ValueError:
            # Scheme not supported by UPath; use fallback string-based path
            return _GenericSchemePath(rebuilt)
