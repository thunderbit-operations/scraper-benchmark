#!/usr/bin/env python3
"""H5 — concurrency model cost: shared driver (N tabs) vs separate drivers (N sessions).

N=4 navigations, two ways: (shared) one driver/one chromedriver with N tabs, and (separate)
N independent drivers (N chromedrivers + N chromes). Reports wall-time distribution over >=3
runs and the peak chrome *browser*-process count AND the peak *chromedriver*-process count —
the Selenium-specific second axis: separate mode spends N driver processes on top of N
browsers. Compare to chromedp/rod (shared 1 proc / separate 4 procs, no separate driver
tier). RUN ALONE (timing-sensitive). Overlapping wall-time ranges => tie.
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
PROBE = PROJECT_DIR / "tests" / "harness" / "selenium_probe.py"
PY_BIN = os.environ.get("SEL_PY", str(PROJECT_DIR / ".venv" / "bin" / "python"))
DRIVER_PATH = os.environ.get("SEL_DRIVER_PATH", "")
N = 4
REPS = 3
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


def cleanup(key: str) -> None:
    subprocess.run(["pkill", "-f", os.path.basename(key)], capture_output=True)
    for i in range(N):
        subprocess.run(["pkill", "-f", os.path.basename(f"{key}-{i}")], capture_output=True)
    time.sleep(0.3)
    shutil.rmtree(key, ignore_errors=True)
    for i in range(N):
        shutil.rmtree(f"{key}-{i}", ignore_errors=True)


def run_mode(base: str, mode: str) -> list[dict[str, Any]]:
    rows = []
    for r in range(REPS):
        key = os.path.join(tempfile.gettempdir(), f"sel_conc_{mode}_{int(time.time()*1000)}_{r}")
        cmd = [PY_BIN, str(PROBE), "concurrency", "--url", f"{base}/classes?delay=0",
               "--mode", mode, "--n", str(N), "--dir-key", key]
        if DRIVER_PATH:
            cmd += ["--driver-path", DRIVER_PATH]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if p.returncode == 0:
            rows.append(json.loads(p.stdout.strip().splitlines()[-1]))
        else:
            rows.append({"error": True, "stderr": p.stderr[-400:]})
        cleanup(key)
    return rows


def agg(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if not r.get("error")]
    walls = [r["wall_ms"] for r in ok]
    bpeaks = [r["chrome_browser_procs_peak"] for r in ok]
    dpeaks = [r["chromedriver_procs_peak"] for r in ok]
    return {
        "runs": rows,
        "wall_ms": {
            "p50": statistics.median(walls) if walls else None,
            "min": min(walls) if walls else None,
            "max": max(walls) if walls else None,
        },
        "chrome_browser_procs_peak": {"min": min(bpeaks) if bpeaks else None, "max": max(bpeaks) if bpeaks else None},
        "chromedriver_procs_peak": {"min": min(dpeaks) if dpeaks else None, "max": max(dpeaks) if dpeaks else None},
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists():
        print(f"probe missing: {PROBE}", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    try:
        shared = agg(run_mode(base, "shared"))
        separate = agg(run_mode(base, "separate"))

        s_rng = (shared["wall_ms"]["min"], shared["wall_ms"]["max"])
        p_rng = (separate["wall_ms"]["min"], separate["wall_ms"]["max"])
        overlap = not (s_rng[1] < p_rng[0] or p_rng[1] < s_rng[0]) if None not in s_rng + p_rng else None

        summary = {
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "tool": "selenium",
            "base_url": base,
            "n_concurrent": N,
            "reps": REPS,
            "shared_one_driver": shared,
            "separate_drivers": separate,
            "verdict": {
                "wall_ranges_overlap": overlap,
                "shared_browser_peak": shared["chrome_browser_procs_peak"],
                "shared_driver_peak": shared["chromedriver_procs_peak"],
                "separate_browser_peak": separate["chrome_browser_procs_peak"],
                "separate_driver_peak": separate["chromedriver_procs_peak"],
                "note": "Shared: one driver + one chrome, N tabs. Separate: N chromedrivers + N "
                        "chromes — the Selenium-specific double cost (a driver process PER "
                        "browser). Wall-time is a tie if ranges overlap. Mirror of the "
                        "chromedp/rod shared-vs-separate test, plus the extra driver-process tier.",
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
