"""Logging filters that keep request/response data out of httpx and httpcore records (W8).

httpx logs the full request URL (userinfo, query, fragment) at INFO; httpcore logs
pre-formatted event text, including response header lists, at DEBUG. The filters attach
to the emitting loggers themselves, so the guarantee holds at any level the application
sets. They only reduce records; they never change levels or handlers.
"""

from __future__ import annotations

import logging
import re

from mountainash_transport._core.safe_display import safe_location

# Every logger httpcore emits on (logging.getLogger calls in httpcore/_sync and _async).
HTTPCORE_LOGGERS = (
    "httpcore.connection",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
)
# httpcore events whose arguments are connection details (host, port, TLS settings), not
# request or response data; every other event is reduced to its name.
_KEEP_EVENTS = ("connect_tcp.", "connect_unix_socket.", "start_tls.")
_URL_STRING = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _display(arg: object) -> object:
    import httpx

    if isinstance(arg, httpx.URL):
        return safe_location(str(arg))
    if isinstance(arg, str) and _URL_STRING.match(arg):
        return safe_location(arg)
    return arg


class _HttpxFilter(logging.Filter):
    """Show every URL in a record's arguments in display form."""

    _w8_log_filter = True

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_display(arg) for arg in record.args)
        elif isinstance(record.args, dict):
            record.args = {key: _display(arg) for key, arg in record.args.items()}
        return True


class _HttpcoreFilter(logging.Filter):
    """Reduce an event that carries request or response data to its name."""

    _w8_log_filter = True

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        event = message.split(" ", 1)[0]
        if not event.startswith(_KEEP_EVENTS):
            record.msg, record.args = event, None
        return True


def _attach(name: str, filter_type: type[logging.Filter]) -> None:
    logger = logging.getLogger(name)
    if not any(getattr(existing, "_w8_log_filter", False) for existing in logger.filters):
        logger.addFilter(filter_type())


def install_log_filters() -> None:
    """Attach the filters; calling it again adds nothing."""
    _attach("httpx", _HttpxFilter)
    for name in HTTPCORE_LOGGERS:
        _attach(name, _HttpcoreFilter)
