from __future__ import annotations

import re
import importlib

import httpx
import pytest

pq = importlib.import_module("pyarrow.parquet")
pa = importlib.import_module("pyarrow")

from mountainash_transport import StorageFacade  # noqa: E402
from mountainash_transport._core.http.engine import HttpRequestEngine  # noqa: E402
from mountainash_transport._core.ranged_io import RangePolicy  # noqa: E402
from mountainash_transport.storage.backends.http import HTTPStorageBackend  # noqa: E402


@pytest.fixture
def parquet_bytes() -> bytes:
    cols = {f"c{i}": pa.array(range(200_000), type=pa.int64()) for i in range(10)}
    sink = pa.BufferOutputStream()
    pq.write_table(pa.table(cols), sink, compression="none", row_group_size=50_000)
    return sink.getvalue().to_pybytes()


def _facade(data: bytes, served: list[int]) -> StorageFacade:
    def handler(request: httpx.Request) -> httpx.Response:
        m = re.fullmatch(r"bytes=(\d+)-(\d+)", request.headers["range"])
        assert m
        s, e = int(m[1]), min(int(m[2]), len(data) - 1)
        served.append(e - s + 1)
        return httpx.Response(206, content=data[s:e + 1],
                              headers={"Content-Range": f"bytes {s}-{e}/{len(data)}", "ETag": '"v1"'})

    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    f = StorageFacade.for_local()
    f._backend = HTTPStorageBackend(None, engine=HttpRequestEngine(httpx.Client(transport=httpx.MockTransport(handler))))
    f._provider_type = CONST_STORAGE_PROVIDER_TYPE.HTTP
    return f


def test_schema_fetches_only_footer_ranges(parquet_bytes) -> None:
    served: list[int] = []
    f = _facade(parquet_bytes, served)
    with f.read_stream("https://h/t.parquet", access="random",
                       range_policy=RangePolicy("readahead", block_size=64 * 1024)) as h:
        assert pq.ParquetFile(h).schema_arrow.names == [f"c{i}" for i in range(10)]
    assert sum(served) < 0.05 * len(parquet_bytes)


def test_projected_read_fetches_only_selected_columns(parquet_bytes) -> None:
    served: list[int] = []
    f = _facade(parquet_bytes, served)
    with f.read_stream("https://h/t.parquet", access="random", range_policy=RangePolicy("none")) as h:
        table = pq.ParquetFile(h).read(columns=["c3"])
    assert table.num_rows == 200_000
    assert sum(served) < 0.2 * len(parquet_bytes)  # one of ten equal columns + footer