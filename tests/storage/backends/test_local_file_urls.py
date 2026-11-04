"""`file://` URLs on the local backend behave like bare paths in every policy state (#59)."""
from __future__ import annotations

import io

import pytest

from mountainash_transport import StorageFacade, copy_between
from mountainash_transport.location import LocationNotAllowed, LocationPolicy

POLICIES = {
    "none": lambda root: None,
    "inactive": lambda root: LocationPolicy(allow_unconfined=True),
    "active": lambda root: LocationPolicy(root=str(root)),
}
FORMS = {
    "file:///": lambda p: f"file://{p}",
    "file://localhost/": lambda p: f"file://localhost{p}",
}


@pytest.fixture(params=list(POLICIES))
def fac(request, tmp_path):
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "f.txt").write_bytes(b"hello")
    return StorageFacade.for_local(policy=POLICIES[request.param](tmp_path))


@pytest.fixture(params=list(FORMS))
def url(request, tmp_path):
    return lambda rel: FORMS[request.param](str(tmp_path / rel))


def test_reads(fac, url):
    assert fac.read(url("d/f.txt")) == b"hello"
    for access in ("sequential", "random", "buffered"):
        with fac.read_stream(url("d/f.txt"), access=access) as s:
            assert s.read() == b"hello"
    assert fac.exists(url("d/f.txt")) and not fac.exists(url("d/missing"))
    assert fac.get_size(url("d/f.txt")) == 5
    assert fac.metadata(url("d/f.txt")).name == "f.txt"
    assert [e.name for e in fac.list_dir(url("d"))] == ["f.txt"]
    assert [e.name for e in fac.list_objects(url("d")).objects] == ["f.txt"]


def test_writes_and_directories(fac, url, tmp_path):
    fac.write(url("d/w.txt"), b"w")
    fac.write_stream(url("d/s.txt"), io.BytesIO(b"s"))
    fac.copy(url("d/f.txt"), url("d/c.txt"))
    assert [(tmp_path / "d" / n).read_bytes() for n in ("w.txt", "s.txt", "c.txt")] == [b"w", b"s", b"hello"]
    fac.delete(url("d/c.txt"))
    assert not (tmp_path / "d" / "c.txt").exists()
    fac.mkdir(url("d/sub/deeper"))
    assert (tmp_path / "d" / "sub" / "deeper").is_dir()
    fac.rmdir(url("d/sub"))
    assert not (tmp_path / "d" / "sub").exists()


def test_copy_between_facades(fac, url, tmp_path):
    other = StorageFacade.for_local(policy=fac._policy)
    copy_between(url("d/f.txt"), url("d/x.txt"), fac, other)
    assert (tmp_path / "d" / "x.txt").read_bytes() == b"hello"


@pytest.mark.parametrize("bad", ["file://alice:s3cr3t@localhost{p}", "file://otherhost{p}", "file://{p}?q=1"])
def test_non_local_file_urls_refused_without_leaking(fac, tmp_path, bad):
    location = bad.format(p=str(tmp_path / "d" / "f.txt"))
    with pytest.raises(LocationNotAllowed) as ei:
        fac.read(location)
    assert "s3cr3t" not in str(ei.value) and "alice" not in str(ei.value)
    assert not (ei.value.__cause__ or ei.value.__context__)
