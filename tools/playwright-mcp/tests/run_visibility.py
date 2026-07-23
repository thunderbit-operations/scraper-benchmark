#!/usr/bin/env python3
"""H2: per-content-class visibility of the Playwright MCP accessibility snapshot.

Navigates the /classes fixture and computes, against pre-registered ground-truth
marker strings, which content the browser_snapshot surfaces vs drops. The boundary
map (which HIDING MECHANISM is dropped) is the finding — not a blanket claim.

Cross-series contrast: class B is a link INJECTED BY JAVASCRIPT AT RUNTIME with no
literal in the served bytes — the same class a static crawler (katana standard mode)
misses. A live accessibility snapshot surfacing it is the concrete contrast.

Nothing hardcoded: presence is computed by substring test of each ground-truth
marker against this run's snapshot text.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server, GT  # noqa: E402
from mcp_client import MCPClient, result_text, _redact  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    server = start_fixture_server()
    outdir = tempfile.mkdtemp(prefix="pwmcp-vis-")

    # marker -> (class, hiding mechanism, expected-per-consensus)
    checks = [
        ("A_heading", GT["A_semantic"]["heading_name"], "A_semantic", "heading role", "present"),
        ("A_link_alpha", GT["A_semantic"]["link_names"][0], "A_semantic", "link role", "present"),
        ("A_button", GT["A_semantic"]["button_name"], "A_semantic", "button role", "present"),
        ("A_input", GT["A_semantic"]["input_name"], "A_semantic", "textbox role", "present"),
        ("B_runtime_injected", GT["B_runtime_injected_marker"], "B_runtime", "JS-injected at runtime, no literal in bytes", "present (live tree)"),
        ("C_nonsemantic_div", GT["C_nonsemantic_div_marker"], "C_hidden", "bare <div>, no role, visible", "consensus: 'only semantic'"),
        ("C_aria_hidden", GT["C_aria_hidden_marker"], "C_hidden", "aria-hidden=true", "consensus: omitted"),
        ("C_display_none", GT["C_display_none_marker"], "C_hidden", "display:none", "hidden"),
        ("C_visibility_hidden", GT["C_visibility_hidden_marker"], "C_hidden", "visibility:hidden", "hidden"),
        ("D_canvas_text", GT["D_canvas_marker"], "D_canvas", "canvas fillText, pixels only", "invisible to a11y"),
    ]

    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "playwright-mcp",
        "base_url": server.base_url,
        "checks": [],
    }
    try:
        with MCPClient(["--headless", "--isolated", "--browser", "chromium",
                        "--output-dir", outdir]) as c:
            result["server_info"] = c.server_info.get("serverInfo", {})
            c.call_tool("browser_navigate", {"url": server.base_url + "/classes"}, timeout=90)
            snap = result_text(c.call_tool("browser_snapshot", {}, timeout=90))
            result["snapshot_text"] = snap

            for key, marker, klass, mechanism, note in checks:
                present = marker in snap
                result["checks"].append({
                    "key": key, "content_class": klass, "hiding_mechanism": mechanism,
                    "consensus_note": note, "present_in_snapshot": present,
                })

            def present(k: str) -> bool:
                return next(x["present_in_snapshot"] for x in result["checks"] if x["key"] == k)

            # Computed boundary map: which mechanisms the snapshot DROPS.
            dropped = [x["hiding_mechanism"] for x in result["checks"] if not x["present_in_snapshot"]]
            surfaced = [x["hiding_mechanism"] for x in result["checks"] if x["present_in_snapshot"]]
            result["boundary_map"] = {
                "surfaced_mechanisms": surfaced,
                "dropped_mechanisms": dropped,
                # Adversarial checks against the SERP consensus:
                "aria_hidden_surfaced_contradicts_consensus": present("C_aria_hidden"),
                "nonsemantic_div_surfaced_contradicts_only_semantic": present("C_nonsemantic_div"),
                "runtime_injected_surfaced_by_live_tree": present("B_runtime_injected"),
                "canvas_text_invisible": not present("D_canvas_text"),
                "display_none_dropped": not present("C_display_none"),
                "visibility_hidden_dropped": not present("C_visibility_hidden"),
            }
            result["cross_series_note"] = (
                "class B (runtime-injected, no literal in bytes) is surfaced here by the "
                "live accessibility snapshot; the same content class is missed by a static "
                "crawl (katana standard mode class C). Live-DOM read vs static parse."
            )
            result["run_completed_at"] = datetime.now(timezone.utc).isoformat()
            write_json(RAW_DIR / "visibility-summary.json", result)
            print(json.dumps({k: v for k, v in result.items() if k != "snapshot_text"},
                             indent=2, ensure_ascii=False))
            return 0
    finally:
        server.stop()
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
