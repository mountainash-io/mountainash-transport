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


@pytest.mark.parametrize("url,bucket,key", [
    ("s3://b/k/obj.parquet", "b", "k/obj.parquet"),
    ("r2://b/k", "b", "k"),
    ("minio://b/k", "b", "k"),
    ("s3express://b/k", "b", "k"),
    ("b2://b/k", "b", "k"),
    ("s3://b", "b", ""),
    ("s3://b/k/", "b", "k"),                      # normalize strips trailing slash
    ("s3://b/k?versionId=x#frag", "b", "k"),       # query/fragment not part of key
])
def test_s3_family_bucket_key(url, bucket, key):
    assert s3_bucket(url) == bucket
    assert s3_key(url) == key


@pytest.mark.parametrize("url", ["S3://b/k", "R2://b/k", "s3:b/k"])
def test_s3_family_invalid_raises(url):
    with pytest.raises(ValueError):
        s3_bucket(url)


@pytest.mark.parametrize("url", [
    "s3:///b/k",                 # empty netloc → no bucket
    "minio://host:9000/b/k",     # endpoint-in-path is unsupported (endpoint = profile)
])
def test_s3_family_unaddressable(url):
    assert s3_bucket(url) is None
    assert s3_key(url) is None


@pytest.mark.parametrize("url", ["gs://b/k", "/local/path", "file:///x"])
def test_non_family_returns_none(url):
    assert s3_bucket(url) is None
    assert s3_key(url) is None


def test_assume_s3_bare_path():
    assert s3_bucket("b/k", assume_s3=True) == "b"
    assert s3_key("b/k", assume_s3=True) == "k"


def test_parse_s3_path_regression_family():
    """The sole caller benefits: parse_s3_path resolves the whole family (spec §3.5)."""
    from mountainash_transport.storage.backends.s3.s3_path import parse_s3_path
    assert parse_s3_path("r2://b/k/obj") == ("b", "k/obj")
    assert parse_s3_path("minio://b/k") == ("b", "k")
    assert parse_s3_path("s3://b/k") == ("b", "k")
