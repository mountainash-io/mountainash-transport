"""W8 design sections 1-2: what a transport error may show."""
from __future__ import annotations

import errno
import traceback
from pathlib import PurePosixPath

import pytest

from mountainash_transport._core.safe_display import (
    raise_safe, safe_cause, safe_detail, safe_location,
)
from mountainash_transport.location import LocationNotAllowed, LocationPolicy, require_known_scheme

# Shared across packages (spec section 5.1): keep identical to the other packages' copies.
RENDERING = [
    # scheme:// — scheme, host, port, path only
    ("https://SENTU:SENTP@h:8443/a/x.csv?sig=SENTQ#SENTF", "https://h:8443/a/x.csv"),
    ("https://SENTU:pa@SENTP@host/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@[::1]:8443/d/x.csv", "https://[::1]:8443/d/x.csv"),
    ("https://host/a@b/x.csv", "https://host/a@b/x.csv"),
    ("https://host/x.csv#access_token=SENTF", "https://host/x.csv"),
    ("https://host/x.csv?SENTQ", "https://host/x.csv"),
    ("https://host/x.csv#f?tok=SENTQ", "https://host/x.csv"),
    ("https://h#SENTF@x/y", "https://h"),
    ("https://h?SENTQ@x/y", "https://h"),
    ("https://host", "https://host"),
    ("s3://bucket/x.csv", "s3://bucket/x.csv"),
    ("file:///tmp/x.csv", "file:///tmp/x.csv"),
    ("HTTPS://SENTU:SENTP@host/x.csv", "HTTPS://host/x.csv"),
    ("postgresql+psycopg://SENTU:SENTP@db/name", "postgresql+psycopg://db/name"),
    # //network path
    ("//SENTU:SENTP@host/x.csv", "//host/x.csv"),
    # whitespace / control characters, as urllib reads them
    (" \thttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@ho\nst/x.csv", "https://host/x.csv"),
    ("https://SENTU:SENTP@ho\rst/x.csv", "https://host/x.csv"),
    ("ht\ttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("\x00https://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    ("\x1fhttps://SENTU:SENTP@host/x.csv", "https://host/x.csv"),
    # other scheme strings
    ("https:/SENTU:SENTP@host/x.csv", "***"),
    ("s3:SENTU:SENTP@bucket/x.csv", "***"),
    ("SENTU:SENTP@host/x.csv", "***"),
    ("a:SENTP@host/x.csv", "***"),
    # local paths
    ("/data/x.csv", "/data/x.csv"),
    ("data/x.csv", "data/x.csv"),
    ("/srv/team@corp/x.csv", "/srv/team@corp/x.csv"),
    ("relative/a:b@c/x.csv", "relative/a:b@c/x.csv"),
    ("C:/d/x.csv", "C:/d/x.csv"),
    ("C:\\d\\x.csv", "C:\\d\\x.csv"),
]
SENTINELS = ("SENTU", "SENTP", "SENTQ", "SENTF")


@pytest.mark.parametrize(("location", "shown"), RENDERING)
def test_safe_location_rendering(location, shown):
    assert safe_location(location) == shown


@pytest.mark.parametrize(("location", "shown"), RENDERING)
def test_location_not_allowed_shows_display_form(location, shown):
    err = LocationNotAllowed(location, "remote not allowed")
    assert err.location == shown
    assert str(err) == f"location not allowed: {shown} (remote not allowed)"
    assert err.reason == "remote not allowed"


def test_pathlike_location_is_shown_as_text():
    assert safe_location(PurePosixPath("/data/x.csv")) == "/data/x.csv"


def _chain(exc):
    pending, seen = [exc], set()
    while pending:
        current = pending.pop()
        if id(current) not in seen:
            seen.add(id(current))
            yield current
            pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)


def _assert_no_sentinel(exc):
    text = "".join(traceback.format_exception(exc))
    for link in _chain(exc):
        text += str(link) + repr(link) + repr(link.args) + repr(vars(link))
    for sentinel in SENTINELS:
        assert sentinel not in text


def test_oserror_keeps_errno_strerror_only():
    native = FileNotFoundError(errno.ENOENT, "No such file or directory", "/x/SENTU:SENTP@h/f")
    assert safe_detail(native) == "[Errno 2] No such file or directory"
    cause = safe_cause(native)
    assert type(cause) is FileNotFoundError and cause is not native
    assert (cause.errno, cause.strerror, cause.filename) == (errno.ENOENT, "No such file or directory", None)


def test_oserror_without_errno_is_class_name_and_not_chained():
    native = ConnectionResetError("peer SENTP")
    assert safe_detail(native) == "ConnectionResetError"
    assert safe_cause(native) is None


def test_other_native_is_class_name_and_unreachable():
    try:
        try:
            raise ValueError("https://SENTU:SENTP@h/?sig=SENTQ#SENTF")
        except ValueError as native:
            assert safe_detail(native) == "ValueError"
            raise_safe(RuntimeError("https://h/: storage error (ValueError)"), native)
    except RuntimeError as err:
        assert err.__cause__ is None and err.__context__ is None
        _assert_no_sentinel(err)


def test_raise_safe_chains_fresh_oserror_and_clears_context():
    try:
        try:
            raise PermissionError(errno.EACCES, "Permission denied", "/SENTP")
        except PermissionError as native:
            raise_safe(RuntimeError("x: permission denied"), native)
    except RuntimeError as err:
        assert type(err.__cause__) is PermissionError and err.__context__ is None
        _assert_no_sentinel(err)


@pytest.mark.parametrize("policy", [None, LocationPolicy(allow_unconfined=True), LocationPolicy()])
def test_unparseable_url_hides_urllib_text(policy):
    # Fullwidth colon: urllib's ValueError names the whole netloc, password included.
    location = "https://SENTU\uff1aSENTP@h/x?sig=SENTQ#SENTF"
    from mountainash_transport.storage.registry.backend_detection import detect_provider_from_path

    # An active policy keeps its established LocationNotAllowed mapping (not a ValueError).
    expected = LocationNotAllowed if policy is not None and policy.active else ValueError
    with pytest.raises(expected) as ei:
        if policy is None:
            detect_provider_from_path(location)
        else:
            require_known_scheme(location, policy)
    assert "https://h/x" in str(ei.value)
    _assert_no_sentinel(ei.value)


def test_trusted_http_error_chained_as_is_subclass_not_trusted():
    from mountainash_transport._core.http.errors import HttpNotFoundError

    trusted = HttpNotFoundError("https://h/x")
    try:
        try:
            raise trusted
        except HttpNotFoundError as native:
            raise_safe(RuntimeError("x"), native)
    except RuntimeError as err:
        assert err.__cause__ is trusted

    class Sub(HttpNotFoundError):
        pass

    try:
        try:
            raise Sub("https://h/x")
        except Sub as native:
            raise_safe(RuntimeError("x"), native)
    except RuntimeError as err:
        assert err.__cause__ is None
