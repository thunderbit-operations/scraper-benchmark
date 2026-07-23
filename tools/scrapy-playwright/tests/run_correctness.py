#!/usr/bin/env python3
"""Correctness and behavior matrix for the Scrapy-Playwright pack.

Every run is a fresh `scrapy runspider` subprocess (avoids Twisted reactor reuse
issues) against the shared local fixture. Conclusions here are counts computed
from run output; nothing is hardcoded. Timing/RSS live in run_resource.py;
lifecycle/backpressure lives in run_lifecycle.py.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fixture_server import ARTICLE, DYNAMIC_PRODUCTS, PRODUCTS, start_fixture_server  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parents[1]
TESTS_DIR = PROJECT_DIR / "tests"
SPIDERS_DIR = TESTS_DIR / "spiders"
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
RAW_DIR = ARTIFACTS_DIR / "raw"
LOGS_DIR = ARTIFACTS_DIR / "logs"
SHOTS_DIR = ARTIFACTS_DIR / "screenshots"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []


def run_spider(spider: str, output: Path, log: Path, env: dict[str, str], timeout: int = 120) -> dict[str, Any]:
    if output.exists():
        output.unlink()
    command = [
        sys.executable, "-m", "scrapy", "runspider", str(SPIDERS_DIR / spider),
        "-O", str(output), "-s", f"LOG_FILE={log}", "-s", "FEED_EXPORT_ENCODING=utf-8",
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, env=env, cwd=PROJECT_DIR, timeout=timeout
        )
        rc, err, timed_out = completed.returncode, completed.stderr, False
    except subprocess.TimeoutExpired as exc:
        rc, err, timed_out = -1, (exc.stderr or ""), True
    elapsed = round(time.monotonic() - started, 3)
    return {
        "spider": spider, "returncode": rc, "elapsed_seconds": elapsed,
        "timed_out": timed_out, "stderr_tail": (err or "")[-800:],
        "output_path": str(output.relative_to(PROJECT_DIR)),
    }


def names_recall(rows: list[dict], expected: list[str]) -> dict[str, Any]:
    found = {r.get("name") or r.get("title") for r in rows}
    return recall_from_found(found, expected)


def recall_from_found(found_names, expected: list[str]) -> dict[str, Any]:
    found = set(found_names)
    missing = [n for n in expected if n not in found]
    return {
        "found_count": len(expected) - len(missing),
        "expected_count": len(expected),
        "recall": round((len(expected) - len(missing)) / len(expected), 3),
        "missing": missing,
    }


def export_csv(json_path: Path, csv_path: Path) -> int:
    import csv
    rows = read_json(json_path)
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return 0
    fields = sorted({k for r in rows if isinstance(r, dict) for k in r})
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})
    return len(rows)


def main() -> int:
    for d in (RAW_DIR, LOGS_DIR, SHOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    server = start_fixture_server()
    base_env = os.environ.copy()
    base_env["FIXTURE_BASE_URL"] = server.base_url

    write_json(RAW_DIR / "local_fixture_ground_truth.json",
               {"products": PRODUCTS, "article": ARTICLE, "dynamic_products": DYNAMIC_PRODUCTS})

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "scrapy-playwright",
        "versions": {
            "scrapy": importlib.metadata.version("Scrapy"),
            "scrapy_playwright": importlib.metadata.version("scrapy-playwright"),
            "playwright": importlib.metadata.version("playwright"),
        },
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "fixture_base_url": server.base_url,
        "transcripts": {},
        "tests": {},
    }
    T = summary["tests"]
    X = summary["transcripts"]

    def do(run_id: str, spider: str, env_extra: dict[str, str] | None = None, timeout: int = 120):
        env = dict(base_env)
        if env_extra:
            env.update(env_extra)
        out = RAW_DIR / f"{run_id}.json"
        log = LOGS_DIR / f"{run_id}.log"
        tr = run_spider(spider, out, log, env, timeout=timeout)
        X[run_id] = tr
        return read_json(out), tr

    try:
        expected_static = [p["name"] for p in PRODUCTS]
        expected_dynamic = [p["name"] for p in DYNAMIC_PRODUCTS]

        # --- Baseline / install checks ---
        qs_rows, qs_tr = do("quickstart_quotes", "quickstart_quotes_spider.py", timeout=60)
        T["quickstart_quotes"] = {
            "check": "official quickstart shape (static quotes, no browser)",
            "success": qs_tr["returncode"] == 0,
            "items": len(qs_rows),
        }

        # --- Static & native baseline (parity with Scrapy pack) ---
        st_rows, _ = do("native_static_catalog", "native_static_catalog_spider.py")
        T["native_static_catalog"] = {
            "check": "HTTP static recall", "items": len(st_rows),
            "product_recall": names_recall(st_rows, expected_static),
        }

        nd_rows, _ = do("native_dynamic_nojs", "native_dynamic_spider.py")
        T["native_dynamic_nojs"] = {
            "check": "native baseline gap: JS catalog without rendering",
            "product_cards_found": nd_rows[0].get("product_cards_found") if nd_rows else None,
            "expected_gap": 0,
        }

        api_rows, _ = do("native_dynamic_api", "native_dynamic_api_spider.py")
        T["native_dynamic_api"] = {
            "check": "HTTP replay of backing JSON API", "items": len(api_rows),
            "product_recall": names_recall(api_rows, expected_dynamic),
        }

        f_rows, _ = do("native_failure_500", "native_failure_spider.py")
        T["native_failure_500"] = {
            "check": "HTTP 500 handling (no browser)",
            "row": f_rows[0] if f_rows else None,
        }

        # --- Playwright rendering: the gap-closing headline ---
        pw_sel, _ = do("pw_dynamic_selectorwait", "pw_dynamic_spider.py",
                       {"PW_TARGET": "catalog", "PW_WAIT_MODE": "selector", "PW_DELAY_MS": "450"})
        pw_sel_names = pw_sel[0].get("product_names", []) if pw_sel else []
        T["pw_dynamic_selectorwait"] = {
            "check": "render + wait_for_selector -> gap closed",
            "row": pw_sel[0] if pw_sel else None,
            "product_recall": recall_from_found(pw_sel_names, expected_dynamic) if pw_sel else None,
        }

        # --- Readiness policy matrix on the SAME fixture (delay 450ms) ---
        pw_none, _ = do("pw_dynamic_nowait", "pw_dynamic_spider.py",
                        {"PW_TARGET": "catalog", "PW_WAIT_MODE": "none", "PW_DELAY_MS": "450"})
        T["pw_dynamic_nowait"] = {
            "check": "render, no explicit wait (delay 450ms)",
            "product_cards_found": pw_none[0].get("product_cards_found") if pw_none else None,
        }
        pw_fix_short, _ = do("pw_dynamic_fixed_short", "pw_dynamic_spider.py",
                             {"PW_TARGET": "catalog", "PW_WAIT_MODE": "fixed", "PW_DELAY_MS": "450", "PW_FIXED_MS": "100"})
        T["pw_dynamic_fixed_short"] = {
            "check": "render, fixed wait 100ms < 450ms delay",
            "product_cards_found": pw_fix_short[0].get("product_cards_found") if pw_fix_short else None,
        }
        pw_fix_long, _ = do("pw_dynamic_fixed_long", "pw_dynamic_spider.py",
                            {"PW_TARGET": "catalog", "PW_WAIT_MODE": "fixed", "PW_DELAY_MS": "450", "PW_FIXED_MS": "1200"})
        T["pw_dynamic_fixed_long"] = {
            "check": "render, fixed wait 1200ms > 450ms delay",
            "product_cards_found": pw_fix_long[0].get("product_cards_found") if pw_fix_long else None,
        }

        # --- Adversarial: selector never appears -> bounded timeout errback ---
        pw_never, _ = do("pw_dynamic_never", "pw_dynamic_spider.py",
                         {"PW_TARGET": "never", "PW_WAIT_MODE": "selector", "PW_TIMEOUT_MS": "3000"}, timeout=60)
        T["pw_dynamic_never"] = {
            "check": "selector never appears -> bounded PlaywrightTimeoutError",
            "row": pw_never[0] if pw_never else None,
        }

        # --- Adversarial: late DOM mutation vs selector-wait readiness ---
        pw_late, _ = do("pw_dynamic_late", "pw_dynamic_spider.py",
                        {"PW_TARGET": "late", "PW_WAIT_MODE": "selector", "PW_DELAY_MS": "1500", "PW_TIMEOUT_MS": "5000"})
        T["pw_dynamic_late"] = {
            "check": "late append after first paint: selector matches initial card, misses late one",
            "row": pw_late[0] if pw_late else None,
        }

        # --- Selective rendering inside one crawl ---
        mix_rows, _ = do("mixed_crawl_graph", "mixed_crawl_graph_spider.py")
        rendered = [r for r in mix_rows if r.get("rendered_with_playwright")]
        dyn_rows = [r for r in mix_rows if "/dynamic/" in r.get("url", "")]
        T["mixed_crawl_graph"] = {
            "check": "selective rendering: static via HTTP, dynamic via Playwright, one scheduler",
            "pages_seen": len(mix_rows),
            "pages_rendered_with_playwright": len(rendered),
            "dynamic_pages": [{"url": r["url"], "rendered": r["rendered_with_playwright"],
                               "cards": r["product_cards_found"]} for r in dyn_rows],
            "depth_counts": {str(d): sum(1 for r in mix_rows if r.get("depth") == d)
                             for d in sorted({r.get("depth") for r in mix_rows})},
            "in_scope": all(r["url"].startswith(server.base_url) for r in mix_rows),
        }

        # --- Screenshot evidence ---
        shot_path = SHOTS_DIR / "dynamic_catalog_rendered.png"
        ss_rows, _ = do("pw_screenshot", "pw_screenshot_spider.py",
                        {"PW_SCREENSHOT_PATH": str(shot_path),
                         "PW_SCREENSHOT_REL": str(shot_path.relative_to(PROJECT_DIR))})
        T["pw_screenshot"] = {
            "check": "full-page screenshot of rendered dynamic catalog",
            "product_cards_found": ss_rows[0].get("product_cards_found") if ss_rows else None,
            "screenshot_exists": shot_path.exists(),
            "screenshot_bytes": shot_path.stat().st_size if shot_path.exists() else 0,
        }

        # --- Public JS page with Playwright ---
        pq_rows, pq_tr = do("public_quotes_js", "public_quotes_js_spider.py", timeout=90)
        T["public_quotes_js"] = {
            "check": "public quotes.toscrape.com/js/ WITH Playwright (native pack saw 0)",
            "success": pq_tr["returncode"] == 0,
            "quote_nodes_found": pq_rows[0].get("quote_nodes_found") if pq_rows else None,
        }

        # --- Exports ---
        static_csv = export_csv(RAW_DIR / "native_static_catalog.json", RAW_DIR / "native_static_catalog.csv")
        api_csv = export_csv(RAW_DIR / "native_dynamic_api.json", RAW_DIR / "native_dynamic_api.csv")
        T["exports"] = {"check": "JSON already emitted; CSV export from same items",
                        "static_csv_rows": static_csv, "api_csv_rows": api_csv}

        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "correctness-summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
