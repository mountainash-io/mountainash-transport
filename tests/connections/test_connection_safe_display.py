"""W8: connection errors carry only safe native text."""
from __future__ import annotations

import errno
import traceback

import pytest

from mountainash_transport.connections.errors import TransportConnectionError

SENT = "SENTP"


def _assert_clean(exc):
    text = "".join(traceback.format_exception(exc))
    pending, seen = [exc], set()
    while pending:
        link = pending.pop()
        if id(link) in seen:
            continue
        seen.add(id(link))
        text += str(link) + repr(link) + repr(link.args) + repr(vars(link))
        pending.extend(e for e in (link.__cause__, link.__context__) if e is not None)
    assert SENT not in text and exc.__context__ is None


def test_s3_client_creation_hides_native_text(monkeypatch):
    import boto3
    from mountainash_transport.connections.s3 import S3Connection

    def boom(*args, **kwargs):
        raise ValueError(f"Invalid endpoint: https://u:{SENT}@h")
    monkeypatch.setattr(boto3, "client", boom)
    connection = S3Connection({"endpoint_url": f"https://u:{SENT}@h"})
    with pytest.raises(TransportConnectionError) as ei:
        connection.connect()
    assert str(ei.value) == "Failed to create S3 client (ValueError)"
    _assert_clean(ei.value)


def test_ssh_oserror_keeps_errno_strerror(monkeypatch):
    import paramiko
    from mountainash_transport.connections.ssh import SSHConnection

    def refuse(self, *args, **kwargs):
        raise OSError(errno.ECONNREFUSED, "Connection refused", f"/{SENT}")
    monkeypatch.setattr(paramiko.SSHClient, "connect", refuse)
    connection = SSHConnection({"hostname": "h", "username": "u", "password": SENT})
    with pytest.raises(TransportConnectionError) as ei:
        connection.connect()
    assert str(ei.value) == "SSH connection failed ([Errno 111] Connection refused)"
    _assert_clean(ei.value)


def test_ssh_paramiko_error_is_class_name(monkeypatch):
    import paramiko
    from mountainash_transport.connections.ssh import SSHConnection

    def fail(self, *args, **kwargs):
        raise paramiko.SSHException(f"bad banner from u:{SENT}@h")
    monkeypatch.setattr(paramiko.SSHClient, "connect", fail)
    with pytest.raises(TransportConnectionError) as ei:
        SSHConnection({"hostname": "h", "username": "u"}).connect()
    assert str(ei.value) == "SSH connection failed (SSHException)"
    _assert_clean(ei.value)


def test_tunnel_startup_cleanup_note_hides_native_text(monkeypatch):
    import socketserver
    import threading

    from mountainash_transport.connections.tunnel import _Forwarder

    close_server = socketserver.TCPServer.server_close

    def failing_close(server):
        close_server(server)
        raise OSError(f"close failed u:{SENT}@h")

    def failing_start(thread):
        raise RuntimeError("thread start failed")

    monkeypatch.setattr(socketserver.TCPServer, "server_close", failing_close)
    monkeypatch.setattr(threading.Thread, "start", failing_start)
    with pytest.raises(RuntimeError) as ei:
        _Forwarder(object(), "h", 22)
    notes = ei.value.__notes__
    assert notes == ["Tunnel cleanup failed (OSError)"]
    assert SENT not in "".join(traceback.format_exception(ei.value))


def test_cancellation_cleanup_note_hides_native_text(monkeypatch):
    from mountainash_transport.connections.http import HTTPConnection

    connection = HTTPConnection({})
    connection.connect()

    def interrupted():
        raise KeyboardInterrupt(f"stop u:{SENT}@h")

    monkeypatch.setattr(connection, "disconnect", interrupted)
    primary = ValueError("body")
    with pytest.raises(ValueError) as ei:
        with connection:
            raise primary
    assert ei.value is primary
    assert primary.__notes__ == ["Connection cleanup also failed (KeyboardInterrupt)"]
    assert SENT not in "".join(traceback.format_exception(primary))
    # cancellation with no primary error still propagates unwrapped
    with pytest.raises(KeyboardInterrupt):
        with connection:
            pass
