"""Shared assertion for the W8 chaining contract (``raise_safe``)."""
from __future__ import annotations


def assert_safe_cause(error: BaseException, native: BaseException) -> None:
    """*error* chains only what ``safe_cause`` allows of *native*, and no hidden context.

    An ``OSError`` with an errno becomes a fresh exception of the same type with
    the same errno and strerror; anything else (no errno, other exception types)
    is not chained.
    """
    cause = error.__cause__
    if isinstance(native, OSError) and native.errno is not None:
        assert type(cause) is type(native)
        assert isinstance(cause, OSError)
        assert (cause.errno, cause.strerror) == (native.errno, native.strerror)
        assert cause.filename is None
    else:
        assert cause is None
    assert error.__context__ is None
