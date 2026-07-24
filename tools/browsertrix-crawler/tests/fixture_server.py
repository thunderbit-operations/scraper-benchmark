#!/usr/bin/env python3
"""Local fixture server for the Browsertrix Crawler evidence pack.

Browsertrix Crawler is a *real-browser archiver*: it drives Chromium, executes
page JS, and writes everything the browser actually fetched into WARC/WACZ. So
the interesting question is not "what URLs exist" (a discovery framing, cf. the
katana pack) but "what does a real-browser archiver actually CAPTURE into the
archive, and what does it miss." The fixture separates the dynamic behaviours
that decide this:

  A. HTML-referenced endpoints  — plain <a href> in served HTML. Any crawler
     that extracts links finds these.
  B. JS-literal, NEVER executed — URL string literals inside a linked
     /static/app.js (inside an uncalled function). The bytes of app.js ARE
     archived, but the endpoints are never fetched, so a real-browser archiver
     that records executed traffic never issues a request for them. This is the
     boundary: an archiver captures what the browser DID, not what code merely
     references. (A static JS parser like katana's -jc recovers these; an
     archiver does not.)
  C. Runtime-DOM-only link       — an <a href> assembled at runtime from
     fragments (never a contiguous literal in any served byte) and appended to
     the DOM. Only a browser that executes the script and then extracts links
     from the rendered DOM can enqueue and fetch it.
  D. Runtime fetch() on load     — the page actually calls fetch() for an
     endpoint whose path is likewise assembled at runtime. A real-browser
     archiver captures this response as ordinary network traffic; a static
     crawler would not even look. This is the archiver's forte.

Plus: an out-of-scope host link (scope test), a depth chain, robots.txt +
sitemap.xml (known-files), a 500 route, and a dead link (robustness).

Server-side hit truth: every request is recorded as (host_header, path) so we
can prove, independent of browsertrix's own logs or the archive, exactly which
(host, path) pairs the crawler actually fetched. Scope is proven by hostname.

The server binds 0.0.0.0 (not just loopback) because the crawl runs INSIDE a
Docker container that reaches this host via `host.docker.internal`; a
loopback-only bind would refuse the container's gateway-sourced connections.
It is an ephemeral server on a random free port, torn down after each run.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from collections import Counter
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


# Server-side truth: (host_header, path) -> count of GETs actually served.
_HITS: Counter = Counter()
_HITS_LOCK = threading.Lock()


def reset_hits() -> None:
    with _HITS_LOCK:
        _HITS.clear()


def snapshot_hits() -> dict[str, int]:
    # Keys are "host||path" strings (JSON-serialisable).
    with _HITS_LOCK:
        return {f"{h}||{p}": c for (h, p), c in _HITS.items()}


def hit_paths() -> set[str]:
    with _HITS_LOCK:
        return {p for (_h, p) in _HITS.keys()}


def hit_hosts() -> set[str]:
    with _HITS_LOCK:
        return {h for (h, _p) in _HITS.keys()}


# --- Ground-truth endpoint classes (paths only; host filled in at runtime) ---
HTML_ENDPOINTS = ["/page/a", "/page/b", "/page/c", "/depth/1"]        # class A
HTML_DEPTH_CHAIN = ["/depth/1", "/depth/2", "/depth/3"]              # class A, nested
JS_LITERAL_ENDPOINTS = ["/api/js-endpoint-7", "/api/js-endpoint-8"]   # class B (in app.js, never called)
RUNTIME_DOM_ENDPOINT = "/runtime-only/endpoint42"                     # class C (assembled at runtime, DOM link)
RUNTIME_FETCH_ENDPOINT = "/api/runtime-xhr-99"                        # class D (assembled + fetched at runtime)
KNOWN_FILE_ENDPOINTS = ["/sitemap/hidden-1", "/sitemap/hidden-2"]     # via sitemap.xml
# Out-of-scope host: a DIFFERENT hostname alias that also resolves to this
# fixture (added via docker --add-host). A server-side hit whose Host header is
# this alias proves the out-of-scope host was actually fetched. Never a real
# internet host, so no third-party traffic is generated.
EXTERNAL_HOST_ALIAS = os.environ.get("SCOPE_OUT_HOST", "outofscope.test")
EXTERNAL_PORT = os.environ.get("SCOPE_OUT_PORT", "")


def ground_truth(base_url: str) -> dict[str, Any]:
    return {
        "base_url": base_url,
        "class_A_html": HTML_ENDPOINTS,
        "class_A_depth_chain": HTML_DEPTH_CHAIN,
        "class_B_js_literal_never_called": JS_LITERAL_ENDPOINTS,
        "class_C_runtime_dom_link": RUNTIME_DOM_ENDPOINT,
        "class_D_runtime_fetch": RUNTIME_FETCH_ENDPOINT,
        "known_file_sitemap": KNOWN_FILE_ENDPOINTS,
        "out_of_scope_host_alias": EXTERNAL_HOST_ALIAS,
    }


def html_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
{body}
</body></html>""".encode("utf-8")


# Class C link + class D fetch are assembled from fragments so neither
# "/runtime-only/endpoint42" nor "/api/runtime-xhr-99" appears as a contiguous
# literal in any served byte (HTML or JS). Only executing the script produces
# them: C is appended to the DOM (needs DOM link extraction to enqueue), D is
# actually fetch()ed (captured as network traffic by an archiver).
RUNTIME_SCRIPT = """
<script>
  // class C: runtime-only DOM link, never a literal anywhere
  var cseg1 = 'runtime' + '-' + 'on' + 'ly';
  var cseg2 = 'endpoint' + (6 * 7);            // 42, computed
  var cpath = '/' + cseg1 + '/' + cseg2;
  var a = document.createElement('a');
  a.href = cpath;
  a.textContent = 'runtime endpoint';
  a.id = 'runtime-link';
  document.body.appendChild(a);

  // class D: runtime fetch(), path also assembled so it is never a literal
  var dseg = 'runtime' + '-' + 'xhr' + '-' + (33 * 3);  // 99, computed
  var dpath = '/api/' + dseg;
  fetch(dpath).then(function (r) { return r.json(); }).catch(function () {});
</script>
"""

# app.js contains class-B endpoints as literals inside a function that is NEVER
# called, so the browser never fetches them. It does NOT contain class C/D paths.
APP_JS = """// fixture app.js
function loadData() {
  // This function is never invoked, so these endpoints are never fetched.
  fetch('/api/js-endpoint-7').then(r => r.json());
  const other = "/api/js-endpoint-8";
  return other;
}
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "BrowsertrixFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _host(self) -> str:
        # Host header without port, so scope-by-hostname is stable across ports.
        raw = self.headers.get("Host", "")
        return raw.split(":", 1)[0] if raw else ""

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        host = self._host()
        with _HITS_LOCK:
            _HITS[(host, path)] += 1

        if path == "/":
            links = "\n".join(f'<a href="{e}">{e}</a>' for e in HTML_ENDPOINTS)
            secondary = ""
            if EXTERNAL_PORT:
                secondary = (f'<a href="http://{EXTERNAL_HOST_ALIAS}:{EXTERNAL_PORT}/page/out">'
                             f'out-of-scope host</a>')
            body = f"""<h1>Browsertrix Fixture Home</h1>
<nav>{links}</nav>
<a href="/dynamic/runtime">runtime page</a>
<a href="/broken-xyz">broken link</a>
<a href="/failure/500">failure</a>
{secondary}
<script src="/static/app.js"></script>
{RUNTIME_SCRIPT}"""
            self._send(HTTPStatus.OK, html_page("Home", body))
            return

        if path == "/static/app.js":
            self._send(HTTPStatus.OK, APP_JS.encode("utf-8"),
                       "application/javascript; charset=utf-8")
            return

        # Dedicated runtime page: JS execution reveals class C link + class D fetch.
        if path == "/dynamic/runtime":
            body = f"""<h1>Runtime Injection Page</h1>
<p>The runtime-only link and runtime fetch are produced by JavaScript below.</p>
<script src="/static/app.js"></script>
{RUNTIME_SCRIPT}"""
            self._send(HTTPStatus.OK, html_page("Runtime", body))
            return

        # Depth chain: /depth/1 -> /depth/2 -> /depth/3
        if path.startswith("/depth/"):
            n = int(path.rsplit("/", 1)[-1])
            nxt = f'<a href="/depth/{n+1}">next depth {n+1}</a>' if n < 3 else "<p>end of chain</p>"
            self._send(HTTPStatus.OK, html_page(f"Depth {n}", f"<h1>Depth {n}</h1>{nxt}"))
            return

        if path.startswith("/page/"):
            self._send(HTTPStatus.OK, html_page(path, f"<h1>{path}</h1><p>static page</p>"))
            return

        if path.startswith("/api/") or path.startswith("/sitemap/") or path.startswith("/runtime-only/"):
            self._send(HTTPStatus.OK,
                       json.dumps({"endpoint": path, "ok": True}).encode("utf-8"),
                       "application/json")
            return

        if path == "/robots.txt":
            host_hdr = self.headers.get("Host", "127.0.0.1")
            body = (f"User-agent: *\nAllow: /\n"
                    f"Sitemap: http://{host_hdr}/sitemap.xml\n").encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/plain; charset=utf-8")
            return

        if path == "/sitemap.xml":
            host_hdr = self.headers.get("Host", "127.0.0.1")
            base = f"http://{host_hdr}"
            urls = "".join(f"<url><loc>{base}{e}</loc></url>" for e in KNOWN_FILE_ENDPOINTS)
            body = (f'<?xml version="1.0" encoding="UTF-8"?>'
                    f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
            self._send(HTTPStatus.OK, body.encode("utf-8"), "application/xml; charset=utf-8")
            return

        if path == "/failure/500":
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, b"fixture 500", "text/plain")
            return

        self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")


class HardenedFixtureServer(ThreadingHTTPServer):
    """Deep listen backlog + address reuse so a browser's concurrent resource
    burst is accepted reliably (stdlib default backlog of 5 drops connects under
    a burst). This changes connection reliability only, not what is captured."""

    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 256


@dataclass
class FixtureServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    base_url: str
    port: int

    def stop(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("0.0.0.0", 0))
        return int(s.getsockname()[1])


def start_fixture_server(port: int | None = None) -> FixtureServer:
    port = port or find_free_port()
    # Bind 0.0.0.0 so the Docker container can reach us via host.docker.internal.
    httpd = HardenedFixtureServer(("0.0.0.0", port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="btrix-fixture", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread,
                         base_url=f"http://127.0.0.1:{port}", port=port)


if __name__ == "__main__":
    srv = start_fixture_server(8977)
    print(f"serving at {srv.base_url} (also reachable as host.docker.internal:{srv.port})")
    print(json.dumps(ground_truth(srv.base_url), indent=2))
    try:
        srv.thread.join()
    except KeyboardInterrupt:
        srv.stop()
