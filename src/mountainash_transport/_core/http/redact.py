"""Redaction of URL credentials (userinfo, query values) from text and URLs."""
from __future__ import annotations

import re

# scheme "://" then userinfo (no "/", "?", "#" or whitespace) then "@".
_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)[^/?#\s@]*@")
# A URL's query: scheme "://" then anything up to "?", then up to "#" or whitespace.
_QUERY = re.compile(r"(?P<head>[A-Za-z][A-Za-z0-9+.\-]*://[^?#\s]*\?)(?P<query>[^#\s]*)")

REDACTED = "***"


def redact_userinfo(text: str) -> str:
    """Replace the userinfo of every ``scheme://userinfo@`` in *text* with ``***``."""
    return _USERINFO.sub(lambda m: f"{m.group('scheme')}{REDACTED}@", text)


def _mask_query(query: str) -> str:
    return "&".join(
        f"{p.split('=', 1)[0]}={REDACTED}" if "=" in p else (REDACTED if p else p)
        for p in query.split("&")
    )


def redact_url(text: str) -> str:
    """Redact userinfo and every query value of each URL in *text* (error surfaces).

    Query values may be signatures or tokens (presigned URLs, ``?token=``);
    keys stay visible for diagnosis.
    """
    text = redact_userinfo(text)
    return _QUERY.sub(lambda m: m.group("head") + _mask_query(m.group("query")), text)


def _safe_cause(exc: BaseException, url: str = "") -> BaseException | None:
    """Suppress credential-bearing native chains from traceback display.

    Hidden ``__context__`` and traceback locals are not sanitized. Follow only
    the chain Python would display, so already-suppressed causes stay hidden.
    """
    if redact_url(url) != url:
        return None
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current)
        if redact_url(message) != message:
            return None
        for note in getattr(current, "__notes__", ()):
            if redact_url(note) != note:
                return None
        # httpx raises RuntimeError when a RequestError has no request attached.
        try:
            request = getattr(current, "request", None)
        except RuntimeError:
            request = None
        if request is not None:
            request_url = str(request.url)
            if redact_url(request_url) != request_url:
                return None
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    return exc
