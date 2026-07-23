#!/usr/bin/env python3
"""H4 — cold-start cost distribution + the Selenium Manager per-call tax.

Each measurement is a FRESH probe process (genuinely cold: instantiate webdriver.Chrome ->
navigate -> first execute_script), so no warm session is reused. Two configs, INTERLEAVED so
drift hits both:

  sm   -> webdriver.Chrome() with Service() (no path): Selenium Manager runs EVERY call to
          resolve the driver (even when cached, it spawns the SM binary once per session).
  path -> webdriver.Chrome() with an explicit Service(driver_path): SKIPS Selenium Manager.

The SM-vs-path delta is the per-call Selenium Manager tax (with the driver already cached;
the one-time network download is measured separately in run_provisioning.py). chromedriver
launch + chrome start dominate both. Reports p50 + min/max/mean over N runs; compare to
chromedp's 102 ms and rod's 119 ms p50 on the identical host/Chrome build. RUN ALONE
(timing-sensitive).
"""
from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
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
N_RUNS = int(os.environ.get("SEL_COLDSTART_RUNS", "5"))
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


def one_coldstart(base: str, use_sm: bool, variant: str = "full") -> int | None:
    udd = tempfile.mkdtemp(prefix="sel_cold_")
    try:
        cmd = [PY_BIN, str(PROBE), "coldstart", "--url", f"{base}/classes?delay=0",
               "--user-data-dir", udd, "--variant", variant]
        if not use_sm and DRIVER_PATH:
            cmd += ["--driver-path", DRIVER_PATH]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if p.returncode == 0:
            return int(json.loads(p.stdout.strip().splitlines()[-1])["elapsed_ms"])
        return None
    finally:
        subprocess.run(["pkill", "-f", os.path.basename(udd)], capture_output=True)
        shutil.rmtree(udd, ignore_errors=True)


def dist(samples: list[int]) -> dict[str, Any]:
    return {
        "p50": statistics.median(samples) if samples else None,
        "min": min(samples) if samples else None,
        "max": max(samples) if samples else None,
        "mean": round(statistics.fmean(samples), 1) if samples else None,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists():
        print(f"probe missing: {PROBE}", file=sys.stderr)
        return 2
    if not DRIVER_PATH:
        print("SEL_DRIVER_PATH not set; the 'path' (skip-SM) config needs it", file=sys.stderr)

    server = start_fixture_server()
    base = server.base_url
    try:
        # pre-warm one throwaway so any first-launch OS cost is not in the samples
        _ = one_coldstart(base, use_sm=False if DRIVER_PATH else True)

        sm_samples: list[int] = []
        path_samples: list[int] = []
        shell_samples: list[int] = []
        for _ in range(N_RUNS):
            v_sm = one_coldstart(base, use_sm=True, variant="full")
            if v_sm is not None:
                sm_samples.append(v_sm)
            if DRIVER_PATH:
                v_p = one_coldstart(base, use_sm=False, variant="full")
                if v_p is not None:
                    path_samples.append(v_p)
                # binary-matched variant: chrome-headless-shell (same binary chromedp/rod
                # used), explicit driver, to decompose "chromedriver/W3C overhead" from
                # "heavier full-Chrome+new-headless binary".
                v_sh = one_coldstart(base, use_sm=False, variant="shell")
                if v_sh is not None:
                    shell_samples.append(v_sh)

        sm_d, path_d = dist(sm_samples), dist(path_samples)
        shell_d = dist(shell_samples)
        tax = (sm_d["p50"] - path_d["p50"]) if (sm_d["p50"] is not None and path_d["p50"] is not None) else None
        sm_rng = (sm_d["min"], sm_d["max"])
        path_rng = (path_d["min"], path_d["max"])
        tax_overlap = (
            not (sm_rng[1] < path_rng[0] or path_rng[1] < sm_rng[0])
            if None not in sm_rng + path_rng else None
        )

        summary: dict[str, Any] = {
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "tool": "selenium",
            "base_url": base,
            "n_runs": N_RUNS,
            "cold_start_ms_samples_selenium_manager": sm_samples,
            "cold_start_ms_selenium_manager": sm_d,
            "cold_start_ms_samples_explicit_driver": path_samples,
            "cold_start_ms_explicit_driver": path_d,
            "cold_start_ms_samples_headless_shell": shell_samples,
            "cold_start_ms_headless_shell": shell_d,
            "selenium_manager_per_call_tax_ms_p50": tax,
            "selenium_manager_tax_ranges_overlap": tax_overlap,
            "full_chrome_over_headless_shell_p50_delta_ms": (
                (path_d["p50"] - shell_d["p50"])
                if (path_d["p50"] is not None and shell_d["p50"] is not None) else None
            ),
            "note": "cold start = fresh process: instantiate webdriver.Chrome -> navigate -> "
                    "first execute_script. 'selenium_manager' runs SM every call (driver cached; "
                    "SM still spawns to resolve); 'explicit_driver' passes Service(path), skips "
                    "SM, drives full Chrome + --headless=new (the pack default, needed for the "
                    "process-truth udd); 'headless_shell' drives the SAME chrome-headless-shell "
                    "binary chromedp/rod used (explicit driver, no custom udd) to isolate the "
                    "binary effect from the chromedriver/W3C overhead. tax = SM.p50 - path.p50. "
                    "The one-time SM network DOWNLOAD is in run_provisioning.py. Compare to "
                    "chromedp 102 ms and rod 119 ms p50 on the same host/Chrome build.",
            "runtime_dependency": {
                "requires_external_chrome": True,
                "requires_chromedriver": True,
                "note": "Selenium needs BOTH an external Chrome AND a chromedriver binary; "
                        "Selenium Manager auto-supplies chromedriver, but the browser must exist.",
            },
            "run_completed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(RAW_DIR / "coldstart-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
