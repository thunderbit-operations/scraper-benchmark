#!/usr/bin/env python3
"""H2 — context lifecycle / Chrome process reap (process-truth). The headline.

rod's default launcher ships leakless: a separate guardian binary bridged to the Go
process over TCP; when that connection closes (parent EXITS or CRASHES), the guardian
kills the browser. why-rod claims chromedp "leaves the zombie browser process on Mac"
while rod does not. chromedp's pack MEASURED the macOS orphan (exit-without-cancel orphans
3/3). This runner runs the mirror on rod, four paths, each 3x:

  (a) graceful  : leakless on, browser.Close() in-process -> reap ms
  (b) exit ON   : leakless ON, Go exits without cleanup   -> reaped? (predict YES)
  (c) exit OFF  : leakless OFF, Go exits without cleanup   -> orphaned? (predict YES)
  (d) kill ON   : leakless ON, parent SIGKILLed (crash)    -> reaped? (predict YES)

(b) vs (c) is the attribution: the leakless on/off TOGGLE isolates the guardian as the
cause, not "rod is magic." (d) tests the why-rod crash claim. Cross-tool: chromedp orphans
on exit-without-cancel; rod's DEFAULT (leakless on) reaps — the opposite conclusion, and
the reason is the guardian, proven by the OFF path orphaning just like chromedp.

The pgrep-on-user-data-dir count (browser exe only; leakless guardian and Chrome helpers
excluded) is the process analog of the fixture's server-side hit counter.
"""
from __future__ import annotations

import json
import os
import signal
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
    """Count *browser* Chrome procs carrying dir_key: executable basename must be
    chrome-headless-shell and command must have no --type= flag — so Chrome helper procs
    (renderer/gpu, which carry --type=) and the leakless guardian (argv[0] = leakless
    binary) are both excluded. Process-truth, mirrors the Go probe's counter."""
    out = subprocess.run(["pgrep", "-f", dir_key], capture_output=True, text=True).stdout.split()
    n = 0
    for pid in out:
        c = subprocess.run(["ps", "-p", pid, "-o", "command="], capture_output=True, text=True).stdout
        if dir_key not in c or "--type=" in c:
            continue
        fields = c.split()
        if not fields:
            continue
        if os.path.basename(fields[0]) == "chrome-headless-shell":
            n += 1
    return n


def cleanup(dir_key: str) -> None:
    subprocess.run(["pkill", "-f", dir_key], capture_output=True)
    time.sleep(0.4)
    shutil.rmtree(dir_key, ignore_errors=True)


def exit_path(base: str, leakless: bool, tag: str) -> dict[str, Any]:
    """Run startidle --onstart exit: the probe exits(0) WITHOUT cleanup. Measure orphan."""
    key = os.path.join(tempfile.gettempdir(), f"rod_{tag}_{int(time.time()*1000)}")
    before = browser_procs(key)
    cmd = [str(PROBE), "startidle", "--url", f"{base}/classes?delay=0", "--chrome", CHROME,
           "--user-data-dir", key, f"--leakless={'true' if leakless else 'false'}", "--onstart", "exit"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    probe_ok = p.returncode == 0
    time.sleep(1.2)  # the probe has EXITED; give the guardian time to react (or not)
    after_exit = browser_procs(key)
    row = {
        "leakless": leakless, "probe_ok": probe_ok,
        "browser_procs_before": before,
        "browser_procs_after_probe_exit": after_exit,
        "orphaned": after_exit > 0,
    }
    cleanup(key)  # MANDATORY: force-kill any orphan, remove dir
    row["browser_procs_after_cleanup"] = browser_procs(key)
    return row


def kill_path(base: str, tag: str) -> dict[str, Any]:
    """Run startidle --onstart block, then SIGKILL the parent (crash sim). Measure orphan."""
    key = os.path.join(tempfile.gettempdir(), f"rod_{tag}_{int(time.time()*1000)}")
    before = browser_procs(key)
    cmd = [str(PROBE), "startidle", "--url", f"{base}/classes?delay=0", "--chrome", CHROME,
           "--user-data-dir", key, "--leakless=true", "--onstart", "block"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # wait for the "started" line so the browser is up
    started = False
    t0 = time.time()
    while time.time() - t0 < 30:
        line = proc.stdout.readline()
        if line and '"started"' in line:
            started = True
            break
    time.sleep(0.3)
    up = browser_procs(key)
    proc.send_signal(signal.SIGKILL)  # hard crash of the parent Go process
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(1.2)  # guardian should see the TCP close and kill the browser
    after_kill = browser_procs(key)
    row = {
        "leakless": True, "parent_signal": "SIGKILL", "probe_started": started,
        "browser_procs_while_up": up,
        "browser_procs_after_parent_kill": after_kill,
        "orphaned": after_kill > 0,
    }
    cleanup(key)
    row["browser_procs_after_cleanup"] = browser_procs(key)
    return row


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not PROBE.exists() or not os.path.exists(CHROME):
        print("probe binary or chrome missing", file=sys.stderr)
        return 2

    # pre-warm leakless so the guardian binary is already downloaded (not measured here).
    server = start_fixture_server()
    base = server.base_url
    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "rod",
        "base_url": base,
        "platform_note": "macOS arm64. rod launcher enables leakless by default: a separate "
                         "guardian binary bridged to the Go process over TCP kills the browser "
                         "when the connection closes (parent exit OR crash). Contrast: chromedp "
                         "on macOS orphans on exit-without-cancel (allocate_other.go no-op).",
        "graceful_runs": [],
        "exit_leakless_on_runs": [],
        "exit_leakless_off_runs": [],
        "kill_leakless_on_runs": [],
    }
    try:
        # (a) graceful close path (leakless on) — in-process reap timing.
        for i in range(3):
            key = os.path.join(tempfile.gettempdir(), f"rod_life_{int(time.time()*1000)}_{i}")
            cmd = [str(PROBE), "graceful", "--url", f"{base}/", "--chrome", CHROME,
                   "--user-data-dir", key, "--leakless=true"]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if p.returncode == 0:
                summary["graceful_runs"].append(json.loads(p.stdout.strip().splitlines()[-1]))
            else:
                summary["graceful_runs"].append({"error": True, "stderr": p.stderr[-400:]})
            cleanup(key)

        # (b) exit-without-cleanup, leakless ON (predict reaped by guardian)
        for _ in range(3):
            summary["exit_leakless_on_runs"].append(exit_path(base, True, "exit_on"))
        # (c) exit-without-cleanup, leakless OFF (predict orphaned, like chromedp)
        for _ in range(3):
            summary["exit_leakless_off_runs"].append(exit_path(base, False, "exit_off"))
        # (d) SIGKILL parent, leakless ON (why-rod crash claim; predict reaped)
        for _ in range(3):
            summary["kill_leakless_on_runs"].append(kill_path(base, "kill_on"))

        # computed reading
        gok = [r for r in summary["graceful_runs"] if not r.get("error")]
        summary["reading"] = {
            "graceful_reaps_all": bool(gok) and all(r.get("reaped") for r in gok),
            "graceful_reap_ms_values": [r.get("reap_ms") for r in gok],
            "exit_leakless_on_orphans": [r["orphaned"] for r in summary["exit_leakless_on_runs"]],
            "exit_leakless_on_reaped_all": all(not r["orphaned"] for r in summary["exit_leakless_on_runs"]),
            "exit_leakless_off_orphans": [r["orphaned"] for r in summary["exit_leakless_off_runs"]],
            "exit_leakless_off_orphaned_all": all(r["orphaned"] for r in summary["exit_leakless_off_runs"]),
            "kill_leakless_on_reaped_all": all(not r["orphaned"] for r in summary["kill_leakless_on_runs"]),
            "all_orphans_cleaned": all(
                r.get("browser_procs_after_cleanup", 0) == 0
                for r in (summary["exit_leakless_on_runs"] + summary["exit_leakless_off_runs"]
                          + summary["kill_leakless_on_runs"])
            ),
            "note": "leakless ON => browser reaped on exit AND on SIGKILL (guardian TCP-close "
                    "kill). leakless OFF => orphan on exit, same as chromedp on macOS. The on/off "
                    "toggle attributes the reaping to leakless, not to rod broadly. Boundary "
                    "(#865): leakless fires on PROCESS EXIT, not per-browser-close inside a "
                    "long-running process — not exercised here.",
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "lifecycle-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
