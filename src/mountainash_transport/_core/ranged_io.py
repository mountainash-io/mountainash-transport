"""Seekable reads over bounded fsspec caches and transport-owned fetchers."""
from __future__ import annotations

import io
import typing as t
from dataclasses import dataclass


from mountainash_transport._core.exceptions import StorageError

CacheName = t.Literal["readahead", "blockcache", "bytes", "none"]


@dataclass(frozen=True)
class RangePolicy:
    """Cache policy; max_blocks applies only to blockcache."""

    cache: CacheName = "readahead"
    block_size: int = 1024 * 1024
    max_blocks: int = 32

    def __post_init__(self) -> None:
        if self.cache not in ("readahead", "blockcache", "bytes", "none"):
            raise ValueError(f"Unknown range cache: {self.cache!r}")
        if self.block_size <= 0:
            raise ValueError("block_size must be positive")
        if self.cache == "blockcache" and self.max_blocks <= 0:
            raise ValueError("max_blocks must be positive for blockcache")

    @classmethod
    def from_profile(cls, profile: object | None) -> RangePolicy:
        """Resolve scalar profile settings against library defaults."""
        values = {
            key: value for key, field in (
                ("cache", "RANGE_CACHE"), ("block_size", "RANGE_BLOCK_SIZE"),
                ("max_blocks", "RANGE_MAX_BLOCKS"),
            ) if (value := getattr(profile, field, None)) is not None
        }
        return cls(**values)


@dataclass(frozen=True)
class RangedSource:
    """One object: size and fetch of half-open byte ranges, optionally owned."""

    size: int
    fetch: t.Callable[[int, int], bytes]
    on_close: t.Callable[[], None] | None = None


class RangedReader(io.RawIOBase):
    """Seekable binary handle; seeking performs no network I/O."""

    def __init__(self, source: RangedSource, policy: RangePolicy) -> None:
        super().__init__()
        self._source = source
        self._pos = 0
        kwargs = {"maxblocks": policy.max_blocks} if policy.cache == "blockcache" else {}
        from fsspec.caching import caches  # type: ignore[import-untyped]
        self._cache = caches[policy.cache](policy.block_size, self._fetch, source.size, **kwargs)

    def _fetch(self, start: int, end: int) -> bytes:
        end = min(end, self._source.size)
        if start >= end:
            return b""
        data = self._source.fetch(start, end)
        if len(data) != end - start:
            raise StorageError(f"Short range: expected {end-start} bytes, received {len(data)}")
        return data

    def _check_open(self) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def readable(self) -> bool:
        self._check_open()
        return True

    def seekable(self) -> bool:
        self._check_open()
        return True

    def tell(self) -> int:
        self._check_open()
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        self._check_open()
        if whence == io.SEEK_SET:
            pos = offset
        elif whence == io.SEEK_CUR:
            pos = self._pos + offset
        elif whence == io.SEEK_END:
            pos = self._source.size + offset
        else:
            raise ValueError(f"Invalid whence: {whence}")
        if pos < 0:
            raise ValueError("Negative seek position")
        self._pos = pos
        return pos

    def read(self, size: int = -1) -> bytes:
        self._check_open()
        end = self._source.size if size < 0 else min(self._pos + size, self._source.size)
        if self._pos >= end:
            return b""
        data = t.cast(bytes, self._cache._fetch(self._pos, end))
        self._pos += len(data)
        return data

    def readinto(self, b: t.Any) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)

    def close(self) -> None:
        if not self.closed:
            try:
                if self._source.on_close is not None:
                    self._source.on_close()
            finally:
                self._cache = None
                super().close()


def strong_etag(value: str | None) -> str | None:
    """Weak validators cannot be used with If-Match."""
    return value if value and not value.startswith("W/") else None
