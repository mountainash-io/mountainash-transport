"""TunnelledConnection — SSH-tunnelled decorator connection via paramiko direct-tcpip."""
from __future__ import annotations

import errno
import select
import socket
import socketserver
import threading
import time
from types import TracebackType
import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import ConnectionTimeoutError, TransportConnectionError
from mountainash_transport._core.protocols import ConnectionProtocol


class _ForwardHandler(socketserver.BaseRequestHandler):
    """Handle one forwarded TCP connection via a paramiko direct-tcpip channel."""

    owner: _Forwarder

    def handle(self) -> None:
        owner = self.owner
        if owner._stop.is_set():
            return
        try:
            channel = owner._transport.open_channel(
                "direct-tcpip", owner._remote, self.request.getpeername(),
            )
        except Exception:
            return
        if channel is None:
            return
        try:
            while not owner._stop.is_set():
                readable, _, _ = select.select([self.request, channel], [], [], 1.0)
                if self.request in readable:
                    data = self.request.recv(1024)
                    if not data:
                        break
                    channel.send(data)
                if channel in readable:
                    data = channel.recv(1024)
                    if not data:
                        break
                    self.request.send(data)
                if channel.closed:
                    break
        except Exception:
            pass
        finally:
            try:
                channel.close()
            except BaseException as exc:
                owner._record_cleanup_error(exc)


class _Forwarder:
    """Own the listener, accepted sockets and workers, with a bounded join."""

    def __init__(self, ssh_transport: t.Any, remote_host: str, remote_port: int) -> None:
        self._transport = ssh_transport
        self._remote = (remote_host, remote_port)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._requests: dict[socket.socket, threading.Thread] = {}
        self._workers_at_stop: tuple[threading.Thread, ...] = ()
        self._cleanup_error: BaseException | None = None
        owner = self

        class Handler(_ForwardHandler):
            pass

        Handler.owner = self

        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True

            def process_request(
                self, request: socket.socket | tuple[bytes, socket.socket], client_address: t.Any,
            ) -> None:
                # The base stub also covers UDP; this TCP server accepts sockets only.
                owner._start_request(t.cast(socket.socket, request), client_address)

        self._server = Server(("127.0.0.1", 0), Handler)
        self._server.timeout = 0.1
        self.local_port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        try:
            self._thread.start()
        except BaseException as primary:
            self.request_stop()
            if self._cleanup_error is not None:
                primary.add_note(f"Tunnel cleanup failed: {self._cleanup_error!r}")
            raise

    def _record_cleanup_error(self, exc: BaseException) -> None:
        with self._lock:
            if self._cleanup_error is None:
                self._cleanup_error = exc

    def _close_socket(self, request: socket.socket) -> None:
        try:
            request.shutdown(socket.SHUT_RDWR)
        except OSError as exc:
            if exc.errno not in (errno.EBADF, errno.ENOTCONN):
                self._record_cleanup_error(exc)
        except BaseException as exc:
            self._record_cleanup_error(exc)
        try:
            request.close()
        except BaseException as exc:
            self._record_cleanup_error(exc)

    def _serve(self) -> None:
        while not self._stop.is_set():
            try:
                self._server.handle_request()
            except (OSError, ValueError):
                if not self._stop.is_set():
                    raise

    def _start_request(self, request: socket.socket, address: t.Any) -> None:
        worker = threading.Thread(target=self._run_request, args=(request, address), daemon=True)
        with self._lock:
            stopped = self._stop.is_set()
            if not stopped:
                self._requests[request] = worker
        if stopped:
            self._close_socket(request)
            return
        try:
            worker.start()
        except BaseException:
            self._close_socket(request)
            with self._lock:
                self._requests.pop(request, None)
            raise

    def _run_request(self, request: socket.socket, address: t.Any) -> None:
        try:
            if not self._stop.is_set():
                self._server.finish_request(request, address)
        finally:
            self._close_socket(request)
            with self._lock:
                self._requests.pop(request, None)

    def request_stop(self) -> None:
        with self._lock:
            self._stop.set()
            requests = tuple(self._requests)
            self._workers_at_stop = tuple(self._requests.values())
        try:
            self._server.server_close()
        except BaseException as exc:
            self._record_cleanup_error(exc)
        for request in requests:
            self._close_socket(request)

    def wait_stopped(self) -> None:
        deadline = time.monotonic() + 1.0
        self._thread.join(max(0.0, deadline - time.monotonic()))
        remaining = [self._thread.name] if self._thread.is_alive() else []
        for worker in self._workers_at_stop:
            if worker.ident is not None:
                worker.join(max(0.0, deadline - time.monotonic()))
            if worker.is_alive() or (worker.ident is None and self._thread.is_alive()):
                remaining.append(worker.name)
        with self._lock:
            error = self._cleanup_error
        if remaining:
            timeout = ConnectionTimeoutError(f"Tunnel workers did not stop: {', '.join(remaining)}")
            if error is not None:
                timeout.add_note(f"Tunnel cleanup failed: {error!r}")
            raise timeout
        if error is not None:
            if not isinstance(error, Exception):
                raise error
            raise TransportConnectionError(f"Tunnel cleanup failed: {error}") from error


class _PatchedEndpointProfile:
    """Wraps a storage profile, replacing endpoint kwargs with the tunnel's local address."""

    _URL_KEYS = frozenset({"base_url", "endpoint_url"})

    def __init__(self, inner: t.Any, host: str, port: int) -> None:
        self._inner = inner
        self._host = host
        self._port = port

    def _patch_endpoint(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        if "hostname" in kwargs:
            kwargs["hostname"] = self._host
            kwargs["port"] = self._port
        for key in self._URL_KEYS:
            if key in kwargs:
                kwargs[key] = f"http://{self._host}:{self._port}"
        return kwargs

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        return self._patch_endpoint(self._inner.to_handler_kwargs())

    def emit(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        # MUST override (not delegate via __getattr__) so the tunnel's local
        # endpoint is injected — otherwise the inner profile's emit returns the
        # real remote host/port and the tunnel is silently bypassed.
        return self._patch_endpoint(self._inner.emit(*args, **kwargs))

    def get_connection_url(self) -> str:
        if hasattr(self._inner, "get_connection_url"):
            return f"tunnel://{self._host}:{self._port}"
        return f"tunnel://{self._host}:{self._port}"

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._inner, name)


class TunnelledConnection(ConnectionProtocol):
    """Decorator connection that SSH-tunnels to a remote target.

    Starts a local TCP forwarder via paramiko direct-tcpip, then builds and
    connects an inner connection targeting 127.0.0.1:<ephemeral-port>.
    """

    def __init__(
        self,
        ssh_connection: ConnectionProtocol,
        inner_connection_factory: t.Callable[[int], ConnectionProtocol],
        remote_host: str,
        remote_port: int,
    ) -> None:
        self._ssh = ssh_connection
        self._inner_factory = inner_connection_factory
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._inner: ConnectionProtocol | None = None
        self._forwarder: _Forwarder | None = None
        self._local_port: int | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _teardown(self, *, close_ssh: bool) -> None:
        inner, self._inner = self._inner, None
        forwarder, self._forwarder = self._forwarder, None
        self._local_port = None
        actions: list[t.Callable[[], None]] = []
        if inner is not None:
            actions.append(inner.disconnect)
        if forwarder is not None:
            actions.append(forwarder.request_stop)
        if close_ssh:
            actions.append(self._ssh.disconnect)
        if forwarder is not None:
            actions.append(forwarder.wait_stopped)
        error: BaseException | None = None
        for action in actions:
            try:
                action()
            except BaseException as exc:
                if error is None:
                    error = exc
                elif isinstance(exc, ConnectionTimeoutError):
                    exc.add_note(f"Earlier cleanup failed: {error!r}")
                    error = exc
                else:
                    error.add_note(f"Further cleanup failed: {exc!r}")
        if error is not None:
            raise error

    # ------------------------------------------------------------------
    # ConnectionProtocol
    # ------------------------------------------------------------------

    def connect(self) -> Self:
        try:
            self._teardown(close_ssh=False)
            if not self._ssh.is_connected:
                self._ssh.connect()
            client = self._ssh.client
            if client is None:
                raise TransportConnectionError("SSH connection has no client after connect()")
            try:
                self._forwarder = _Forwarder(
                    client.get_transport(), self._remote_host, self._remote_port,
                )
            except OSError as exc:
                raise TransportConnectionError(f"Failed to bind tunnel listener: {exc}") from exc
            self._local_port = self._forwarder.local_port
            self._inner = self._inner_factory(self._local_port)
            self._inner.connect()
        except BaseException as primary:
            try:
                self.disconnect()
            except BaseException as cleanup:
                primary.add_note(f"Tunnel cleanup failed: {cleanup!r}")
                for note in getattr(cleanup, "__notes__", ()):
                    primary.add_note(note)
            raise
        return self

    def disconnect(self) -> None:
        self._teardown(close_ssh=True)

    @property
    def client(self) -> t.Any:
        return self._inner.client if self._inner is not None else None

    @property
    def is_connected(self) -> bool:
        return self._inner is not None and self._inner.is_connected

    @property
    def local_port(self) -> int | None:
        return self._local_port

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.disconnect()
        except BaseException as cleanup:
            if exc_value is None:
                raise
            exc_value.add_note(f"Tunnel cleanup failed: {cleanup!r}")
            for note in getattr(cleanup, "__notes__", ()):
                exc_value.add_note(note)
