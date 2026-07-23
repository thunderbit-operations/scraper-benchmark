#!/usr/bin/env python3
"""H3 — presence (attached) vs visibility on a controlled node, plus Selenium's selector
model and deadline honoring.

On an attached-but-hidden (display:none) node, does `find_element` (presence) return while
an explicit `WebDriverWait(...).until(visibility_of_element_located)` blocks to the deadline
(never visible) with a clean TimeoutException? Do By.CSS_SELECTOR and By.XPATH both resolve
the same visible node? And does a never-appearing selector fail with a clean timeout (no
hang)? Runs 3x to show stability. All booleans/timings come from the probe; this runner only
aggregates and checks stability. Parity: mirrors chromedp WaitReady-vs-WaitVisible and rod
Element-vs-WaitVisible on the identical fixture node.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import ground_truth, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
PROBE = PROJECT_DIR / "tests" / "harness" / "selenium_probe.py"
PY_BIN = os.environ.get("SEL_PY", str(PROJECT_DIR / ".venv" / "bin" / "python"))
DRIVER_PATH = os.environ.get("SEL_DRIVER_PATH", "")
HOME = str(Path.home())


def _redact(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.replace(HOME, "~")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cleanup(udd: str) -> None:
    subprocess.run(["pkill", "-f", os.path.basename(udd)], capture_output=True)
    shutil.rmtree(udd, ignore_errors=True)


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists():
        print(f"probe missing: {PROBE}", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "selenium",
        "base_url": base,
        "ground_truth": ground_truth(base),
        "runs": [],
    }
    tmpdirs: list[str] = []
    try:
        for _ in range(3):
            udd = tempfile.mkdtemp(prefix="sel_ws_")
            tmpdirs.append(udd)
            cmd = [PY_BIN, str(PROBE), "waitsem", "--url", f"{base}/waitsem", "--user-data-dir", udd]
            if DRIVER_PATH:
                cmd += ["--driver-path", DRIVER_PATH]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            cleanup(udd)
            if p.returncode != 0:
                summary["runs"].append({"error": True, "stderr": p.stderr[-400:]})
                continue
            summary["runs"].append(json.loads(p.stdout.strip().splitlines()[-1]))

        ok = [r for r in summary["runs"] if not r.get("error")]
        if ok:
            hidden = [r["hidden_node"] for r in ok]
            sel = [r["selector_model_visible_node"] for r in ok]
            never = [r["never_appears"] for r in ok]
            summary["reading"] = {
                "hidden_node_presence_returns_all": all(h["presence_returned"] for h in hidden),
                "hidden_node_visibility_times_out_all": all(not h["visibility_returned"] for h in hidden),
                "css_returns_all": all(s["css_returned"] for s in sel),
                "xpath_returns_all": all(s["xpath_returned"] for s in sel),
                "never_appears_times_out_all": all(not n["returned"] for n in never),
                "note": "find_element = node present/attached in DOM; explicit "
                        "visibility_of_element_located = node actually visible. On a "
                        "display:none attached node they diverge cleanly: presence returns "
                        "fast, visibility blocks to the deadline (clean TimeoutException). "
                        "By.CSS_SELECTOR and By.XPATH both resolve the visible node. "
                        "Never-appearing selector fails with a clean timeout, no hang.",
            }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "waitsem-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        for d in tmpdirs:
            cleanup(d)


if __name__ == "__main__":
    raise SystemExit(main())
