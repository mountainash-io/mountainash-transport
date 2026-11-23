"""Seek within a file without reading all of it: locally, and over HTTP byte ranges."""

import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mountainash_transport import RangePolicy, StorageFacade

BODY = bytes(range(256)) * 4096  # 1 MiB with a recognisable pattern


class RangeServer(BaseHTTPRequestHandler):
    """A tiny in-process web server that honours single byte ranges."""

    sent: list[int] = []

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self) -> None:
        start, end = (int(part) for part in self.headers["Range"].removeprefix("bytes=").split("-"))
        chunk = BODY[start:end + 1]
        self.send_response(206)
        self.send_header("Content-Range", f"bytes {start}-{start + len(chunk) - 1}/{len(BODY)}")
        self.send_header("Content-Length", str(len(chunk)))
        self.end_headers()
        self.wfile.write(chunk)
        RangeServer.sent.append(len(chunk))

    def log_message(self, *args: object) -> None:
        pass


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "data.bin")
        with StorageFacade.from_path(path) as storage:
            storage.write(path, BODY)
            with storage.read_stream(path, access="random") as handle:
                handle.seek(-4, 2)
                tail = handle.read()
        assert tail == BODY[-4:]
        print(f"local: last 4 bytes {tail.hex()}")

    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/data.bin"
    try:
        with StorageFacade.from_path(url) as web:
            for policy in (RangePolicy("none"), RangePolicy("readahead", block_size=64 * 1024)):
                RangeServer.sent.clear()
                with web.read_stream(url, access="random", range_policy=policy) as handle:
                    handle.seek(500_000)
                    first = handle.read(4)
                    second = handle.read(4)
                assert first + second == BODY[500_000:500_008]
                print(f"http {policy.cache}: 8 bytes read in {len(RangeServer.sent)} request(s), "
                      f"{sum(RangeServer.sent)} bytes transferred")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
