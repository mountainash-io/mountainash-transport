"""delete_many: every path attempted, missing counts as deleted, one error lists the failures (#10 §4)."""
from __future__ import annotations

import typing as t
from pathlib import Path

import pytest
from mountainash_auth_client import PasswordAuthProfile

from mountainash_transport import BulkDeleteError, StorageError, StorageFacade
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.settings.storage.profiles import SFTPStorageProfile


@pytest.fixture(params=["local", "sftp"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> t.Iterator[tuple[StorageFacade, Path, str]]:
    """A facade, the real directory behind it, and the facade's path prefix for it."""
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


def test_every_path_is_attempted_and_failures_are_listed_in_input_order(
    store: tuple[StorageFacade, Path, str],
) -> None:
    facade, root, prefix = store
    for name in ("ok1", "ok2", "ok3"):
        (root / name).write_bytes(b"x")
    (root / "bad1").mkdir()  # a directory is not deleted by a file delete
    (root / "bad2").mkdir()
    names = ["ok1", "bad1", "ok2", "missing", "bad2", "ok3"]
    with pytest.raises(BulkDeleteError) as caught:
        facade.delete_many(f"{prefix}/{name}" for name in names)
    assert [path.rsplit("/", 1)[-1] for path, _ in caught.value.failures] == ["bad1", "bad2"]
    assert all(isinstance(error, StorageError) for _, error in caught.value.failures)
    assert "2 path(s)" in str(caught.value)
    assert sorted(p.name for p in root.iterdir()) == ["bad1", "bad2"]


def test_missing_paths_and_missing_parents_count_as_deleted(store: tuple[StorageFacade, Path, str]) -> None:
    facade, root, prefix = store
    (root / "a").write_bytes(b"x")
    facade.delete_many([f"{prefix}/a", f"{prefix}/a", f"{prefix}/missing", f"{prefix}/no-such-dir/file"])
    assert list(root.iterdir()) == []


def test_empty_input_does_nothing(store: tuple[StorageFacade, Path, str]) -> None:
    facade, _root, _prefix = store
    facade.delete_many([])


def test_a_path_outside_the_root_is_refused_before_anything_is_deleted(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"x")
    with StorageFacade(P.LOCAL, policy=LocationPolicy(root=str(tmp_path))) as facade, \
            pytest.raises(LocationNotAllowed):
        facade.delete_many(iter([str(tmp_path / "a.txt"), str(tmp_path / ".." / "x")]))
    assert (tmp_path / "a.txt").exists()


def test_the_error_message_names_a_few_paths_and_counts_the_rest() -> None:
    failures = tuple((f"s3://b/k{i}", StorageError("denied")) for i in range(7))
    message = str(BulkDeleteError(failures))
    assert message.startswith("7 path(s) could not be deleted: s3://b/k0, ")
    assert "s3://b/k4" in message and "s3://b/k5" not in message and "(+2 more)" in message


# --- S3 ---------------------------------------------------------------------


def _s3() -> tuple[t.Any, t.Any]:
    import boto3
    from botocore.stub import Stubber

    from mountainash_transport.storage.backends.s3 import S3StorageBackend

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    backend = S3StorageBackend(None)
    backend._client = client
    return backend, Stubber(client)


def _expect(stub: t.Any, bucket: str, keys: list[str], errors: list[dict[str, str]] | None = None) -> None:
    stub.add_response(
        "delete_objects", {"Errors": errors or []},
        {"Bucket": bucket, "Delete": {"Objects": [{"Key": k} for k in keys], "Quiet": True}},
    )


def test_s3_sends_one_request_per_bucket_per_thousand_keys() -> None:
    backend, stub = _s3()
    a_keys = [f"a{i}" for i in range(2500)]
    b_keys = ["b0", "b1", "b2"]
    paths = [f"s3://a/{k}" for k in a_keys[:1]] + [f"s3://b/{k}" for k in b_keys[:1]] \
        + [f"s3://a/{k}" for k in a_keys[1:]] + [f"s3://b/{k}" for k in b_keys[1:]]
    _expect(stub, "a", a_keys[:1000])
    _expect(stub, "a", a_keys[1000:2000])
    _expect(stub, "a", a_keys[2000:])
    _expect(stub, "b", b_keys)
    with stub:
        backend.delete_many(paths)
        stub.assert_no_pending_responses()


def test_s3_sends_a_repeated_key_once() -> None:
    backend, stub = _s3()
    _expect(stub, "a", ["k1", "k2"])
    with stub:
        backend.delete_many(["s3://a/k1", "s3://a/k2", "s3://a/k1"])
        stub.assert_no_pending_responses()


def test_s3_per_key_failures_are_mapped_and_listed_in_input_order() -> None:
    from mountainash_transport import PermissionDeniedError

    backend, stub = _s3()
    paths = ["s3://a/k1", "s3://b/k2", "s3://a/k3", "s3://a/gone", "s3://b/k4"]
    _expect(stub, "a", ["k1", "k3", "gone"], [
        {"Key": "k3", "Code": "AccessDenied", "Message": "denied"},
        {"Key": "gone", "Code": "NoSuchKey", "Message": "missing"},  # D4: counts as deleted
    ])
    _expect(stub, "b", ["k2", "k4"], [
        {"Key": "k4", "Code": "AccessDenied", "Message": "denied"},
        {"Key": "k2", "Code": "AccessDenied", "Message": "denied"},
    ])
    with stub, pytest.raises(BulkDeleteError) as caught:
        backend.delete_many(paths)
    assert [path for path, _ in caught.value.failures] == ["s3://b/k2", "s3://a/k3", "s3://b/k4"]
    assert all(type(error) is PermissionDeniedError for _, error in caught.value.failures)


def test_s3_missing_bucket_counts_as_deleted_and_a_denied_chunk_lists_all_its_keys() -> None:
    backend, stub = _s3()
    stub.add_client_error("delete_objects", service_error_code="NoSuchBucket", http_status_code=404)
    stub.add_client_error("delete_objects", service_error_code="AccessDenied", http_status_code=403)
    with stub, pytest.raises(BulkDeleteError) as caught:
        backend.delete_many(["s3://gone/k1", "s3://locked/k1", "s3://locked/k2"])
    assert [path for path, _ in caught.value.failures] == ["s3://locked/k1", "s3://locked/k2"]
