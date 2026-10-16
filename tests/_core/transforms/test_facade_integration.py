"""Facade integration tests for the pipeline= kwarg."""
from __future__ import annotations

import contextlib
import gzip
import io
import typing as t
from pathlib import Path

import pytest

from mountainash_transport import StorageFacade
from mountainash_transport._core.transforms import Gzip, Pipeline


@pytest.fixture
def local_facade() -> StorageFacade:
    return StorageFacade.for_local()


def test_facade_read_with_pipeline_decompresses(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"hello"))
    assert local_facade.read(str(path), pipeline=Gzip()) == b"hello"


def test_facade_read_stream_with_pipeline_decompresses(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"streamed"))
    with local_facade.read_stream(str(path), pipeline=Gzip()) as stream:
        assert stream.read() == b"streamed"


def test_facade_read_with_none_pipeline_is_unchanged(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"abc")
    assert local_facade.read(str(path), pipeline=None) == b"abc"
    assert local_facade.read(str(path)) == b"abc"


def test_facade_read_accepts_bare_transform_or_pipeline(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"ok"))
    assert local_facade.read(str(path), pipeline=Gzip()) == b"ok"
    assert local_facade.read(str(path), pipeline=Pipeline(Gzip())) == b"ok"


def test_facade_read_closes_source_stream(local_facade, tmp_path):
    """Regression: read() must close the underlying backend source stream."""
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"payload"))

    # Patch read_to_stream to capture the source for inspection
    opened_streams = []
    original = local_facade._backend.read_to_stream

    def tracking_read(p):
        s = original(p)
        opened_streams.append(s)
        return s

    local_facade._backend.read_to_stream = tracking_read
    try:
        local_facade.read(str(path), pipeline=Gzip())
    finally:
        local_facade._backend.read_to_stream = original

    assert len(opened_streams) == 1
    assert opened_streams[0].closed, "source stream was not closed"


def test_facade_read_stream_closes_source_on_exit(local_facade, tmp_path):
    """Regression: read_stream() returned object closes source when its close() is called."""
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"payload"))

    opened_streams = []
    original = local_facade._backend.read_to_stream

    def tracking_read(p):
        s = original(p)
        opened_streams.append(s)
        return s

    local_facade._backend.read_to_stream = tracking_read
    try:
        with local_facade.read_stream(str(path), pipeline=Gzip()) as s:
            s.read()
    finally:
        local_facade._backend.read_to_stream = original

    assert len(opened_streams) == 1
    assert opened_streams[0].closed, "source stream was not closed after with-block exit"


class _FailingUnwrap:
    """Transform whose unwrap records its input stream then raises."""

    def __init__(self) -> None:
        self.received: io.IOBase | None = None

    def wrap(self, stream):
        return stream

    def unwrap(self, stream):
        self.received = stream
        raise RuntimeError("unwrap failed")


def _track_sources(facade: StorageFacade, monkeypatch) -> list:
    opened: list = []
    original = facade._backend.read_to_stream

    def tracking_read(p):
        s = original(p)
        opened.append(s)
        return s

    monkeypatch.setattr(facade._backend, "read_to_stream", tracking_read)
    return opened


def test_read_stream_closes_source_when_transform_construction_fails(
    local_facade, tmp_path, monkeypatch,
):
    path = tmp_path / "data.bin"
    path.write_bytes(b"payload")
    opened = _track_sources(local_facade, monkeypatch)
    failing = _FailingUnwrap()

    with pytest.raises(RuntimeError, match="unwrap failed"):
        local_facade.read_stream(str(path), pipeline=Pipeline(failing))

    assert failing.received is opened[0]
    assert opened[0].closed


def test_read_stream_closes_built_layers_when_later_transform_fails(
    local_facade, tmp_path, monkeypatch,
):
    """Outer gzip layer is built, inner layer fails: both gzip wrapper and source close."""
    path = tmp_path / "data.bin.gz"
    path.write_bytes(gzip.compress(b"payload"))
    opened = _track_sources(local_facade, monkeypatch)
    failing = _FailingUnwrap()

    with pytest.raises(RuntimeError, match="unwrap failed"):
        local_facade.read_stream(str(path), pipeline=Pipeline(Gzip(), failing))

    assert isinstance(failing.received, gzip.GzipFile)
    assert failing.received.closed
    assert opened[0].closed


@pytest.mark.parametrize("failing_close", ["layer", "source"])
def test_construction_error_survives_cleanup_failure(
    local_facade: StorageFacade, monkeypatch: pytest.MonkeyPatch, failing_close: str,
) -> None:
    events: list[str] = []

    class Handle(io.BytesIO):
        def __init__(self, name: str) -> None:
            super().__init__(b"payload")
            self.name = name

        def close(self) -> None:
            events.append(self.name)
            super().close()
            if self.name == failing_close:
                raise ValueError("cleanup failed")

    source, layer = Handle("source"), Handle("layer")

    class Transform:
        def wrap(self, stream: t.BinaryIO) -> t.BinaryIO:
            return stream

        def unwrap(self, stream: t.BinaryIO) -> t.BinaryIO:
            return layer

    monkeypatch.setattr(local_facade._backend, "read_to_stream", lambda path: source)
    with pytest.raises(RuntimeError, match="unwrap failed"):
        local_facade.read_stream("unused", pipeline=Pipeline(Transform(), _FailingUnwrap()))
    assert events == ["layer", "source"]
    assert layer.closed and source.closed


def test_read_stream_seeks_plain_local_file(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"abc")
    with local_facade.read_stream(str(path)) as s:
        assert s.seekable()
        assert s.read(1) == b"a"
        assert s.tell() == 1
        assert s.seek(0) == 0
        assert s.read(1) == b"a"


def test_read_stream_seeks_decoded_offsets_through_gzip(local_facade, tmp_path):
    """Positions refer to decoded bytes, not compressed source offsets."""
    path = tmp_path / "data.gz"
    path.write_bytes(gzip.compress(b"hello world"))
    with local_facade.read_stream(str(path), pipeline=Gzip()) as s:
        assert s.seekable()
        assert s.seek(6) == 6
        assert s.read() == b"world"
        assert s.tell() == 11
        assert s.seek(0) == 0
        assert s.read(5) == b"hello"


class _ForwardOnly(io.RawIOBase):
    def __init__(self, data: bytes) -> None:
        self._inner = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        return self._inner.readinto(b)


class _ForwardOnlyTransform:
    def wrap(self, stream):
        return stream

    def unwrap(self, stream):
        return _ForwardOnly(stream.read())


def test_read_stream_non_seekable_effective_stream_stays_non_seekable(
    local_facade, tmp_path, monkeypatch,
):
    path = tmp_path / "plain.bin"
    path.write_bytes(b"abc")
    opened = _track_sources(local_facade, monkeypatch)
    with local_facade.read_stream(str(path), pipeline=_ForwardOnlyTransform()) as s:
        assert not s.seekable()
        with pytest.raises(io.UnsupportedOperation):
            s.seek(0)
        assert s.read() == b"abc"
    assert opened[0].closed


def test_read_stream_malformed_gzip_fails_on_consumption_and_closes(
    local_facade, tmp_path, monkeypatch,
):
    """Opening succeeds; decoding fails during read; the context still closes the source."""
    path = tmp_path / "bad.gz"
    path.write_bytes(b"not gzip")
    opened = _track_sources(local_facade, monkeypatch)

    with pytest.raises(gzip.BadGzipFile):
        with local_facade.read_stream(str(path), infer=True) as s:
            s.read()

    assert s.closed
    assert opened[0].closed


@pytest.mark.parametrize("access", ["read", "sequential", "buffered"])
@pytest.mark.parametrize("malformed", [False, True])
def test_nested_gzip_closes_every_decoder(
    local_facade: StorageFacade, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    access: str, malformed: bool,
) -> None:
    """Keep decoders alive so GC cannot mask a missed explicit close."""
    decoders: list[t.BinaryIO] = []

    class TrackedGzip(Gzip):
        def unwrap(self, source: t.BinaryIO) -> t.BinaryIO:
            decoder = super().unwrap(source)
            decoders.append(decoder)
            return decoder

    path = tmp_path / "nested.gz.gz"
    inner_bytes = b"not gzip" if malformed else gzip.compress(b"payload")
    path.write_bytes(gzip.compress(inner_bytes))
    sources = _track_sources(local_facade, monkeypatch)
    pipeline = Pipeline(TrackedGzip(), TrackedGzip())
    try:
        with pytest.raises(gzip.BadGzipFile) if malformed else contextlib.nullcontext():
            if access == "read":
                assert local_facade.read(str(path), pipeline=pipeline) == b"payload"
            else:
                with local_facade.read_stream(
                    str(path), pipeline=pipeline, access=access,  # type: ignore[arg-type]
                ) as stream:
                    assert stream.read() == b"payload"
        assert all(decoder.closed for decoder in decoders)
        assert sources[0].closed
    finally:
        for decoder in reversed(decoders):
            decoder.close()


@pytest.mark.parametrize("failure", ["consumer", "inner", "outer", "source"])
def test_stream_close_unwinds_all_layers_even_when_close_raises(
    local_facade: StorageFacade, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    events: list[str] = []
    handles: list[io.BytesIO] = []

    class OwnedBytes(io.BytesIO):
        def __init__(self, name: str, data: bytes) -> None:
            super().__init__(data)
            self.name = name
            handles.append(self)

        def close(self) -> None:
            events.append(self.name)
            super().close()
            if self.name == failure:
                raise RuntimeError(failure)

    class Layer:
        def __init__(self, name: str) -> None:
            self.name = name

        def unwrap(self, source: t.BinaryIO) -> t.BinaryIO:
            return OwnedBytes(self.name, source.read())

        def wrap(self, source: t.BinaryIO) -> t.BinaryIO:
            return source

    source = OwnedBytes("source", b"payload")
    monkeypatch.setattr(local_facade._backend, "read_to_stream", lambda path: source)
    stream = local_facade.read_stream("unused", pipeline=Pipeline(Layer("outer"), Layer("inner")))
    try:
        with pytest.raises(RuntimeError, match=failure):
            with stream:
                assert stream.read() == b"payload"
                if failure == "consumer":
                    raise RuntimeError("consumer")
        assert events == ["inner", "outer", "source"]
        assert stream.closed
        assert all(handle.closed for handle in handles)
        stream.close()
        assert events == ["inner", "outer", "source"]
    finally:
        for handle in handles:
            io.BytesIO.close(handle)


def test_facade_write_with_pipeline_compresses(local_facade, tmp_path):
    path = tmp_path / "out.gz"
    local_facade.write(str(path), b"payload", pipeline=Gzip())
    assert gzip.decompress(path.read_bytes()) == b"payload"


def test_facade_write_stream_with_pipeline_compresses(local_facade, tmp_path):
    path = tmp_path / "out.gz"
    local_facade.write_stream(str(path), io.BytesIO(b"streamed"), pipeline=Gzip())
    assert gzip.decompress(path.read_bytes()) == b"streamed"


def test_facade_write_read_roundtrip_through_pipeline(local_facade, tmp_path):
    path = tmp_path / "data.gz"
    local_facade.write(str(path), b"roundtrip", pipeline=Gzip())
    assert local_facade.read(str(path), pipeline=Gzip()) == b"roundtrip"


def test_facade_write_with_none_pipeline_is_unchanged(local_facade, tmp_path):
    path = tmp_path / "plain.bin"
    local_facade.write(str(path), b"raw", pipeline=None)
    assert path.read_bytes() == b"raw"


def test_copy_between_source_pipeline_decodes(local_facade, tmp_path):
    """Copy a gzipped source to a plaintext destination using source_pipeline."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.gz"
    dst_path = tmp_path / "dest.bin"
    src_path.write_bytes(gzip.compress(b"hello world"))

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        source_pipeline=Gzip(),
    )
    assert dst_path.read_bytes() == b"hello world"


def test_copy_between_destination_pipeline_encodes(local_facade, tmp_path):
    """Copy a plaintext source to a gzipped destination using destination_pipeline."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.gz"
    src_path.write_bytes(b"hello world")

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        destination_pipeline=Gzip(),
    )
    assert gzip.decompress(dst_path.read_bytes()) == b"hello world"


def test_copy_between_forces_stream_when_pipeline_present(local_facade, tmp_path, monkeypatch):
    """When any pipeline is given, native copy is skipped even for same-backend."""
    from mountainash_transport import copy_between

    src_path = tmp_path / "source.bin"
    dst_path = tmp_path / "dest.gz"
    src_path.write_bytes(b"x")

    copy_called = {"value": False}
    orig_copy = local_facade.copy

    def tracking_copy(*args, **kwargs):
        copy_called["value"] = True
        return orig_copy(*args, **kwargs)

    monkeypatch.setattr(local_facade, "copy", tracking_copy)

    copy_between(
        str(src_path),
        str(dst_path),
        local_facade,
        local_facade,
        destination_pipeline=Gzip(),
    )
    assert copy_called["value"] is False  # native copy was NOT used
    assert gzip.decompress(dst_path.read_bytes()) == b"x"
