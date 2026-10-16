"""TunnelledConnection behavioral tests."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import select
import socket
import socketserver
import threading
import time
import typing as t
from unittest.mock import MagicMock

import httpx
import pytest

from mountainash_transport._core.protocols import ConnectionProtocol
from mountainash_transport.connections.errors import ConnectionTimeoutError, TransportConnectionError
from mountainash_transport.connections.http import HTTPConnection
from mountainash_transport.connections.tunnel import TunnelledConnection, _PatchedEndpointProfile


def _close_socket(sock: socket.socket) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    sock.close()


class _Channel:
    def __init__(self, address, rig) -> None:
        self.socket = socket.create_connection(address, timeout=3)
        self.socket.settimeout(None)
        self.rig = rig
        self.worker = threading.current_thread()

    @property
    def closed(self) -> bool:
        return self.socket.fileno() == -1

    def fileno(self) -> int:
        return self.socket.fileno()

    def recv(self, size: int) -> bytes:
        return self.socket.recv(size)

    def send(self, data: bytes) -> int:
        return self.socket.send(data)

    def close(self) -> None:
        _close_socket(self.socket)
        if self.rig.channel_close_error:
            raise OSError("channel cleanup failed")


class _SSH:
    """SDK boundary double; channels carry real TCP traffic."""

    def __init__(self, rig) -> None:
        self.rig = rig
        self.is_connected = False
        self.connects = 0
        self.channels: list[_Channel] = []

    @property
    def client(self):
        return self if self.is_connected else None

    def get_transport(self):
        return self

    def connect(self):
        self.connects += 1
        self.is_connected = True
        return self

    def open_channel(self, kind, address, origin):
        if self.rig.channel_gate is not None:
            entered, release = self.rig.channel_gate
            entered.set()
            release.wait()
        if not self.is_connected:
            raise OSError("SSH disconnected")
        channel = _Channel(address, self.rig)
        self.channels.append(channel)
        return channel

    def disconnect(self) -> None:
        self.is_connected = False
        for channel in self.channels:
            _close_socket(channel.socket)
        if self.rig.ssh_close_error:
            raise TransportConnectionError("SSH cleanup failed")

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        self.disconnect()


class _Rig:
    def __init__(self) -> None:
        self.channel_close_error = False
        self.inner_close_error = False
        self.ssh_close_error = False
        self.fail_startup = ""
        self.fail_thread_start = False
        self.failure = RuntimeError("injected startup failure")
        self.channel_gate: tuple[threading.Event, threading.Event] | None = None
        self.gates: list[threading.Event] = []
        self.servers: list[socketserver.TCPServer] = []
        self.accepted: list[socket.socket] = []
        self.accepted_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.clients: list[httpx.Client] = []
        self.peers: list[socket.socket] = []
        self.ssh = _SSH(self)
        self.connection: TunnelledConnection
        self.peer: ThreadingHTTPServer

    def open_peer(self) -> socket.socket:
        port = self.connection.local_port
        assert port is not None
        sock = socket.socket()
        self.peers.append(sock)
        sock.settimeout(3)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        sock.connect(("127.0.0.1", port))
        return sock

    def assert_released(self) -> None:
        assert not self.ssh.is_connected
        assert self.connection.client is None
        assert self.connection.local_port is None
        assert all(client.is_closed for client in self.clients)
        assert all(server.socket.fileno() == -1 for server in self.servers)
        assert all(sock.fileno() == -1 for sock in self.accepted)
        for worker in self.threads:
            if worker.ident is not None:
                worker.join(2)
                assert not worker.is_alive()


@pytest.fixture
def rig(monkeypatch) -> t.Iterator[_Rig]:
    state = _Rig()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            flood = self.path == "/flood"
            self.send_response(200)
            self.send_header("Content-Length", str(32 * 1024 * 1024) if flood else "7")
            self.end_headers()
            try:
                if flood:
                    for _ in range(512):
                        self.wfile.write(b"x" * 65536)
                else:
                    self.wfile.write(b"payload")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args) -> None:
            pass

    state.peer = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    peer_thread = threading.Thread(target=state.peer.serve_forever, daemon=True)
    peer_thread.start()
    activate = socketserver.TCPServer.server_activate
    accept = socketserver.TCPServer.get_request
    start = threading.Thread.start
    client_type = httpx.Client

    def record_server(server):
        activate(server)
        state.servers.append(server)

    def record_accept(server):
        sock, address = accept(server)
        if server is not state.peer:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            state.accepted.append(sock)
            state.accepted_event.set()
        return sock, address

    def record_thread(worker):
        if state.fail_thread_start:
            state.fail_thread_start = False
            raise state.failure
        state.threads.append(worker)
        start(worker)

    def record_client(**kwargs):
        client = client_type(**kwargs)
        state.clients.append(client)
        close = client.close

        def close_client():
            close()
            if state.inner_close_error:
                raise OSError("inner cleanup failed")

        monkeypatch.setattr(client, "close", close_client)
        return client

    class Inner(HTTPConnection):
        def connect(self):
            super().connect()
            if state.fail_startup == "inner":
                raise state.failure
            return self

    def factory(port):
        if state.fail_startup == "factory":
            raise state.failure
        return Inner({"base_url": f"http://127.0.0.1:{port}", "trust_env": False})

    monkeypatch.setattr(socketserver.TCPServer, "server_activate", record_server)
    monkeypatch.setattr(socketserver.TCPServer, "get_request", record_accept)
    monkeypatch.setattr(threading.Thread, "start", record_thread)
    monkeypatch.setattr(httpx, "Client", record_client)
    state.connection = TunnelledConnection(state.ssh, factory, "127.0.0.1", state.peer.server_port)
    try:
        yield state
    finally:
        state.channel_close_error = state.inner_close_error = state.ssh_close_error = False
        for gate in state.gates:
            gate.set()
        try:
            state.connection.disconnect()
        except Exception:
            pass
        state.ssh.disconnect()
        for client in state.clients:
            client.close()
        for sock in state.peers + state.accepted:
            _close_socket(sock)
        for server in state.servers:
            server.server_close()
        state.peer.shutdown()
        state.peer.server_close()
        peer_thread.join(3)
        for worker in state.threads:
            if worker.ident is not None:
                worker.join(3)


def test_real_relay_context_and_repeated_disconnect(rig) -> None:
    conn = rig.connection
    assert isinstance(conn, ConnectionProtocol)
    with conn:
        conn.connect()
        assert conn.client is not None
        assert conn.client.get("/").content == b"payload"
    rig.assert_released()
    conn.disconnect()


@pytest.mark.parametrize("stage", ["factory", "inner", "thread"])
def test_failed_startup_releases_partial_resources(rig, stage) -> None:
    rig.fail_startup = stage
    rig.fail_thread_start = stage == "thread"
    with pytest.raises(RuntimeError) as caught:
        rig.connection.connect()
    assert caught.value is rig.failure
    rig.assert_released()


def test_listener_bind_failure_releases_ssh(rig, monkeypatch) -> None:
    def fail(server):
        raise OSError("bind failed")

    monkeypatch.setattr(socketserver.TCPServer, "server_bind", fail)
    with pytest.raises(TransportConnectionError):
        rig.connection.connect()
    assert not rig.ssh.is_connected


@pytest.mark.parametrize("owner", ["inner", "ssh", "channel"])
def test_cleanup_failure_still_releases_other_resources(rig, owner) -> None:
    rig.connection.connect()
    assert rig.connection.client.get("/").content == b"payload"
    setattr(rig, f"{owner}_close_error", True)
    with pytest.raises(TransportConnectionError):
        rig.connection.disconnect()
    rig.assert_released()


def test_context_preserves_body_error(rig) -> None:
    primary = ValueError("body failed")
    rig.inner_close_error = True
    with pytest.raises(ValueError) as caught:
        with rig.connection:
            rig.connection.connect()
            raise primary
    assert caught.value is primary
    assert primary.__notes__
    rig.assert_released()


def test_reconnect_releases_previous_resources_but_reuses_ssh(rig) -> None:
    conn = rig.connection.connect()
    assert conn.client.get("/").content == b"payload"
    old_client, old_listener = rig.clients[0], rig.servers[0].socket
    conn.connect()
    assert old_client.is_closed and old_listener.fileno() == -1
    assert conn.client.get("/").content == b"payload"
    assert rig.ssh.connects == 1
    conn.disconnect()
    rig.assert_released()


def test_failed_reconnect_aborts_replacement(rig) -> None:
    conn = rig.connection.connect()
    rig.inner_close_error = True
    with pytest.raises(TransportConnectionError):
        conn.connect()
    assert len(rig.clients) == 1
    rig.assert_released()
    rig.inner_close_error = False
    conn.connect()
    assert conn.client.get("/").content == b"payload"


def test_backpressured_receiver_is_released(rig) -> None:
    rig.connection.connect()
    peer = rig.open_peer()
    peer.sendall(b"GET /flood HTTP/1.1\r\nHost: localhost\r\n\r\n")
    assert rig.accepted_event.wait(3)
    sender = rig.accepted[0]
    deadline = time.monotonic() + 3
    while select.select([], [sender], [], 0)[1]:
        assert time.monotonic() < deadline, "receiver did not establish backpressure"
        threading.Event().wait(0.01)
    rig.connection.disconnect()
    rig.assert_released()


def test_worker_unregistered_during_stop_is_still_joined(rig, monkeypatch) -> None:
    close_release, exit_release, exited = (threading.Event() for _ in range(3))
    rig.gates.extend((close_release, exit_release))
    close_channel = _Channel.close
    disconnect_ssh = rig.ssh.disconnect
    run = threading.Thread.run

    def delayed_close(channel):
        close_release.wait()
        close_channel(channel)

    def delayed_exit(worker):
        run(worker)
        if rig.ssh.channels and worker is rig.ssh.channels[0].worker:
            exited.set()
            exit_release.wait()

    def release_channel():
        disconnect_ssh()
        close_release.set()
        assert exited.wait(3)

    monkeypatch.setattr(_Channel, "close", delayed_close)
    monkeypatch.setattr(threading.Thread, "run", delayed_exit)
    monkeypatch.setattr(rig.ssh, "disconnect", release_channel)
    rig.connection.connect()
    assert rig.connection.client.get("/").content == b"payload"
    try:
        with pytest.raises(ConnectionTimeoutError):
            rig.connection.disconnect()
    finally:
        close_release.set()
        exit_release.set()
    rig.assert_released()



@pytest.mark.parametrize("cleanup_error", ["none", "channel", "inner"])
@pytest.mark.parametrize("worker", ["serving", "request"])
def test_stalled_worker_reports_timeout_after_other_cleanup(rig, monkeypatch, worker, cleanup_error) -> None:
    rig.connection.connect()
    if cleanup_error != "none":
        assert rig.connection.client.get("/").content == b"payload"
        setattr(rig, f"{cleanup_error}_close_error", True)
    entered, release = threading.Event(), threading.Event()
    rig.gates.append(release)
    if worker == "serving":
        original = getattr(socketserver.BaseServer, "_handle_request_noblock")

        def stall(server):
            if server is not rig.peer:
                entered.set()
                release.wait()
            original(server)

        monkeypatch.setattr(socketserver.BaseServer, "_handle_request_noblock", stall)
    else:
        rig.channel_gate = entered, release
    peer = rig.open_peer()
    peer.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    assert entered.wait(3)
    errors = []
    finished = threading.Event()

    def stop():
        try:
            rig.connection.disconnect()
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    try:
        assert finished.wait(2.5), "disconnect blocked on the stalled worker"
        assert len(errors) == 1 and isinstance(errors[0], ConnectionTimeoutError)
        if cleanup_error != "none":
            assert f"{cleanup_error} cleanup failed" in str(errors[0].__notes__)
        assert not rig.ssh.is_connected
        assert all(server.socket.fileno() == -1 for server in rig.servers)
        assert all(sock.fileno() == -1 for sock in rig.accepted)
    finally:
        release.set()
        stopper.join(3)
    rig.assert_released()


def test_request_worker_start_failure_does_not_poison_close(rig) -> None:
    rig.connection.connect()
    rig.fail_thread_start = True
    peer = rig.open_peer()
    peer.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    try:
        assert peer.recv(1) == b""
    except ConnectionResetError:
        pass
    rig.connection.disconnect()
    rig.assert_released()


def test_failed_request_socket_cleanup_is_reported(rig, monkeypatch) -> None:
    close = socket.socket.close
    failed = set()

    def fail_once(sock):
        close(sock)
        if sock in rig.accepted and sock not in failed:
            failed.add(sock)
            raise OSError("accepted socket cleanup failed")

    monkeypatch.setattr(socket.socket, "close", fail_once)
    rig.connection.connect()
    rig.fail_thread_start = True
    peer = rig.open_peer()
    peer.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    try:
        assert peer.recv(1) == b""
    except ConnectionResetError:
        pass
    with pytest.raises(TransportConnectionError) as caught:
        rig.connection.disconnect()
    assert isinstance(caught.value.__cause__, OSError)
    rig.assert_released()


def test_startup_error_wins_over_inner_cleanup_failure(rig) -> None:
    rig.fail_startup = "inner"
    rig.inner_close_error = True
    with pytest.raises(RuntimeError) as caught:
        rig.connection.connect()
    assert caught.value is rig.failure
    assert "inner cleanup failed" in str(rig.failure.__notes__)
    rig.assert_released()


@pytest.mark.parametrize("gate_at", ["accept", "thread_start"])
def test_stop_racing_request_registration_closes_socket_without_channel(rig, monkeypatch, gate_at) -> None:
    rig.connection.connect()
    entered, release, stopping = (threading.Event() for _ in range(3))
    rig.gates.append(release)
    disconnect = rig.ssh.disconnect

    def mark_stopping():
        disconnect()
        stopping.set()

    monkeypatch.setattr(rig.ssh, "disconnect", mark_stopping)
    if gate_at == "accept":
        accept = socketserver.TCPServer.get_request

        def gated_accept(server):
            result = accept(server)
            entered.set()
            release.wait()
            return result

        monkeypatch.setattr(socketserver.TCPServer, "get_request", gated_accept)
    else:
        start = threading.Thread.start

        def gated_start(worker):
            if threading.current_thread() is not threading.main_thread():
                entered.set()
                release.wait()
            start(worker)

        monkeypatch.setattr(threading.Thread, "start", gated_start)
    peer = rig.open_peer()
    peer.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    assert entered.wait(3)
    errors = []

    def stop():
        try:
            rig.connection.disconnect()
        except BaseException as exc:
            errors.append(exc)

    stopper = threading.Thread(target=stop)
    stopper.start()
    try:
        assert stopping.wait(2), "request registration blocked stop"
    finally:
        release.set()
        stopper.join(3)
    assert not errors
    assert not rig.ssh.channels
    rig.assert_released()



# ---------------------------------------------------------------------------
# _PatchedEndpointProfile
# ---------------------------------------------------------------------------


class TestPatchedEndpointProfile:
    def _make_inner(self, kwargs: dict) -> MagicMock:
        inner = MagicMock()
        inner.to_handler_kwargs.return_value = kwargs
        inner.some_attr = "value"
        return inner

    def test_patches_hostname_and_port(self):
        inner = self._make_inner({"hostname": "db.internal", "port": 5432, "user": "admin"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        kwargs = profile.to_handler_kwargs()
        assert kwargs["hostname"] == "127.0.0.1"
        assert kwargs["port"] == 54321
        assert kwargs["user"] == "admin"

    def test_patches_base_url(self):
        inner = self._make_inner({"base_url": "https://s3.amazonaws.com", "region": "us-east-1"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 9000)
        kwargs = profile.to_handler_kwargs()
        assert kwargs["base_url"] == "http://127.0.0.1:9000"
        assert kwargs["region"] == "us-east-1"

    def test_patches_endpoint_url(self):
        inner = self._make_inner({"endpoint_url": "https://storage.googleapis.com"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 8080)
        kwargs = profile.to_handler_kwargs()
        assert kwargs["endpoint_url"] == "http://127.0.0.1:8080"

    def test_unrecognised_kwargs_pass_through(self):
        inner = self._make_inner({"driver": "postgres", "database": "mydb"})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 5432)
        kwargs = profile.to_handler_kwargs()
        assert kwargs == {"driver": "postgres", "database": "mydb"}

    def test_delegates_other_attributes(self):
        inner = self._make_inner({})
        inner.some_attr = "delegated"
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 1234)
        assert profile.some_attr == "delegated"

    def test_get_connection_url_shows_tunnel(self):
        inner = self._make_inner({})
        profile = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        assert profile.get_connection_url() == "tunnel://127.0.0.1:54321"


# ---------------------------------------------------------------------------
# _PatchedEndpointProfile.emit() override
# ---------------------------------------------------------------------------


class TestPatchedEndpointEmit:
    def test_emit_patches_hostname_and_port(self):
        from mountainash_auth_client.targets import TargetFamily
        from mountainash_transport.settings.storage.profiles.sftp_storage_profile import SFTPStorageProfile

        inner = SFTPStorageProfile(HOST="real-remote", USERNAME="u", PORT=22)
        patched = _PatchedEndpointProfile(inner, "127.0.0.1", 54321)
        out = patched.emit(TargetFamily.PARAMIKO)
        assert out["hostname"] == "127.0.0.1"
        assert out["port"] == 54321

    def test_emit_patches_endpoint_url(self):
        from mountainash_auth_client.targets import TargetFamily
        from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile

        inner = S3StorageProfile(FLAVOR="minio", ENDPOINT_URL="http://real:9000", REGION="us-east-1")
        patched = _PatchedEndpointProfile(inner, "127.0.0.1", 7777)
        out = patched.emit(TargetFamily.BOTO)
        assert out["endpoint_url"] == "http://127.0.0.1:7777"


@pytest.mark.parametrize("boundary", ["listener", "socket"])
def test_cleanup_cancellation_is_not_wrapped(rig, monkeypatch, boundary) -> None:
    rig.connection.connect()
    assert rig.connection.client.get("/").content == b"payload"
    cancellation = KeyboardInterrupt("cleanup interrupted")
    fired = False
    if boundary == "listener":
        close_server = socketserver.TCPServer.server_close

        def interrupt_server(server):
            nonlocal fired
            close_server(server)
            if server in rig.servers and not fired:
                fired = True
                raise cancellation

        monkeypatch.setattr(socketserver.TCPServer, "server_close", interrupt_server)
    else:
        close_socket = socket.socket.close

        def interrupt_socket(sock):
            nonlocal fired
            close_socket(sock)
            if sock in rig.accepted and not fired:
                fired = True
                raise cancellation

        monkeypatch.setattr(socket.socket, "close", interrupt_socket)
    with pytest.raises(KeyboardInterrupt) as caught:
        rig.connection.disconnect()
    assert caught.value is cancellation
    rig.assert_released()


def test_context_retains_inner_and_ssh_cleanup_failures(rig) -> None:
    primary = ValueError("body fault")
    with pytest.raises(ValueError) as caught:
        with rig.connection:
            rig.connection.connect()
            rig.inner_close_error = rig.ssh_close_error = True
            raise primary
    assert caught.value is primary
    assert "inner cleanup failed" in str(primary.__notes__)
    assert "SSH cleanup failed" in str(primary.__notes__)
    rig.assert_released()
