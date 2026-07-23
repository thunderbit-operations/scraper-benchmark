#!/usr/bin/env python3
"""Local fixture server for the Katana evidence pack.

The whole point is three DISTINCT endpoint classes that separate what each Katana
mode can discover:

  A. HTML-referenced endpoints — plain <a href> in the served HTML. Any crawler
     (standard mode) should find these.
  B. JS-literal endpoints — URL string literals inside a linked /static/app.js.
     A browserless crawl misses them unless JS parsing (-jc) is enabled.
  C. Runtime-DOM-only endpoint — a path ASSEMBLED at runtime from fragments so it
     never appears as a contiguous literal in ANY served byte (not the HTML, not
     the JS source). Only a real browser that executes the script and inspects the
     resulting DOM can discover it. This is the true boundary of headless mode.

Plus: an external out-of-scope link, a depth chain, robots.txt + sitemap.xml
(known-files), a 500 route, and a broken link — for scope/depth/known-files/
robustness tests.

Ground truth is emitted to a JSON the harness reads, and every discoverable path
is defined here so recall is measured against a known set, never guessed.
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


# Server-side truth: which paths the crawler actually FETCHED (not just emitted).
# This is how we prove scope discipline (out-of-scope host never fetched) and
# known-files behavior, independent of Katana's own stdout.
_HITS: Counter = Counter()
_HITS_LOCK = threading.Lock()


def reset_hits() -> None:
    with _HITS_LOCK:
        _HITS.clear()


def snapshot_hits() -> dict[str, int]:
    with _HITS_LOCK:
        return dict(_HITS)


# --- Ground-truth endpoint classes (paths only; host filled in at runtime) ---
HTML_ENDPOINTS = ["/page/a", "/page/b", "/page/c", "/depth/1"]      # class A
HTML_DEPTH_CHAIN = ["/depth/1", "/depth/2", "/depth/3"]             # class A, nested
JS_LITERAL_ENDPOINTS = ["/api/js-endpoint-7", "/api/js-endpoint-8"]  # class B (in app.js)
RUNTIME_DOM_ENDPOINT = "/runtime-only/endpoint42"                    # class C (assembled at runtime)
KNOWN_FILE_ENDPOINTS = ["/sitemap/hidden-1", "/sitemap/hidden-2"]    # via sitemap.xml
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

# app.js contains class-B endpoints as literals (discoverable by -jc), but does
# NOT contain the class-C runtime path as a literal.
APP_JS = """// fixture app.js
function loadData() {
  fetch('/api/js-endpoint-7').then(r => r.json());
  const other = "/api/js-endpoint-8";
  return other;
}
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "KatanaFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        with _HITS_LOCK:
            _HITS[path] += 1

        if path == "/":
            links = "\n".join(f'<a href="{e}">{e}</a>' for e in HTML_ENDPOINTS)
            # No external link here (it would trigger a real-internet fetch and
            # pollute timing); scope is tested separately via /scope-seed with a
            # fast local secondary host.
            body = f"""<h1>Katana Fixture Home</h1>
<nav>{links}</nav>
<a href="/broken-xyz">broken link</a>
<a href="/failure/500">failure</a>
<a href="/dynamic/runtime">runtime page</a>
{RUNTIME_DOM_SCRIPT.replace('<script src="/static/app.js"></script>', '')}"""
            # Note: home also loads app.js so class-B endpoints are reachable via JS parsing.
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
    """Katana crawls with -c 10 concurrent fetchers, which arrives as a burst of
    simultaneous connects. socketserver's default listen backlog is 5; under the
    burst that overflows and the kernel silently drops/resets connects, which
    katana experiences as dial timeouts (default -timeout 10 x -retry 1 => multi-
    second stalls) — a fixture limitation, not katana behavior. A deep backlog and
    address reuse make accepts reliable so measured behavior isn't confounded by
    connection drops."""

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


def start_fixture_server(port: int | None = None) -> FixtureServer:
    port = port or find_free_port()
    httpd = HardenedFixtureServer(("127.0.0.1", port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="katana-fixture", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    srv = start_fixture_server(8977)
    print(f"serving at {srv.base_url}")
    print(json.dumps(ground_truth(srv.base_url), indent=2))
    try:
        srv.thread.join()
    except KeyboardInterrupt:
        srv.stop()
