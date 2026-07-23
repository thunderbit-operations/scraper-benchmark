#!/usr/bin/env python3
"""H2 — context lifecycle / process reap across the THREE-process chain (process-truth).
The headline.

Selenium's chain is python -> chromedriver -> chrome (+ helpers): chromedriver is a
SEPARATE long-lived child process, not an in-process CDP client like chromedp/rod. So a
lifecycle test must count BOTH the chromedriver process (by pid) AND the chrome browser
process (by pgrep on a unique --user-data-dir). Four paths:

  (a) graceful  : driver.quit() (W3C DELETE session + kill chromedriver) -> reap both, ms
  (b) exit      : python EXITS without quit() (os._exit) -> orphan?  (predict: BOTH orphan)
  (c) kill      : python SIGKILLed mid-session (crash)   -> orphan?  (predict: BOTH orphan)

Cross-tool contrast: chromedp on macOS orphans the browser on exit-without-cancel (1 proc);
rod's default leakless REAPS on exit AND crash (0 procs). Selenium has NO leakless-style
guardian and NO parent-death signal wired by default, so a no-quit exit / crash leaves the
chromedriver process alive AND the browser it owns alive — a TWO-process orphan. quit() is
mandatory. Every orphan here is force-cleaned (kill the chromedriver pid + pkill the udd);
the runner verifies zero leftover at the end.
"""
from __future__ import annotations

import json
import os
import signal
import shutil
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
BROWSER_EXE = "Google Chrome for Testing"
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


def browser_procs(udd_key: str) -> int:
    """Browser Chrome procs carrying udd_key: argv[0] basename == BROWSER_EXE and no
    --type= (so helpers are excluded). Process-truth, mirrors the probe's counter."""
    out = subprocess.run(["pgrep", "-f", udd_key], capture_output=True, text=True).stdout.split()
    n = 0
    for pid in out:
        c = subprocess.run(["ps", "-p", pid, "-o", "command="], capture_output=True, text=True).stdout
        if udd_key not in c or "--type=" in c:
            continue
        argv0 = c.strip().split(" --", 1)[0]
        if os.path.basename(argv0.strip()) == BROWSER_EXE:
            n += 1
    return n


def chromedriver_alive(pid: int) -> bool:
    c = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
    return bool(c.strip()) and "chromedriver" in c


def force_clean(udd: str, cd_pid: int | None) -> dict[str, int]:
    """Kill the chromedriver pid AND any chrome procs carrying the udd; return residual."""
    if cd_pid:
        try:
            os.kill(cd_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    subprocess.run(["pkill", "-f", os.path.basename(udd)], capture_output=True)
    time.sleep(0.4)
    shutil.rmtree(udd, ignore_errors=True)
    return {
        "browser_procs_after_cleanup": browser_procs(os.path.basename(udd)),
        "chromedriver_alive_after_cleanup": int(chromedriver_alive(cd_pid) if cd_pid else 0),
    }


def probe_cmd(sub: str, udd: str, base: str, extra: list[str]) -> list[str]:
    cmd = [PY_BIN, str(PROBE), sub, "--url", f"{base}/", "--user-data-dir", udd]
    if DRIVER_PATH:
        cmd += ["--driver-path", DRIVER_PATH]
    return cmd + extra


def graceful_run(base: str) -> dict[str, Any]:
    udd = tempfile.mkdtemp(prefix="sel_life_gr_")
    cd_pid = None
    try:
        p = subprocess.run(probe_cmd("graceful", udd, base, []), capture_output=True, text=True, timeout=90)
        if p.returncode != 0:
            return {"error": True, "stderr": p.stderr[-400:]}
        row = json.loads(p.stdout.strip().splitlines()[-1])
        cd_pid = row.get("chromedriver_pid")
        return row
    finally:
        force_clean(udd, cd_pid)


def exit_run(base: str) -> dict[str, Any]:
    """python exits WITHOUT quit() (os._exit); measure BOTH driver + browser orphan."""
    udd = tempfile.mkdtemp(prefix="sel_life_exit_")
    key = os.path.basename(udd)
    cmd = probe_cmd("startidle", udd, base, ["--onstart", "exit"])
    # startidle navigates /classes; override url to a real page
    cmd[cmd.index("--url") + 1] = f"{base}/classes?delay=0"
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    line = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {}
    cd_pid = line.get("chromedriver_pid")
    time.sleep(1.2)  # probe has exited; give any death-signal path time to fire (or not)
    driver_orphan = chromedriver_alive(cd_pid) if cd_pid else False
    browser_orphan = browser_procs(key)
    row = {
        "probe_ok": p.returncode == 0,
        "chromedriver_pid": cd_pid,
        "browser_procs_up": line.get("browser_procs_up"),
        "chromedriver_orphaned": driver_orphan,
        "browser_procs_after_exit": browser_orphan,
        "both_orphaned": bool(driver_orphan) and browser_orphan > 0,
    }
    row.update(force_clean(udd, cd_pid))
    return row


def kill_run(base: str) -> dict[str, Any]:
    """python SIGKILLed mid-session (crash); measure BOTH driver + browser orphan."""
    udd = tempfile.mkdtemp(prefix="sel_life_kill_")
    key = os.path.basename(udd)
    cmd = probe_cmd("startidle", udd, base, ["--onstart", "block"])
    cmd[cmd.index("--url") + 1] = f"{base}/classes?delay=0"
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    cd_pid = None
    started = False
    t0 = time.time()
    while time.time() - t0 < 40:
        line = proc.stdout.readline()
        if line and '"started"' in line:
            cd_pid = json.loads(line)["chromedriver_pid"]
            started = True
            break
    time.sleep(0.3)
    up = browser_procs(key)
    proc.send_signal(signal.SIGKILL)  # hard crash of the parent python process
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(1.2)
    driver_orphan = chromedriver_alive(cd_pid) if cd_pid else False
    browser_orphan = browser_procs(key)
    row = {
        "probe_started": started,
        "chromedriver_pid": cd_pid,
        "browser_procs_while_up": up,
        "chromedriver_orphaned": driver_orphan,
        "browser_procs_after_parent_kill": browser_orphan,
        "both_orphaned": bool(driver_orphan) and browser_orphan > 0,
    }
    row.update(force_clean(udd, cd_pid))
    return row


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
        "platform_note": "macOS arm64. Selenium chain = python -> chromedriver -> chrome. "
                         "chromedriver is a separate child process; there is no leakless-style "
                         "guardian and no parent-death signal wired by default, so a no-quit "
                         "exit / crash orphans BOTH the driver and the browser. Contrast: "
                         "chromedp orphans the browser only (1 proc) on macOS exit-without-cancel; "
                         "rod's default leakless reaps everything on exit AND crash.",
        "graceful_runs": [],
        "exit_no_quit_runs": [],
        "kill_crash_runs": [],
    }
    try:
        for _ in range(3):
            summary["graceful_runs"].append(graceful_run(base))
        for _ in range(3):
            summary["exit_no_quit_runs"].append(exit_run(base))
        for _ in range(3):
            summary["kill_crash_runs"].append(kill_run(base))

        gok = [r for r in summary["graceful_runs"] if not r.get("error")]
        summary["reading"] = {
            "graceful_reaps_both_all": bool(gok) and all(r.get("reaped_both") for r in gok),
            "graceful_reap_ms_values": [r.get("reap_ms") for r in gok],
            "exit_both_orphaned_all": all(r["both_orphaned"] for r in summary["exit_no_quit_runs"]),
            "exit_chromedriver_orphaned": [r["chromedriver_orphaned"] for r in summary["exit_no_quit_runs"]],
            "exit_browser_procs_after": [r["browser_procs_after_exit"] for r in summary["exit_no_quit_runs"]],
            "kill_both_orphaned_all": all(r["both_orphaned"] for r in summary["kill_crash_runs"]),
            "kill_chromedriver_orphaned": [r["chromedriver_orphaned"] for r in summary["kill_crash_runs"]],
            "kill_browser_procs_after": [r["browser_procs_after_parent_kill"] for r in summary["kill_crash_runs"]],
            "all_orphans_cleaned": all(
                r.get("browser_procs_after_cleanup", 0) == 0
                and r.get("chromedriver_alive_after_cleanup", 0) == 0
                for r in (summary["exit_no_quit_runs"] + summary["kill_crash_runs"])
            ),
            "note": "graceful quit() reaps BOTH chromedriver + chrome. A no-quit exit AND a "
                    "SIGKILL crash each orphan BOTH the chromedriver process and the browser "
                    "(no guardian, no parent-death signal) — the opposite of rod's leakless "
                    "default, and one process worse than chromedp's browser-only orphan. All "
                    "orphans were force-cleaned (kill chromedriver pid + pkill udd).",
        }
        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "lifecycle-summary.json", summary)
        print(json.dumps(_redact(summary), indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
