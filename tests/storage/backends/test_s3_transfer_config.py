"""S3 profile transfer settings reach boto3's transfer manager (#4)."""
from __future__ import annotations

import io
import typing as t

import pytest

import mountainash_transport.storage.backends  # noqa: F401
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
from mountainash_transport.storage.backends.s3 import S3StorageBackend

MIB = 1024 * 1024
PAYLOAD = b"z" * (6 * MIB)  # below boto3's default 8 MiB threshold


def _backend(profile: S3StorageProfile, calls: list[str]) -> tuple[S3StorageBackend, t.Any]:
    """A real boto3 client with stubbed responses, so the transfer manager decides the requests."""
    import boto3
    from botocore.stub import Stubber

    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="k", aws_secret_access_key="s")
    stub = Stubber(client)
    responses = {
        "put_object": {}, "create_multipart_upload": {"UploadId": "u"},
        "upload_part": {"ETag": '"e"'}, "complete_multipart_upload": {},
    }
    for operation in calls:
        stub.add_response(operation, responses[operation], None)
    stub.activate()
    backend = S3StorageBackend(profile)
    backend._client = client
    return backend, stub


def test_defaults_keep_boto3_transfer_settings() -> None:
    backend, stub = _backend(S3StorageProfile(FLAVOR="aws", REGION="us-east-1"), ["put_object"])
    backend.write_from_stream("s3://b/k", io.BytesIO(PAYLOAD))
    stub.assert_no_pending_responses()


def test_profile_threshold_and_part_size_drive_multipart_upload() -> None:
    profile = S3StorageProfile(
        FLAVOR="aws", REGION="us-east-1",
        MULTIPART_THRESHOLD=1 * MIB, MULTIPART_CHUNKSIZE=5 * MIB, MAX_CONCURRENCY=1,
    )
    calls = ["create_multipart_upload", "upload_part", "upload_part", "complete_multipart_upload"]
    backend, stub = _backend(profile, calls)
    backend.write_from_stream("s3://b/k", io.BytesIO(PAYLOAD))
    stub.assert_no_pending_responses()


@pytest.mark.parametrize("field", ["MULTIPART_THRESHOLD", "MULTIPART_CHUNKSIZE", "MAX_CONCURRENCY"])
def test_transfer_settings_are_not_boto3_client_arguments(field: str) -> None:
    from mountainash_auth_client.targets import TargetFamily

    profile = S3StorageProfile(FLAVOR="aws", REGION="us-east-1", **{field: 8 * MIB})
    assert field.lower() not in profile.emit(TargetFamily.BOTO)
