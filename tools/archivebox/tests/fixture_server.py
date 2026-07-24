#!/usr/bin/env python3
"""Local fixture server for the ArchiveBox evidence pack.

ArchiveBox runs many *redundant* preservation extractors over the same page
(wget/WARC, singlefile, dom, pdf, screenshot, readability, mercury, htmltotext,
title, favicon, headers, ...). The whole point of this fixture is to plant FOUR
distinct, greppable content tokens whose visibility separates what each output
can and cannot preserve:

  STATIC_TOKEN     — served as visible <article> text in the initial HTML of BOTH
                     pages. Any content extractor (even static wget) must capture
                     it. Baseline for "true redundancy".

  RUNTIME_TOKEN    — injected into the article DOM by JavaScript AT RUNTIME on the
                     /dynamic page. Assembled from fragments + a char code so the
                     contiguous token string never appears in ANY served byte
                     (not the HTML, not the JS source). Only an extractor that
                     executes JS and reads the resulting DOM (chrome-based:
                     singlefile / dom / pdf / screenshot) can preserve it. This is
                     the true boundary between "preservation" outputs.

  JSLIT_TOKEN      — a string literal INSIDE /static/app.js. Present in the served
                     JS bytes (so byte-level captures that save the .js — wget/WARC,
                     singlefile inlining — contain it) but never rendered as visible
                     page text (so text extractors readability/htmltotext/mercury
                     should NOT surface it). Separates "saved the bytes" from
                     "extracted the reading text".

  BOILER_TOKEN     — placed in <nav>/<aside>/<footer> chrome on both pages. Full-page
                     captures keep it; article-text extractors (readability/mercury)
                     should STRIP it. Separates "whole page" from "just the article".

Plus a /failure/500 route and a favicon for robustness / favicon-extractor coverage.

Every token and route is emitted to ground_truth() so capture is measured against a
known set, never guessed. Binds 0.0.0.0 so a container can reach it via
host.docker.internal (colima/Docker Desktop).
"""

from __future__ import annotations

import json
import socket
import threading
from collections import Counter
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

# Server-side truth: which paths were actually FETCHED (independent of ArchiveBox's
# own stdout). Lets us prove e.g. that wget fetched app.js while chrome inlined it.
_HITS: Counter = Counter()
_HITS_LOCK = threading.Lock()


def reset_hits() -> None:
    with _HITS_LOCK:
        _HITS.clear()


def snapshot_hits() -> dict[str, int]:
    with _HITS_LOCK:
        return dict(_HITS)


# --- The four content tokens (unique, greppable, no regex metachars) ---
STATIC_TOKEN = "STATICTOKENq7w8e9"       # visible article text, initial HTML, both pages
RUNTIME_TOKEN = "RUNTIMETOKENr4t5y6"     # injected into DOM at runtime (assembled below)
JSLIT_TOKEN = "JSLITTOKENu1i2o3"         # literal inside app.js, never rendered
BOILER_TOKEN = "BOILERTOKENa1s2d3"       # nav/aside/footer chrome

ROUTES = ["/static", "/dynamic", "/static/app.js", "/failure/500", "/favicon.ico"]


def ground_truth(base_url: str) -> dict[str, Any]:
    return {
        "base_url": base_url,
        "tokens": {
            "STATIC_TOKEN": STATIC_TOKEN,
            "RUNTIME_TOKEN": RUNTIME_TOKEN,
            "JSLIT_TOKEN": JSLIT_TOKEN,
            "BOILER_TOKEN": BOILER_TOKEN,
        },
        # Which token SHOULD be recoverable from each page by an ideal capture:
        "static_page": {
            "url": f"{base_url}/static",
            "expected_visible_text": [STATIC_TOKEN, BOILER_TOKEN],
            "expected_runtime_only": [],
            "expected_js_bytes": [],
        },
        "dynamic_page": {
            "url": f"{base_url}/dynamic",
            "expected_visible_text_static_fetch": [STATIC_TOKEN, BOILER_TOKEN],
            "expected_visible_text_after_js": [STATIC_TOKEN, BOILER_TOKEN, RUNTIME_TOKEN],
            "expected_js_bytes": [JSLIT_TOKEN],
            "runtime_only_token": RUNTIME_TOKEN,
        },
        "routes": ROUTES,
    }


def _doc(title: str, body: str) -> bytes:
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{title}</title><link rel="icon" href="/favicon.ico"></head>'
        f"<body>{body}</body></html>"
    ).encode("utf-8")


_BOILER = (
    f'<nav id="topnav">nav {BOILER_TOKEN} home about</nav>'
    f'<aside class="sidebar">aside {BOILER_TOKEN} related links</aside>'
)
_FOOTER = f'<footer>footer {BOILER_TOKEN} copyright</footer>'


def _article(paragraphs: str) -> str:
    return (
        f'<article><h1>Fixture Article</h1>'
        f"{paragraphs}"
        f"</article>"
    )


# The runtime token is assembled from pieces + a computed char code so the
# contiguous string RUNTIME_TOKEN appears in NO served byte. Only executing this
# yields the real text node in the article DOM.
_RUNTIME_SCRIPT = """
<script src="/static/app.js"></script>
<script>
  // Assemble the runtime token from fragments; it never appears contiguously
  // in any served byte (not this HTML, not the JS). Only executing this and
  // reading the resulting DOM yields the whole token as a visible text node.
  var head = 'RUNTIME' + 'TOKEN';
  var tail = 'r4t5' + 'y' + String.fromCharCode(54);   // '6'
  var tok = head + tail;
  var p = document.createElement('p');
  p.id = 'runtime-content';
  p.textContent = 'runtime injected paragraph ' + tok + ' end';
  document.querySelector('article').appendChild(p);
</script>
"""

# app.js carries JSLIT_TOKEN as a bare string literal (byte-level, never rendered).
_APP_JS = f"""// fixture app.js
// This literal lives in the JS bytes but is never inserted as visible page text:
var _marker = "{JSLIT_TOKEN}";
function noop() {{ return _marker.length; }}
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "ArchiveBoxFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with _HITS_LOCK:
            _HITS[path] += 1

        if path == "/static":
            para = (
                f"<p>intro paragraph one.</p>"
                f"<p>The static content token is {STATIC_TOKEN} embedded here.</p>"
                f"<p>closing paragraph three.</p>"
            )
            body = _BOILER + _article(para) + _FOOTER
            self._send(HTTPStatus.OK, _doc("Static", body))
            return

        if path == "/dynamic":
            # Same STATIC_TOKEN + boilerplate in initial HTML; RUNTIME_TOKEN is
            # added only after app.js + the inline script execute.
            para = (
                f"<p>intro paragraph one.</p>"
                f"<p>The static content token is {STATIC_TOKEN} embedded here.</p>"
            )
            body = _BOILER + _article(para) + _FOOTER + _RUNTIME_SCRIPT
            self._send(HTTPStatus.OK, _doc("Dynamic", body))
            return

        if path == "/static/app.js":
            self._send(HTTPStatus.OK, _APP_JS.encode("utf-8"),
                       "application/javascript; charset=utf-8")
            return

        if path == "/favicon.ico":
            # 1x1 transparent GIF so the favicon extractor has something to save.
            gif = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff"
                   b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01"
                   b"\x00\x00\x02\x01D\x00;")
            self._send(HTTPStatus.OK, gif, "image/gif")
            return

        if path == "/failure/500":
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, b"fixture 500", "text/plain")
            return

        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")


class HardenedFixtureServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 256


@dataclass
class FixtureServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    base_url: str

    def stop(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("0.0.0.0", 0))
        return int(s.getsockname()[1])


def start_fixture_server(port: int | None = None) -> FixtureServer:
    # Bind 0.0.0.0 so a container reaches it via host.docker.internal.
    port = port or find_free_port()
    httpd = HardenedFixtureServer(("0.0.0.0", port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="archivebox-fixture", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    srv = start_fixture_server(8988)
    print(f"serving at {srv.base_url}")
    print(json.dumps(ground_truth(srv.base_url), indent=2))
    try:
        srv.thread.join()
    except KeyboardInterrupt:
        srv.stop()
