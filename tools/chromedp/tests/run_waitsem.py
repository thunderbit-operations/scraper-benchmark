#!/usr/bin/env python3
"""H2 — WaitReady vs WaitVisible semantics on a controlled node + selector semantics.

On an attached-but-hidden (display:none) node, does WaitReady return (attachment is
enough) while WaitVisible blocks to the context deadline (never visible)? And does the
default selector query behave like ByID/ByQuery on a visible node (the #440 trap)?
Runs 3x to show the result is stable. All booleans/timings come from the probe; this
runner only aggregates and checks stability.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import ground_truth, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
PROBE = PROJECT_DIR / "tests" / "harness" / "chromedp_probe"
CHROME = os.environ.get(
    "CHROMEDP_CHROME",
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-1232/"
        "chrome-headless-shell-mac-arm64/chrome-headless-shell"
    ),
)


def _redact(obj: Any) -> Any:
    home = str(Path.home())
    if isinstance(obj, str):
        return obj.replace(home, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists() or not os.path.exists(CHROME):
        print("probe binary or chrome missing", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "chromedp",
        "base_url": base,
        "ground_truth": ground_truth(base),
        "runs": [],
    }
    tmpdirs: list[str] = []
    try:
        for _ in range(3):
            udd = tempfile.mkdtemp(prefix="chromedp_ws_")
            tmpdirs.append(udd)
            cmd = [str(PROBE), "waitsem", "--url", f"{base}/waitsem", "--chrome", CHROME, "--user-data-dir", udd]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if p.returncode != 0:
                summary["runs"].append({"error": True, "stderr": p.stderr[-400:]})
                continue
            summary["runs"].append(json.loads(p.stdout.strip().splitlines()[-1]))

        # Stability + computed reading (from the measured runs, not hardcoded).
        ok = [r for r in summary["runs"] if not r.get("error")]
        if ok:
            hidden = [r["hidden_node"] for r in ok]
            sel = [r["selector_semantics_visible_node"] for r in ok]
            summary["reading"] = {
                "hidden_node_waitready_returns_all": all(h["waitready_returned"] for h in hidden),
                "hidden_node_waitvisible_times_out_all": all(not h["waitvisible_returned"] for h in hidden),
                "waitvisible_deadline_error_all": all(h["waitvisible_err"] == "context deadline exceeded" for h in hidden),
                "default_query_returns_all": all(s["default_query_returned"] for s in sel),
                "byid_returns_all": all(s["byid_returned"] for s in sel),
                "byquery_returns_all": all(s["byquery_returned"] for s in sel),
                "selector_440_hang_reproduced": any(
                    (not s["default_query_returned"]) and s["byid_returned"] for s in sel
                ),
                "note": "WaitReady = node attached to DOM; WaitVisible = node actually visible. "
                        "On a display:none attached node they diverge cleanly. The #440 "
                        "default-query hang is reported as reproduced only if measured.",
            }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "waitsem-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        for d in tmpdirs:
            subprocess.run(["pkill", "-f", d], capture_output=True)
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
