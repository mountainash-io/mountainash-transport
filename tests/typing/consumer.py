"""Installed public typing contract; checked by tools/qualify_typing.py.

Function bodies are never executed. Each line carrying a code-qualified
type-ignore comment is a negative contract: the qualifier strips the comment
and requires that exact error at that line.
"""
from __future__ import annotations

from typing import Any, BinaryIO, assert_type

from mountainash_auth_client import AuthProfile, IAMAuthProfile

from mountainash_transport import (
    AuthenticationError,
    PermissionDeniedError,
    ConnectionProtocol,
    EnumerateResult,
    Gzip,
    HttpNotFoundError,
    HttpRequestEngine,
    HttpResponse,
    HttpTransportError,
    PathNotFoundError,
    Pipeline,
    RangePolicy,
    StorageEntry,
    StorageError,
    StorageFacade,
    StorageProfileProtocol,
    StorageReadProtocol,
    copy_between,
    create_connection,
    infer_pipeline,
    resolve_storage,
)
from mountainash_transport.settings.storage.profiles.local_storage_profile import LocalStorageProfile
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
from mountainash_transport.storage.backends.local import LocalStorageBackend
from mountainash_transport.storage.backends.sftp import SFTPStorageBackend
from mountainash_transport.storage.protocols import StorageEnumerateProtocol


def facade_contracts(storage: StorageFacade, data: bytes) -> None:
    assert_type(StorageFacade.from_path("s3://reports/sales.csv"), StorageFacade)
    assert_type(StorageFacade.for_local(), StorageFacade)
    with StorageFacade.for_local() as owned:
        assert_type(owned, StorageFacade)
        assert_type(owned.close(), None)
    assert_type(storage.read("/tmp/sales.csv"), bytes)
    assert_type(storage.read("/tmp/sales.csv.gz", infer=True, gzip=Gzip()), bytes)
    assert_type(storage.read_stream("/tmp/sales.csv"), BinaryIO)
    assert_type(storage.read_stream("s3://reports/file", access="random",
                                  range_policy=RangePolicy("none")), BinaryIO)
    storage.read_stream("/tmp/file", access="mmap")  # type: ignore[arg-type]
    RangePolicy(cache="invalid")  # type: ignore[arg-type]
    assert_type(storage.metadata("/tmp/sales.csv"), StorageEntry)
    assert_type(storage.list_dir("/tmp"), list[StorageEntry])
    assert_type(storage.list_objects("s3://reports/"), EnumerateResult)
    storage.list_objects("/tmp", max_results="one")  # type: ignore[arg-type]
    assert_type(storage.get_size("/tmp/sales.csv"), int | None)
    assert_type(storage.supports(StorageReadProtocol), bool)
    assert_type(storage.write("/tmp/sales.csv", data, pipeline=Pipeline(Gzip())), None)
    assert_type(storage.write("/tmp/sales.csv", data, create_parents=False), None)
    with storage.read_stream("/tmp/source") as source:
        assert_type(storage.write_stream("/tmp/destination", source, create_parents=False), None)
    storage.write("/tmp/sales.csv", data, create_parents="false")  # type: ignore[arg-type]
    assert_type(copy_between("/a", "/b", storage, storage, destination_pipeline=Gzip()), None)
    assert_type(infer_pipeline("sales.csv.gz"), tuple[Pipeline | None, str])

    storage.read(123)  # type: ignore[arg-type]
    storage.write("/tmp/sales.csv", "not bytes")  # type: ignore[arg-type]
    storage.read("/tmp/sales.csv", pipeline="gzip")  # type: ignore[arg-type]


def filesystem_enumeration_contracts(local: LocalStorageBackend, sftp: SFTPStorageBackend) -> None:
    local_enumerator: StorageEnumerateProtocol = local
    sftp_enumerator: StorageEnumerateProtocol = sftp
    assert_type(local.list_objects("/tmp", delimiter=None, max_results=1), EnumerateResult)
    assert_type(sftp.list_objects("reports", delimiter="/", max_results=1), EnumerateResult)


def error_contracts() -> None:
    assert issubclass(PathNotFoundError, StorageError)
    assert issubclass(HttpNotFoundError, HttpTransportError)
    permission: AuthenticationError = PermissionDeniedError("access denied")
    storage_error: StorageError = permission


def profile_contracts() -> None:
    s3 = S3StorageProfile(FLAVOR="aws", REGION="ap-southeast-2", BUCKET="reports")
    assert_type(s3.FLAVOR, str)
    assert_type(s3.BUCKET, str | None)
    assert_type(s3.CONNECT_TIMEOUT, float | None)
    assert_type(s3.RANGE_CACHE, str | None)
    assert_type(s3.RANGE_BLOCK_SIZE, int | None)
    assert_type(s3.to_handler_kwargs(), dict[str, Any])
    assert_type(s3.get_connection_url(), str)
    local = LocalStorageProfile(ROOT_PATH="/srv/reports")
    assert_type(local.ROOT_PATH, str | None)
    profile: StorageProfileProtocol = s3

    s3.REGION = 5  # type: ignore[assignment]
    s3.NOT_A_FIELD  # type: ignore[attr-defined]
    _ = profile.BUCKET  # type: ignore[attr-defined]


def connection_contracts(profile: StorageProfileProtocol) -> None:
    assert_type(create_connection(profile), ConnectionProtocol[Any])
    assert_type(create_connection(profile, IAMAuthProfile(ACCESS_KEY_ID="k")), ConnectionProtocol[Any])
    storage_profile, auth_profile = resolve_storage("lake")
    assert_type(storage_profile, StorageProfileProtocol)
    assert_type(auth_profile, AuthProfile)

    create_connection("not a profile")  # type: ignore[arg-type]
    resolve_storage(name=1)  # type: ignore[arg-type]


def http_contracts(engine: HttpRequestEngine) -> None:
    assert_type(engine.request("GET", "https://files.example.com/sales.csv"), HttpResponse)
    assert_type(engine.request("GET", "https://files.example.com/sales.csv").content, bytes)

    engine.request("GET", "https://files.example.com", content="text")  # type: ignore[arg-type]
