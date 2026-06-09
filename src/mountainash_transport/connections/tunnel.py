"""TunnelledConnection — SSH-tunnelled decorator connection via paramiko direct-tcpip."""
from __future__ import annotations

import select
import socketserver
import threading
import typing as t

from typing_extensions import Self

from mountainash_transport.connections.errors import TransportConnectionError
from mountainash_transport._core.protocols import ConnectionProtocol


class _ForwardHandler(socketserver.BaseRequestHandler):
    """Handle one forwarded TCP connection via a paramiko direct-tcpip channel."""

    ssh_transport: t.Any = None
    remote_host: str = ""
    remote_port: int = 0

    def handle(self) -> None:
        try:
            channel = self.ssh_transport.open_channel(
                "direct-tcpip",
                (self.remote_host, self.remote_port),
                self.request.getpeername(),
            )
        except Exception:
            return

        if channel is None:
            return

        try:
            while True:
                r, _, _ = select.select([self.request, channel], [], [], 1.0)
                if self.request in r:
                    data = self.request.recv(1024)
                    if not data:
                        break
                    channel.send(data)
                if channel in r:
                    data = channel.recv(1024)
                    if not data:
                        break
                    self.request.send(data)
                if channel.closed:
                    break
        except Exception:
            pass
        finally:
            channel.close()
            self.request.close()


def _start_forwarder(
    ssh_transport: t.Any,
    remote_host: str,
    remote_port: int,
) -> socketserver.TCPServer:
    """Create a threading TCP server that forwards connections via direct-tcpip.

    Returns the server (bound to an ephemeral port on 127.0.0.1).
    """

    class Handler(_ForwardHandler):
        pass

    Handler.ssh_transport = ssh_transport
    Handler.remote_host = remote_host
    Handler.remote_port = remote_port

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    t_thread = threading.Thread(target=server.serve_forever, daemon=True)
    t_thread.start()
    return server


class _PatchedEndpointProfile:
    """Wraps a storage profile, replacing endpoint kwargs with the tunnel's local address."""

    _URL_KEYS = frozenset({"base_url", "endpoint_url"})

    def __init__(self, inner: t.Any, host: str, port: int) -> None:
        self._inner = inner
        self._host = host
        self._port = port

    def to_handler_kwargs(self) -> dict[str, t.Any]:
        kwargs = self._inner.to_handler_kwargs()
        if "hostname" in kwargs:
            kwargs["hostname"] = self._host
            kwargs["port"] = self._port
        for key in self._URL_KEYS:
            if key in kwargs:
                kwargs[key] = f"http://{self._host}:{self._port}"
        return kwargs

    def get_connection_url(self) -> str:
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
        self._server: socketserver.TCPServer | None = None
        self._local_port: int | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _teardown(self) -> None:
        """Disconnect inner connection and shut down forwarder server."""
        if self._inner is not None:
            try:
                self._inner.disconnect()
            except Exception:
                pass
            self._inner = None

        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None

        self._local_port = None

    # ------------------------------------------------------------------
    # ConnectionProtocol
    # ------------------------------------------------------------------

    def connect(self) -> Self:
        if self._inner is not None:
            self._teardown()

        if not self._ssh.is_connected:
            self._ssh.connect()

        transport = self._ssh.client.get_transport()

        try:
            server = _start_forwarder(transport, self._remote_host, self._remote_port)
        except OSError as exc:
            raise TransportConnectionError(
                f"Failed to bind tunnel listener: {exc}"
            ) from exc

        self._server = server
        self._local_port = server.server_address[1]

        inner = self._inner_factory(self._local_port)
        inner.connect()
        self._inner = inner

        return self

    def disconnect(self) -> None:
        self._teardown()
        self._ssh.disconnect()

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

    def __exit__(self, *args: t.Any) -> None:
        self.disconnect()
