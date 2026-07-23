#!/usr/bin/env python3
"""H4 — cold-start cost distribution.

Each measurement is a FRESH probe process (genuinely cold: allocator -> context ->
navigate -> first eval), so no warm browser is reused. Reports p50 + min/max over N
runs. RUN ALONE (timing-sensitive). Also records that chromedp needs an external
Chrome binary at runtime (the "no dependencies" claim is about the Go module).
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
PROBE = PROJECT_DIR / "tests" / "harness" / "chromedp_probe"
CHROME = os.environ.get(
    "CHROMEDP_CHROME",
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium_headless_shell-1232/"
        "chrome-headless-shell-mac-arm64/chrome-headless-shell"
    ),
)
N_RUNS = int(os.environ.get("CHROMEDP_COLDSTART_RUNS", "5"))


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
    samples: list[int] = []
    tmpdirs: list[str] = []
    try:
        for i in range(N_RUNS):
            udd = tempfile.mkdtemp(prefix="chromedp_cold_")
            tmpdirs.append(udd)
            cmd = [str(PROBE), "coldstart", "--url", f"{base}/classes?delay=0",
                   "--chrome", CHROME, "--user-data-dir", udd]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if p.returncode == 0:
                d = json.loads(p.stdout.strip().splitlines()[-1])
                samples.append(int(d["elapsed_ms"]))

        summary: dict[str, Any] = {
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "tool": "chromedp",
            "base_url": base,
            "chrome": CHROME,
            "n_runs": N_RUNS,
            "cold_start_ms_samples": samples,
            "cold_start_ms": {
                "p50": statistics.median(samples) if samples else None,
                "min": min(samples) if samples else None,
                "max": max(samples) if samples else None,
                "mean": round(statistics.fmean(samples), 1) if samples else None,
            },
            "runtime_dependency": {
                "requires_external_chrome": True,
                "note": "chromedp is pure Go (no cgo) at the module level, but requires a "
                        "Chrome/Chromium executable at runtime (supplied here via ExecPath). "
                        "The measurement fails immediately with no Chrome present.",
            },
            "run_completed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(RAW_DIR / "coldstart-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()
        for d in tmpdirs:
            subprocess.run(["pkill", "-f", d], capture_output=True)
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
