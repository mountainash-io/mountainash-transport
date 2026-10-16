"""Tests for the Pipeline class."""
from __future__ import annotations

import io
from typing import BinaryIO

import pytest

from mountainash_transport._core.transforms import Pipeline


class _RecordingTransform:
    """Transform that tags bytes with a prefix on wrap and strips it on unwrap.

    wrap(b"data") -> prefix + b"data"
    unwrap(prefix + b"data") -> b"data"
    """
    def __init__(self, prefix: bytes) -> None:
        self.prefix = prefix

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        return io.BytesIO(self.prefix + stream.read())

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        data = stream.read()
        assert data.startswith(self.prefix), f"expected prefix {self.prefix!r}"
        return io.BytesIO(data[len(self.prefix):])


def test_empty_pipeline_is_identity_on_read():
    source = io.BytesIO(b"hello")
    out = Pipeline().apply_read(source)
    assert out.read() == b"hello"


def test_empty_pipeline_is_identity_on_write():
    source = io.BytesIO(b"hello")
    out = Pipeline().apply_write(source)
    assert out.read() == b"hello"


def test_single_transform_wrap_and_unwrap_roundtrip():
    t = _RecordingTransform(b"[A]")
    pipeline = Pipeline(t)
    written = pipeline.apply_write(io.BytesIO(b"payload"))
    assert written.read() == b"[A]payload"
    read = pipeline.apply_read(io.BytesIO(b"[A]payload"))
    assert read.read() == b"payload"


def test_multi_transform_outermost_first_ordering_on_write():
    """Pipeline(outer, inner).apply_write applies inner first, outer last."""
    outer = _RecordingTransform(b"[OUT]")
    inner = _RecordingTransform(b"[IN]")
    pipeline = Pipeline(outer, inner)
    out = pipeline.apply_write(io.BytesIO(b"data"))
    # inner wraps first: [IN]data; then outer wraps: [OUT][IN]data
    assert out.read() == b"[OUT][IN]data"


def test_multi_transform_outermost_first_ordering_on_read():
    """Pipeline(outer, inner).apply_read strips outer first, inner last."""
    outer = _RecordingTransform(b"[OUT]")
    inner = _RecordingTransform(b"[IN]")
    pipeline = Pipeline(outer, inner)
    out = pipeline.apply_read(io.BytesIO(b"[OUT][IN]data"))
    assert out.read() == b"data"


def test_pipeline_instance_is_reusable():
    t = _RecordingTransform(b"[X]")
    pipeline = Pipeline(t)
    a = pipeline.apply_write(io.BytesIO(b"one"))
    b = pipeline.apply_write(io.BytesIO(b"two"))
    assert a.read() == b"[X]one"
    assert b.read() == b"[X]two"


def test_pipeline_roundtrip_is_symmetric():
    t1 = _RecordingTransform(b"[A]")
    t2 = _RecordingTransform(b"[B]")
    pipeline = Pipeline(t1, t2)
    original = b"hello world"
    encoded = pipeline.apply_write(io.BytesIO(original)).read()
    decoded = pipeline.apply_read(io.BytesIO(encoded)).read()
    assert decoded == original


def test_read_pipeline_owns_unique_layers_but_not_the_input() -> None:
    source = io.BytesIO(b"payload")
    layers: list[io.BytesIO] = []
    closes: list[int] = []

    class Layer(io.BytesIO):
        def close(self) -> None:
            closes.append(id(self))
            super().close()

    class Transform:
        def wrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

        def unwrap(self, stream: BinaryIO) -> BinaryIO:
            layer = Layer(stream.read())
            layers.append(layer)
            return layer

    class Identity(Transform):
        def unwrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

    pipeline = Pipeline(Identity(), Transform(), Identity(), Transform())
    try:
        with pipeline.apply_read(source) as result:
            assert result.read() == b"payload"
        result.close()
        assert all(layer.closed for layer in layers)
        assert closes == [id(layer) for layer in reversed(layers)]
        assert not source.closed
    finally:
        for layer in layers:
            io.BytesIO.close(layer)
        source.close()


def test_failed_pipeline_does_not_close_identity_input() -> None:
    class Identity:
        def wrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

        def unwrap(self, stream: BinaryIO) -> BinaryIO:
            return stream

    class Failing(Identity):
        def unwrap(self, stream: BinaryIO) -> BinaryIO:
            raise RuntimeError("construction")

    with io.BytesIO(b"payload") as source:
        with pytest.raises(RuntimeError, match="construction"):
            Pipeline(Identity(), Failing()).apply_read(source)
        assert not source.closed
