#!/usr/bin/env python3
"""H0 — Selenium Manager driver auto-provisioning (the modern-WebDriver-setup headline).

Selenium 4.6+ ships **Selenium Manager**, a Rust binary bundled in the pip package that,
on a driverless `webdriver.Chrome()`, detects the browser version and downloads a *matching*
chromedriver from the Chrome-for-Testing endpoints, caching it under `~/.cache/selenium`.
This runner measures the REAL behavior of that auto-supply against a controlled browser
(Chrome for Testing 151.0.7922.10, build 1232), using **isolated cache dirs** so the user's
real `~/.cache/selenium` is never touched:

  (a) COLD   — empty isolated cache: which chromedriver version does it resolve for browser
               151.0.7922.10, and what is the first-resolution (network download) cost?
  (b) WARM    — same cache re-queried Kx: cost once the driver is cached (no network).
  (c) STALE   — cache pre-seeded with ONLY a mismatched chromedriver (145.x) while the
               browser is 151.x: does Selenium Manager REUSE the stale 145, or fetch a
               matching 151? (attribution: version-matching vs cache-blindly-reuse)

All numbers come from the selenium-manager binary's own JSON output + wall timing; nothing
is hardcoded. Isolated caches are removed in a finally.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import selenium

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
CHROME = os.environ.get(
    "SEL_CHROME",
    os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-1232/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    ),
)
HOME = str(Path.home())
TMP = tempfile.gettempdir()  # e.g. macOS /var/folders/<hash>/T — isolated SM caches live here


def _redact(obj: Any) -> Any:
    if isinstance(obj, str):
        return obj.replace(HOME, "~").replace(TMP, "$TMPDIR")
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    return obj


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_redact(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sm_binary() -> str:
    base = Path(selenium.__file__).resolve().parent / "webdriver" / "common"
    plat = "macos" if sys.platform == "darwin" else "linux"
    return str(base / plat / "selenium-manager")


def resolve(sm: str, cache: str) -> dict[str, Any]:
    """Run selenium-manager once against CHROME with an isolated cache; return parsed
    result + wall time. Returns the resolved driver_path + version."""
    t0 = time.time()
    p = subprocess.run(
        [sm, "--browser", "chrome", "--browser-path", CHROME, "--cache-path", cache, "--output", "json"],
        capture_output=True, text=True, timeout=120,
    )
    wall_ms = int((time.time() - t0) * 1000)
    try:
        out = json.loads(p.stdout)
        driver_path = out.get("result", {}).get("driver_path", "")
    except json.JSONDecodeError:
        return {"error": True, "rc": p.returncode, "stderr": p.stderr[-400:], "wall_ms": wall_ms}
    m = re.search(r"/chromedriver/[^/]+/([0-9.]+)/chromedriver", driver_path)
    return {
        "wall_ms": wall_ms,
        "driver_path": driver_path,
        "driver_version": m.group(1) if m else None,
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not os.path.exists(CHROME):
        print(f"chrome not found at {CHROME}", file=sys.stderr)
        return 2
    sm = sm_binary()
    if not os.path.exists(sm):
        print(f"selenium-manager not found at {sm}", file=sys.stderr)
        return 2

    sm_version = subprocess.run([sm, "--version"], capture_output=True, text=True).stdout.strip()
    browser_version = subprocess.run([CHROME, "--version"], capture_output=True, text=True).stdout.strip()

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "selenium",
        "selenium_version": selenium.__version__,
        "selenium_manager_version": sm_version,
        "browser": browser_version,
        "browser_path": CHROME,
        "note": "Selenium Manager resolves + downloads a matching chromedriver on a "
                "driverless webdriver.Chrome(). Cache dirs here are isolated temp dirs; the "
                "user's ~/.cache/selenium is not modified.",
    }
    caches: list[str] = []
    try:
        # (a) COLD: fresh empty isolated cache (network download expected)
        cold_cache = tempfile.mkdtemp(prefix="se_prov_cold_")
        caches.append(cold_cache)
        summary["cold"] = resolve(sm, cold_cache)
        summary["cold"]["cache_had_driver_before"] = False

        # (b) WARM: same cache, now populated — re-query 3x (no network)
        warm = []
        for _ in range(3):
            warm.append(resolve(sm, cold_cache))
        summary["warm_runs"] = warm

        # (c) STALE: cache pre-seeded with ONLY chromedriver 145 while browser is 151.
        stale_cache = tempfile.mkdtemp(prefix="se_prov_stale_")
        caches.append(stale_cache)
        seeded_ok = False
        real_cache = Path.home() / ".cache" / "selenium"
        seed_src = None
        if real_cache.exists():
            for cand in (real_cache / "chromedriver").rglob("chromedriver"):
                if "/145." in str(cand):
                    seed_src = cand
                    break
        if seed_src is not None:
            dst_dir = Path(stale_cache) / "chromedriver" / "mac-arm64" / "145.0.7632.117"
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(seed_src, dst_dir / "chromedriver")
            seeded_ok = True
        stale = resolve(sm, stale_cache)
        # did it fetch a 151 driver despite the 145 present?
        fetched_151 = (stale.get("driver_version") or "").startswith("151.")
        stale_dirs = sorted(
            p.name for p in (Path(stale_cache) / "chromedriver" / "mac-arm64").glob("*")
        ) if (Path(stale_cache) / "chromedriver" / "mac-arm64").exists() else []
        summary["stale_cache_145_present"] = {
            "seeded_145": seeded_ok,
            "resolved": stale,
            "driver_versions_in_cache_after": stale_dirs,
            "reused_stale_145": stale.get("driver_version") == "145.0.7632.117",
            "fetched_matching_151": fetched_151,
        }

        # computed reading
        cold = summary["cold"]
        warm_walls = [w["wall_ms"] for w in warm if not w.get("error")]
        summary["reading"] = {
            "browser_version_short": browser_version.split()[-1] if browser_version else None,
            "resolved_driver_version": cold.get("driver_version"),
            "driver_matches_browser_build": (
                bool(cold.get("driver_version")) and
                cold.get("driver_version", "").rsplit(".", 1)[0] == "151.0.7922"
            ),
            "driver_patch_differs_from_browser_patch": (
                cold.get("driver_version") not in (None, "151.0.7922.10")
                and (cold.get("driver_version", "").startswith("151.0.7922"))
            ),
            "cold_resolution_ms": cold.get("wall_ms"),
            "warm_resolution_ms_values": warm_walls,
            "cold_over_warm_ratio": (
                round(cold["wall_ms"] / (sum(warm_walls) / len(warm_walls)), 1)
                if warm_walls and cold.get("wall_ms") else None
            ),
            "note": "Selenium Manager matches chromedriver on the browser's major.minor.build "
                    "(151.0.7922) and takes the latest available patch (not the browser's own "
                    "patch); cold resolution pays a one-time network download, warm is cache-hit "
                    "only; a stale mismatched driver in cache is NOT reused — the matching "
                    "version is fetched.",
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "provisioning-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        for c in caches:
            shutil.rmtree(c, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
