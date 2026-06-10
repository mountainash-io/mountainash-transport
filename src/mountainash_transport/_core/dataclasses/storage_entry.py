"""StorageEntry — unified resource descriptor for all storage backends."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EntryType(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    PREFIX = "prefix"


@dataclass(frozen=True, slots=True)
class StorageEntry:
    """A single storage resource — file, directory, or object-store prefix."""

    path: str
    name: str
    size: int | None = None
    last_modified: datetime | None = None
    etag: str = ""
    content_type: str = ""
    entry_type: EntryType = EntryType.FILE
    storage_class: str = ""
    source: str = ""
    version_id: str = ""
    checksum: str = ""
    checksum_algorithm: str = ""


@dataclass(frozen=True, slots=True)
class EnumerateResult:
    """Structured return type for object-store listings."""

    objects: tuple[StorageEntry, ...]
    common_prefixes: tuple[StorageEntry, ...]
