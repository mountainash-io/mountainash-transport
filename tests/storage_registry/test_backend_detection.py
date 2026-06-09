"""Tests for storage_registry.backend_detection.detect_provider_from_path."""
from __future__ import annotations

import pytest

from mountainash_transport.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.storage_registry.backend_detection import (
    detect_provider_from_path,
)


def test_local_path_returns_local():
    assert detect_provider_from_path("/tmp/foo") == CONST_STORAGE_PROVIDER_TYPE.LOCAL


def test_relative_local_path_returns_local():
    assert detect_provider_from_path("foo/bar.txt") == CONST_STORAGE_PROVIDER_TYPE.LOCAL


def test_empty_path_returns_local():
    assert detect_provider_from_path("") == CONST_STORAGE_PROVIDER_TYPE.LOCAL


def test_s3_scheme_returns_s3():
    assert (
        detect_provider_from_path("s3://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.S3
    )


def test_gs_scheme_returns_gcs():
    assert (
        detect_provider_from_path("gs://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.GCS
    )


def test_gcs_alias_resolves_to_gcs():
    assert (
        detect_provider_from_path("gcs://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.GCS
    )


def test_azure_scheme_returns_azure_blob():
    assert (
        detect_provider_from_path("azure://container/blob")
        == CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB
    )


def test_az_alias_resolves_to_azure_blob():
    assert (
        detect_provider_from_path("az://container/blob")
        == CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB
    )


def test_minio_scheme_now_resolves():
    assert (
        detect_provider_from_path("minio://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.MINIO
    )


def test_r2_scheme_resolves():
    assert (
        detect_provider_from_path("r2://bucket/key")
        == CONST_STORAGE_PROVIDER_TYPE.R2
    )


def test_ftp_scheme_resolves():
    assert (
        detect_provider_from_path("ftp://host/file")
        == CONST_STORAGE_PROVIDER_TYPE.FTP
    )


def test_github_scheme_resolves():
    assert (
        detect_provider_from_path("github://owner/repo/path")
        == CONST_STORAGE_PROVIDER_TYPE.GITHUB
    )


def test_describe_only_scheme_raises_no_backend():
    with pytest.raises(ValueError, match="has no registered backend"):
        detect_provider_from_path("hdfs://cluster/path")


def test_http_scheme_resolves_to_http_provider():
    from mountainash_transport.constants import CONST_STORAGE_PROVIDER_TYPE
    assert detect_provider_from_path("http://example.com/file.txt") == CONST_STORAGE_PROVIDER_TYPE.HTTP


def test_https_scheme_resolves_to_http_provider():
    from mountainash_transport.constants import CONST_STORAGE_PROVIDER_TYPE
    assert detect_provider_from_path("https://example.com/file.txt") == CONST_STORAGE_PROVIDER_TYPE.HTTP


def test_unrecognised_scheme_raises():
    with pytest.raises(ValueError, match="Unrecognised scheme"):
        detect_provider_from_path("gopher://example.com/")
