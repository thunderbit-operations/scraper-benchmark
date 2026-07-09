#!/usr/bin/env python3
"""Reproducible evaluation material for the Firecrawl single-tool pack.

Tests a SELF-HOSTED Firecrawl instance (no cloud key) via its HTTP API:
scrape -> LLM-ready markdown, including a JS-rendered page (routed through the
bundled playwright-service). Public scraping-friendly demo sites only.
Research material, not final blog copy.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Point this at your own self-hosted Firecrawl instance (docker compose default: 3002).
API = os.environ.get("FIRECRAWL_API_URL", "http://localhost:3002")
# Self-hosted Firecrawl bypasses auth when Supabase is not configured, so any bearer
# value works. Set FIRECRAWL_API_KEY if your instance enforces authentication.
API_KEY = os.environ.get("FIRECRAWL_API_KEY", "<YOUR_FIRECRAWL_API_KEY>")
PROJECT_DIR = Path(__file__).resolve().parent
RAW = PROJECT_DIR / "results"
RAW.mkdir(parents=True, exist_ok=True)
now = lambda: datetime.now(timezone.utc).isoformat()


def post(path, payload, timeout=120):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API + path, data=data,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {API_KEY}"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


def wait_for_api(retries=60, delay=5):
    for i in range(retries):
        try:
            with urllib.request.urlopen(API + "/", timeout=5) as r:
                if r.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def main() -> int:
    summary = {"run_started_at": now(), "tool": "firecrawl",
               "mode": "self_hosted_docker", "api": API, "tests": {}}

    if not wait_for_api():
        summary["blocker"] = "Self-hosted API did not become reachable at " + API
        summary["run_completed_at"] = now()
        (RAW / "firecrawl-test-summary.json").write_text(json.dumps(summary, indent=2), "utf-8")
        print("API not reachable")
        return 2

    # 1) Scrape a static public page -> markdown (the core LLM-ready value).
    t0 = time.time()
    try:
        st, resp = post("/v1/scrape", {"url": "https://books.toscrape.com/", "formats": ["markdown", "html"]})
        data = resp.get("data", {})
        md = data.get("markdown", "")
        (RAW / "public_books_scrape.md").write_text(md, "utf-8")
        (RAW / "public_books_scrape_response.json").write_text(json.dumps(resp, indent=2)[:200000], "utf-8")
        summary["tests"]["scrape_static_markdown"] = {
            "url": "https://books.toscrape.com/", "tested_on": now(), "http_status": st,
            "success": resp.get("success", False) and len(md) > 0,
            "markdown_chars": len(md),
            "has_metadata": bool(data.get("metadata")),
            "title": (data.get("metadata") or {}).get("title"),
            "elapsed_seconds": round(time.time() - t0, 2),
        }
    except Exception as exc:  # noqa: BLE001
        summary["tests"]["scrape_static_markdown"] = {"url": "https://books.toscrape.com/", "success": False, "error": repr(exc)}

    # 2) Scrape a JS-rendered public page -> markdown (routes through playwright-service).
    t0 = time.time()
    try:
        st, resp = post("/v1/scrape", {"url": "https://quotes.toscrape.com/js/", "formats": ["markdown"]})
        data = resp.get("data", {})
        md = data.get("markdown", "")
        (RAW / "public_quotes_js_scrape.md").write_text(md, "utf-8")
        # Ground-truth-ish signal: rendered quotes contain the well-known Einstein quote author.
        summary["tests"]["scrape_js_markdown"] = {
            "url": "https://quotes.toscrape.com/js/", "tested_on": now(), "http_status": st,
            "success": resp.get("success", False) and len(md) > 0,
            "markdown_chars": len(md),
            "mentions_author_einstein": "Einstein" in md,
            "note": "JS page; Firecrawl self-host renders it via the bundled playwright-service.",
            "elapsed_seconds": round(time.time() - t0, 2),
        }
    except Exception as exc:  # noqa: BLE001
        summary["tests"]["scrape_js_markdown"] = {"url": "https://quotes.toscrape.com/js/", "success": False, "error": repr(exc)}

    # 3) Error handling: scrape a non-existent host.
    t0 = time.time()
    try:
        st, resp = post("/v1/scrape", {"url": "https://this-domain-should-not-exist-thunderbit-test.invalid/", "formats": ["markdown"]}, timeout=60)
        summary["tests"]["scrape_error_case"] = {"url": "invalid host", "tested_on": now(), "http_status": st, "success": True, "api_success_flag": resp.get("success"), "error_field": resp.get("error"), "note": "Non-2xx target: API returns a structured error, not a crash.", "elapsed_seconds": round(time.time() - t0, 2)}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")[:2000]
        except Exception:
            pass
        summary["tests"]["scrape_error_case"] = {"url": "invalid host", "tested_on": now(), "success": True, "http_status": exc.code, "structured_error_body": body, "note": "API surfaced an HTTP error status for the bad target."}
    except Exception as exc:  # noqa: BLE001
        summary["tests"]["scrape_error_case"] = {"url": "invalid host", "success": False, "error": repr(exc)}

    summary["run_completed_at"] = now()
    (RAW / "firecrawl-test-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
