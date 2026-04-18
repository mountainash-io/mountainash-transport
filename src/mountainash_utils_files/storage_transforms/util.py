"""Stream utilities — explicit opt-in buffering for callers that need length."""

from __future__ import annotations

import io
import shutil
import tempfile
from typing import BinaryIO, Literal


def materialize(
    stream: BinaryIO,
    *,
    to: Literal["memory", "tempfile"] = "memory",
    memory_cutoff: int = 64 * 1024 * 1024,
) -> tuple[BinaryIO, int]:
    """Drain *stream* into a seekable buffer; return (buffer, length).

    - to="memory": io.BytesIO. Simple, RAM-bounded.
    - to="tempfile": tempfile.SpooledTemporaryFile that rolls to disk
      past memory_cutoff. Safe for large streams.

    After return, the original *stream* is exhausted and the returned
    buffer is positioned at 0.
    """
    if to == "memory":
        buffer: BinaryIO = io.BytesIO()
    elif to == "tempfile":
        buffer = tempfile.SpooledTemporaryFile(max_size=memory_cutoff)
    else:
        raise ValueError(f"to={to!r} must be 'memory' or 'tempfile'")

    shutil.copyfileobj(stream, buffer)
    length = buffer.tell()
    buffer.seek(0)
    return buffer, length
