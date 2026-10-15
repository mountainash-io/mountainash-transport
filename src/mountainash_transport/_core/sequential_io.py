"""Forward-only adapters, retaining at most one incoming chunk."""
from __future__ import annotations

import io
import typing as t

MapError = t.Callable[[Exception], Exception | None]


class ForwardOnlyReader(io.RawIOBase):
    """Sized native reads with owned closure and deferred error translation."""

    def __init__(self, read: t.Callable[[int], bytes], close: t.Callable[[], None],
                 map_error: MapError | None = None) -> None:
        super().__init__()
        self._read = read
        self._close = close
        self._map_error = map_error

    def readable(self) -> bool:
        return True

    def readinto(self, b: t.Any) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        if not len(b):
            return 0
        try:
            data = self._read(len(b))
        except Exception as exc:
            mapped = self._map_error(exc) if self._map_error else None
            if mapped is not None:
                raise mapped from exc
            raise
        b[:len(data)] = data
        return len(data)

    def close(self) -> None:
        if not self.closed:
            try:
                self._close()
            finally:
                super().close()


class IterBytesReader(ForwardOnlyReader):
    """Adapt an iterator without draining it or copying the remaining chunk."""

    def __init__(self, chunks: t.Iterator[bytes], close: t.Callable[[], None],
                 map_error: MapError | None = None) -> None:
        self._chunks = chunks
        self._pending = memoryview(b"")
        super().__init__(self._next, close, map_error)

    def _next(self, size: int) -> bytes:
        while not self._pending:
            chunk = next(self._chunks, None)
            if chunk is None:
                return b""
            self._pending = memoryview(chunk)
        data = self._pending[:size].tobytes()
        self._pending = self._pending[len(data):]
        return data
