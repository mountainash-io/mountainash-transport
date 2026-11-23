"""Facade move(): a native rename on Local and SFTP; refused where the store has none (#10)."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from mountainash_auth_client import IAMAuthProfile

from mountainash_transport import (
    PathNotFoundError,
    StorageError,
    StorageFacade,
    UnsupportedOperationError,
)
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.settings.storage.profiles import S3StorageProfile

Store = tuple[str, StorageFacade, Path, str]  # the shared `store` fixture (tests/storage/conftest.py)


def test_move_renames(store: Store) -> None:
    _backend, facade, root, prefix = store
    (root / "a.csv").write_bytes(b"region,total\n")
    facade.move(f"{prefix}/a.csv", f"{prefix}/b.csv")
    assert not (root / "a.csv").exists()
    assert (root / "b.csv").read_bytes() == b"region,total\n"


def test_move_overwrites_the_destination(store: Store) -> None:
    _backend, facade, root, prefix = store
    (root / "a.csv").write_bytes(b"new")
    (root / "b.csv").write_bytes(b"old")
    facade.move(f"{prefix}/a.csv", f"{prefix}/b.csv")
    assert (root / "b.csv").read_bytes() == b"new"
    assert not (root / "a.csv").exists()


def test_move_of_a_missing_source_is_absence(store: Store) -> None:
    _backend, facade, root, prefix = store
    with pytest.raises(PathNotFoundError):
        facade.move(f"{prefix}/missing.csv", f"{prefix}/b.csv")


def test_move_creates_destination_parents_unless_told_not_to(store: Store) -> None:
    _backend, facade, root, prefix = store
    (root / "a.csv").write_bytes(b"x")
    with pytest.raises(PathNotFoundError):
        facade.move(f"{prefix}/a.csv", f"{prefix}/new/b.csv", create_parents=False)
    assert (root / "a.csv").exists()
    facade.move(f"{prefix}/a.csv", f"{prefix}/new/deeper/b.csv")
    assert (root / "new" / "deeper" / "b.csv").read_bytes() == b"x"


def test_move_is_refused_where_the_store_cannot_rename() -> None:
    profile = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL="http://127.0.0.1:9", BUCKET="b")
    with StorageFacade(P.MINIO, profile, auth_profile=IAMAuthProfile(ACCESS_KEY_ID="k", SECRET_ACCESS_KEY="s")) as s3, \
            pytest.raises(UnsupportedOperationError):
        s3.move("minio://b/a.csv", "minio://b/b.csv")


def test_move_checks_both_paths_against_the_location_policy(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_bytes(b"x")
    with StorageFacade(P.LOCAL, policy=LocationPolicy(root=str(tmp_path))) as facade, \
            pytest.raises(LocationNotAllowed):
        facade.move(str(tmp_path / "a.csv"), str(tmp_path.parent / "escaped.csv"))
    assert (tmp_path / "a.csv").exists()


def test_local_move_across_filesystems_is_a_storage_error(tmp_path: Path) -> None:
    other = Path(tempfile.mkdtemp(dir="/dev/shm")) if os.path.isdir("/dev/shm") else None
    if other is None or os.stat(other).st_dev == os.stat(tmp_path).st_dev:
        pytest.skip("needs two filesystems")
    (tmp_path / "a.csv").write_bytes(b"x")
    try:
        with StorageFacade.for_local() as facade, pytest.raises(StorageError) as caught:
            facade.move(str(tmp_path / "a.csv"), str(other / "a.csv"))
        assert not isinstance(caught.value, PathNotFoundError)
        assert (tmp_path / "a.csv").exists()
    finally:
        for leftover in other.iterdir():
            leftover.unlink()
        other.rmdir()
