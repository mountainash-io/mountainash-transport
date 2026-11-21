"""Real paramiko SSH servers and HTTP targets for tunnel, SFTP and example tests.

Only the bastion resolves ``target.test`` (to 127.0.0.1), so a request that
reaches a target proves it went through the tunnel. :class:`DirectorySFTPTarget`
serves a local directory over SFTP for tests and recipes that read and write.
"""
from __future__ import annotations

import errno
import datetime
import os
import select
import socket
import ssl
import threading
import typing as t
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import paramiko
from paramiko.common import AUTH_FAILED, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

TARGET = "target.test"


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def write_pki(directory: Path) -> tuple[Path, Path]:
    """Write a throwaway CA and a ``target.test`` leaf; return (ca.pem, leaf+key.pem)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    day = datetime.timedelta(days=1)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca = (
        x509.CertificateBuilder().subject_name(_name("tunnel test CA")).issuer_name(_name("tunnel test CA"))
        .public_key(ca_key.public_key()).serial_number(1)
        .not_valid_before(now - day).not_valid_after(now + day)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = ec.generate_private_key(ec.SECP256R1())
    leaf = (
        x509.CertificateBuilder().subject_name(_name(TARGET)).issuer_name(ca.subject)
        .public_key(leaf_key.public_key()).serial_number(2)
        .not_valid_before(now - day).not_valid_after(now + day)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(TARGET)]), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    ca_pem = directory / "ca.pem"
    ca_pem.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    leaf_pem = directory / "leaf.pem"
    leaf_pem.write_bytes(
        leaf.public_bytes(serialization.Encoding.PEM)
        + leaf_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        )
    )
    return ca_pem, leaf_pem


class HTTPTarget:
    """HTTP server recording (method, path, Host, SNI) per request; TLS when given a cert."""

    def __init__(self, cert: Path | None = None) -> None:
        self.seen: list[tuple[str, str, str | None, str | None]] = []
        self.sni: str | None = None
        target = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"  # keep-alive unless the request asks to close

            def _reply(self) -> None:
                target.seen.append((self.command, self.path, self.headers.get("Host"), target.sni))
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self.send_response(200)
                self.send_header("Content-Length", "7")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(b"payload")

            do_GET = do_HEAD = do_POST = _reply

            def log_message(self, *args: t.Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        if cert is not None:
            ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ctx.load_cert_chain(cert)

            def record_sni(sock: t.Any, server_name: str | None, _ctx: t.Any) -> None:
                target.sni = server_name

            ctx.sni_callback = record_sni
            self._server.socket = ctx.wrap_socket(self._server.socket, server_side=True)
        self.port = self._server.server_address[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()


def _pump(channel: t.Any, sock: socket.socket) -> None:
    try:
        while True:
            readable, _, _ = select.select([channel, sock], [], [], 1.0)
            if channel in readable:
                data = channel.recv(65536)
                if not data:
                    break
                sock.sendall(data)
            if sock in readable:
                data = sock.recv(65536)
                if not data:
                    break
                channel.sendall(data)
    except OSError:
        pass
    finally:
        for close in (channel.close, sock.close):
            try:
                close()
            except Exception:
                pass


class _SSHServer:
    """Accept SSH sessions on 127.0.0.1 with password ``u``/``p`` and one host key."""

    def __init__(self) -> None:
        self.host_key = paramiko.ECDSAKey.generate()
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port = self._listener.getsockname()[1]
        self._transports: list[paramiko.Transport] = []
        self._closed = False
        threading.Thread(target=self._accept, daemon=True).start()

    def known_hosts_line(self, host: str) -> str:
        return f"[{host}]:{self.port} {self.host_key.get_name()} {self.host_key.get_base64()}\n"

    def _interface(self) -> paramiko.ServerInterface:
        raise NotImplementedError

    def _serve(self, transport: paramiko.Transport, interface: t.Any) -> None:
        pass

    def _accept(self) -> None:
        while not self._closed:
            try:
                sock, _ = self._listener.accept()
            except OSError:
                return
            transport = paramiko.Transport(sock)
            transport.add_server_key(self.host_key)
            self._prepare(transport)
            interface = self._interface()
            try:
                transport.start_server(server=interface)
            except Exception:
                continue
            self._transports.append(transport)
            threading.Thread(target=self._serve, args=(transport, interface), daemon=True).start()

    def _prepare(self, transport: paramiko.Transport) -> None:
        pass

    @property
    def sessions(self) -> int:
        """SSH sessions accepted so far."""
        return len(self._transports)

    def drop_sessions(self) -> None:
        """Close every open session from the server side, as a network outage would."""
        for transport in self._transports:
            transport.close()

    def close(self) -> None:
        self._closed = True
        self._listener.close()
        for transport in self._transports:
            transport.close()


class _PasswordInterface(paramiko.ServerInterface):
    def check_auth_password(self, username: str, password: str) -> int:
        return AUTH_SUCCESSFUL if (username, password) == ("u", "p") else AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        return OPEN_SUCCEEDED


class Bastion(_SSHServer):
    """SSH server allowing direct-tcpip; records each requested destination."""

    def __init__(self) -> None:
        self.destinations: list[tuple[str, int]] = []
        super().__init__()

    def _interface(self) -> paramiko.ServerInterface:
        bastion = self

        class Interface(_PasswordInterface):
            def check_channel_direct_tcpip_request(
                self, chanid: int, origin: tuple[str, int], destination: tuple[str, int],
            ) -> int:
                bastion.destinations.append(destination)
                self.pending = destination
                return OPEN_SUCCEEDED

        return Interface()

    def _serve(self, transport: paramiko.Transport, interface: t.Any) -> None:
        while transport.is_active():
            channel = transport.accept(1)
            if channel is None:
                continue
            host, port = interface.pending
            try:
                real = socket.create_connection(("127.0.0.1" if host in (TARGET, "::1") else host, port), timeout=3)
            except OSError:
                channel.close()
                continue
            threading.Thread(target=_pump, args=(channel, real), daemon=True).start()


class SFTPTarget(_SSHServer):
    """SSH server with the paramiko SFTP subsystem over a fixed in-memory listing."""

    def _interface(self) -> paramiko.ServerInterface:
        return _PasswordInterface()

    def _prepare(self, transport: paramiko.Transport) -> None:
        transport.set_subsystem_handler("sftp", paramiko.SFTPServer, _ListingSFTP)


class _ListingSFTP(paramiko.SFTPServerInterface):
    def list_folder(self, path: str) -> list[paramiko.SFTPAttributes]:
        attrs = paramiko.SFTPAttributes()
        attrs.filename = "remote.csv"
        attrs.st_mode = 0o100644
        return [attrs]


class DirectorySFTPTarget(_SSHServer):
    """SSH server whose SFTP subsystem reads and writes real files.

    With *root*, SFTP paths resolve under that directory (``/a`` is ``root/a``).
    Without it, paths are host paths, relative ones against the process's cwd.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        super().__init__()

    def _interface(self) -> paramiko.ServerInterface:
        return _PasswordInterface()

    def _prepare(self, transport: paramiko.Transport) -> None:
        transport.set_subsystem_handler("sftp", paramiko.SFTPServer, _DirectorySFTP, self.root)


class _FileHandle(paramiko.SFTPHandle):
    filename: str
    readfile: t.IO[t.Any]
    writefile: t.IO[t.Any]

    def stat(self) -> t.Any:
        try:
            return paramiko.SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def chattr(self, attr: t.Any) -> int:
        return paramiko.sftp.SFTP_OK


class _DirectorySFTP(paramiko.SFTPServerInterface):
    """Map SFTP paths onto the filesystem; errors become SFTP status codes."""

    def __init__(self, server: t.Any, root: Path | None) -> None:
        super().__init__(server)
        self._root = root

    def _real(self, path: str) -> str:
        if self._root is None:
            return path  # like sftp-server: the kernel resolves links and "..", relative to cwd
        return str(self._root / path.lstrip("/"))

    def _attempt(self, action: t.Callable[[], t.Any]) -> t.Any:
        try:
            return action()
        except OSError as exc:
            return paramiko.SFTPServer.convert_errno(exc.errno)

    def _done(self, action: t.Callable[..., None], *paths: str) -> t.Any:
        def run() -> int:
            action(*(self._real(path) for path in paths))
            return paramiko.sftp.SFTP_OK
        return self._attempt(run)

    def list_folder(self, path: str) -> t.Any:
        def listing() -> list[paramiko.SFTPAttributes]:
            real = self._real(path)
            entries = []
            for name in os.listdir(real):
                attrs = paramiko.SFTPAttributes.from_stat(os.lstat(os.path.join(real, name)))
                attrs.filename = name
                entries.append(attrs)
            return entries
        return self._attempt(listing)

    def stat(self, path: str) -> t.Any:
        return self._attempt(lambda: paramiko.SFTPAttributes.from_stat(os.stat(self._real(path))))

    def lstat(self, path: str) -> t.Any:
        return self._attempt(lambda: paramiko.SFTPAttributes.from_stat(os.lstat(self._real(path))))

    def open(self, path: str, flags: int, attr: t.Any) -> t.Any:
        def opened() -> _FileHandle:
            fd = os.open(self._real(path), flags, 0o644)
            if flags & os.O_WRONLY:
                mode = "ab" if flags & os.O_APPEND else "wb"
            elif flags & os.O_RDWR:
                mode = "a+b" if flags & os.O_APPEND else "r+b"
            else:
                mode = "rb"
            handle = _FileHandle(flags)
            handle.filename = self._real(path)
            handle.readfile = handle.writefile = os.fdopen(fd, mode)
            return handle
        return self._attempt(opened)

    def remove(self, path: str) -> t.Any:
        return self._done(os.remove, path)

    def rename(self, oldpath: str, newpath: str) -> t.Any:
        # OpenSSH's plain rename refuses an existing destination (link + unlink).
        def refuse_existing(old: str, new: str) -> None:
            if os.path.lexists(new):
                raise FileExistsError(errno.EEXIST, "File exists")
            os.rename(old, new)
        return self._done(refuse_existing, oldpath, newpath)

    def posix_rename(self, oldpath: str, newpath: str) -> t.Any:
        return self._done(os.replace, oldpath, newpath)

    def mkdir(self, path: str, attr: t.Any) -> t.Any:
        return self._done(os.mkdir, path)

    def rmdir(self, path: str) -> t.Any:
        return self._done(os.rmdir, path)

    def chattr(self, path: str, attr: t.Any) -> int:
        return paramiko.sftp.SFTP_OK
