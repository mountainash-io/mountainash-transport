"""Native-backed reader preserving the file's supported binary operations."""
from __future__ import annotations

import errno
import typing as t
from types import TracebackType

from ._helpers import _map_local_error, _mapped


class _LocalReader:
    def __init__(self, source: t.BinaryIO, path: str) -> None:
        self._source = source
        self._path = path
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed or self._source.closed

    def __getattr__(self, name: str) -> t.Any:
        # BinaryIO's optional native methods differ by handle. Do not fabricate
        # unsupported capabilities or wrap the native handle in another buffer.
        with _mapped(self._path):
            value = getattr(self._source, name)
        if not callable(value):
            return value

        def invoke(*args: t.Any, **kwargs: t.Any) -> t.Any:
            if self.closed:
                raise ValueError("I/O operation on closed file")
            try:
                return value(*args, **kwargs)
            except OSError as exc:
                if name == "seek" and exc.errno == errno.EINVAL:
                    raise
                mapped = _map_local_error(exc, self._path)
                if mapped is None:
                    raise
                raise mapped from exc
        return invoke

    def __iter__(self) -> _LocalReader:
        return self

    def __next__(self) -> bytes:
        return t.cast(bytes, self.__getattr__("__next__")())

    def close(self) -> None:
        if self._closed:
            return
        try:
            with _mapped(self._path):
                self._source.close()
        finally:
            self._closed = True

    def __enter__(self) -> _LocalReader:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None,
        exc: BaseException | None, tb: TracebackType | None,
    ) -> None:
        self.close()
