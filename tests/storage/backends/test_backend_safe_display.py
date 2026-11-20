"""W8: backend errors show the display form and safe native text only."""
from __future__ import annotations

import errno
import traceback
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mountainash_transport._core.exceptions import StorageError

SENTINELS = ("SENTU", "SENTP", "SENTQ", "SENTF")
# parse_s3_path rejects userinfo before any client call, so the S3 location carries only query and fragment.
S3_REMOTE = "s3://host/dir/x.csv?sig=SENTQ#SENTF"


def _chain(exc):
    pending, seen = [exc], set()
    while pending:
        current = pending.pop()
        if id(current) not in seen:
            seen.add(id(current))
            yield current
            pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)


def _assert_no_sentinel(exc):
    text = "".join(traceback.format_exception(exc))
    for link in _chain(exc):
        text += str(link) + repr(link) + repr(link.args) + repr(vars(link))
    for sentinel in SENTINELS:
        assert sentinel not in text


def _s3_backend(error):
    from mountainash_transport.storage.backends.s3 import S3StorageBackend
    client = MagicMock()
    client.get_object.side_effect = error
    client.head_object.side_effect = error
    backend = S3StorageBackend(None)
    backend._client = client
    return backend


def _sftp_backend(error):
    from mountainash_transport.storage.backends.sftp import SFTPStorageBackend
    client = MagicMock()
    client.open.side_effect = error
    client.stat.side_effect = error
    return SFTPStorageBackend(connection=SimpleNamespace(client=client))


def _s3_errors():
    from botocore import exceptions as e
    return [
        e.ClientError({"Error": {"Code": "SlowDown", "Message": "SENTP"}}, "GetObject"),
        e.EndpointConnectionError(endpoint_url="https://SENTU:SENTP@h/?sig=SENTQ"),
        ConnectionResetError(errno.ECONNRESET, "Connection reset by peer"),
    ]


def _sftp_errors():
    import paramiko
    return [
        paramiko.SSHException("SENTU:SENTP@host"),
        OSError(errno.EIO, "I/O error", "/dir/SENTP"),
        paramiko.SFTPError("SENTQ"),
    ]


@pytest.mark.parametrize("index", range(3))
def test_s3_errors_show_display_form(index):
    backend = _s3_backend(_s3_errors()[index])
    with pytest.raises(StorageError) as ei:
        backend.read_to_bytes(S3_REMOTE)
    assert "s3://host/dir/x.csv" in str(ei.value)
    _assert_no_sentinel(ei.value)


@pytest.mark.parametrize("index", range(3))
def test_sftp_errors_show_display_form(index):
    backend = _sftp_backend(_sftp_errors()[index])
    with pytest.raises(StorageError) as ei:
        backend.read_to_bytes("/dir/x.csv")
    _assert_no_sentinel(ei.value)


def test_oserror_filename_unreachable(tmp_path):
    from mountainash_transport.storage.backends.local import LocalStorageBackend
    target = tmp_path / "SENTU:SENTP@h"
    target.mkdir()
    with pytest.raises(StorageError) as ei:
        LocalStorageBackend(None).read_to_bytes(str(target))   # IsADirectoryError, errno EISDIR
    assert "[Errno 21] Is a directory" in str(ei.value)
    for link in list(_chain(ei.value))[1:]:
        assert getattr(link, "filename", None) is None
    assert ei.value.__context__ is None


def test_deferred_local_read_failure_chain_is_fresh(tmp_path, monkeypatch):
    from mountainash_transport.storage.backends.local._io import _LocalReader
    source = MagicMock()
    source.closed = False
    source.read.side_effect = OSError(errno.EIO, "I/O error", "/SENTP")
    with pytest.raises(StorageError) as ei:
        _LocalReader(source, "/data/x.csv").read()
    assert type(ei.value.__cause__) is OSError and ei.value.__cause__.filename is None
    assert ei.value.__context__ is None
