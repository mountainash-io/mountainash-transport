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

    def __truediv__(self, name: str) -> _GenericSchemePath:
        """Support path joining via `/` so StoragePath.join works uniformly."""
        base = str(self).rstrip("/")
        clean = name.strip("/\\")
        return _GenericSchemePath(f"{base}/{clean}") if clean else _GenericSchemePath(base)


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
    def join(
        cls,
        path: Union[str, UPath, None],
        name: Optional[str],
    ) -> Optional[_NormalizedPath]:
        """Return normalize(path) / stripped(name). None if either is falsy."""
        if path is None or name is None:
            return None
        clean_name = name.strip("/\\") if len(name) > 0 else ""
        if not clean_name:
            return None
        base = cls.normalize(path)
        if base is None:
            return None
        return base / clean_name

    @classmethod
    def normalize(cls, path: Union[str, UPath, None]) -> Optional[_NormalizedPath]:
        """Normalize a path (see module docstring for contract)."""
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
        cls._check_strict_casing(text, scheme)
        cls._check_url_form(text)
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

    @staticmethod
    def _check_strict_casing(text: str, canonical_scheme: str) -> None:
        """Reject mixed-case schemes when the SchemeSpec is strict.

        Extracts the literal prefix up to the first ':' from `text` and
        compares it to the canonical scheme. Aliases in the input must also
        be lowercase to be accepted.
        """
        raw_prefix = text.split(":", 1)[0]
        spec = SCHEMES[canonical_scheme]
        if not spec.strict:
            return
        # Accept canonical form OR a lowercase alias; reject anything else.
        if raw_prefix == canonical_scheme:
            return
        if raw_prefix in _ALIAS_TO_CANONICAL and raw_prefix == raw_prefix.lower():
            return
        raise ValueError(
            f"mixed-case scheme not accepted: {raw_prefix!r} "
            f"(expected lowercase canonical {canonical_scheme!r})"
        )

    @staticmethod
    def _check_url_form(text: str) -> None:
        """Reject `scheme:x` (missing `//`) — urlparse accepts it but it's ambiguous."""
        colon = text.find(":")
        if colon < 0:
            return
        if text[colon : colon + 3] != "://":
            raise ValueError(
                f"malformed URL — missing '//' after scheme: {text!r}"
            )
