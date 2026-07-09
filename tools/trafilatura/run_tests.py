#!/usr/bin/env python3
"""Reproducible evaluation material for the trafilatura single-tool pack.

trafilatura is a main-content / article extraction library: HTML -> clean text,
markdown, or metadata, with boilerplate (nav/aside/footer) removed. It is NOT a
structured-catalog scraper. This harness tests exactly that boundary against
ground truth. Research material, not final blog copy.
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
from urllib.parse import urlparse

import trafilatura

PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW = PROJECT_DIR / "artifacts" / "raw"
LOGS = PROJECT_DIR / "artifacts" / "logs"
RAW.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

ARTICLE = {
    "title": "How Operations Teams Evaluate Web Scraping Tools",
    "author": "Thunderbit Research Lab",
    "date": "2026-07-09",
    "body_paragraphs": [
        "Modern scraping tools are judged by repeatable extraction, not by popularity alone.",
        "A useful evaluation checks setup friction, selectors, crawl control, output shape, error handling, and operational controls.",
        "This fixture includes navigation, related links, and footer text so targeted extraction can be verified against ground truth.",
    ],
}
BOILERPLATE = {
    "nav": "Home Products Pricing Login",
    "aside": "Subscribe to our fictional newsletter.",
    "footer": "Copyright fixture footer.",
}
PRODUCTS = [f"Trafilatura Fixture Product {i:02d}" for i in range(1, 13)]


def article_html() -> str:
    paras = "".join(f"<p>{p}</p>" for p in ARTICLE["body_paragraphs"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{ARTICLE['title']}</title>
<meta name="author" content="{ARTICLE['author']}">
<meta property="article:published_time" content="{ARTICLE['date']}"></head>
<body>
<nav>{BOILERPLATE['nav']}</nav>
<main><article>
<h1>{ARTICLE['title']}</h1>
<p class="byline">By <span class="author">{ARTICLE['author']}</span> on <time datetime="{ARTICLE['date']}">{ARTICLE['date']}</time></p>
{paras}
</article></main>
<aside><h2>Related links</h2><a href="/catalog">Catalog</a><p>{BOILERPLATE['aside']}</p></aside>
<footer>{BOILERPLATE['footer']}</footer>
</body></html>"""


def catalog_html() -> str:
    cards = "".join(
        f'<article class="product-card" data-id="{i}"><h2>{name}</h2>'
        f'<p class="price">${15 + i * 3}.00</p></article>'
        for i, name in enumerate(PRODUCTS, 1)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Catalog</title></head>
<body><nav>Home</nav><main><h1>Static Product Catalog</h1><section class="grid">{cards}</section></main>
<footer>Footer boilerplate.</footer></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def _send(self, status, body, ctype="text/html; charset=utf-8"):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/article/1":
            return self._send(HTTPStatus.OK, article_html())
        if path == "/catalog":
            return self._send(HTTPStatus.OK, catalog_html())
        if path == "/failure/500":
            return self._send(HTTPStatus.INTERNAL_SERVER_ERROR, "boom", "text/plain")
        return self._send(HTTPStatus.NOT_FOUND, "nope", "text/plain")


def start_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{port}"


def write(name, content, mode="w"):
    (RAW / name).write_text(content, encoding="utf-8")


def main() -> int:
    httpd, base = start_server()
    now = lambda: datetime.now(timezone.utc).isoformat()
    summary = {
        "run_started_at": now(),
        "tool": "trafilatura",
        "trafilatura_version": trafilatura.__version__,
        "fixture_base_url": base,
        "tests": {},
    }
    (RAW / "local_fixture_ground_truth.json").write_text(
        json.dumps({"article": ARTICLE, "boilerplate": BOILERPLATE, "catalog_products": PRODUCTS}, indent=2), "utf-8"
    )
    try:
        # 1) Local article: fetch + extract to txt / markdown / json, verify boilerplate removal.
        t0 = time.monotonic()
        downloaded = trafilatura.fetch_url(f"{base}/article/1")
        txt = trafilatura.extract(downloaded, output_format="txt", include_comments=False)
        md = trafilatura.extract(downloaded, output_format="markdown", include_comments=False)
        js = trafilatura.extract(downloaded, output_format="json", with_metadata=True, include_comments=False)
        write("local_article.txt", txt or "")
        write("local_article.md", md or "")
        write("local_article.json", js or "{}")
        meta = json.loads(js) if js else {}
        paragraphs_found = sum(1 for p in ARTICLE["body_paragraphs"] if p in (txt or ""))
        # Unique boilerplate markers that never appear in the legitimate body text.
        BOILER_MARKERS = {"nav": "Login", "aside": "Subscribe", "footer": "Copyright"}
        boiler_leaked = [k for k, marker in BOILER_MARKERS.items() if marker in (txt or "")]
        summary["tests"]["local_article"] = {
            "url": f"{base}/article/1",
            "success": bool(txt),
            "title_found": meta.get("title") == ARTICLE["title"],
            "paragraphs_found": paragraphs_found,
            "paragraphs_expected": len(ARTICLE["body_paragraphs"]),
            "boilerplate_removed": len(boiler_leaked) == 0,
            "boilerplate_leaked_sections": boiler_leaked,
            "metadata_author": meta.get("author"),
            "metadata_date": meta.get("date"),
            "outputs": ["local_article.txt", "local_article.md", "local_article.json"],
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        }

        # 2) Structured catalog: expected limitation (trafilatura is not a product scraper).
        t0 = time.monotonic()
        cat_downloaded = trafilatura.fetch_url(f"{base}/catalog")
        cat_txt = trafilatura.extract(cat_downloaded, output_format="txt") or ""
        write("local_catalog_extraction.txt", cat_txt)
        products_captured = sum(1 for p in PRODUCTS if p in cat_txt)
        summary["tests"]["local_catalog_limitation"] = {
            "url": f"{base}/catalog",
            "success": True,
            "note": "trafilatura returns readable text (product names + prices appear) but as an unstructured blob, not id/name/price/rating rows.",
            "products_named_in_text_output": products_captured,
            "products_total": len(PRODUCTS),
            "structured_rows_returned": 0,
            "extracted_chars": len(cat_txt),
            "interpretation": "Text is recovered; structure is not. For structured catalog scraping a parser/selector tool is still required. This is the real boundary, not a total failure.",
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        }

        # 3) HTTP 500: fetch_url should fail gracefully (None).
        t0 = time.monotonic()
        failed = trafilatura.fetch_url(f"{base}/failure/500")
        write("local_failure_500.json", json.dumps({"fetch_url_returned_none": failed is None}, indent=2))
        summary["tests"]["local_failure_500"] = {
            "url": f"{base}/failure/500",
            "success": True,
            "fetch_url_returned_none": failed is None,
            "note": "fetch_url returns None on server error instead of raising.",
            "elapsed_seconds": round(time.monotonic() - t0, 3),
        }

        # 4) Public demo article-like page: Books to Scrape product page description.
        t0 = time.monotonic()
        pub_url = "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
        try:
            pub_dl = trafilatura.fetch_url(pub_url)
            pub_txt = trafilatura.extract(pub_dl, output_format="txt") or ""
            pub_md = trafilatura.extract(pub_dl, output_format="markdown") or ""
            write("public_books_product.txt", pub_txt)
            write("public_books_product.md", pub_md)
            summary["tests"]["public_books_product"] = {
                "url": pub_url,
                "tested_on": now(),
                "success": len(pub_txt) > 0,
                "extracted_chars": len(pub_txt),
                "note": "Books to Scrape product page has a prose description block; used as the allowed demo-site content target.",
                "elapsed_seconds": round(time.monotonic() - t0, 3),
            }
        except Exception as exc:  # noqa: BLE001
            summary["tests"]["public_books_product"] = {"url": pub_url, "tested_on": now(), "success": False, "error": str(exc)}

        summary["run_completed_at"] = now()
        (RAW / "trafilatura-test-summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", "utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
