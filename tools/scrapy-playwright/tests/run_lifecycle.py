#!/usr/bin/env python3
"""Scheduler / lifecycle / backpressure harness.

These are the operational boundaries the official README documents but reviews
rarely exercise on a live process: page cap per context, context cap, page
concurrency vs the cap, correctly-closed pages, and the deliberate unclosed-page
stall. Every run is a fresh subprocess against the shared fixture. Behavior is
read from Scrapy's playwright/* stats, never assumed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
SPIDERS_DIR = PROJECT_DIR / "tests" / "spiders"
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []


def parse_pw_stats(log: Path) -> dict[str, int]:
    if not log.exists():
        return {}
    text = log.read_text(encoding="utf-8", errors="replace")
    out: dict[str, int] = {}
    for m in re.finditer(r"'(playwright/[^']+|item_scraped_count|finish_reason)':\s*(\d+|'[^']*')", text):
        key, val = m.group(1), m.group(2)
        out[key] = int(val) if val.isdigit() else val.strip("'")
    return out


def run(run_id: str, env: dict[str, str], settings: list[str], timeout: int) -> dict[str, Any]:
    out = RAW_DIR / f"{run_id}.json"
    log = LOGS_DIR / f"{run_id}.log"
    if out.exists():
        out.unlink()
    if log.exists():
        log.unlink()
    command = [
        sys.executable, "-m", "scrapy", "runspider", str(SPIDERS_DIR / "pw_pages_spider.py"),
        "-O", str(out), "-s", f"LOG_FILE={log}", "-s", "FEED_EXPORT_ENCODING=utf-8",
    ] + settings
    started = time.monotonic()
    try:
        completed = subprocess.run(command, capture_output=True, text=True, env=env,
                                   cwd=PROJECT_DIR, timeout=timeout)
        rc, timed_out = completed.returncode, False
    except subprocess.TimeoutExpired:
        rc, timed_out = -1, True
    elapsed = round(time.monotonic() - started, 3)
    rows = read_json(out)
    rendered = [r for r in rows if r.get("outcome") == "rendered"]
    errbacks = [r for r in rows if r.get("outcome") == "errback"]
    return {
        "run_id": run_id, "returncode": rc, "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "items_total": len(rows), "items_rendered": len(rendered), "items_errback": len(errbacks),
        "pw_stats": parse_pw_stats(log),
    }


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    server = start_fixture_server()
    base_env = os.environ.copy()
    base_env["FIXTURE_BASE_URL"] = server.base_url

    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "scrapy-playwright",
        "tests": {},
    }
    T = result["tests"]

    def env_with(**kw) -> dict[str, str]:
        e = dict(base_env)
        for k, v in kw.items():
            e[k] = str(v)
        return e

    try:
        # 1) Page concurrency tracks CONCURRENT_REQUESTS (pages closed, high cap).
        conc_runs = {}
        for c in (1, 4, 8):
            r = run(
                f"lifecycle_concurrency_{c}",
                env_with(PW_N=8, PW_INCLUDE_PAGE="true", PW_CLOSE_PAGE="true"),
                ["-s", f"CONCURRENT_REQUESTS={c}",
                 "-s", "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=16", "-s", "LOG_LEVEL=INFO"],
                timeout=90,
            )
            conc_runs[str(c)] = r
        T["page_concurrency_vs_setting"] = {
            "check": "playwright/page_count/max_concurrent should rise with CONCURRENT_REQUESTS",
            "runs": conc_runs,
            "observed_max_concurrent": {c: r["pw_stats"].get("playwright/page_count/max_concurrent")
                                        for c, r in conc_runs.items()},
        }

        # 2) Page cap becomes backpressure: cap=2, concurrency=8, pages closed => all finish.
        r_cap = run(
            "lifecycle_pagecap_2",
            env_with(PW_N=8, PW_INCLUDE_PAGE="true", PW_CLOSE_PAGE="true"),
            ["-s", "CONCURRENT_REQUESTS=8",
             "-s", "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=2", "-s", "LOG_LEVEL=INFO"],
            timeout=90,
        )
        T["page_cap_backpressure"] = {
            "check": "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=2 caps concurrency but all 8 still complete",
            "run": r_cap,
            "max_concurrent": r_cap["pw_stats"].get("playwright/page_count/max_concurrent"),
            "items_rendered": r_cap["items_rendered"],
        }

        # 3) Context cap = 1 under concurrency 8 (document behavior).
        r_ctx = run(
            "lifecycle_contextcap_1",
            env_with(PW_N=8, PW_INCLUDE_PAGE="true", PW_CLOSE_PAGE="true"),
            ["-s", "CONCURRENT_REQUESTS=8", "-s", "PLAYWRIGHT_MAX_CONTEXTS=1",
             "-s", "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=16", "-s", "LOG_LEVEL=INFO"],
            timeout=90,
        )
        T["context_cap"] = {
            "check": "PLAYWRIGHT_MAX_CONTEXTS=1: single context, all pages still complete",
            "run": r_ctx,
            "context_max_concurrent": r_ctx["pw_stats"].get("playwright/context_count/max_concurrent"),
            "items_rendered": r_ctx["items_rendered"],
        }

        # 4) Healthy lifecycle via the handler's auto-close path (no include_page):
        #    the handler closes each page after extracting content, so
        #    page_count/closed should equal page_count with no leak.
        r_closed = run(
            "lifecycle_closed_pages",
            env_with(PW_N=6, PW_INCLUDE_PAGE="false"),
            ["-s", "CONCURRENT_REQUESTS=4",
             "-s", "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=16", "-s", "LOG_LEVEL=INFO"],
            timeout=90,
        )
        T["auto_closed_pages"] = {
            "check": "handler auto-close path: page_count/closed == page_count, no leak",
            "run": r_closed,
            "page_count": r_closed["pw_stats"].get("playwright/page_count"),
            "page_count_closed": r_closed["pw_stats"].get("playwright/page_count/closed"),
        }

        # 5) Deliberate unclosed pages under a low cap: the wedge.
        #    cap=2, 6 pages held open (include_page) and never closed. A side-channel
        #    progress file records every page that actually renders, so we can see
        #    how many got through before the crawl wedged (independent of whether the
        #    feed was ever finalized). CLOSESPIDER_TIMEOUT is set low; if graceful
        #    shutdown cannot complete because downloads are stuck on the page
        #    semaphore, the external subprocess timeout is the real bound.
        progress = RAW_DIR / "unclosed_stall_progress.txt"
        if progress.exists():
            progress.unlink()
        r_leak = run(
            "lifecycle_unclosed_stall",
            env_with(PW_N=6, PW_INCLUDE_PAGE="true", PW_CLOSE_PAGE="false",
                     PW_PROGRESS_FILE=str(progress)),
            ["-s", "CONCURRENT_REQUESTS=8",
             "-s", "PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=2", "-s", "LOG_LEVEL=INFO",
             "-s", "CLOSESPIDER_TIMEOUT=8"],
            timeout=22,
        )
        rendered_before_wedge = 0
        if progress.exists():
            rendered_before_wedge = len([ln for ln in progress.read_text().splitlines() if ln.strip()])
        # Did the process require the external kill (graceful shutdown failed)?
        clean_exit = (r_leak["returncode"] == 0) and not r_leak["timed_out"]
        T["unclosed_page_wedge"] = {
            "check": "hold pages open under cap=2 => cap-many render then the crawl wedges; "
                     "closespider_timeout cannot clean up stuck page-semaphore downloads; external kill needed",
            "run": r_leak,
            "page_cap": 2,
            "pages_requested": 6,
            "rendered_before_wedge_sidechannel": rendered_before_wedge,
            "graceful_shutdown_succeeded": clean_exit,
            "required_external_kill": not clean_exit,
        }

        result["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "lifecycle-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
