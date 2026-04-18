"""Tests for StoragePath.

Regression tests for bugs documented in the hygiene spec are grouped
under the `test_bug_*` names so coverage maps directly onto the bug list.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest
from upath import UPath

from mountainash_utils_files.path_helpers.storage_path import StoragePath


@pytest.mark.parametrize(
    "path,expected",
    [
        ("s3://bucket/object", "s3"),
        ("gs://bucket/object", "gs"),
        ("gcs://bucket/object", "gs"),        # alias resolves
        ("azure://container/blob", "azure"),
        ("az://container/blob", "azure"),     # alias resolves
        ("sftp://user@host/p", "sftp"),
        ("ftp://host/p", "ftp"),
        ("ssh://user@host/p", "ssh"),
        ("smb://host/share/p", "smb"),
        ("b2://bucket/key", "b2"),
        ("github://owner/repo/p", "github"),
        ("dbfs:/some/path", "dbfs"),
        ("hdfs://host/path", "hdfs"),
        ("file:///tmp/x", "file"),
        ("SSH://user@host/p", "ssh"),         # forgiving on case
        ("S3://bucket/object", "s3"),         # forgiving on case
    ],
)
def test_identify_scheme_known(path: str, expected: str):
    assert StoragePath.identify_scheme(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/path/to/file",
        "~",
        "~/",
        "~/data/dir/",
        "randomfile.txt",
        "./file.txt",
        "../file.txt",
        "/",
    ],
)
def test_identify_scheme_bare_is_empty_string(path: str):
    assert StoragePath.identify_scheme(path) == ""


def test_identify_scheme_upath_input():
    assert StoragePath.identify_scheme(UPath("s3://bucket/key")) == "s3"


def test_identify_scheme_none_is_empty_string():
    assert StoragePath.identify_scheme(None) == ""


def test_identify_scheme_empty_string_is_empty_string():
    assert StoragePath.identify_scheme("") == ""


def test_bug_5_unknown_backend_scheme_returns_none_not_raises():
    """Bug 5: Old identify_storage_system returned keys without matching helpers.

    New contract: unrecognised scheme → None (not KeyError, not ValueError).
    """
    assert StoragePath.identify_scheme("nonsense://x") is None


def test_bug_7_no_print_on_unknown_scheme():
    """Bug 7: Old code printed a diagnostic on unknown schemes."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        StoragePath.identify_scheme("nonsense://x")
    assert buf.getvalue() == ""


def test_to_str_none_passthrough():
    assert StoragePath.to_str(None) is None


def test_to_str_string_input():
    assert StoragePath.to_str("s3://b/k") == "s3://b/k"


def test_to_str_upath_input():
    assert StoragePath.to_str(UPath("s3://b/k")) == "s3://b/k"


def test_matches_literal():
    assert StoragePath.matches("file.csv", "file.csv") is True


def test_matches_star():
    assert StoragePath.matches("file*.csv", "file1.csv") is True
    assert StoragePath.matches("file*.csv", "file.csv") is True
    assert StoragePath.matches("file*.csv", "nope.csv") is False


def test_matches_question_mark():
    assert StoragePath.matches("f?le.csv", "file.csv") is True
    assert StoragePath.matches("f?le.csv", "fle.csv") is False


def test_matches_no_match():
    assert StoragePath.matches("*.csv", "file.parquet") is False


@pytest.mark.parametrize(
    "path,expected_str",
    [
        ("/path/to/file", "/path/to/file"),
        ("/path/to/file/", "/path/to/file"),
        ("/", "/"),
        ("randomfile.txt", "randomfile.txt"),
        ("randomfile.txt/", "randomfile.txt"),
        ("./file.txt", "file.txt"),
        ("../file.txt", "../file.txt"),
    ],
)
def test_normalize_bare_paths(path: str, expected_str: str):
    result = StoragePath.normalize(path)
    assert result is not None
    assert str(result) == str(UPath(expected_str))


def test_normalize_none_returns_none():
    assert StoragePath.normalize(None) is None


def test_normalize_empty_string_returns_none():
    assert StoragePath.normalize("") is None


def test_normalize_expands_tilde():
    result = StoragePath.normalize("~")
    assert result is not None
    assert not str(result).startswith("~"), f"~ should expand, got {result}"


def test_normalize_upath_input():
    result = StoragePath.normalize(UPath("/tmp/x"))
    assert str(result) == "/tmp/x"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("s3://bucket/object", "s3://bucket/object"),
        ("s3://bucket/object/", "s3://bucket/object"),
        ("s3://bucket", "s3://bucket"),
        ("sftp://user@host/p", "sftp://user@host/p"),
        ("ssh://user@host/p", "ssh://user@host/p"),
        ("github://owner/repo/p", "github://owner/repo/p"),
        ("file:///tmp/x", "file:///tmp/x"),
    ],
)
def test_normalize_schemed_canonical(path: str, expected: str):
    result = StoragePath.normalize(path)
    assert result is not None
    assert str(result) == str(UPath(expected))


def test_normalize_resolves_gcs_alias_to_gs():
    result = StoragePath.normalize("gcs://bucket/key")
    assert result is not None
    assert str(result) == str(UPath("gs://bucket/key"))


def test_normalize_resolves_az_alias_to_azure():
    result = StoragePath.normalize("az://container/blob")
    assert result is not None
    assert str(result) == "azure://container/blob"


def test_bug_2_normalize_always_returns_explicit_value():
    """Bug 2: old `_normalize_path_schema` fell through to None on a valid input branch.

    New contract: every reachable branch returns an explicit value.
    A scheme-valid path is never silently dropped.
    """
    result = StoragePath.normalize("s3://bucket/object")
    assert result is not None, "schemed path must not silently return None"


@pytest.mark.parametrize(
    "path",
    [
        "S3://bucket/object",      # mixed-case canonical
        "SSH://host/p",            # mixed-case canonical
        "GCS://bucket/key",        # mixed-case alias
        "AZ://container/blob",     # mixed-case alias
    ],
)
def test_normalize_mixed_case_scheme_raises(path: str):
    with pytest.raises(ValueError, match="mixed-case|case"):
        StoragePath.normalize(path)


@pytest.mark.parametrize(
    "path",
    [
        "nonsense://bucket/key",
        "totallymadeup://x",
    ],
)
def test_normalize_unknown_scheme_raises(path: str):
    with pytest.raises(ValueError, match="[Uu]nknown scheme"):
        StoragePath.normalize(path)


@pytest.mark.parametrize(
    "path",
    [
        "s3:bucket/object",         # missing //
        "s3:bucket/object/",
    ],
)
def test_normalize_malformed_url_raises(path: str):
    with pytest.raises(ValueError, match="[Mm]alformed|missing|//"):
        StoragePath.normalize(path)


def test_bug_1_no_str_replace_count_kwarg():
    """Bug 1: old code called `str.replace(..., __count=1)` which is a TypeError.

    The new path never calls str.replace with a kwarg, so the defect is
    structurally impossible. This test exercises the valid-input branch
    (which in the old code was unreachable past the dead replace call)
    and asserts it produces a clean result.
    """
    # Exercise the path that would have hit the broken branch in old code.
    result = StoragePath.normalize("s3://bucket/object")
    assert result is not None
    assert str(result) == "s3://bucket/object"
