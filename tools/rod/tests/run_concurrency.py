#!/usr/bin/env python3
"""H5 — concurrency model cost: shared browser (N pages/tabs) vs separate browsers.

N=4 navigations, done two ways: (shared) one browser with N pages, and (separate) N
independent browsers/launchers. Reports wall-time distribution over >=3 runs and the peak
Chrome *browser*-process count for each (leakless guardian and Chrome helpers excluded).
Compare to chromedp (shared 1 proc / separate 4 procs). RUN ALONE (timing-sensitive).
Overlapping wall-time ranges => tie (no faster/slower claim).
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server  # noqa: E402

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
N = 4
REPS = 3


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


def cleanup(key: str) -> None:
    subprocess.run(["pkill", "-f", key], capture_output=True)
    time.sleep(0.3)
    shutil.rmtree(key, ignore_errors=True)
    for i in range(N):
        shutil.rmtree(f"{key}-{i}", ignore_errors=True)


def run_mode(base: str, mode: str) -> list[dict[str, Any]]:
    rows = []
    for r in range(REPS):
        key = os.path.join(tempfile.gettempdir(), f"rod_conc_{mode}_{int(time.time()*1000)}_{r}")
        cmd = [str(PROBE), "concurrency", "--url", f"{base}/classes?delay=0", "--chrome", CHROME,
               "--mode", mode, "--n", str(N), "--dir-key", key]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if p.returncode == 0:
            rows.append(json.loads(p.stdout.strip().splitlines()[-1]))
        else:
            rows.append({"error": True, "stderr": p.stderr[-400:]})
        cleanup(key)
    return rows


def agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if not r.get("error")]
    walls = [r["wall_ms"] for r in ok]
    peaks = [r["chrome_procs_peak"] for r in ok]
    return {
        "runs": rows,
        "wall_ms": {
            "p50": statistics.median(walls) if walls else None,
            "min": min(walls) if walls else None,
            "max": max(walls) if walls else None,
        },
        "chrome_procs_peak": {"min": min(peaks) if peaks else None, "max": max(peaks) if peaks else None},
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists() or not os.path.exists(CHROME):
        print("probe binary or chrome missing", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    try:
        shared = agg(run_mode(base, "shared"))
        separate = agg(run_mode(base, "separate"))

        # tie logic: overlapping wall-time ranges => tie
        s_rng = (shared["wall_ms"]["min"], shared["wall_ms"]["max"])
        p_rng = (separate["wall_ms"]["min"], separate["wall_ms"]["max"])
        overlap = not (s_rng[1] < p_rng[0] or p_rng[1] < s_rng[0]) if None not in s_rng + p_rng else None

        summary = {
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "tool": "rod",
            "base_url": base,
            "n_concurrent": N,
            "reps": REPS,
            "shared_one_browser": shared,
            "separate_browsers": separate,
            "verdict": {
                "wall_ranges_overlap": overlap,
                "shared_peak_procs": shared["chrome_procs_peak"],
                "separate_peak_procs": separate["chrome_procs_peak"],
                "note": "Shared-browser pages run N navigations in ONE Chrome process; separate "
                        "mode spends N browser processes. Wall-time is a tie if ranges overlap. "
                        "Mirror of the chromedp shared-vs-separate test.",
            },
            "run_completed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(RAW_DIR / "concurrency-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
