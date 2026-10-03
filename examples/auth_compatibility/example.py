"""Pair storage profiles with auth profiles; see rejections before any I/O."""

from mountainash_auth_client import IAMAuthProfile, PasswordAuthProfile

from mountainash_transport import create_connection
from mountainash_transport.connections.errors import UnsupportedAuthProfileError
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile


def rejected(profile: S3StorageProfile, auth: object) -> str:
    try:
        create_connection(profile, auth)
    except UnsupportedAuthProfileError:
        return "unsupported auth mode"
    except ValueError:
        return "invalid for flavor"
    return "accepted"


def main() -> None:
    aws = S3StorageProfile(FLAVOR="aws", REGION="ap-southeast-2", BUCKET="reports")
    r2 = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="abc123", BUCKET="reports")
    keys = IAMAuthProfile(ACCESS_KEY_ID="example-access-key", SECRET_ACCESS_KEY="example-secret")
    role = IAMAuthProfile(ROLE_ARN="arn:aws:iam::123456789012:role/reports-reader")
    password = PasswordAuthProfile(USERNAME="report_user", PASSWORD="example-password")

    results = {
        "aws + access keys": rejected(aws, keys),
        "aws + assume role": rejected(aws, role),
        "aws + password": rejected(aws, password),
        "r2 + assume role": rejected(r2, role),
    }
    assert results == {
        "aws + access keys": "accepted",
        "aws + assume role": "accepted",
        "aws + password": "unsupported auth mode",
        "r2 + assume role": "invalid for flavor",
    }
    for pairing, outcome in results.items():
        print(f"{pairing}: {outcome}")


if __name__ == "__main__":
    main()
