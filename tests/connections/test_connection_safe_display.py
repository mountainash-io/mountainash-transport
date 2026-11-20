"""W8: connection errors carry only safe native text."""
from __future__ import annotations

import errno
import traceback

import pytest

from mountainash_transport.connections.errors import TransportConnectionError

SENT = "SENTP"


def _assert_clean(exc):
    text = "".join(traceback.format_exception(exc)) + repr(exc.args)
    link = exc.__cause__
    while link is not None:
        text += str(link) + repr(link.args)
        link = link.__cause__
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
