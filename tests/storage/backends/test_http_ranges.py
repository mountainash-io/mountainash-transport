from __future__ import annotations

import httpx
import pytest
from mountainash_transport._core.http.engine import HttpRequestEngine
from mountainash_transport._core.exceptions import StorageError


def _transport(handler):
    return httpx.MockTransport(handler)

class _ExplodingStream(httpx.SyncByteStream):
    def __iter__(self):
        raise AssertionError("body must not be read")


class TestHTTPRangeProbe:
    def _backend(self, handler):
        from mountainash_transport.storage.backends.http import HTTPStorageBackend
        return HTTPStorageBackend(None, engine=HttpRequestEngine(httpx.Client(transport=_transport(handler))))

    def test_200_to_probe_raises_without_reading_body(self):
        from mountainash_transport._core.exceptions import RangeNotSupportedError
        b = self._backend(lambda r: httpx.Response(200, stream=_ExplodingStream()))
        with pytest.raises(RangeNotSupportedError):
            b.open_ranged("https://h/f")

    def test_unknown_total_raises(self):
        from mountainash_transport._core.exceptions import RangeNotSupportedError
        b = self._backend(lambda r: httpx.Response(206, content=b"a", headers={"Content-Range": "bytes 0-0/*"}))
        with pytest.raises(RangeNotSupportedError):
            b.open_ranged("https://h/f")

    def test_non_identity_encoding_rejected_unread(self):
        from mountainash_transport._core.exceptions import RangeNotSupportedError
        b = self._backend(lambda r: httpx.Response(
            206, stream=_ExplodingStream(),
            headers={"Content-Range": "bytes 0-0/10", "Content-Encoding": "gzip"}))
        with pytest.raises(RangeNotSupportedError):
            b.open_ranged("https://h/f")

    def test_content_range_mismatch_rejected(self):
        def handler(r):
            if r.headers["range"] == "bytes=0-0":
                return httpx.Response(206, content=b"a", headers={"Content-Range": "bytes 0-0/10"})
            return httpx.Response(206, content=b"zz", headers={"Content-Range": "bytes 8-9/10"})
        src = self._backend(handler).open_ranged("https://h/f")
        with pytest.raises(StorageError):
            src.fetch(0, 2)

    def test_weak_etag_not_pinned(self):
        seen: list[str | None] = []
        def handler(r):
            seen.append(r.headers.get("if-match"))
            s, e = map(int, r.headers["range"][6:].split("-"))
            return httpx.Response(206, content=b"x" * (e - s + 1),
                                  headers={"Content-Range": f"bytes {s}-{e}/10", "ETag": 'W/"v1"'})
        src = self._backend(handler).open_ranged("https://h/f")
        src.fetch(2, 4)
        assert seen == [None, None]

    def test_200_to_range_fetch_rejected_unread(self):
        from mountainash_transport._core.exceptions import RangeNotSupportedError
        def handler(r):
            if r.headers["range"] == "bytes=0-0":
                return httpx.Response(206, content=b"a", headers={"Content-Range": "bytes 0-0/10"})
            return httpx.Response(200, stream=_ExplodingStream())
        src = self._backend(handler).open_ranged("https://h/f")
        with pytest.raises(RangeNotSupportedError):
            src.fetch(0, 5)

    def test_http_probe_416_empty_resource_is_empty_handle(self):
        b = self._backend(lambda r: httpx.Response(416, headers={"Content-Range": "bytes */0"}))
        assert b.open_ranged("https://h/empty").size == 0

    @pytest.mark.parametrize("headers", [{"Content-Range": "bytes */100"}, {}])
    def test_http_probe_416_non_empty_or_unknown_raises(self, headers):
        b = self._backend(lambda r: httpx.Response(416, headers=headers))
        with pytest.raises(StorageError):
            b.open_ranged("https://h/f")

    @pytest.mark.parametrize("content_range", ["bytes 3-3/10", "bytes 0-0/0"])
    def test_malformed_probe_interval_rejected(self, content_range):
        from mountainash_transport._core.exceptions import RangeNotSupportedError
        b = self._backend(lambda r: httpx.Response(206, content=b"a", headers={"Content-Range": content_range}))
        with pytest.raises(RangeNotSupportedError):
            b.open_ranged("https://h/f")