"""Tests for the StreamTransform protocol."""
from __future__ import annotations

from typing import BinaryIO


def test_stream_transform_protocol_is_runtime_checkable():
    from mountainash_transport._core.transforms import StreamTransform

    class Identity:
        def wrap(self, stream: BinaryIO) -> BinaryIO:
            return stream
        def unwrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

    assert isinstance(Identity(), StreamTransform)


def test_stream_transform_protocol_rejects_incomplete_impl():
    from mountainash_transport._core.transforms import StreamTransform

    class OnlyWrap:
        def wrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

    assert not isinstance(OnlyWrap(), StreamTransform)
