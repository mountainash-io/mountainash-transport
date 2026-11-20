"""W8 acceptance: no sentinel from any facade operation, with or without a policy."""
from __future__ import annotations

import io
import logging
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mountainash_transport._core.exceptions import PermissionDeniedError, StorageConnectionError
from mountainash_transport import StorageError, StorageFacade, UnsupportedOperationError
from mountainash_transport.location import LocationPolicy

SENT = ("SENTU", "SENTP", "SENTQ", "SENTF")
POLICIES = [None, LocationPolicy(allow_unconfined=True),
            LocationPolicy(allowed_remote={"http": frozenset({"127.0.0.1"}), "s3": frozenset({"bucket"})})]
OPERATIONS = {
    "read": lambda f, p: f.read(p),
    "read_stream": lambda f, p: f.read_stream(p).read(),
    "write": lambda f, p: f.write(p, b"x"),
    "write_stream": lambda f, p: f.write_stream(p, io.BytesIO(b"x")),
    "metadata": lambda f, p: f.metadata(p),
    "get_size": lambda f, p: f.get_size(p),
    "exists": lambda f, p: f.exists(p),
    "delete": lambda f, p: f.delete(p),
    "list_objects": lambda f, p: f.list_objects(p),
    "list_dir": lambda f, p: f.list_dir(p),
    "mkdir": lambda f, p: f.mkdir(p),
    "rmdir": lambda f, p: f.rmdir(p),
    "copy": lambda f, p: f.copy(p, p + "-copy"),
}
UNSUPPORTED = {
    "http": {"delete", "list_objects", "list_dir", "mkdir", "rmdir", "copy"},
    "s3": {"list_dir", "mkdir", "rmdir"},
    "sftp": {"copy"},
}


def _expect(kind, operation):
    """Exception the operation must raise: unsupported ops fail before any I/O."""
    return UnsupportedOperationError if operation in UNSUPPORTED[kind] else StorageError


def _run(facade, operation, path, expected, caplog):
    with pytest.raises(expected) as info:
        OPERATIONS[operation](facade, path)
    if expected is StorageError:
        assert not isinstance(info.value, UnsupportedOperationError)
    _walk(info.value, caplog.records)
    return info.value


def _walk(exc, records):
    text = "".join(traceback.format_exception(exc))
    pending, seen = [exc], set()
    while pending:
        link = pending.pop()
        if id(link) in seen:
            continue
        seen.add(id(link))
        text += str(link) + repr(link) + repr(link.args) + repr(vars(link))
        pending.extend(e for e in (link.__cause__, link.__context__) if e is not None)
    text += "".join(r.getMessage() for r in records)
    for sentinel in SENT:
        assert sentinel not in text, sentinel


@pytest.fixture
def failing_server():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def _fail(self):
            hits.append(self.command)
            self.send_response(500)
            self.send_header("Set-Cookie", "s=SENTP")
            self.send_header("Location", "http://SENTU:SENTP@127.0.0.1/x?sig=SENTQ")
            self.send_header("Content-Length", "0")
            self.end_headers()
        do_GET = do_HEAD = do_PUT = do_DELETE = _fail
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1], hits
    server.shutdown()


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_http_walk(failing_server, policy, operation, caplog, library_loggers_debug):
    caplog.set_level(logging.DEBUG)
    port, hits = failing_server
    url = f"http://SENTU:SENTP@127.0.0.1:{port}/x.csv?sig=SENTQ#SENTF"
    with StorageFacade.from_path(url, policy=policy) as facade:
        _run(facade, operation, url, _expect("http", operation), caplog)
    if operation not in UNSUPPORTED["http"]:
        assert hits, "backend never reached the server"


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def _s3_facade(monkeypatch, policy):
    from botocore.exceptions import ClientError
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    from mountainash_transport.storage.backends.s3 import S3StorageBackend

    error = ClientError({"Error": {"Code": "InternalError", "Message": "SENTP"}}, "Op")
    client = MagicMock()
    for name in ("get_object", "put_object", "head_object", "delete_object", "list_objects_v2",
                 "copy_object", "copy", "upload_fileobj", "get_paginator"):
        getattr(client, name).side_effect = error
    backend = S3StorageBackend(None)
    backend._client = client
    monkeypatch.setattr(import_module("mountainash_transport.storage.facade.facade"),
                        "get_storage_backend", lambda *args, **kwargs: backend)
    return StorageFacade(CONST_STORAGE_PROVIDER_TYPE.S3, policy=policy), client


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_s3_credential_url_rejected(monkeypatch, policy, operation, caplog):
    """A credential-bearing authority is refused before any SDK call."""
    caplog.set_level(logging.DEBUG)
    facade, client = _s3_facade(monkeypatch, policy)
    path = "s3://SENTU:SENTP@bucket/x.csv?sig=SENTQ#SENTF"
    with facade:
        expected = UnsupportedOperationError if operation in UNSUPPORTED["s3"] else (ValueError, StorageError)
        with pytest.raises(expected) as info:
            OPERATIONS[operation](facade, path)
        _walk(info.value, caplog.records)
    assert not client.method_calls


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_s3_walk(monkeypatch, policy, operation, caplog):
    """A valid bucket reaches the SDK, whose sentinel-bearing error is walked."""
    caplog.set_level(logging.DEBUG)
    facade, client = _s3_facade(monkeypatch, policy)
    path = "s3://bucket/x.csv?sig=SENTQ#SENTF"
    with facade:
        _run(facade, operation, path, _expect("s3", operation), caplog)
    assert bool(client.method_calls) == (operation not in UNSUPPORTED["s3"])


REACHABLE_SFTP = ("/dir/x.csv", "sftp://SENTU:SENTP@host:22/dir/x.csv")
SFTP_PATHS = ["/dir/x.csv", "sftp://SENTU:SENTP@host:22/dir/x.csv?sig=SENTQ#SENTF",
              "sftp://SENTU:SENTP@host:22/dir/x.csv", "sftp://SENTU:SENTP@other:2222/dir/x.csv", "sftp://host:22/dir/x.csv?sig=SENTQ#SENTF"]


@pytest.mark.parametrize("path", SFTP_PATHS)
@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_sftp_walk(monkeypatch, policy, operation, path, caplog):
    import paramiko
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    from mountainash_transport.storage.backends.sftp import SFTPStorageBackend

    caplog.set_level(logging.DEBUG)
    error = paramiko.SSHException("SENTU:SENTP")
    client = MagicMock()
    for name in ("open", "stat", "listdir_attr", "remove", "rmdir", "mkdir"):
        getattr(client, name).side_effect = error
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    backend.storage_profile = SimpleNamespace(HOST="host", PORT=22)
    monkeypatch.setattr(import_module("mountainash_transport.storage.facade.facade"),
                        "get_storage_backend", lambda *args, **kwargs: backend)
    with StorageFacade(CONST_STORAGE_PROVIDER_TYPE.SFTP, policy=policy) as facade:
        _run(facade, operation, path, _expect("sftp", operation), caplog)
    assert bool(client.method_calls) == (operation not in UNSUPPORTED["sftp"] and path in REACHABLE_SFTP
                                                       and (path == "/dir/x.csv" or policy is not POLICIES[2]))


class _Faulting:
    """Stand-in for ``os``/``shutil`` whose I/O functions raise a native error."""

    def __init__(self, real, names, error):
        self._real, self._names, self._error = real, names, error

    def __getattr__(self, name):
        if name in self._names:
            def fail(*args, **kwargs):
                raise self._error
            return fail
        return getattr(self._real, name)


LOCAL_ERRORS = {
    "oserror": (OSError(5, "Input/output error", "/x/SENTP"), StorageError),
    "permission": (PermissionError(13, "Permission denied", "/x/SENTP"), PermissionDeniedError),
    "connection": (ConnectionResetError(104, "Connection reset by peer", "/x/SENTP"), StorageConnectionError),
    "errnoless": (OSError("SENTP native text"), StorageError),
}
LOCAL_OPERATIONS = sorted(set(OPERATIONS) - {"exists"})  # exists answers False on a failing stat
LOCAL_IO = {"stat", "lstat", "remove", "rmdir", "mkdir", "makedirs", "scandir"}
LOCAL_SHUTIL = {"copy2", "copyfile", "rmtree"}


def _fail_local_io(monkeypatch, error):
    """Make every local-backend I/O primitive raise *error*."""
    import os
    import shutil
    import sys

    def fail(*args, **kwargs):
        raise error

    for name, module in list(sys.modules.items()):
        if not name.startswith("mountainash_transport.storage.backends.local."):
            continue
        if getattr(module, "os", None) is os:
            monkeypatch.setattr(module, "os", _Faulting(os, LOCAL_IO, error))
        if getattr(module, "shutil", None) is shutil:
            monkeypatch.setattr(module, "shutil", _Faulting(shutil, LOCAL_SHUTIL, error))
        monkeypatch.setattr(module, "open", fail, raising=False)


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", LOCAL_OPERATIONS)
@pytest.mark.parametrize("kind", sorted(LOCAL_ERRORS))
def test_local_native_oserrors_walk(monkeypatch, tmp_path, kind, operation, policy, caplog):
    """OSErrors carrying sentinels in filename or text reach the caller only as [Errno N] strerror."""
    import mountainash_transport.storage.backends  # noqa: F401

    caplog.set_level(logging.DEBUG)
    error, expected = LOCAL_ERRORS[kind]
    _fail_local_io(monkeypatch, error)
    path = str(tmp_path / "a.csv")
    with StorageFacade.from_path(path, policy=policy) as facade:
        with pytest.raises(StorageError) as info:
            OPERATIONS[operation](facade, path)
    assert isinstance(info.value, expected), repr(info.value)
    assert not isinstance(info.value, UnsupportedOperationError)
    _walk(info.value, caplog.records)


@pytest.mark.parametrize("operation", LOCAL_OPERATIONS)
def test_local_non_oserror_passes_through_unclassified(monkeypatch, tmp_path, operation):
    """A non-OSError is indistinguishable from the caller's own error, so it propagates as raised."""
    import mountainash_transport.storage.backends  # noqa: F401

    error = ValueError("native text")
    _fail_local_io(monkeypatch, error)
    path = str(tmp_path / "a.csv")
    with StorageFacade.from_path(path) as facade:
        with pytest.raises(ValueError) as info:
            OPERATIONS[operation](facade, path)
    assert info.value is error
