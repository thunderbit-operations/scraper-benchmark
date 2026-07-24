#!/usr/bin/env python3
"""Local fixture server for the Browserless evidence pack.

Focus of this pack = DEPLOYMENT + LIFECYCLE overhead of a containerized headless
browser service, NOT another browser-library feature comparison. The fixture
therefore exists to (a) give the REST endpoints controlled ground truth to render,
and (b) provide a server-side, tool-independent way to occupy a session for a
controlled duration (the concurrency-ceiling probe).

The Browserless container reaches this server on the HOST via
`host.docker.internal` (colima maps it with --add-host host-gateway), so the
server binds 0.0.0.0 (loopback-only would be unreachable from inside the
container). It is only ever bound on the local machine; no external exposure.

Routes:
  /                     home
  /render               A page whose visible marker text is INJECTED BY JS at load
                        (assembled from fragments -> no contiguous literal in bytes).
                        This is the class a STATIC fetch misses; a real browser
                        render (which Browserless is) should surface it. Same content
                        class katana's static crawl misses / playwright-mcp catches
                        -> the cross-series data point.
  /slow?ms=N            Server SLEEPS N ms before sending the response body, so a
                        browser navigation to it occupies a Browserless session for
                        ~N ms. Deterministic, tool-independent session occupancy for
                        the concurrency-ceiling / queue / 429 probe.
  /hits                 JSON of server-side hit counts (what the browser FETCHED),
                        independent of the container's own /sessions reporting.
  /favicon.ico          204 (removes a console confound)

Every marker is a UNIQUE string so presence/absence is measured against a known
set, never guessed.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections import Counter
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse, parse_qs


_HITS: Counter = Counter()
_LOCK = threading.Lock()

# Ground-truth markers (unique; presence/absence is the measurement).
GT = {
    # Static markers that ARE literals in the served bytes.
    "static_heading": "Browserless Fixture Static Heading",
    "static_paragraph": "STATIC_PARAGRAPH_MARKER_AA",
    # Runtime-injected marker: assembled from fragments + a computed number so the
    # string "Runtime Injected Marker 88" is NOT a contiguous literal in any byte
    # the server sends. Only a real browser render surfaces it.
    "runtime_injected_marker": "Runtime Injected Marker 88",
    # A value a /scrape selector should pull out by CSS.
    "scrape_target_id": "scrape-me",
    "scrape_target_text": "SCRAPE_TARGET_VALUE_CC",
}


def reset_hits() -> None:
    with _LOCK:
        _HITS.clear()


def snapshot_hits() -> dict[str, int]:
    with _LOCK:
        return dict(_HITS)


def html_page(title: str, body: str, head_extra: str = "") -> bytes:
    return (
        f"<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title>{head_extra}</head>\n<body>\n{body}\n</body></html>"
    ).encode("utf-8")


# Runtime-injection script: assemble marker + a scrape target at load time.
RUNTIME_SCRIPT = """
<script>
  var n = 80 + 8;                                             // 88, computed
  var label = 'Runtime' + ' ' + 'Injected' + ' ' + 'Marker' + ' ' + n;
  var d = document.createElement('div');
  d.id = 'runtime-injected';
  d.textContent = label;
  document.body.appendChild(d);
  // A CSS-addressable scrape target, also injected at runtime.
  var s = document.createElement('span');
  s.id = 'scrape-me';
  s.textContent = 'SCRAPE' + '_TARGET_' + 'VALUE' + '_CC';
  document.body.appendChild(s);
</script>
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "BrowserlessFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _record(self, path: str) -> None:
        with _LOCK:
            _HITS[path] += 1

    def _send(self, status: int, body: bytes,
              ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        self._record(path)

        if path == "/favicon.ico":
            self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
            return

        if path == "/":
            body = ('<h1>Browserless Fixture</h1>'
                    '<nav><a href="/render">render</a> '
                    '<a href="/slow?ms=1000">slow</a></nav>')
            self._send(HTTPStatus.OK, html_page("Home", body))
            return

        if path == "/render":
            body = (
                f'<h1>{GT["static_heading"]}</h1>'
                f'<p>{GT["static_paragraph"]}</p>'
                f'{RUNTIME_SCRIPT}'
            )
            self._send(HTTPStatus.OK, html_page("Render", body))
            return

        if path == "/slow":
            qs = parse_qs(parsed.query)
            try:
                ms = max(0, min(60000, int(qs.get("ms", ["1000"])[0])))
            except ValueError:
                ms = 1000
            time.sleep(ms / 1000.0)
            body = f'<h1>Slow Page</h1><p>slept {ms} ms server-side</p>'
            self._send(HTTPStatus.OK, html_page("Slow", body))
            return

        if path == "/hits":
            self._send(HTTPStatus.OK,
                       json.dumps(snapshot_hits()).encode("utf-8"),
                       "application/json")
            return

        self._send(HTTPStatus.NOT_FOUND, b"<h1>not found 404</h1>")


class HardenedFixtureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 512


@dataclass
class FixtureServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    base_url: str          # host-visible base (127.0.0.1) for the harness itself
    port: int

    def stop(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_fixture_server(port: int | None = None) -> FixtureServer:
    port = port or find_free_port()
    # Bind 0.0.0.0 so the Browserless container can reach it via host.docker.internal.
    httpd = HardenedFixtureServer(("0.0.0.0", port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever,
                              name="bl-fixture", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread,
                         base_url=f"http://127.0.0.1:{port}", port=port)


if __name__ == "__main__":
    srv = start_fixture_server(8990)
    print(f"serving at {srv.base_url} (0.0.0.0:{srv.port})")
    print(json.dumps(GT, indent=2))
    try:
        srv.thread.join()
    except KeyboardInterrupt:
        srv.stop()
