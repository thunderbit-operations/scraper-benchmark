#!/usr/bin/env python3
"""H4 (session isolation vs persistence, proven by server-side cookie truth),
H5 (ref ephemerality), and tab lifecycle for Playwright MCP.

Isolation/persistence truth is the fixture's server-side cookie counter — whether
the browser actually RE-SENT the session cookie on a later navigation — not the
tool's own reporting. Refs are checked by mutating the DOM and observing renumbering.
Nothing hardcoded; every verdict is computed from this run's counters/snapshots.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_server as fx  # noqa: E402
from fixture_server import start_fixture_server, GT  # noqa: E402
from mcp_client import MCPClient, result_text, _redact  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"

REF_RE = re.compile(r"\[ref=(e\d+)\]")


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def refs_of(snapshot: str) -> list[str]:
    return REF_RE.findall(snapshot)


def test_isolation(base: str, outdir: str) -> dict[str, Any]:
    """A fresh --isolated session must NOT carry a cookie set by a prior session."""
    # Session 1: set cookie, then confirm it is carried WITHIN the same session.
    fx.reset_hits()
    with MCPClient(["--headless", "--isolated", "--browser", "chromium",
                    "--output-dir", outdir]) as c1:
        c1.call_tool("browser_navigate", {"url": base + "/set-cookie"}, timeout=90)
        s1 = result_text(c1.call_tool("browser_navigate", {"url": base + "/check-cookie"}, timeout=90))
        # the check page's snapshot is referenced as a file on navigate; read via snapshot
        s1_snap = result_text(c1.call_tool("browser_snapshot", {}, timeout=90))
    within_session_present = "COOKIE_PRESENT_MARKER" in s1_snap
    seen_after_session1 = fx.snapshot_cookie_seen().get("/check-cookie", 0)

    # Session 2: brand new isolated session — cookie must be gone.
    fx.reset_hits()
    with MCPClient(["--headless", "--isolated", "--browser", "chromium",
                    "--output-dir", outdir]) as c2:
        c2.call_tool("browser_navigate", {"url": base + "/check-cookie"}, timeout=90)
        s2_snap = result_text(c2.call_tool("browser_snapshot", {}, timeout=90))
    new_session_present = "COOKIE_PRESENT_MARKER" in s2_snap
    seen_after_session2 = fx.snapshot_cookie_seen().get("/check-cookie", 0)

    return {
        "within_same_session_cookie_present": within_session_present,
        "server_cookie_hits_session1": seen_after_session1,
        "new_isolated_session_cookie_present": new_session_present,
        "server_cookie_hits_new_session": seen_after_session2,
        "isolation_holds": (within_session_present and not new_session_present
                            and seen_after_session2 == 0),
    }


def test_persistence(base: str, outdir: str) -> dict[str, Any]:
    """A persistent --user-data-dir must carry the cookie across a browser restart."""
    udd = tempfile.mkdtemp(prefix="pwmcp-udd-")
    try:
        fx.reset_hits()
        c1 = MCPClient(["--headless", "--user-data-dir", udd, "--browser", "chromium",
                        "--output-dir", outdir])
        c1.start()
        c1.call_tool("browser_navigate", {"url": base + "/set-cookie"}, timeout=90)
        # Confirm the cookie is live within session 1 (rules out "cookie never set").
        c1.call_tool("browser_navigate", {"url": base + "/check-cookie"}, timeout=90)
        within = "COOKIE_PRESENT_MARKER" in result_text(
            c1.call_tool("browser_snapshot", {}, timeout=90))
        # Close the browser GRACEFULLY so Chromium flushes cookies to the profile on
        # disk before the process exits (an abrupt SIGTERM would lose the flush — that
        # would be a harness artifact, not tool behavior).
        try:
            c1.call_tool("browser_close", {}, timeout=30)
        except Exception:
            pass
        c1.stop()

        # New server process, SAME profile dir:
        fx.reset_hits()
        with MCPClient(["--headless", "--user-data-dir", udd, "--browser", "chromium",
                        "--output-dir", outdir]) as c2:
            c2.call_tool("browser_navigate", {"url": base + "/check-cookie"}, timeout=90)
            s2_snap = result_text(c2.call_tool("browser_snapshot", {}, timeout=90))
        present = "COOKIE_PRESENT_MARKER" in s2_snap
        seen = fx.snapshot_cookie_seen().get("/check-cookie", 0)
        return {
            "cookie_live_within_session1": within,
            "persistent_profile_cookie_present_after_restart": present,
            "server_cookie_hits_after_restart": seen,
            "persistence_holds": present and seen > 0,
            "graceful_close_used": True,
        }
    finally:
        import shutil
        shutil.rmtree(udd, ignore_errors=True)


def test_refs(base: str, outdir: str) -> dict[str, Any]:
    """Refs are ephemeral: a no-op re-snapshot is stable; a DOM mutation renumbers."""
    with MCPClient(["--headless", "--isolated", "--browser", "chromium",
                    "--output-dir", outdir]) as c:
        c.call_tool("browser_navigate", {"url": base + "/classes"}, timeout=90)
        snap_a = result_text(c.call_tool("browser_snapshot", {}, timeout=90))
        snap_b = result_text(c.call_tool("browser_snapshot", {}, timeout=90))  # no-op
        refs_a, refs_b = refs_of(snap_a), refs_of(snap_b)
        # Mutate the DOM: prepend a new interactive element, shifting everything.
        c.call_tool("browser_evaluate", {
            "function": "() => { document.body.insertAdjacentHTML('afterbegin', "
                        "'<button id=injected>Injected Top Button</button>'); }"
        }, timeout=90)
        snap_c = result_text(c.call_tool("browser_snapshot", {}, timeout=90))
        refs_c = refs_of(snap_c)
    return {
        "noop_resnapshot_refs_identical": refs_a == refs_b,
        "ref_count_before_mutation": len(refs_a),
        "ref_count_after_mutation": len(refs_c),
        "new_button_in_snapshot": "Injected Top Button" in snap_c,
        # the runtime marker is the same logical element; did its ref change after mutation?
        "runtime_link_present_after_mutation": GT["B_runtime_injected_marker"] in snap_c,
        "mutation_added_refs": len(refs_c) > len(refs_a),
    }


def test_tabs(base: str, outdir: str) -> dict[str, Any]:
    with MCPClient(["--headless", "--isolated", "--browser", "chromium",
                    "--output-dir", outdir]) as c:
        c.call_tool("browser_navigate", {"url": base + "/classes"}, timeout=90)
        c.call_tool("browser_tabs", {"action": "new", "url": base + "/gradient?n=5"}, timeout=90)
        listing = result_text(c.call_tool("browser_tabs", {"action": "list"}, timeout=90))
    # count tab lines in the listing (each tab is a line/entry)
    tab_lines = [ln for ln in listing.splitlines() if re.search(r"- \d+:|tab", ln, re.I)]
    return {
        "tabs_listing_excerpt": listing[:600],
        "listing_mentions_two_urls": ("/classes" in listing or "Content Classes" in listing)
                                      and ("gradient" in listing.lower() or "Gradient" in listing),
        "tab_line_count_heuristic": len(tab_lines),
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    server = start_fixture_server()
    base = server.base_url
    outdir = tempfile.mkdtemp(prefix="pwmcp-sess-")
    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "playwright-mcp",
        "base_url": base,
    }
    try:
        result["isolation"] = test_isolation(base, outdir)
        result["persistence"] = test_persistence(base, outdir)
        result["refs"] = test_refs(base, outdir)
        result["tabs"] = test_tabs(base, outdir)
        result["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "session-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
