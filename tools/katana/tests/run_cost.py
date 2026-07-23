#!/usr/bin/env python3
"""Katana mode-cost: standard vs headless wall-time distribution on the same fixture.

Timing-sensitive — run ALONE. Three isolated katana processes per mode; report
p50 and spread. Differences inside the noise band (overlapping ranges) are a tie.
This puts a price tag on headless's runtime-DOM coverage.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
KATANA = os.path.expanduser("~/go/bin/katana")
RUNS = 3


def _redact(obj: Any) -> Any:
    # Fold the $HOME prefix back to ~ so committed artifacts carry no absolute
    # user path and a re-run reproduces the exact bytes we published.
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


def timed(base_url: str, extra: list[str]) -> float:
    # -duc drops the startup GitHub version-check (a network round-trip added to
    # EVERY run) so the timing reflects crawl cost, not a shared network confound.
    # Applied identically to both modes; defaults otherwise unchanged (no -timeout
    # tuning) so the standard-mode 500-retry tail is reported honestly.
    t = time.monotonic()
    subprocess.run([KATANA, "-u", base_url, "-silent", "-nc", "-duc", "-d", "4"] + extra,
                   capture_output=True, text=True, timeout=240)
    return round(time.monotonic() - t, 2)


def summarize(xs: list[float]) -> dict[str, float]:
    return {"runs": len(xs), "min": min(xs), "p50": round(statistics.median(xs), 2),
            "max": max(xs), "mean": round(statistics.mean(xs), 2)}


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(KATANA):
        print("katana missing", file=sys.stderr)
        return 2
    server = start_fixture_server()
    base = server.base_url
    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "katana", "runs_per_mode": RUNS, "base_url": base,
    }
    try:
        std = [timed(base, []) for _ in range(RUNS)]
        hl = [timed(base, ["-hl"]) for _ in range(RUNS)]
        s_std, s_hl = summarize(std), summarize(hl)
        overlap = not (s_std["max"] < s_hl["min"] or s_hl["max"] < s_std["min"])
        ratio = round(s_hl["p50"] / s_std["p50"], 1) if s_std["p50"] > 0 else None
        result["standard"] = {"raw": std, **s_std}
        result["headless"] = {"raw": hl, **s_hl}
        result["verdict"] = {
            "ranges_overlap": overlap,
            "headless_over_standard_p50_ratio": ratio,
            "call": "tie" if overlap else f"headless ~{ratio}x standard",
        }
        write_json(RAW_DIR / "cost-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
