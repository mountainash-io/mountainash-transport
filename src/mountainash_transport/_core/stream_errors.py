"""Preserve caller errors when a transfer invokes and wraps caller-owned I/O."""
from __future__ import annotations

import typing as t
from types import TracebackType

_READS = frozenset({"read", "read1"})
_READS_INTO = frozenset({"readinto", "readinto1"})


def seekable_extent(stream: t.BinaryIO) -> int | None:
    """Bytes from a seekable stream's position to its end, position unchanged; None if not seekable.

    Writers report this as the stored size of a seekable source: SDKs may read
    such a body more than once (checksums, retries), so a read count would overstate it.
    """
    if not stream.seekable():
        return None
    start = stream.tell()
    end = stream.seek(0, 2)
    stream.seek(start)
    return end - start


class _CallerInput:
    """Delegate input capabilities; retain errors only for this transfer.

    ``close()`` is a no-op: the caller owns the stream, and an SDK that closes
    what it is given (boto3 does after a single-request upload) must not close
    the caller's stream. ``closed`` still reports the source's state.
    ``bytes_read`` counts what was read through it: the stored size of a
    non-seekable source, which an SDK can read only once.
    """

    def __init__(self, source: t.BinaryIO) -> None:
        self._source = source
        self._errors: list[tuple[BaseException, TracebackType | None]] = []
        self.bytes_read = 0

    def close(self) -> None:
        """Leave the borrowed source open."""

    def __getattr__(self, name: str) -> t.Any:
        try:
            value = getattr(self._source, name)
        except BaseException as exc:
            self._errors.append((exc, exc.__traceback__))
            raise
        if not callable(value):
            return value

        def invoke(*args: t.Any, **kwargs: t.Any) -> t.Any:
            try:
                result = value(*args, **kwargs)
            except BaseException as exc:
                self._errors.append((exc, exc.__traceback__))
                raise
            if name in _READS and result:
                self.bytes_read += len(result)
            elif name in _READS_INTO and result:
                self.bytes_read += result
            return result
        return invoke

    def original_in(self, error: BaseException) -> tuple[BaseException, TracebackType | None] | None:
        pending = [error]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            for original, traceback in self._errors:
                if current is original:
                    return original, traceback
            if current.__context__ is not None:
                pending.append(current.__context__)
            if current.__cause__ is not None:
                pending.append(current.__cause__)
        return None
