"""Facade move(): a native rename on Local and SFTP; refused where the store has none (#10)."""
from __future__ import annotations

import os
import tempfile
import typing as t
from pathlib import Path

import pytest
from mountainash_auth_client import IAMAuthProfile, PasswordAuthProfile

from mountainash_transport import (
    PathNotFoundError,
    StorageError,
    StorageFacade,
    UnsupportedOperationError,
)
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.settings.storage.profiles import S3StorageProfile, SFTPStorageProfile


@pytest.fixture(params=["local", "sftp"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> t.Iterator[tuple[StorageFacade, Path, str]]:
    """A facade, the real directory behind it, and the path prefix the facade uses for it."""
    root = tmp_path / "root"
    root.mkdir()
    if request.param == "local":
        with StorageFacade.for_local() as facade:
            yield facade, root, str(root)
        return
    from connections.tunnel_rig import DirectorySFTPTarget

    server = DirectorySFTPTarget(root)
    known = tmp_path / "known_hosts"
    known.write_text(server.known_hosts_line("127.0.0.1"))
    profile = SFTPStorageProfile(HOST="127.0.0.1", PORT=server.port, USERNAME="u", KNOWN_HOSTS_FILE=str(known),
                                 LOOK_FOR_KEYS=False, ALLOW_AGENT=False)
    try:
        with StorageFacade(P.SFTP, profile, auth_profile=PasswordAuthProfile(USERNAME="u", PASSWORD="p")) as facade:
            yield facade, root, ""
    finally:
        server.close()


def test_move_renames(store: tuple[StorageFacade, Path, str]) -> None:
    facade, root, prefix = store
    (root / "a.csv").write_bytes(b"region,total\n")
    facade.move(f"{prefix}/a.csv", f"{prefix}/b.csv")
    assert not (root / "a.csv").exists()
    assert (root / "b.csv").read_bytes() == b"region,total\n"


def test_move_overwrites_the_destination(store: tuple[StorageFacade, Path, str]) -> None:
    facade, root, prefix = store
    (root / "a.csv").write_bytes(b"new")
    (root / "b.csv").write_bytes(b"old")
    facade.move(f"{prefix}/a.csv", f"{prefix}/b.csv")
    assert (root / "b.csv").read_bytes() == b"new"
    assert not (root / "a.csv").exists()


def test_move_of_a_missing_source_is_absence(store: tuple[StorageFacade, Path, str]) -> None:
    facade, root, prefix = store
    with pytest.raises(PathNotFoundError):
        facade.move(f"{prefix}/missing.csv", f"{prefix}/b.csv")


def test_move_creates_destination_parents_unless_told_not_to(store: tuple[StorageFacade, Path, str]) -> None:
    facade, root, prefix = store
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
