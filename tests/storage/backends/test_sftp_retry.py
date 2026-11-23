"""SFTP operations survive a dropped session: reconnect and retry (#5).

A real loopback SFTP server drops every session from its side, as a network
outage would; the backend must reconnect and run the operation again.
"""
from __future__ import annotations

import io
import os
import typing as t
from pathlib import Path

import pytest

from mountainash_transport import PathNotFoundError, PermissionDeniedError, StorageConnectionError
from mountainash_transport.storage.backends.sftp import SFTPStorageBackend

PAYLOAD = b"region,total\n" * 1000


class Server(t.Protocol):
    sessions: int
    port: int
    def drop_sessions(self) -> None: ...


@pytest.fixture
def rig(tmp_path: Path) -> t.Iterator[tuple[Server, Path, t.Callable[..., SFTPStorageBackend]]]:
    from connections.tunnel_rig import DirectorySFTPTarget
    from mountainash_auth_client import PasswordAuthProfile
    from mountainash_transport import create_connection
    from mountainash_transport.settings.storage.profiles import SFTPStorageProfile

    root = tmp_path / "root"
    root.mkdir()
    server = DirectorySFTPTarget(root)
    known = tmp_path / "known_hosts"
    known.write_text(server.known_hosts_line("127.0.0.1"))
    connections: list[t.Any] = []

    def backend(**retry: t.Any) -> SFTPStorageBackend:
        profile = SFTPStorageProfile(HOST="127.0.0.1", PORT=server.port, USERNAME="u",
                                     KNOWN_HOSTS_FILE=str(known), LOOK_FOR_KEYS=False, ALLOW_AGENT=False,
                                     RETRY_BACKOFF_BASE=0.0, **retry)
        connection = create_connection(profile, PasswordAuthProfile(USERNAME="u", PASSWORD="p")).connect()
        connections.append(connection)
        return SFTPStorageBackend(profile, connection=connection)

    yield t.cast(Server, server), root, backend
    for connection in connections:
        try:
            connection.disconnect()
        except Exception:
            pass
    server.close()


class OneShot(io.RawIOBase):
    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: t.Any) -> int:
        chunk = self._data.read(len(buffer))
        buffer[: len(chunk)] = chunk
        return len(chunk)


def test_read_after_a_dropped_session_reconnects(rig: t.Any) -> None:
    server, root, backend = rig
    (root / "a.csv").write_bytes(PAYLOAD)
    sftp = backend()
    server.drop_sessions()
    assert sftp.read_to_bytes("/a.csv") == PAYLOAD
    assert server.sessions == 2


@pytest.mark.parametrize("operation", ["metadata", "list_dir", "list_objects", "mkdir", "delete", "move", "read_stream"])
def test_every_operation_reconnects(rig: t.Any, operation: str) -> None:
    server, root, backend = rig
    (root / "d").mkdir()
    (root / "d" / "a.csv").write_bytes(PAYLOAD)
    sftp = backend()
    server.drop_sessions()
    if operation == "metadata":
        assert sftp.get_size("/d/a.csv") == len(PAYLOAD)
    elif operation == "list_dir":
        assert [e.name for e in sftp.list_dir("/d")] == ["a.csv"]
    elif operation == "list_objects":
        assert [e.name for e in sftp.list_objects("/d").objects] == ["a.csv"]
    elif operation == "mkdir":
        sftp.mkdir("/d/new/deeper")
        assert (root / "d" / "new" / "deeper").is_dir()
    elif operation == "delete":
        sftp.delete_file("/d/a.csv")
        assert not (root / "d" / "a.csv").exists()
    elif operation == "move":
        sftp.move("/d/a.csv", "/d/b.csv")
        assert (root / "d" / "b.csv").read_bytes() == PAYLOAD
    else:
        with sftp.read_to_stream("/d/a.csv") as stream:
            assert stream.read() == PAYLOAD
    assert server.sessions == 2


def test_seekable_upload_is_resent_whole_after_a_dropped_session(rig: t.Any) -> None:
    server, root, backend = rig
    sftp = backend()
    server.drop_sessions()
    source = io.BytesIO(b"skip" + PAYLOAD)
    source.seek(4)
    entry = sftp.write_from_stream("/up/b.csv", source)
    assert (root / "up" / "b.csv").read_bytes() == PAYLOAD
    assert entry.size == len(PAYLOAD)  # the resent upload's result, not the dropped attempt's


def test_non_seekable_upload_is_attempted_once(rig: t.Any) -> None:
    server, root, backend = rig
    sftp = backend()
    server.drop_sessions()
    with pytest.raises(StorageConnectionError):
        sftp.write_from_stream("/b.csv", t.cast(t.BinaryIO, OneShot(PAYLOAD)), create_parents=False)
    assert server.sessions == 1


def test_permission_denied_is_not_retried(rig: t.Any) -> None:
    if os.geteuid() == 0:
        pytest.skip("root reads any file")
    server, root, backend = rig
    secret = root / "secret.csv"
    secret.write_bytes(PAYLOAD)
    secret.chmod(0)
    sftp = backend()
    with pytest.raises(PermissionDeniedError):
        sftp.read_to_bytes("/secret.csv")
    assert server.sessions == 1


def test_one_attempt_when_retry_is_disabled(rig: t.Any) -> None:
    server, root, backend = rig
    (root / "a.csv").write_bytes(PAYLOAD)
    sftp = backend(RETRY_MAX_ATTEMPTS=1)
    server.drop_sessions()
    with pytest.raises(StorageConnectionError):
        sftp.read_to_bytes("/a.csv")
    assert server.sessions == 1


def test_delete_whose_reply_was_lost_reports_absence_on_retry() -> None:
    """The file is gone after the first attempt; the retry honestly finds nothing."""
    from mountainash_transport.settings.storage.profiles import SFTPStorageProfile

    class Session:
        def __init__(self, files: set[str]) -> None:
            self.files = files

        def remove(self, path: str) -> None:
            if path not in self.files:
                raise FileNotFoundError(2, "No such file")
            self.files.discard(path)
            if not reconnects:
                raise EOFError("session dropped before the reply")

    files = {"/a.csv"}
    reconnects: list[int] = []

    class Connection:
        client: t.Any = Session(files)

        def disconnect(self) -> None:
            self.client = None

        def connect(self) -> Connection:
            reconnects.append(1)
            self.client = Session(files)
            return self

    profile = SFTPStorageProfile(HOST="h", USERNAME="u", RETRY_BACKOFF_BASE=0.0)
    sftp = SFTPStorageBackend(profile, connection=Connection())
    with pytest.raises(PathNotFoundError):
        sftp.delete_file("/a.csv")
    assert files == set()
    assert reconnects == [1]
