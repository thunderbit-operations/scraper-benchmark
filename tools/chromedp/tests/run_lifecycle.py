#!/usr/bin/env python3
"""H3 — context lifecycle / Chrome process reap (process-truth).

Two measured behaviors, each repeated 3x:
  (a) cancel path: start Chrome, count browser processes carrying our unique
      user-data-dir, cancel the context+allocator, and time the reap to 0.
  (b) exit-without-cancel path: a Go process that forgets `defer cancel()` and just
      exits — does Chrome orphan on macOS? Measured AFTER the probe process exits, then
      the orphan is force-cleaned by this runner (guaranteed no leftover process).

The pgrep-on-user-data-dir count is the process analog of the fixture's server-side
hit counter — fetch/lifecycle truth independent of chromedp's own return values.
"""
from __future__ import annotations

import json
import os
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


def browser_procs(dir_key: str) -> int:
    """Count *browser* (non --type=) Chrome procs carrying dir_key — process-truth."""
    out = subprocess.run(["pgrep", "-f", dir_key], capture_output=True, text=True).stdout.split()
    n = 0
    for pid in out:
        c = subprocess.run(["ps", "-p", pid, "-o", "command="], capture_output=True, text=True).stdout
        if dir_key in c and "--type=" not in c:
            n += 1
    return n


def cleanup(dir_key: str) -> None:
    subprocess.run(["pkill", "-f", dir_key], capture_output=True)
    time.sleep(0.4)
    shutil.rmtree(dir_key, ignore_errors=True)


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
        "platform_note": "macOS arm64. chromedp allocate.go uses exec.CommandContext; "
                         "the force-kill-children guarantee in godoc is Linux-scoped.",
        "cancel_runs": [],
        "orphan_runs": [],
    }
    try:
        # (a) cancel path
        for i in range(3):
            key = os.path.join(tempfile.gettempdir(), f"chromedp_life_{int(time.time()*1000)}_{i}")
            cmd = [str(PROBE), "lifecycle", "--url", f"{base}/", "--chrome", CHROME, "--user-data-dir", key]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if p.returncode == 0:
                summary["cancel_runs"].append(json.loads(p.stdout.strip().splitlines()[-1]))
            else:
                summary["cancel_runs"].append({"error": True, "stderr": p.stderr[-400:]})
            cleanup(key)

        # (b) exit-without-cancel path (macOS orphan measurement)
        for i in range(3):
            key = os.path.join(tempfile.gettempdir(), f"chromedp_orphan_{int(time.time()*1000)}_{i}")
            before = browser_procs(key)
            cmd = [str(PROBE), "startnocancel", "--url", f"{base}/classes?delay=0",
                   "--chrome", CHROME, "--user-data-dir", key]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            probe_ok = p.returncode == 0
            # the probe has now EXITED without cancelling; measure orphan survival
            time.sleep(1.0)
            after_exit = browser_procs(key)
            summary["orphan_runs"].append({
                "probe_ok": probe_ok,
                "browser_procs_before": before,
                "browser_procs_after_probe_exit": after_exit,
                "orphaned": after_exit > 0,
            })
            cleanup(key)  # MANDATORY: force-kill any orphan, remove dir
            summary["orphan_runs"][-1]["browser_procs_after_cleanup"] = browser_procs(key)

        # computed reading
        cok = [r for r in summary["cancel_runs"] if not r.get("error")]
        summary["reading"] = {
            "cancel_reaps_all": bool(cok) and all(r.get("reaped") for r in cok),
            "reap_ms_values": [r.get("reap_ms") for r in cok],
            "orphan_on_exit_all": bool(summary["orphan_runs"]) and all(r["orphaned"] for r in summary["orphan_runs"]),
            "all_orphans_cleaned": all(r.get("browser_procs_after_cleanup", 0) == 0 for r in summary["orphan_runs"]),
            "note": "cancel => Chrome reaped (exec.CommandContext kill); exit-without-cancel "
                    "on macOS => Chrome orphaned (no parent-death signal). Contrast is the finding.",
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "lifecycle-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
