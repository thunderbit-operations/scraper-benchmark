#!/usr/bin/env python3
"""Local fixture server for the Playwright MCP evidence pack.

The point is FOUR distinct content classes that separate what an accessibility-tree
snapshot can and cannot surface, plus a complexity gradient for cost scaling and a
server-side cookie counter for session-isolation fetch-truth.

Content classes (each carries a UNIQUE ground-truth marker string so the harness
measures presence/absence against a known set — never guesses):

  A. Semantic accessible elements — <a>, <button>, <input>, headings with real
     roles+names. Any a11y snapshot should surface these.
  B. Runtime-injected accessible element — an <a> created by JS at load time, whose
     href and text are ASSEMBLED from fragments so no contiguous literal exists in
     any served byte. A *live* accessibility tree should still surface it (this is
     the class a STATIC crawler — e.g. katana standard mode — misses; the contrast
     is the cross-series point).
  C. Non-semantic / hidden content — a bare <div> with text (no role) and an
     aria-hidden block. The default "interestingOnly" snapshot is expected to drop
     these.
  D. Canvas-drawn text — a known string painted onto <canvas> via fillText. It lives
     only in pixels; the accessibility tree cannot see it (vision mode territory).

Plus: /gradient?n=N (N interactive elements) for cost-vs-complexity, a cookie
set/check pair for isolation truth, and 500/404 routes for robustness.
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


# Server-side truth: what the browser actually FETCHED, and whether the isolation
# cookie was ever presented back — independent of the MCP server's own reporting.
_HITS: Counter = Counter()
_COOKIE_SEEN: Counter = Counter()  # keyed by path; counts requests carrying the cookie
_LOCK = threading.Lock()

COOKIE_NAME = "wave_d_session"
COOKIE_VALUE = "SECRET_ISOLATION_TOKEN_5F"


def reset_hits() -> None:
    with _LOCK:
        _HITS.clear()
        _COOKIE_SEEN.clear()


def snapshot_hits() -> dict[str, int]:
    with _LOCK:
        return dict(_HITS)


def snapshot_cookie_seen() -> dict[str, int]:
    with _LOCK:
        return dict(_COOKIE_SEEN)


# --- Ground-truth markers (unique strings; presence/absence is the measurement) ---
GT = {
    "A_semantic": {
        "link_names": ["Alpha Page Link", "Beta Page Link"],
        "button_name": "Submit Order Button",
        "input_name": "Search Query Field",
        "heading_name": "Semantic Section Heading",
    },
    # B marker text is assembled at runtime from fragments (see RUNTIME_SCRIPT) so it
    # is NOT a literal anywhere in served bytes.
    "B_runtime_injected_marker": "Runtime Injected Link 77",
    # Class C now maps FOUR distinct hiding mechanisms so we can enumerate exactly
    # which ones the MCP snapshot drops vs surfaces (the boundary, not a blanket claim).
    "C_nonsemantic_div_marker": "NONSEMANTIC_DIV_TEXT_ZZ",      # bare <div>, no role, visible
    "C_aria_hidden_marker": "ARIA_HIDDEN_SECRET_QQ",            # aria-hidden="true"
    "C_display_none_marker": "DISPLAY_NONE_SECRET_DD",          # style=display:none
    "C_visibility_hidden_marker": "VISIBILITY_HIDDEN_SECRET_VV",  # style=visibility:hidden
    "D_canvas_marker": "CANVAS_ONLY_STRING_XY",
}


def ground_truth(base_url: str) -> dict[str, Any]:
    return {"base_url": base_url, **GT}


def html_page(title: str, body: str, head_extra: str = "") -> bytes:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>{head_extra}</head>
<body>
{body}
</body></html>""".encode("utf-8")


# Class B: assemble the marker + href from fragments and a computed number so neither
# "Runtime Injected Link 77" nor "/runtime/injected-77" appears as a literal in bytes.
RUNTIME_SCRIPT = """
<script>
  var num = 70 + 7;                                   // 77, computed
  var label = 'Runtime' + ' ' + 'Injected' + ' ' + 'Link' + ' ' + num;
  var path = '/' + 'runtime' + '/' + 'injected' + '-' + num;
  var a = document.createElement('a');
  a.href = path;
  a.textContent = label;
  a.id = 'runtime-injected';
  document.body.appendChild(a);
</script>
"""

# Class D: draw a known string onto canvas. The string lives only in pixels.
CANVAS_SCRIPT = """
<canvas id="c" width="400" height="80" role="img" aria-label="chart"></canvas>
<script>
  var cv = document.getElementById('c');
  var ctx = cv.getContext('2d');
  ctx.font = '24px sans-serif';
  var s = 'CANVAS' + '_ONLY_' + 'STRING' + '_XY';
  ctx.fillText(s, 10, 40);
</script>
"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "PwMcpFixture/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _record(self, path: str) -> None:
        cookie = self.headers.get("Cookie", "") or ""
        with _LOCK:
            _HITS[path] += 1
            if f"{COOKIE_NAME}={COOKIE_VALUE}" in cookie:
                _COOKIE_SEEN[path] += 1

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8",
              extra_headers: list[tuple[str, str]] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        self._record(path)

        if path == "/favicon.ico":
            # Serve empty 204 so the browser's auto favicon fetch is not a console
            # error (removes a confound from navigate-response measurements).
            self._send(HTTPStatus.NO_CONTENT, b"", "image/x-icon")
            return

        if path == "/":
            body = (
                "<h1>Playwright MCP Fixture</h1>"
                '<nav><a href="/classes">content classes</a>'
                '<a href="/gradient?n=10">gradient</a></nav>'
            )
            self._send(HTTPStatus.OK, html_page("Home", body))
            return

        # The content-class page: A semantic + B runtime + C non-semantic/hidden + D canvas.
        if path == "/classes":
            a = GT["A_semantic"]
            body = (
                f'<h1>{a["heading_name"]}</h1>'
                f'<a href="/page/alpha">{a["link_names"][0]}</a>'
                f'<a href="/page/beta">{a["link_names"][1]}</a>'
                f'<button>{a["button_name"]}</button>'
                f'<label>{a["input_name"]}<input type="text" name="q"></label>'
                # Class C: four hiding mechanisms (map which the snapshot drops)
                f'<div>{GT["C_nonsemantic_div_marker"]}</div>'
                f'<div aria-hidden="true">{GT["C_aria_hidden_marker"]}</div>'
                f'<div style="display:none">{GT["C_display_none_marker"]}</div>'
                f'<div style="visibility:hidden">{GT["C_visibility_hidden_marker"]}</div>'
                # Class D: canvas-drawn text
                f"{CANVAS_SCRIPT}"
                # Class B: runtime-injected accessible link (assembled at runtime)
                f"{RUNTIME_SCRIPT}"
            )
            self._send(HTTPStatus.OK, html_page("Content Classes", body))
            return

        # Complexity gradient: N interactive elements (each a distinct accessible name).
        if path == "/gradient":
            qs = parse_qs(parsed.query)
            try:
                n = max(0, min(5000, int(qs.get("n", ["10"])[0])))
            except ValueError:
                n = 10
            items = "\n".join(
                f'<button id="b{i}">Gradient Item {i} action label</button>'
                for i in range(n)
            )
            body = f"<h1>Gradient n={n}</h1><main>{items}</main>"
            self._send(HTTPStatus.OK, html_page(f"Gradient {n}", body))
            return

        # Isolation: set the session cookie.
        if path == "/set-cookie":
            body = "<h1>Cookie Set</h1><p>SESSION_COOKIE_HAS_BEEN_SET</p>"
            # Max-Age makes this a PERSISTENT cookie (not a session cookie) so it can
            # survive a persistent-profile browser restart — required to test the
            # persistence vs isolation contrast honestly.
            self._send(HTTPStatus.OK, html_page("Set Cookie", body),
                       extra_headers=[("Set-Cookie",
                                       f"{COOKIE_NAME}={COOKIE_VALUE}; Path=/; Max-Age=3600")])
            return

        # Isolation: report (in the PAGE and via server counter) whether the cookie came back.
        if path == "/check-cookie":
            cookie = self.headers.get("Cookie", "") or ""
            present = f"{COOKIE_NAME}={COOKIE_VALUE}" in cookie
            marker = "COOKIE_PRESENT_MARKER" if present else "COOKIE_ABSENT_MARKER"
            self._send(HTTPStatus.OK, html_page("Check Cookie", f"<h1>{marker}</h1>"))
            return

        if path.startswith("/page/") or path.startswith("/runtime/"):
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
    thread = threading.Thread(target=httpd.serve_forever, name="pwmcp-fixture", daemon=True)
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
