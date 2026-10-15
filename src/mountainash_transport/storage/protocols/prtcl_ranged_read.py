"""Optional remote random-access read capability."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.ranged_io import RangedSource


@t.runtime_checkable
class RangedReadProtocol(t.Protocol):
    def open_ranged(self, path: str) -> RangedSource:
        """Open an object with known size and half-open byte-range fetching."""
        ...
