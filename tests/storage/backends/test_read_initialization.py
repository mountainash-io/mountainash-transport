"""Opening failures release acquired handles; profile settings retain validation."""
from __future__ import annotations

import io
import typing as t
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mountainash_transport import RangePolicy, StorageError
from mountainash_transport.storage.backends.sftp import SFTPStorageBackend


def test_profile_does_not_discard_invalid_zero_block_size() -> None:
    with pytest.raises(ValueError):
        RangePolicy.from_profile(SimpleNamespace(RANGE_BLOCK_SIZE=0))


def test_sftp_stat_failure_is_mapped_and_closes_handle() -> None:
    handle = MagicMock()
    handle.stat.side_effect = OSError("cannot stat")
    client = MagicMock()
    client.open.return_value = handle
    backend = SFTPStorageBackend(None)
    backend._get_client = lambda: client  # type: ignore[method-assign]
    with pytest.raises(StorageError):
        backend.open_ranged("/file")
    handle.close.assert_called_once()


@pytest.mark.parametrize("provider", ["s3", "sftp"])
def test_empty_ranged_objects_do_not_fetch(provider: str) -> None:
    from mountainash_transport._core.ranged_io import RangedReader
    from mountainash_transport.storage.backends.s3 import S3StorageBackend
    client = MagicMock()
    if provider == "s3":
        backend: t.Any = S3StorageBackend(None)
        backend._client = client
        client.head_object.return_value = {"ContentLength": 0}
    else:
        backend = SFTPStorageBackend(None)
        backend._get_client = lambda: client
        handle = MagicMock(spec=io.BytesIO)
        handle.stat = lambda: SimpleNamespace(st_size=0)
        client.open.return_value = handle
    with RangedReader(backend.open_ranged("bucket/file"), RangePolicy()) as stream:
        assert stream.read() == b""
    client.get_object.assert_not_called()
