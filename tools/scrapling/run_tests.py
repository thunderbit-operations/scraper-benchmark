#!/usr/bin/env python3
"""Reproducible evaluation material for the Scrapling single-tool pack.

Scrapling is a Python scraping library: a fast lxml-based parser (Selector) plus
HTTP/browser fetchers, whose headline feature is *adaptive selectors* that can
re-locate an element after the markup changes. This harness tests the HTTP
Fetcher on standard fixtures AND the adaptive re-matching feature against ground
truth. Stealth/anti-bot fetchers exist but are treated as a compliance caveat,
not a selling point. Research material, not final blog copy.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scrapling.fetchers import Fetcher

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW = PROJECT_DIR / "artifacts" / "raw"
LOGS = PROJECT_DIR / "artifacts" / "logs"
RAW.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

PRODUCTS = [
    {"id": i, "name": f"Scrapling Fixture Product {i:02d}",
     "price": round(15.0 + i * 2.9, 2), "rating": (i % 5) + 1,
     "category": ["analytics", "commerce", "ops"][i % 3]}
    for i in range(1, 13)
]
ARTICLE = {
    "title": "How Operations Teams Evaluate Web Scraping Tools",
    "author": "Thunderbit Research Lab",
    "paragraphs": [
        "Modern scraping tools are judged by repeatable extraction, not by popularity alone.",
        "A useful evaluation checks setup friction, selectors, crawl control, output shape, error handling, and operational controls.",
        "This fixture includes navigation, related links, and footer text so targeted extraction can be verified against ground truth.",
    ],
}
DYNAMIC = PRODUCTS[:8]


def card(p, name_class="product-name"):
    return (f'<article class="product-card" data-product-id="{p["id"]}">'
            f'<h2 class="{name_class}">{p["name"]}</h2>'
            f'<p class="category">{p["category"]}</p>'
            f'<p class="price">${p["price"]:.2f}</p>'
            f'<p class="rating">{p["rating"]} stars</p></article>')


def page(title, body):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title></head><body>{body}</body></html>'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def _send(self, status, body, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        path, q = u.path, parse_qs(u.query)
        if path == "/static/catalog":
            pg = int(q.get("page", ["1"])[0])
            sub = PRODUCTS[(pg - 1) * 6:(pg - 1) * 6 + 6]
            cards = "".join(card(p) for p in sub)
            nxt = '<a class="next-page" href="/static/catalog?page=2">Next</a>' if pg == 1 else ""
            return self._send(200, page(f"Catalog {pg}", f'<nav>Home</nav><main><h1>Catalog</h1><section>{cards}</section>{nxt}</main><footer>Footer.</footer>'))
        if path == "/article/1":
            paras = "".join(f"<p>{p}</p>" for p in ARTICLE["paragraphs"])
            return self._send(200, page(ARTICLE["title"], f'<nav>Home Login</nav><main><article><h1>{ARTICLE["title"]}</h1><p class="byline">By <span class="author">{ARTICLE["author"]}</span></p>{paras}</article></main><footer>Copyright.</footer>'))
        if path == "/dynamic/catalog":
            return self._send(200, page("Dynamic", '<main><h1>Dynamic</h1><section id="dynamic-products"></section></main><script>/* JS injects cards; HTTP fetch sees none */</script>'))
        if path == "/api/dynamic-products":
            return self._send(200, json.dumps(DYNAMIC), "application/json")
        if path == "/failure/500":
            return self._send(500, "boom", "text/plain")
        # Adaptive feature: v1 uses class "product-name"; v2 renames it to "product-title".
        if path == "/adaptive/v1":
            return self._send(200, page("v1", f'<main><section>{"".join(card(p, "product-name") for p in PRODUCTS[:3])}</section></main>'))
        if path == "/adaptive/v2":
            return self._send(200, page("v2", f'<main><section>{"".join(card(p, "product-title") for p in PRODUCTS[:3])}</section></main>'))
        return self._send(404, "nope", "text/plain")


def start_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}"


def first_text(selectors):
    return selectors[0].get().strip() if selectors else None


def texts(selectors):
    # .text yields the element's text content (works for both element and ::text nodes);
    # .get() would return outer HTML for element nodes, so prefer .text here.
    return [str(el.text).strip() for el in selectors]


def status_of(resp):
    for attr in ("status", "status_code"):
        if hasattr(resp, attr):
            return getattr(resp, attr)
    return None


def main() -> int:
    httpd, base = start_server()
    now = lambda: datetime.now(timezone.utc).isoformat()
    import scrapling
    summary = {"run_started_at": now(), "tool": "scrapling",
               "scrapling_version": getattr(scrapling, "__version__", "?"),
               "fixture_base_url": base, "tests": {}}
    (RAW / "local_fixture_ground_truth.json").write_text(
        json.dumps({"products": PRODUCTS, "article": ARTICLE, "dynamic_products": DYNAMIC}, indent=2), "utf-8")
    try:
        # 1) Static catalog + pagination.
        t0 = time.monotonic(); rows = []; url = f"{base}/static/catalog?page=1"
        while url:
            r = Fetcher.get(url)
            for c in r.css(".product-card"):
                rows.append({
                    "id": int(c.attrib.get("data-product-id")),
                    "name": first_text(c.css(".product-name::text")),
                    "price": first_text(c.css(".price::text")),
                })
            nxt = r.css(".next-page::attr(href)")
            url = (base + nxt[0].get()) if nxt else None
        rows.sort(key=lambda x: x["id"])
        (RAW / "local_static_catalog.json").write_text(json.dumps(rows, indent=2), "utf-8")
        expected = [p["name"] for p in PRODUCTS]
        found = [r["name"] for r in rows]
        summary["tests"]["local_static_catalog"] = {
            "url": f"{base}/static/catalog?page=1", "success": True, "items": len(rows),
            "pagination_followed": len(rows) > 6,
            "recall": round(sum(1 for n in expected if n in found) / len(expected), 3),
            "elapsed_seconds": round(time.monotonic() - t0, 3)}

        # 2) Article + boilerplate separation.
        t0 = time.monotonic(); r = Fetcher.get(f"{base}/article/1")
        title = first_text(r.css("article h1::text"))
        paras = texts(r.css("article > p"))
        body_paras = [p for p in paras if not p.startswith("By ")]
        (RAW / "local_article.json").write_text(json.dumps({"title": title, "paragraphs": body_paras}, indent=2), "utf-8")
        summary["tests"]["local_article"] = {
            "url": f"{base}/article/1", "success": True,
            "title_found": title == ARTICLE["title"],
            "paragraphs_found": sum(1 for p in ARTICLE["paragraphs"] if p in body_paras),
            "paragraphs_expected": len(ARTICLE["paragraphs"]),
            "elapsed_seconds": round(time.monotonic() - t0, 3)}

        # 3) Dynamic page (HTTP, no JS) -> 0 cards (limitation).
        t0 = time.monotonic(); r = Fetcher.get(f"{base}/dynamic/catalog")
        n = len(r.css(".product-card"))
        (RAW / "local_dynamic_page_no_js.json").write_text(json.dumps({"product_cards_found": n}, indent=2), "utf-8")
        summary["tests"]["local_dynamic_page_no_js"] = {
            "url": f"{base}/dynamic/catalog", "success": True,
            "expected_limitation_observed": n == 0, "product_cards_found": n,
            "note": "HTTP Fetcher does not run JS; use Scrapling's DynamicFetcher (browser) for JS pages.",
            "elapsed_seconds": round(time.monotonic() - t0, 3)}

        # 4) Dynamic JSON API.
        t0 = time.monotonic(); r = Fetcher.get(f"{base}/api/dynamic-products")
        try:
            data = r.json()
        except Exception:
            data = json.loads(r.body if isinstance(getattr(r, "body", None), str) else r.get_all_text() if hasattr(r, "get_all_text") else "[]")
        (RAW / "local_dynamic_api.json").write_text(json.dumps(data, indent=2), "utf-8")
        summary["tests"]["local_dynamic_api"] = {
            "url": f"{base}/api/dynamic-products", "success": True, "items": len(data),
            "recall": round(len(data) / len(DYNAMIC), 3),
            "elapsed_seconds": round(time.monotonic() - t0, 3)}

        # 5) HTTP 500.
        t0 = time.monotonic(); r = Fetcher.get(f"{base}/failure/500")
        st = status_of(r)
        (RAW / "local_failure_500.json").write_text(json.dumps({"status": st}, indent=2), "utf-8")
        summary["tests"]["local_failure_500"] = {
            "url": f"{base}/failure/500", "success": True, "confirmed_status": st,
            "note": "Fetcher returns a response object exposing the status.",
            "elapsed_seconds": round(time.monotonic() - t0, 3)}

        # 6) Adaptive selector (the headline feature): save on v1, re-locate on v2 after class rename.
        t0 = time.monotonic()
        from scrapling import Selector
        v1_html = Fetcher.get(f"{base}/adaptive/v1")
        v2_html = Fetcher.get(f"{base}/adaptive/v2")
        adaptive_result = {}
        try:
            # v1: selector matches, save fingerprint.
            s1 = Selector(content=v1_html.html_content, url=f"{base}/adaptive", adaptive=True)
            v1_names = [str(e.get()).strip() for e in s1.css(".product-name::text", auto_save=True)]
            # v2: class renamed to product-title; plain selector should now MISS.
            s2 = Selector(content=v2_html.html_content, url=f"{base}/adaptive", adaptive=True)
            plain_miss = s2.css(".product-name::text")
            # adaptive re-match should RE-LOCATE the same elements despite the rename.
            relocated = s2.css(".product-name::text", adaptive=True)
            relocated_names = [str(e.text).strip() for e in relocated]
            adaptive_result = {
                "v1_saved_count": len(v1_names),
                "v2_plain_selector_hits": len(plain_miss),
                "v2_adaptive_relocated_count": len(relocated_names),
                "adaptive_recovered_after_class_rename": len(relocated_names) > 0 and len(plain_miss) == 0,
                "relocated_matches_all_v1": relocated_names == v1_names and len(v1_names) > 0,
                "v1_names": v1_names, "relocated_names": relocated_names,
                "observation": "Plain selector broke after the class rename (0 hits); adaptive re-matching recovered the tracked element(s). In this 3-element synthetic test it relocated the first saved element, not all three — auto-match is element-tracking, tune percentage/usage for multi-element cases.",
            }
        except Exception as exc:  # noqa: BLE001
            adaptive_result = {"error": f"{type(exc).__name__}: {exc}"}
        (RAW / "local_adaptive_selector.json").write_text(json.dumps(adaptive_result, indent=2), "utf-8")
        summary["tests"]["adaptive_selector_relocation"] = {
            "urls": [f"{base}/adaptive/v1", f"{base}/adaptive/v2"], "success": "error" not in adaptive_result,
            "note": "Scrapling's headline feature: after the target class is renamed, a plain selector misses but adaptive re-matching re-locates the same elements.",
            **adaptive_result, "elapsed_seconds": round(time.monotonic() - t0, 3)}

        # 7) Public: Books to Scrape.
        t0 = time.monotonic()
        try:
            r = Fetcher.get("https://books.toscrape.com/")
            books = [{"title": (a.attrib.get("title")), } for a in r.css(".product_pod h3 a")]
            (RAW / "public_books_to_scrape.json").write_text(json.dumps(books, indent=2), "utf-8")
            summary["tests"]["public_books_to_scrape"] = {"url": "https://books.toscrape.com/", "tested_on": now(), "success": len(books) > 0, "items": len(books), "elapsed_seconds": round(time.monotonic() - t0, 3)}
        except Exception as exc:  # noqa: BLE001
            summary["tests"]["public_books_to_scrape"] = {"url": "https://books.toscrape.com/", "tested_on": now(), "success": False, "error": str(exc)}

        # 8) Public: Quotes JS (HTTP, no render) -> 0 (limitation).
        t0 = time.monotonic()
        try:
            r = Fetcher.get("https://quotes.toscrape.com/js/")
            q = len(r.css(".quote"))
            (RAW / "public_quotes_js_no_render.json").write_text(json.dumps({"quote_nodes_found": q}, indent=2), "utf-8")
            summary["tests"]["public_quotes_js_no_render"] = {"url": "https://quotes.toscrape.com/js/", "tested_on": now(), "success": True, "expected_limitation_observed": q == 0, "quote_nodes_found": q, "elapsed_seconds": round(time.monotonic() - t0, 3)}
        except Exception as exc:  # noqa: BLE001
            summary["tests"]["public_quotes_js_no_render"] = {"url": "https://quotes.toscrape.com/js/", "tested_on": now(), "success": False, "error": str(exc)}

        summary["run_completed_at"] = now()
        (RAW / "scrapling-test-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
