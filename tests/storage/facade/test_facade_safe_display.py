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
def test_http_walk(failing_server, policy, operation, caplog):
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


@pytest.mark.parametrize("policy", POLICIES)
@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_sftp_walk(monkeypatch, policy, operation, caplog):
    import paramiko
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
    from mountainash_transport.storage.backends.sftp import SFTPStorageBackend

    caplog.set_level(logging.DEBUG)
    error = paramiko.SSHException("SENTU:SENTP")
    client = MagicMock()
    for name in ("open", "stat", "listdir_attr", "remove", "rmdir", "mkdir"):
        getattr(client, name).side_effect = error
    backend = SFTPStorageBackend(connection=SimpleNamespace(client=client))
    monkeypatch.setattr(import_module("mountainash_transport.storage.facade.facade"),
                        "get_storage_backend", lambda *args, **kwargs: backend)
    with StorageFacade(CONST_STORAGE_PROVIDER_TYPE.SFTP, policy=policy) as facade:
        _run(facade, operation, "/dir/x.csv", _expect("sftp", operation), caplog)
    assert bool(client.method_calls) == (operation not in UNSUPPORTED["sftp"])
