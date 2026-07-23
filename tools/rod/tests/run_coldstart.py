#!/usr/bin/env python3
"""H4 — cold-start cost distribution (incl. the leakless tax).

Each measurement is a FRESH probe process (genuinely cold: launcher -> connect -> page ->
navigate -> first eval), so no warm browser is reused. leakless is ON (rod's default), so
this cold-start INCLUDES the leakless-guardian spawn tax — the honest number a rod user
pays. The leakless guardian binary is pre-warmed (downloaded) once before the timed runs so
a one-time download does not pollute the distribution. Reports p50 + min/max over N runs;
compare to chromedp's 102 ms p50 on the identical host/Chrome. Also records that rod needs
an external Chrome at runtime (its .Bin(path) disables auto-download; the "pure Go" claim is
about the module). RUN ALONE (timing-sensitive).
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
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
N_RUNS = int(os.environ.get("ROD_COLDSTART_RUNS", "5"))


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


def one_coldstart(base: str, leakless: bool = True) -> int | None:
    udd = tempfile.mkdtemp(prefix="rod_cold_")
    try:
        cmd = [str(PROBE), "coldstart", "--url", f"{base}/classes?delay=0",
               "--chrome", CHROME, "--user-data-dir", udd,
               f"--leakless={'true' if leakless else 'false'}"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if p.returncode == 0:
            return int(json.loads(p.stdout.strip().splitlines()[-1])["elapsed_ms"])
        return None
    finally:
        subprocess.run(["pkill", "-f", udd], capture_output=True)
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
    if not PROBE.exists() or not os.path.exists(CHROME):
        print("probe binary or chrome missing", file=sys.stderr)
        return 2

    server = start_fixture_server()
    base = server.base_url
    try:
        # pre-warm: one throwaway cold start so the leakless guardian download (if any) is
        # not part of the measured samples.
        _ = one_coldstart(base, True)

        # leakless ON (rod default) and OFF, INTERLEAVED so drift hits both equally — this
        # isolates the leakless-guardian spawn tax instead of guessing at it.
        on_samples: list[int] = []
        off_samples: list[int] = []
        for _ in range(N_RUNS):
            v_on = one_coldstart(base, True)
            if v_on is not None:
                on_samples.append(v_on)
            v_off = one_coldstart(base, False)
            if v_off is not None:
                off_samples.append(v_off)

        on_d, off_d = dist(on_samples), dist(off_samples)
        tax = (on_d["p50"] - off_d["p50"]) if (on_d["p50"] is not None and off_d["p50"] is not None) else None
        on_rng = (on_d["min"], on_d["max"])
        off_rng = (off_d["min"], off_d["max"])
        tax_ranges_overlap = (
            not (on_rng[1] < off_rng[0] or off_rng[1] < on_rng[0])
            if None not in on_rng + off_rng else None
        )

        summary: dict[str, Any] = {
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "tool": "rod",
            "base_url": base,
            "chrome": CHROME,
            "n_runs": N_RUNS,
            "leakless": True,
            "cold_start_ms_samples": on_samples,          # leakless ON = rod default
            "cold_start_ms": on_d,
            "cold_start_leakless_off_samples": off_samples,
            "cold_start_leakless_off_ms": off_d,
            "leakless_tax_ms_p50": tax,
            "leakless_tax_ranges_overlap": tax_ranges_overlap,
            "note": "cold_start_ms is rod's DEFAULT (leakless ON), incl. the guardian spawn "
                    "tax. leakless_off is the same cycle without the guardian, to isolate the "
                    "tax (tax = on.p50 - off.p50; ranges overlap => tax within noise). Guardian "
                    "binary pre-warmed. Compare to chromedp 102 ms p50 on the same host/Chrome.",
            "runtime_dependency": {
                "requires_external_chrome": True,
                "note": "rod is pure Go at the module level, but drives a Chrome/Chromium binary "
                        "at runtime (supplied here via launcher.Bin, which disables auto-download). "
                        "With no Chrome and auto-download disabled, launch fails.",
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
