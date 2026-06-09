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

        shutil.copyfileobj(stream, buffer)
        length = buffer.tell()
        buffer.seek(0)
        return buffer, length

    elif to == "tempfile":
        file_buffer: tempfile.SpooledTemporaryFile = tempfile.SpooledTemporaryFile(max_size=memory_cutoff)
        shutil.copyfileobj(stream, file_buffer)

        #Need to open stream to the file
        length = file_buffer.tell()
        file_buffer.seek(0)
        return file_buffer, length

    else:
        raise ValueError(f"to={to!r} must be 'memory' or 'tempfile'")
