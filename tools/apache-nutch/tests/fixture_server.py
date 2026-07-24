#!/usr/bin/env python3
"""Local fixture server for the Apache Nutch evidence pack.

This is the SAME same-fixture philosophy used by the katana pack (three distinct
endpoint classes + server-side hit truth), so Nutch's discovery coverage can be
compared on identical ground truth. The endpoint classes are what separate what a
browserless static crawler (Nutch / katana standard), a regex JS-link extractor
(Nutch parse-js / katana -jc), and a real browser (headless) can each discover:

  A. HTML-referenced endpoints  -- plain <a href> in the served HTML. Any crawler
     that parses HTML finds these.
  B. JS-literal endpoints       -- URL string literals inside a linked
     /static/app.js. A browserless crawl misses them UNLESS a JS-link extractor is
     enabled (Nutch: the parse-js plugin; katana: -jc / jsluice).
  C. Runtime-DOM-only endpoint  -- a path ASSEMBLED at runtime from fragments so it
     never appears as a contiguous literal in ANY served byte (not the HTML, not
     the JS source). Only a real browser that executes the script and inspects the
     resulting DOM can discover it. Neither Nutch (default/parse-js) nor katana
     standard/-jc can reach it.

Plus: an out-of-scope secondary host link, a depth chain, robots.txt + sitemap.xml
(known-files), a 500 route, and a broken link -- for scope/depth/known-files/
robustness tests.

Every discoverable path is defined here, so recall is measured against a known set,
never guessed. The server also records the ORDER and TIMESTAMP of every hit, which
is how politeness (inter-request delay to the same host) is measured from the
server side, independent of Nutch's own logs.
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
from urllib.parse import urlparse


# Server-side truth: which paths the crawler actually FETCHED (not just discovered),
# how many times, and WHEN. This proves scope discipline and politeness from the
# server side, independent of Nutch's own stdout / crawldb.
_HITS: Counter = Counter()
_HIT_LOG: list[dict[str, Any]] = []  # ordered [{path, ts_monotonic, ua}]
_HITS_LOCK = threading.Lock()


def reset_hits() -> None:
    with _HITS_LOCK:
        _HITS.clear()
        _HIT_LOG.clear()


def snapshot_hits() -> dict[str, int]:
    with _HITS_LOCK:
        return dict(_HITS)


def snapshot_hit_log() -> list[dict[str, Any]]:
    with _HITS_LOCK:
        return list(_HIT_LOG)


# --- Ground-truth endpoint classes (paths only; host filled in at runtime) ---
HTML_ENDPOINTS = ["/page/a", "/page/b", "/page/c", "/depth/1"]      # class A
HTML_DEPTH_CHAIN = ["/depth/1", "/depth/2", "/depth/3"]             # class A, nested
JS_LITERAL_ENDPOINTS = ["/api/js-endpoint-7", "/api/js-endpoint-8"]  # class B (in app.js)
RUNTIME_DOM_ENDPOINT = "/runtime-only/endpoint42"                    # class C (assembled at runtime)
KNOWN_FILE_ENDPOINTS = ["/sitemap/hidden-1", "/sitemap/hidden-2"]    # via sitemap.xml only
EXTERNAL_LINK = "https://example.com/external-should-not-be-crawled"  # out of scope


def ground_truth(base_url: str) -> dict[str, Any]:
    return {
        "base_url": base_url,
        "class_A_html": HTML_ENDPOINTS,
        "class_A_depth_chain": HTML_DEPTH_CHAIN,
        "class_B_js_literal": JS_LITERAL_ENDPOINTS,
        "class_C_runtime_dom_only": RUNTIME_DOM_ENDPOINT,
        "known_file_sitemap": KNOWN_FILE_ENDPOINTS,
        "external_out_of_scope": EXTERNAL_LINK,
    }


def html_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
{body}
</body></html>""".encode("utf-8")


# The runtime-only path is assembled from fragments so no contiguous literal
# "/runtime-only/endpoint42" exists anywhere in the bytes we serve.
RUNTIME_DOM_SCRIPT = """
<script src="/static/app.js"></script>
<script>
  // Assemble the path from pieces + a char code so it is never a literal string
  // in this HTML or in app.js. Only executing this yields the real href.
  var seg1 = 'runtime' + '-' + 'on' + 'ly';
  var seg2 = 'endpoint' + (6 * 7);            // 42, computed
  var p = '/' + seg1 + '/' + seg2;
  var a = document.createElement('a');
  a.href = p;
  a.textContent = 'runtime endpoint';
  a.id = 'runtime-link';
  document.body.appendChild(a);
</script>
"""

# app.js contains class-B endpoints as literals (discoverable by a JS-link
# extractor), but does NOT contain the class-C runtime path as a literal.
APP_JS = """// fixture app.js
function loadData() {
  fetch('/api/js-endpoint-7').then(r => r.json());
  const other = "/api/js-endpoint-8";
  return other;
}
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "NutchFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _record(self, path: str) -> None:
        with _HITS_LOCK:
            _HITS[path] += 1
            _HIT_LOG.append({
                "path": path,
                "ts_monotonic": round(time.monotonic(), 4),
                "ua": self.headers.get("User-Agent", ""),
            })

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        # Out-of-band introspection: a secondary fixture running in its OWN process
        # exposes its hit counter here so scope discipline can be proven from that
        # server's side. This route is NOT recorded as a hit.
        if path == "/__hits__":
            body = json.dumps({"hits": snapshot_hits()}).encode("utf-8")
            self._send(HTTPStatus.OK, body, "application/json")
            return

        self._record(path)

        if path == "/":
            links = "\n".join(f'<a href="{e}">{e}</a>' for e in HTML_ENDPOINTS)
            body = f"""<h1>Nutch Fixture Home</h1>
<nav>{links}</nav>
<a href="/broken-xyz">broken link</a>
<a href="/failure/500">failure</a>
<a href="/dynamic/runtime">runtime page</a>
{RUNTIME_DOM_SCRIPT.replace('<script src="/static/app.js"></script>', '')}"""
            # Home also loads app.js so class-B endpoints are reachable via a JS
            # link extractor that scans the fetched app.js bytes.
            body = '<script src="/static/app.js"></script>\n' + body
            self._send(HTTPStatus.OK, html_page("Home", body))
            return

        # Scope seed: links to an out-of-scope host passed via env (a second
        # fixture on a different hostname), so scope discipline can be proven from
        # that server's hit counter.
        if path == "/scope-seed":
            import os as _os
            secondary = _os.environ.get("SCOPE_SECONDARY_URL", "")
            body = (f"<h1>Scope Seed</h1>"
                    f'<a href="/page/a">in-scope</a>'
                    f'<a href="{secondary}/page/out">out-of-scope host</a>')
            self._send(HTTPStatus.OK, html_page("Scope Seed", body))
            return

        if path == "/static/app.js":
            self._send(HTTPStatus.OK, APP_JS.encode("utf-8"), "application/javascript; charset=utf-8")
            return

        # The dedicated runtime page: only JS execution reveals class-C endpoint.
        if path == "/dynamic/runtime":
            body = f"""<h1>Runtime Injection Page</h1>
<p>The runtime-only endpoint is injected by JavaScript below.</p>
{RUNTIME_DOM_SCRIPT}"""
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
            # Endpoints return small JSON so a hit is verifiable.
            self._send(HTTPStatus.OK, json.dumps({"endpoint": path, "ok": True}).encode("utf-8"),
                       "application/json")
            return

        if path == "/robots.txt":
            host = self.headers.get("Host", "127.0.0.1")
            body = (f"User-agent: *\nAllow: /\n"
                    f"Sitemap: http://{host}/sitemap.xml\n").encode("utf-8")
            self._send(HTTPStatus.OK, body, "text/plain; charset=utf-8")
            return

        if path == "/sitemap.xml":
            # Sitemaps require ABSOLUTE <loc> URLs; build them from the Host header.
            host = self.headers.get("Host", "127.0.0.1")
            base = f"http://{host}"
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
    """A deep listen backlog + address reuse so a burst of concurrent fetcher
    connects is accepted reliably (stdlib default backlog of 5 drops connects under
    a burst, which a crawler experiences as dial timeouts -- a fixture limitation,
    not crawler behavior). This changes connection reliability only, not results."""

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
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def start_fixture_server(port: int | None = None, host: str = "127.0.0.1") -> FixtureServer:
    port = port or find_free_port()
    httpd = HardenedFixtureServer((host, port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="nutch-fixture", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://{host}:{port}")


if __name__ == "__main__":
    # Optional args: [port] [host]. Used to launch a SECONDARY out-of-scope fixture
    # (e.g. host "localhost") in its own process for the scope test. Prints the
    # base_url on the first line so a parent can read it.
    import sys as _sys
    _port = int(_sys.argv[1]) if len(_sys.argv) > 1 else 8977
    _host = _sys.argv[2] if len(_sys.argv) > 2 else "127.0.0.1"
    srv = start_fixture_server(_port, host=_host)
    print(srv.base_url, flush=True)
    try:
        srv.thread.join()
    except KeyboardInterrupt:
        srv.stop()
