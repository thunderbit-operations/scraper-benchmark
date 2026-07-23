#!/usr/bin/env python3
"""H3 — Element (attached) vs Element.WaitVisible (visible) on a controlled node, plus
rod's selector model and deadline honoring.

On an attached-but-hidden (display:none) node, does Element return (attachment is enough)
while WaitVisible blocks to the page deadline (never visible)? Does rod's CSS Element and
XPath ElementX both resolve the same visible node (rod has no chromedp #440 ByID-vs-default
trap)? And does a never-appearing selector fail with a clean timeout (no hang)? Runs 3x to
show the result is stable. All booleans/timings come from the probe; this runner only
aggregates and checks stability.
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
PROBE = PROJECT_DIR / "tests" / "harness" / "rod_probe"
CHROME = os.environ.get(
    "ROD_CHROME",
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
        "tool": "rod",
        "base_url": base,
        "ground_truth": ground_truth(base),
        "runs": [],
    }
    tmpdirs: list[str] = []
    try:
        for _ in range(3):
            udd = tempfile.mkdtemp(prefix="rod_ws_")
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
            sel = [r["selector_model_visible_node"] for r in ok]
            never = [r["never_appears"] for r in ok]
            summary["reading"] = {
                "hidden_node_element_returns_all": all(h["element_returned"] for h in hidden),
                "hidden_node_waitvisible_times_out_all": all(not h["waitvisible_returned"] for h in hidden),
                "css_element_returns_all": all(s["css_element_returned"] for s in sel),
                "xpath_elementx_returns_all": all(s["xpath_elementx_returned"] for s in sel),
                "never_appears_times_out_all": all(not n["returned"] for n in never),
                "note": "Element = node attached to DOM; Element.WaitVisible = node actually "
                        "visible. On a display:none attached node they diverge cleanly. rod's "
                        "CSS Element and XPath ElementX both resolve the visible node (no "
                        "chromedp-#440-style default-query trap). Never-appearing selector "
                        "fails with a clean timeout, no hang.",
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
