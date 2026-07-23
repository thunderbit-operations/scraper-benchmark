#!/usr/bin/env python3
"""Tool-surface enumeration (default vs --caps=vision) + robustness for Playwright MCP.

Confirms, by reading tools/list (never hardcoding), how many tools the server exposes
by default and which coordinate/vision tools --caps=vision adds. Robustness: navigate
to a 500 and a 404 route and confirm a snapshot still returns without crashing.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server  # noqa: E402
from mcp_client import MCPClient, result_text, _redact  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tool_names(args: list[str]) -> list[str]:
    with MCPClient(args) as c:
        return sorted(t["name"] for t in c.list_tools())


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    server = start_fixture_server()
    outdir = tempfile.mkdtemp(prefix="pwmcp-tools-")
    base_args = ["--headless", "--isolated", "--browser", "chromium", "--output-dir", outdir]
    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "playwright-mcp",
    }
    try:
        default_tools = tool_names(base_args)
        vision_tools = tool_names(base_args + ["--caps", "vision"])
        added_by_vision = sorted(set(vision_tools) - set(default_tools))
        result["tool_surface"] = {
            "default_tool_count": len(default_tools),
            "vision_tool_count": len(vision_tools),
            "tools_added_by_caps_vision": added_by_vision,
            "default_tools": default_tools,
        }

        # Robustness: 500 + 404 routes still yield a snapshot, no crash.
        robustness = {}
        with MCPClient(base_args) as c:
            for label, path in [("http_500", "/failure/500"), ("http_404", "/does-not-exist-404")]:
                nav = c.call_tool("browser_navigate", {"url": server.base_url + path}, timeout=90)
                snap = result_text(c.call_tool("browser_snapshot", {}, timeout=90))
                robustness[label] = {
                    "navigate_ok": "Error" not in result_text(nav)[:40],
                    "snapshot_returned_nonempty": len(snap) > 0,
                    "snapshot_bytes": len(snap.encode("utf-8")),
                }
        result["robustness"] = robustness
        result["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "tools-robustness-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        import shutil
        shutil.rmtree(outdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
