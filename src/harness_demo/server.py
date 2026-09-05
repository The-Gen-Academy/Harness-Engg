from __future__ import annotations

import contextlib
import functools
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@contextlib.contextmanager
def temporary_server(root: Path, host: str = "127.0.0.1") -> Iterator[str]:
    handler = functools.partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer((host, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def serve_forever(root: Path, host: str, port: int) -> None:
    handler = functools.partial(QuietHandler, directory=str(root))
    server = ThreadingHTTPServer((host, port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
