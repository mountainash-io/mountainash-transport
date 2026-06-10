"""Tests for HttpResponse and HttpStreamResponse."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from mountainash_transport._core.http.errors import HttpDecodeError
from mountainash_transport._core.http.response import HttpResponse, HttpStreamResponse


# ---------------------------------------------------------------------------
# HttpResponse
# ---------------------------------------------------------------------------


class TestHttpResponse:
    def _make(self, **kwargs) -> HttpResponse:
        defaults = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "content": b'{"key": "value"}',
            "url": "https://example.com/api",
            "method": "GET",
        }
        defaults.update(kwargs)
        return HttpResponse(**defaults)

    def test_all_fields_accessible(self):
        r = self._make()
        assert r.status_code == 200
        assert r.headers == {"content-type": "application/json"}
        assert r.content == b'{"key": "value"}'
        assert r.url == "https://example.com/api"
        assert r.method == "GET"

    def test_frozen_immutability(self):
        r = self._make()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.status_code = 404  # type: ignore[misc]

    def test_text_decodes_utf8(self):
        r = self._make(content="héllo".encode("utf-8"))
        assert r.text == "héllo"

    def test_text_plain_ascii(self):
        r = self._make(content=b"hello world")
        assert r.text == "hello world"

    def test_json_parses_valid_json(self):
        payload = {"key": "value", "number": 42}
        r = self._make(content=json.dumps(payload).encode("utf-8"))
        assert r.json() == payload

    def test_json_parses_list(self):
        payload = [1, 2, 3]
        r = self._make(content=json.dumps(payload).encode("utf-8"))
        assert r.json() == payload

    def test_json_raises_http_decode_error_on_invalid_json(self):
        r = self._make(content=b"not-json{{{")
        with pytest.raises(HttpDecodeError):
            r.json()

    def test_json_raises_http_decode_error_on_bad_encoding(self):
        # invalid UTF-8 bytes — not valid JSON either
        r = self._make(content=b"\xff\xfe")
        with pytest.raises(HttpDecodeError):
            r.json()

    def test_json_is_a_method_not_a_property(self):
        r = self._make()
        # Calling .json should return a callable, not the parsed data
        assert callable(r.json)

    def test_json_error_chained_from_original(self):
        r = self._make(content=b"bad")
        with pytest.raises(HttpDecodeError) as exc_info:
            r.json()
        assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# HttpStreamResponse
# ---------------------------------------------------------------------------


class TestHttpStreamResponse:
    def _make_mock_response(self, **kwargs) -> MagicMock:
        mock = MagicMock()
        mock.status_code = kwargs.get("status_code", 200)
        mock.headers = kwargs.get("headers", {"content-type": "text/plain"})
        mock.url = kwargs.get("url", MagicMock())
        mock.url.__str__ = lambda self: "https://example.com/stream"
        mock.request = MagicMock()
        mock.request.method = kwargs.get("method", "GET")
        return mock

    def test_status_code(self):
        mock = self._make_mock_response(status_code=206)
        r = HttpStreamResponse(mock)
        assert r.status_code == 206

    def test_headers_as_dict(self):
        headers = {"content-type": "text/plain", "x-custom": "value"}
        mock = self._make_mock_response(headers=headers)
        r = HttpStreamResponse(mock)
        assert r.headers == headers

    def test_url_as_str(self):
        mock = self._make_mock_response()
        r = HttpStreamResponse(mock)
        assert isinstance(r.url, str)
        assert r.url == "https://example.com/stream"

    def test_method(self):
        mock = self._make_mock_response(method="POST")
        r = HttpStreamResponse(mock)
        assert r.method == "POST"

    def test_iter_bytes_delegates(self):
        mock = self._make_mock_response()
        chunks = [b"chunk1", b"chunk2"]
        mock.iter_bytes.return_value = iter(chunks)
        r = HttpStreamResponse(mock)
        result = list(r.iter_bytes(chunk_size=1024))
        assert result == chunks
        mock.iter_bytes.assert_called_once_with(chunk_size=1024)

    def test_iter_bytes_default_chunk_size(self):
        mock = self._make_mock_response()
        mock.iter_bytes.return_value = iter([b"data"])
        r = HttpStreamResponse(mock)
        list(r.iter_bytes())
        mock.iter_bytes.assert_called_once_with(chunk_size=65536)

    def test_iter_text_delegates(self):
        mock = self._make_mock_response()
        chunks = ["line1\n", "line2\n"]
        mock.iter_text.return_value = iter(chunks)
        r = HttpStreamResponse(mock)
        result = list(r.iter_text(chunk_size=512))
        assert result == chunks
        mock.iter_text.assert_called_once_with(chunk_size=512)

    def test_iter_text_default_chunk_size(self):
        mock = self._make_mock_response()
        mock.iter_text.return_value = iter(["text"])
        r = HttpStreamResponse(mock)
        list(r.iter_text())
        mock.iter_text.assert_called_once_with(chunk_size=65536)

    def test_read_delegates(self):
        mock = self._make_mock_response()
        mock.read.return_value = b"full content"
        r = HttpStreamResponse(mock)
        result = r.read()
        assert result == b"full content"
        mock.read.assert_called_once()

    def test_close_delegates(self):
        mock = self._make_mock_response()
        r = HttpStreamResponse(mock)
        r.close()
        mock.close.assert_called_once()
