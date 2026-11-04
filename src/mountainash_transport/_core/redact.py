"""Redaction of URL credentials (userinfo, query values) from text — stdlib only.

Each helper is a single left-to-right scan, linear in the input length.
"""
from __future__ import annotations

import re
import typing as t

REDACTED = "***"

# Start of a URL scheme: not preceded by a scheme character, so a long run of
# letters is entered once rather than at every offset.
_SCHEME = re.compile(r"(?<![A-Za-z0-9+.\-])[A-Za-z][A-Za-z0-9+.\-]*://")
_AUTHORITY_END = re.compile(r"[/?#\s]")
_URL_END = re.compile(r"\s")


def redact_userinfo(text: str) -> str:
    """Replace the userinfo of every ``scheme://userinfo@`` in *text* with ``***``.

    Userinfo runs to the last ``@`` of the authority, as ``urlsplit`` reads it,
    so a raw ``@`` inside a password is masked too.
    """
    out: list[str] = []
    pos = 0
    while (match := _SCHEME.search(text, pos)) is not None:
        start = match.end()
        end_match = _AUTHORITY_END.search(text, start)
        end = end_match.start() if end_match else len(text)
        at = text.rfind("@", start, end)
        out.append(text[pos:start])
        out.append(f"{REDACTED}{text[at:end]}" if at >= 0 else text[start:end])
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _mask_query(query: str) -> str:
    return "&".join(
        f"{p.split('=', 1)[0]}={REDACTED}" if "=" in p else (REDACTED if p else p)
        for p in query.split("&")
    )


def _mask_query_in(segment: str) -> str:
    """Mask the query values of one URL or location (no whitespace inside)."""
    q = segment.find("?")
    if q < 0:
        return segment
    h = segment.find("#", q)
    end = h if h >= 0 else len(segment)
    return segment[: q + 1] + _mask_query(segment[q + 1 : end]) + segment[end:]


def redact_url(text: str) -> str:
    """Redact userinfo and every query value of each URL in *text* (error surfaces).

    Query values may be signatures or tokens (presigned URLs, ``?token=``);
    keys stay visible for diagnosis.
    """
    text = redact_userinfo(text)
    out: list[str] = []
    pos = 0
    while (match := _SCHEME.search(text, pos)) is not None:
        end_match = _URL_END.search(text, match.end())
        end = end_match.start() if end_match else len(text)
        out.append(text[pos : match.start()])
        out.append(_mask_query_in(text[match.start() : end]))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def redact_location(location: str) -> str:
    """Redact one location string, URL or not; never raises.

    Userinfo is removed the way ``urlsplit`` reads it (``scheme://user@host`` →
    ``scheme://host``); a location without ``//`` whose first segment holds an
    ``@`` (``user:pass@host/x``, ``s3:user:pw@bucket``) has that prefix replaced
    with ``***@``. Query values are masked, keys kept.
    """
    text = location.strip("".join(chr(c) for c in range(0x21)))
    for ch in "\t\r\n":
        text = text.replace(ch, "")
    slashes = text.find("//")
    start = slashes + 2 if slashes >= 0 else 0
    end_match = re.compile(r"[/?#]").search(text, start)
    end = end_match.start() if end_match else len(text)
    at = text.rfind("@", start, end)
    if at >= 0:
        text = text[:start] + text[at + 1 :] if slashes >= 0 else f"{REDACTED}{text[at:]}"
    return _mask_query_in(text)


def _safe_cause(exc: BaseException, url: str = "") -> BaseException | None:
    """Return *exc* as a displayable cause, or ``None`` if its chain holds credentials.

    Follows the chain Python would display. Raise with :func:`raise_redacted`,
    which also drops the hidden ``__context__`` when the cause is withheld.
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


def raise_redacted(error: BaseException, native: BaseException, url: str = "") -> t.NoReturn:
    """Raise *error* from *native*, or with no reachable native chain if it holds credentials.

    Call from inside the ``except`` block handling *native*. ``raise ... from None``
    alone hides the native exception from tracebacks but keeps it in
    ``__context__``; this clears that too.
    """
    cause = _safe_cause(native, url)
    try:
        raise error from cause
    finally:
        if cause is None:
            error.__context__ = None
