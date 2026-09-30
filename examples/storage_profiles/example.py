"""Build S3-family profiles and inspect the SDK arguments they emit."""

from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile
from mountainash_transport.settings.storage.registry import get_settings_class, get_spec


def main() -> None:
    aws = S3StorageProfile(FLAVOR="aws", REGION="ap-southeast-2", BUCKET="reports")
    r2 = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="abc123", BUCKET="reports")

    aws_kwargs = aws.to_handler_kwargs()
    r2_kwargs = r2.to_handler_kwargs()
    assert aws_kwargs["region_name"] == "ap-southeast-2"
    assert "endpoint_url" not in aws_kwargs
    assert r2_kwargs["endpoint_url"] == "https://abc123.r2.cloudflarestorage.com"
    assert not any("secret" in key or "access_key" in key for key in {*aws_kwargs, *r2_kwargs})

    spec = get_spec("s3")
    assert get_settings_class("s3") is S3StorageProfile
    assert "FLAVOR" in {parameter.name for parameter in spec.parameters}

    print(f"aws: {aws.get_connection_url()}")
    print(f"r2: {r2.get_connection_url()}")
    print(f"s3 auth modes: {', '.join(sorted(mode.value for mode in spec.supported_auth))}")


if __name__ == "__main__":
    main()
