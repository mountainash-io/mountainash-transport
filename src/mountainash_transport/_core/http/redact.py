"""Redaction of URL userinfo (``user:password@``) from text and URLs."""
from __future__ import annotations

import re

# scheme "://" then userinfo (no "/", "?", "#" or whitespace) then "@".
_USERINFO = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.\-]*://)[^/?#\s@]*@")

REDACTED = "***"


def redact_userinfo(text: str) -> str:
    """Replace the userinfo of every ``scheme://userinfo@`` in *text* with ``***``."""
    return _USERINFO.sub(lambda m: f"{m.group('scheme')}{REDACTED}@", text)
