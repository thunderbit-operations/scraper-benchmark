#!/usr/bin/env python3
"""Resource and reliability harness: elapsed distribution, browser-inclusive RSS,
and the memory-visibility hypothesis.

Two questions, both decision-relevant and rarely quantified in SERP tutorials:

1. Selective vs full rendering cost. The mixed crawl reaches the SAME pages and
   extracts the SAME cards whether it renders only the dynamic route (selective)
   or every request (all). We assert extraction parity, then compare elapsed +
   peak process-tree RSS across 3 isolated runs each. Differences inside the
   noise band (<5% or overlapping ranges) are called a tie.

2. Memory visibility. Scrapy's default MemoryUsage extension measures only the
   Python process; the browser lives in separate processes. We run the same
   render workload with (a) the default extension and (b) scrapy-playwright's
   ScrapyPlaywrightMemoryUsageExtension, and compare the memusage/max each
   reports against an external psutil peak of the whole process tree.

Every run is a fresh subprocess so peak RSS is never contaminated by a prior
high-load run (v3 gate 3). Nothing is hardcoded; all numbers come from output.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import DYNAMIC_PRODUCTS, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
SPIDERS_DIR = PROJECT_DIR / "tests" / "spiders"
RAW_DIR = PROJECT_DIR / "artifacts" / "raw"
LOGS_DIR = PROJECT_DIR / "artifacts" / "logs"

RUNS = 3
POLL_SECONDS = 0.05


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []


def sample_tree_rss_peak(proc: psutil.Process, stop: threading.Event, out: dict) -> None:
    """Poll RSS of proc + all descendants; record peak bytes and sample count."""
    peak = 0
    samples = 0
    while not stop.is_set():
        total = 0
        try:
            procs = [proc] + proc.children(recursive=True)
            for p in procs:
                try:
                    total += p.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            break
        peak = max(peak, total)
        samples += 1
        time.sleep(POLL_SECONDS)
    out["peak_tree_rss_bytes"] = peak
    out["rss_samples"] = samples


def run_measured(spider: str, output: Path, log: Path, env: dict[str, str],
                 extra_settings: list[str] | None = None, timeout: int = 180) -> dict[str, Any]:
    if output.exists():
        output.unlink()
    if log.exists():
        log.unlink()
    command = [
        sys.executable, "-m", "scrapy", "runspider", str(SPIDERS_DIR / spider),
        "-O", str(output), "-s", f"LOG_FILE={log}", "-s", "FEED_EXPORT_ENCODING=utf-8",
    ]
    if extra_settings:
        command.extend(extra_settings)

    started = time.monotonic()
    popen = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env=env, cwd=PROJECT_DIR)
    ps_proc = psutil.Process(popen.pid)
    stop = threading.Event()
    rss_out: dict = {}
    sampler = threading.Thread(target=sample_tree_rss_peak, args=(ps_proc, stop, rss_out), daemon=True)
    sampler.start()
    try:
        rc = popen.wait(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        popen.kill()
        rc = -1
        timed_out = True
    stop.set()
    sampler.join(timeout=2)
    elapsed = round(time.monotonic() - started, 3)

    stats = parse_scrapy_stats(log)
    return {
        "spider": spider, "returncode": rc, "timed_out": timed_out,
        "elapsed_seconds": elapsed,
        "peak_tree_rss_mb": round(rss_out.get("peak_tree_rss_bytes", 0) / (1024 * 1024), 1),
        "rss_samples": rss_out.get("rss_samples", 0),
        "scrapy_stats": stats,
    }


def parse_scrapy_stats(log: Path) -> dict[str, Any]:
    """Pull selected numeric stats from the Scrapy log's final stats dump."""
    if not log.exists():
        return {}
    text = log.read_text(encoding="utf-8", errors="replace")
    keys = ["downloader/request_count", "item_scraped_count", "memusage/startup",
            "memusage/max", "playwright/request_count", "playwright/page_count"]
    out: dict[str, Any] = {}
    for k in keys:
        m = re.search(rf"'{re.escape(k)}':\s*(\d+)", text)
        if m:
            out[k] = int(m.group(1))
    return out


def extraction_signature(rows: list[dict]) -> dict[str, int]:
    """Canonical url -> cards map, ignoring the rendered flag, for parity assert.

    The URL is canonicalized with rstrip('/') because a browser navigation adds a
    trailing slash to the bare host seed (http://host -> http://host/) while a
    plain HTTP request keeps it as-is. That is cosmetic normalization of the same
    home page, not an extraction difference; no other fixture URL ends in '/'.
    """
    return {r["url"].rstrip("/"): r.get("product_cards_found", 0) for r in rows}


def summarize(nums: list[float]) -> dict[str, float]:
    return {
        "runs": len(nums),
        "min": round(min(nums), 3),
        "p50": round(statistics.median(nums), 3),
        "max": round(max(nums), 3),
        "mean": round(statistics.mean(nums), 3),
    }


def tie_or_winner(a: dict, b: dict, label_a: str, label_b: str, metric: str) -> dict:
    """Overlapping [min,max] ranges => tie. Else the lower p50 wins, with % gap."""
    overlap = not (a["max"] < b["min"] or b["max"] < a["min"])
    verdict = "tie_overlapping_ranges" if overlap else (
        f"{label_a}_lower" if a["p50"] < b["p50"] else f"{label_b}_lower")
    lo, hi = sorted([a["p50"], b["p50"]])
    gap_pct = round((hi - lo) / lo * 100, 1) if lo > 0 else None
    if not overlap and gap_pct is not None and gap_pct < 5:
        verdict = "tie_within_5pct"
    return {"metric": metric, "verdict": verdict, "p50_gap_pct": gap_pct,
            label_a: a, label_b: b}


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    server = start_fixture_server()
    env = os.environ.copy()
    env["FIXTURE_BASE_URL"] = server.base_url

    result: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "scrapy-playwright",
        "runs_per_condition": RUNS,
        "poll_seconds": POLL_SECONDS,
        "note": "peak_tree_rss_mb = scrapy process + all descendant (browser) processes, sampled externally",
    }

    try:
        # ---------- Q1: selective vs all rendering, same result ----------
        modes = {"selective": "selective", "all": "all"}
        per_mode: dict[str, list[dict]] = {"selective": [], "all": []}
        signatures: dict[str, dict] = {}
        for mode, pw_mode in modes.items():
            for i in range(RUNS):
                out = RAW_DIR / f"resource_crawl_{mode}_run{i+1}.json"
                log = LOGS_DIR / f"resource_crawl_{mode}_run{i+1}.log"
                run_env = dict(env)
                run_env["PW_RENDER_MODE"] = pw_mode
                r = run_measured("mixed_crawl_graph_spider.py", out, log, run_env)
                r["run_index"] = i + 1
                rows = read_json(out)
                r["items"] = len(rows)
                signatures.setdefault(mode, extraction_signature(rows))
                per_mode[mode].append(r)

        sel_sig = signatures.get("selective", {})
        all_sig = signatures.get("all", {})
        parity_ok = sel_sig == all_sig

        sel_elapsed = summarize([r["elapsed_seconds"] for r in per_mode["selective"]])
        all_elapsed = summarize([r["elapsed_seconds"] for r in per_mode["all"]])
        sel_rss = summarize([r["peak_tree_rss_mb"] for r in per_mode["selective"]])
        all_rss = summarize([r["peak_tree_rss_mb"] for r in per_mode["all"]])

        result["selective_vs_all"] = {
            "parity_assert": {
                "same_extraction": parity_ok,
                "selective_signature": sel_sig,
                "all_signature": all_sig,
            },
            "elapsed_seconds": tie_or_winner(sel_elapsed, all_elapsed, "selective", "all", "elapsed_seconds"),
            "peak_tree_rss_mb": tie_or_winner(sel_rss, all_rss, "selective", "all", "peak_tree_rss_mb"),
            "raw_runs": per_mode,
        }

        # ---------- Q2: memory visibility (default vs playwright extension) ----------
        # Same render workload (all-render crawl). Frequent memusage sampling so
        # the interval poll actually captures the browser-inclusive peak.
        default_ext = ["-s", "MEMUSAGE_ENABLED=True", "-s", "MEMUSAGE_CHECK_INTERVAL_SECONDS=0.25"]
        pw_ext = [
            "-s", "MEMUSAGE_ENABLED=True",
            "-s", "MEMUSAGE_CHECK_INTERVAL_SECONDS=0.25",
            "-s", "EXTENSIONS={\"scrapy.extensions.memusage.MemoryUsage\": null, "
                  "\"scrapy_playwright.memusage.ScrapyPlaywrightMemoryUsageExtension\": 0}",
        ]
        mem_env = dict(env)
        mem_env["PW_RENDER_MODE"] = "all"

        mem_runs: dict[str, list[dict]] = {"default_extension": [], "playwright_extension": []}
        for i in range(RUNS):
            d_out = RAW_DIR / f"mem_default_run{i+1}.json"
            d_log = LOGS_DIR / f"mem_default_run{i+1}.log"
            dr = run_measured("mixed_crawl_graph_spider.py", d_out, d_log, mem_env, extra_settings=default_ext)
            dr["run_index"] = i + 1
            mem_runs["default_extension"].append(dr)

            p_out = RAW_DIR / f"mem_playwright_run{i+1}.json"
            p_log = LOGS_DIR / f"mem_playwright_run{i+1}.log"
            pr = run_measured("mixed_crawl_graph_spider.py", p_out, p_log, mem_env, extra_settings=pw_ext)
            pr["run_index"] = i + 1
            mem_runs["playwright_extension"].append(pr)

        def stat_mb(runs: list[dict], key: str) -> list[float]:
            vals = []
            for r in runs:
                v = r.get("scrapy_stats", {}).get(key)
                if v is not None:
                    vals.append(round(v / (1024 * 1024), 1))
            return vals

        default_memmax = stat_mb(mem_runs["default_extension"], "memusage/max")
        pw_memmax = stat_mb(mem_runs["playwright_extension"], "memusage/max")
        default_tree = [r["peak_tree_rss_mb"] for r in mem_runs["default_extension"]]
        pw_tree = [r["peak_tree_rss_mb"] for r in mem_runs["playwright_extension"]]

        result["memory_visibility"] = {
            "hypothesis": "default MemoryUsage reports Python-only; playwright extension includes browser procs",
            "default_extension_memusage_max_mb": default_memmax,
            "playwright_extension_memusage_max_mb": pw_memmax,
            "external_psutil_peak_tree_rss_mb": {
                "under_default_extension_runs": default_tree,
                "under_playwright_extension_runs": pw_tree,
            },
            "raw_runs": mem_runs,
            "reading_guide": "compare each memusage/max stat against the external psutil tree peak from the same run",
        }

        result["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "resource-summary.json", result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
