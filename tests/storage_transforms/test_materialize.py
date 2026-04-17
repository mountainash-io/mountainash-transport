"""Tests for the materialize() utility."""
from __future__ import annotations

import io
import tempfile

import pytest

from mountainash_utils_files.storage_transforms.util import materialize


def test_materialize_memory_mode_small_stream():
    source = io.BytesIO(b"hello world")
    buffered, length = materialize(source, to="memory")
    assert length == 11
    assert buffered.read() == b"hello world"


def test_materialize_returns_seekable_buffer_positioned_at_zero():
    source = io.BytesIO(b"data")
    buffered, _ = materialize(source, to="memory")
    assert buffered.tell() == 0
    assert buffered.seekable() is True


def test_materialize_exhausts_original_stream():
    source = io.BytesIO(b"abc")
    materialize(source, to="memory")
    assert source.read() == b""


def test_materialize_tempfile_mode_below_cutoff_stays_in_memory():
    source = io.BytesIO(b"x" * 100)
    buffered, length = materialize(source, to="tempfile", memory_cutoff=1024)
    assert length == 100
    # SpooledTemporaryFile below cutoff exposes an internal _file that is BytesIO
    assert isinstance(buffered, tempfile.SpooledTemporaryFile)
    assert buffered.read() == b"x" * 100


def test_materialize_tempfile_mode_above_cutoff_rolls_to_disk():
    source = io.BytesIO(b"x" * 5000)
    buffered, length = materialize(source, to="tempfile", memory_cutoff=1024)
    assert length == 5000
    assert isinstance(buffered, tempfile.SpooledTemporaryFile)
    # After exceeding cutoff the spooled file has rolled over
    assert buffered._rolled is True
    assert buffered.read() == b"x" * 5000


def test_materialize_invalid_mode_raises():
    with pytest.raises(ValueError, match="to="):
        materialize(io.BytesIO(b""), to="bogus")  # type: ignore[arg-type]
