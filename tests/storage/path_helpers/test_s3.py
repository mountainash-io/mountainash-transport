"""Tests for S3-specific path extractors."""
from __future__ import annotations

import pytest
from upath import UPath

from mountainash_transport.storage.path_helpers.s3 import s3_bucket, s3_key


@pytest.mark.parametrize(
    "path,expected_bucket",
    [
        ("s3://my-bucket", "my-bucket"),
        ("s3://my-bucket/key", "my-bucket"),
        ("s3://my-bucket/k/nested/file.parquet", "my-bucket"),
        (UPath("s3://b/k"), "b"),
    ],
)
def test_s3_bucket_happy(path, expected_bucket):
    assert s3_bucket(path) == expected_bucket


@pytest.mark.parametrize(
    "path",
    [
        "/local/path",
        "gs://b/k",
        "",
        None,
    ],
)
def test_s3_bucket_non_s3_returns_none(path):
    assert s3_bucket(path) is None


@pytest.mark.parametrize(
    "path,expected_key",
    [
        ("s3://bucket", ""),
        ("s3://bucket/", ""),
        ("s3://bucket/key", "key"),
        ("s3://bucket/a/b/c.parquet", "a/b/c.parquet"),
    ],
)
def test_s3_key_happy(path: str, expected_key: str):
    assert s3_key(path) == expected_key


@pytest.mark.parametrize(
    "path",
    [
        "/local/path",
        "gs://b/k",
        None,
    ],
)
def test_s3_key_non_s3_returns_none(path):
    assert s3_key(path) is None


def test_bug_3_format_namespace_is_gone():
    """Bug 3: old S3PathHelper.format_namespace returned 's3://' even when a
    bucket was extractable. Function deleted — callers compose the string
    from s3_bucket() instead.
    """
    from mountainash_transport.storage.path_helpers import s3

    assert not hasattr(s3, "format_namespace")
