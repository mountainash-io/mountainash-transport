"""Tests for StorageEntry, EntryType, and EnumerateResult."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mountainash_transport._core.dataclasses.storage_entry import (
    EntryType,
    EnumerateResult,
    StorageEntry,
)


class TestEntryType:
    def test_values(self):
        assert EntryType.FILE == "file"
        assert EntryType.DIRECTORY == "directory"
        assert EntryType.PREFIX == "prefix"

    def test_is_str(self):
        assert isinstance(EntryType.FILE, str)


class TestStorageEntry:
    def test_minimal_construction(self):
        entry = StorageEntry(path="/tmp/file.txt", name="file.txt")
        assert entry.path == "/tmp/file.txt"
        assert entry.name == "file.txt"
        assert entry.size is None
        assert entry.last_modified is None
        assert entry.etag == ""
        assert entry.content_type == ""
        assert entry.entry_type == EntryType.FILE
        assert entry.storage_class == ""
        assert entry.source == ""
        assert entry.version_id == ""
        assert entry.checksum == ""
        assert entry.checksum_algorithm == ""

    def test_full_construction(self):
        ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        entry = StorageEntry(
            path="s3://bucket/key.txt",
            name="key.txt",
            size=1024,
            last_modified=ts,
            etag="abc123",
            content_type="text/plain",
            entry_type=EntryType.FILE,
            storage_class="STANDARD",
            source="s3",
            version_id="v1",
            checksum="abc==",
            checksum_algorithm="SHA256",
        )
        assert entry.size == 1024
        assert entry.version_id == "v1"
        assert entry.checksum == "abc=="
        assert entry.checksum_algorithm == "SHA256"

    def test_frozen(self):
        entry = StorageEntry(path="/tmp/f.txt", name="f.txt")
        with pytest.raises(AttributeError):
            entry.path = "/other"

    def test_size_none_vs_zero(self):
        none_entry = StorageEntry(path="/a", name="a", size=None)
        zero_entry = StorageEntry(path="/b", name="b", size=0)
        assert none_entry.size is None
        assert zero_entry.size == 0

    def test_prefix_entry(self):
        entry = StorageEntry(
            path="s3://bucket/data",
            name="data",
            entry_type=EntryType.PREFIX,
            source="s3",
        )
        assert entry.entry_type == EntryType.PREFIX
        assert entry.size is None

    def test_directory_entry(self):
        entry = StorageEntry(
            path="/tmp/mydir",
            name="mydir",
            entry_type=EntryType.DIRECTORY,
            source="local",
        )
        assert entry.entry_type == EntryType.DIRECTORY


class TestEnumerateResult:
    def test_construction(self):
        obj = StorageEntry(path="s3://b/k", name="k", source="s3")
        prefix = StorageEntry(
            path="s3://b/dir", name="dir",
            entry_type=EntryType.PREFIX, source="s3",
        )
        result = EnumerateResult(objects=(obj,), common_prefixes=(prefix,))
        assert len(result.objects) == 1
        assert len(result.common_prefixes) == 1
        assert result.objects[0].name == "k"
        assert result.common_prefixes[0].entry_type == EntryType.PREFIX

    def test_empty(self):
        result = EnumerateResult(objects=(), common_prefixes=())
        assert result.objects == ()
        assert result.common_prefixes == ()

    def test_frozen(self):
        result = EnumerateResult(objects=(), common_prefixes=())
        with pytest.raises(AttributeError):
            result.objects = ()

    def test_tuples_are_immutable(self):
        result = EnumerateResult(objects=(), common_prefixes=())
        with pytest.raises(AttributeError):
            result.objects.append(None)
