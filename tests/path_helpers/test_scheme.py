"""Tests for the scheme registry."""
from __future__ import annotations

import dataclasses

import pytest

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.path_helpers.scheme import (
    SCHEMES,
    SchemeSpec,
    _ALIAS_TO_CANONICAL,
)


def test_every_canonical_scheme_is_lowercase():
    for key, spec in SCHEMES.items():
        assert key == spec.scheme, f"key {key!r} must match spec.scheme {spec.scheme!r}"
        assert spec.scheme == spec.scheme.lower()


def test_aliases_are_lowercase_and_unique():
    seen: set[str] = set()
    for spec in SCHEMES.values():
        for alias in spec.aliases:
            assert alias == alias.lower()
            assert alias not in SCHEMES, f"alias {alias!r} collides with a canonical key"
            assert alias not in seen, f"alias {alias!r} repeats across SchemeSpecs"
            seen.add(alias)


def test_alias_to_canonical_covers_every_alias():
    expected = {
        alias: spec.scheme
        for spec in SCHEMES.values()
        for alias in spec.aliases
    }
    assert _ALIAS_TO_CANONICAL == expected


@pytest.mark.parametrize(
    "expected_key",
    [
        "", "file", "s3", "s3u", "gs", "azure", "sftp", "ftp", "ssh", "smb",
        "b2", "github", "dbfs", "hdfs", "webhdfs", "spark", "trino",
        "gdrive", "dropbox", "onedrive", "sharepoint",
    ],
)
def test_expected_schemes_present(expected_key: str):
    assert expected_key in SCHEMES


def test_bare_local_scheme_is_non_strict():
    assert SCHEMES[""].strict is False


def test_gcs_alias_resolves_to_gs():
    assert _ALIAS_TO_CANONICAL["gcs"] == "gs"


def test_az_alias_resolves_to_azure():
    assert _ALIAS_TO_CANONICAL["az"] == "azure"


def test_schemespec_is_frozen():
    spec = SCHEMES["s3"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.scheme = "nope"  # type: ignore[misc]


def test_schemespec_has_provider_field_defaulting_to_none():
    spec = SchemeSpec(scheme="example")
    assert spec.provider is None


def test_schemespec_accepts_provider():
    spec = SchemeSpec(scheme="s3", provider=CONST_STORAGE_PROVIDER_TYPE.S3)
    assert spec.provider == CONST_STORAGE_PROVIDER_TYPE.S3


_EXPECTED_PROVIDERS: dict[str, CONST_STORAGE_PROVIDER_TYPE] = {
    "":          CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    "file":      CONST_STORAGE_PROVIDER_TYPE.LOCAL,
    "s3":        CONST_STORAGE_PROVIDER_TYPE.S3,
    "s3express": CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    "gs":        CONST_STORAGE_PROVIDER_TYPE.GCS,
    "azure":     CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
    "r2":        CONST_STORAGE_PROVIDER_TYPE.R2,
    "minio":     CONST_STORAGE_PROVIDER_TYPE.MINIO,
    "b2":        CONST_STORAGE_PROVIDER_TYPE.B2,
    "sftp":      CONST_STORAGE_PROVIDER_TYPE.SFTP,
    "ssh":       CONST_STORAGE_PROVIDER_TYPE.SSH,
    "ftp":       CONST_STORAGE_PROVIDER_TYPE.FTP,
    "smb":       CONST_STORAGE_PROVIDER_TYPE.SMB,
    "github":    CONST_STORAGE_PROVIDER_TYPE.GITHUB,
}

_DESCRIBE_ONLY_SCHEMES: tuple[str, ...] = (
    "s3u", "http", "https", "dbfs", "hdfs", "webhdfs", "spark", "trino",
    "gdrive", "dropbox", "onedrive", "sharepoint",
)


@pytest.mark.parametrize("scheme,expected", list(_EXPECTED_PROVIDERS.items()))
def test_known_schemes_map_to_expected_providers(
    scheme: str, expected: CONST_STORAGE_PROVIDER_TYPE
):
    assert SCHEMES[scheme].provider == expected


@pytest.mark.parametrize("scheme", _DESCRIBE_ONLY_SCHEMES)
def test_describe_only_schemes_have_none_provider(scheme: str):
    assert SCHEMES[scheme].provider is None


def test_every_spec_has_provider_attribute():
    for spec in SCHEMES.values():
        assert hasattr(spec, "provider")


def test_new_entries_present():
    for key in ("s3express", "r2", "minio", "http", "https"):
        assert key in SCHEMES
