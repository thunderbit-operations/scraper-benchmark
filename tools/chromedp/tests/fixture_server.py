#!/usr/bin/env python3
"""Local fixture server for the chromedp evidence pack.

The point is THREE content classes that separate *when* content exists in the DOM,
so a live-browser driver's wait strategy is what decides recall (not merely "it's a
browser"). Reuses the katana / playwright-mcp same-fixture + server-side-hit-counter
philosophy.

Content classes (each carries a UNIQUE ground-truth marker so the harness measures
presence/absence against a known set — never guesses):

  A. Static HTML  — an <a> with a marker that is a LITERAL in the served bytes.
     Present the instant the HTML is parsed; any read gets it.
  B. Sync-injected — a node created by an INLINE <script> that runs during initial
     parse. Present by the load event. Its marker + href are ASSEMBLED from
     fragments, so no contiguous literal exists in any served byte (only executing
     the JS reveals it — proving the browser rendered, not just read bytes).
  C. Delayed-injected — a node created `DELAY` ms AFTER the load event via
     setTimeout. Marker + href assembled from fragments too. `Navigate` returns on
     the load event, so a naive read MISSES class C; only a wait keyed to the node
     (WaitVisible / poll) recovers it. This is the adversarial timing boundary, and
     the SAME content class katana's static crawl misses and playwright-mcp catches.

Plus: a /waitsem page (attached-but-hidden node for WaitReady-vs-WaitVisible), leaf
pages, a 500 route and a dead link. A server-side hit counter records which paths
Chrome actually FETCHED — fetch-truth independent of chromedp's own return values.
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
from urllib.parse import urlparse, parse_qs


# Server-side truth: which paths the browser actually FETCHED, independent of what
# chromedp reports. This is how class-A/B/C leaf fetches and robustness are proven.
_HITS: Counter = Counter()
_HITS_LOCK = threading.Lock()


def reset_hits() -> None:
    with _HITS_LOCK:
        _HITS.clear()


def snapshot_hits() -> dict[str, int]:
    with _HITS_LOCK:
        return dict(_HITS)


# --- Ground-truth markers (unique strings; presence/absence is the measurement) ---
# A is a literal in served HTML. B and C are assembled at runtime from fragments so
# neither the marker nor the href appears as a contiguous literal in any served byte.
GT = {
    "A_static_marker": "STATIC_ALPHA_MARKER_A",       # literal in /classes HTML
    "A_static_href": "/page/alpha",                    # literal <a href>
    "B_sync_marker": "SYNC_INJECTED_MARKER_B",         # assembled by inline script
    "B_sync_href": "/sync/injected-11",                # assembled (11 computed)
    "C_delayed_marker": "DELAYED_INJECTED_MARKER_C",   # assembled after load (setTimeout)
    "C_delayed_href": "/delayed/injected-42",          # assembled (42 computed)
    "waitsem_hidden_marker": "HIDDEN_ATTACHED_MARKER_H",  # display:none, attached
    "waitsem_visible_marker": "VISIBLE_MARKER_V",         # visible node
}


def ground_truth(base_url: str) -> dict[str, Any]:
    return {"base_url": base_url, **GT}


def html_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title></head>
<body>
{body}
</body></html>""".encode("utf-8")


# Class B: an INLINE script that runs during initial parse (present by load event).
# Marker + href are assembled from fragments + a computed number, so no contiguous
# literal "SYNC_INJECTED_MARKER_B" or "/sync/injected-11" exists in the served bytes.
SYNC_SCRIPT = """
<script>
  (function () {
    var n = 5 + 6;                                          // 11, computed
    var marker = 'SYNC' + '_INJECTED_' + 'MARKER' + '_B';   // assembled
    var href = '/' + 'sync' + '/' + 'injected' + '-' + n;   // assembled
    var a = document.createElement('a');
    a.href = href; a.id = 'sync-injected'; a.textContent = marker;
    document.body.appendChild(a);
  })();
</script>
"""


def delayed_script(delay_ms: int) -> str:
    # Class C: inject DELAY ms AFTER the load event, so `Navigate` (which returns on
    # load) cannot see it without an explicit wait. Marker + href assembled from
    # fragments so only executing + waiting reveals them.
    return f"""
<script>
  window.addEventListener('load', function () {{
    setTimeout(function () {{
      var n = 6 * 7;                                             // 42, computed
      var marker = 'DELAYED' + '_INJECTED_' + 'MARKER' + '_C';  // assembled
      var href = '/' + 'delayed' + '/' + 'injected' + '-' + n;  // assembled
      var a = document.createElement('a');
      a.href = href; a.id = 'delayed-injected'; a.textContent = marker;
      document.body.appendChild(a);
    }}, {delay_ms});
  }});
</script>
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "ChromedpFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
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
        with _HITS_LOCK:
            _HITS[path] += 1

        if path == "/favicon.ico":
            self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
            return

        if path == "/":
            body = ('<h1>chromedp fixture</h1>'
                    '<nav><a href="/classes">content classes</a>'
                    '<a href="/waitsem">wait semantics</a></nav>')
            self._send(HTTPStatus.OK, html_page("Home", body))
            return

        # Main page: class A static + class B sync-injected + class C delayed-injected.
        # ?delay=N sets the class-C post-load injection delay (default 800ms).
        if path == "/classes":
            qs = parse_qs(parsed.query)
            try:
                delay = max(0, min(10000, int(qs.get("delay", ["800"])[0])))
            except ValueError:
                delay = 800
            body = (
                # Class A: literal marker + literal href in the served bytes.
                f'<h1>content classes</h1>'
                f'<a href="{GT["A_static_href"]}" id="static-alpha">{GT["A_static_marker"]}</a>'
                f'<p data-delay="{delay}">delay={delay}ms</p>'
                # Class B: sync inline-script injection (present by load event).
                f'{SYNC_SCRIPT}'
                # Class C: delayed post-load injection.
                f'{delayed_script(delay)}'
            )
            self._send(HTTPStatus.OK, html_page("Content Classes", body))
            return

        # Wait-semantics page: an attached-but-hidden node (display:none) and a
        # visible node, both with real ids, for WaitReady vs WaitVisible.
        if path == "/waitsem":
            body = (
                f'<h1>wait semantics</h1>'
                f'<div id="visible-target">{GT["waitsem_visible_marker"]}</div>'
                f'<div id="hidden-target" style="display:none">{GT["waitsem_hidden_marker"]}</div>'
            )
            self._send(HTTPStatus.OK, html_page("Wait Semantics", body))
            return

        if path.startswith("/page/") or path.startswith("/sync/") or path.startswith("/delayed/"):
            self._send(HTTPStatus.OK, html_page(path, f"<h1>{path}</h1><p>leaf page</p>"))
            return

        if path == "/failure/500":
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, b"<h1>fixture 500</h1>")
            return

        self._send(HTTPStatus.NOT_FOUND, b"<h1>not found 404</h1>")


class HardenedFixtureServer(ThreadingHTTPServer):
    """Deep listen backlog + address reuse so a browser's connection burst is accepted
    reliably (stdlib default backlog of 5 drops connects under load). Connection
    reliability only; does not change page content."""

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
    thread = threading.Thread(target=httpd.serve_forever, name="chromedp-fixture", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    srv = start_fixture_server(8990)
    print(f"serving at {srv.base_url}")
    print(json.dumps(ground_truth(srv.base_url), indent=2))
    try:
        srv.thread.join()
    except KeyboardInterrupt:
        srv.stop()
