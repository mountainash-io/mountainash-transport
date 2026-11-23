"""StorageFacade.local_path: a plain local file for native readers, or None (#27)."""
from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from mountainash_transport import Gzip, PathNotFoundError, StorageError, StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy


def test_local_file_resolves_to_an_absolute_path_a_native_reader_can_open(tmp_path: Path) -> None:
    (tmp_path / "sales.csv").write_bytes(b"region,total\n")
    with StorageFacade.for_local() as storage:
        for spelling in (str(tmp_path / "sales.csv"), (tmp_path / "sales.csv").as_uri()):
            resolved = storage.local_path(spelling)
            assert resolved == str(tmp_path / "sales.csv")
            assert Path(resolved).read_bytes() == b"region,total\n"


def test_missing_file_raises_like_read_stream(tmp_path: Path) -> None:
    with StorageFacade.for_local() as storage:
        with pytest.raises(PathNotFoundError):
            storage.local_path(str(tmp_path / "missing.csv"))


def test_directory_is_refused_like_read_stream(tmp_path: Path) -> None:
    with StorageFacade.for_local() as storage:
        with pytest.raises(StorageError):
            storage.local_path(str(tmp_path))


@pytest.mark.parametrize("options", [{"pipeline": Gzip()}, {"infer": True}], ids=["passed", "inferred"])
def test_a_transform_pipeline_means_no_plain_file(tmp_path: Path, options: dict) -> None:
    (tmp_path / "sales.csv.gz").write_bytes(gzip.compress(b"region,total\n"))
    with StorageFacade.for_local() as storage:
        assert storage.local_path(str(tmp_path / "sales.csv.gz"), **options) is None


def test_inferred_pipeline_without_transform_suffix_still_resolves(tmp_path: Path) -> None:
    (tmp_path / "sales.csv").write_bytes(b"x")
    with StorageFacade.for_local() as storage:
        assert storage.local_path(str(tmp_path / "sales.csv"), infer=True) == str(tmp_path / "sales.csv")


def test_location_policy_applies(tmp_path: Path) -> None:
    inside = tmp_path / "root"
    inside.mkdir()
    (tmp_path / "outside.csv").write_bytes(b"x")
    with StorageFacade.for_local(policy=LocationPolicy(root=str(inside))) as storage:
        with pytest.raises(LocationNotAllowed):
            storage.local_path(str(tmp_path / "outside.csv"))


def test_remote_backend_returns_none_without_io() -> None:
    url = "http://files.example.invalid/sales.csv"  # unresolvable: any request would fail
    with StorageFacade.from_path(url) as storage:
        assert storage.local_path(url) is None
