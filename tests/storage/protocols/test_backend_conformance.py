"""Enforce that every registered backend conforms to its declared protocols."""
import re
from pathlib import Path

import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
from mountainash_transport.storage.protocols import (
    RangedReadProtocol,
    StorageReadProtocol, StorageWriteProtocol,
    StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
    StorageCopyProtocol, StorageDirectoryProtocol, StorageMoveProtocol,
)
from mountainash_transport.storage.registry import get_registered_backends
import mountainash_transport.storage.backends  # noqa: F401

_S3_FAMILY = (P.S3, P.S3EXPRESS, P.R2, P.MINIO, P.B2)
_S3_PROTOCOLS = {
    StorageReadProtocol, StorageWriteProtocol,
    StorageEnumerateProtocol, StorageDeleteProtocol, StorageMetadataProtocol,
    StorageCopyProtocol, RangedReadProtocol,
}

EXPECTED_PROTOCOLS = {
    P.LOCAL: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageDeleteProtocol, StorageMetadataProtocol,
        StorageCopyProtocol, StorageDirectoryProtocol,
        StorageEnumerateProtocol, StorageMoveProtocol,
    },
    **{provider: _S3_PROTOCOLS for provider in _S3_FAMILY},
    P.SFTP: {
        StorageReadProtocol, StorageWriteProtocol,
        StorageDeleteProtocol, StorageMetadataProtocol,
        StorageDirectoryProtocol,
        StorageEnumerateProtocol, RangedReadProtocol, StorageMoveProtocol,
    },
    P.HTTP: {
        StorageReadProtocol, StorageWriteProtocol, StorageMetadataProtocol,
        RangedReadProtocol,
    },
}

# Local random access uses the native file handle, not the ranged-read protocol.
EXCLUDED_PROTOCOLS = {
    P.LOCAL: {RangedReadProtocol},
    **{provider: {StorageDirectoryProtocol, StorageMoveProtocol} for provider in _S3_FAMILY},
    P.SFTP: {StorageCopyProtocol},
    P.HTTP: {
        StorageEnumerateProtocol,
        StorageDeleteProtocol, StorageCopyProtocol, StorageDirectoryProtocol, StorageMoveProtocol,
    },
}


def test_matrix_covers_every_registered_backend():
    assert set(EXPECTED_PROTOCOLS) == set(get_registered_backends())
    assert set(EXCLUDED_PROTOCOLS) == set(get_registered_backends())


# README "Supported storage" table: row label -> providers, column header -> protocol.
_README_ROWS = {
    "Local filesystem": (P.LOCAL,),
    "S3, S3 Express, R2, MinIO, B2": _S3_FAMILY,
    "SFTP": (P.SFTP,),
    "HTTP/HTTPS": (P.HTTP,),
}
_README_COLUMNS = {
    "Read": StorageReadProtocol,
    "Write": StorageWriteProtocol,
    "Metadata": StorageMetadataProtocol,
    "Delete": StorageDeleteProtocol,
    "Copy": StorageCopyProtocol,
    "Move": StorageMoveProtocol,
    "Directories": StorageDirectoryProtocol,
    "Object enumeration": StorageEnumerateProtocol,
    "Ranged reads": RangedReadProtocol,
}


def _readme_support_table() -> tuple[list[str], list[list[str]]]:
    readme = (Path(__file__).parents[3] / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Supported storage", 1)[1].split("\n## ", 1)[0]
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("|") and not re.fullmatch(r"\|[-|\s]+\|", line.strip())
    ]
    return rows[0], rows[1:]


def test_readme_support_table_matches_backends():
    """The README matrix states exactly what each registered backend implements (#48)."""
    header, rows = _readme_support_table()
    assert set(_README_COLUMNS) <= set(header)
    assert {row[0] for row in rows} == set(_README_ROWS)
    backends = get_registered_backends()
    covered = {p for providers in _README_ROWS.values() for p in providers}
    assert covered == set(backends)
    for row in rows:
        for column, protocol in _README_COLUMNS.items():
            claimed = row[header.index(column)] != ""
            for provider in _README_ROWS[row[0]]:
                assert issubclass(backends[provider], protocol) == claimed, (
                    f"README says {row[0]} {column}={claimed}"
                )


class TestProtocolConformance:
    @pytest.mark.parametrize("provider_type", list(EXPECTED_PROTOCOLS.keys()))
    def test_backend_implements_required_protocols(self, provider_type):
        backends = get_registered_backends()
        assert provider_type in backends
        backend_cls = backends[provider_type]
        for protocol in EXPECTED_PROTOCOLS[provider_type]:
            assert issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} does not implement {protocol.__name__}"
            )

    @pytest.mark.parametrize("provider_type", list(EXCLUDED_PROTOCOLS.keys()))
    def test_backend_excludes_unsupported_protocols(self, provider_type):
        backends = get_registered_backends()
        backend_cls = backends[provider_type]
        for protocol in EXCLUDED_PROTOCOLS[provider_type]:
            assert not issubclass(backend_cls, protocol), (
                f"{backend_cls.__name__} should NOT implement {protocol.__name__}"
            )
