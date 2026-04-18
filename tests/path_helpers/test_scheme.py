"""Tests for the scheme registry."""
from __future__ import annotations

import dataclasses

import pytest

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
