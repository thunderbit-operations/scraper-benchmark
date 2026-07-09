#!/usr/bin/env python3
"""Generate raw evaluation material for the Crawl4AI single-tool review."""

from __future__ import annotations

import asyncio
import base64
import importlib.metadata
import json
import platform
import socket
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


PROJECT_DIR = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
RAW_DIR = ARTIFACTS_DIR / "raw"
LOGS_DIR = ARTIFACTS_DIR / "logs"
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"


PRODUCTS = [
    {
        "id": i,
        "name": f"Fixture Product {i:02d}",
        "price": round(19.5 + i * 3.7, 2),
        "rating": (i % 5) + 1,
        "category": ["analytics", "commerce", "ops"][i % 3],
    }
    for i in range(1, 13)
]

ARTICLE = {
    "title": "How Operations Teams Evaluate Web Scraping Tools",
    "author": "Thunderbit Research Lab",
    "date": "2026-07-07",
    "body_paragraphs": [
        "Modern scraping tools are no longer judged only by whether they can download HTML.",
        "A useful evaluation checks setup friction, JavaScript rendering, structured output, retry behavior, and how cleanly the result can feed downstream AI or spreadsheet workflows.",
        "This fixture intentionally includes navigation, related links, and promotional text so extraction quality can be inspected instead of assumed.",
    ],
}


def html_page(title: str, body: str, extra_head: str = "") -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  {extra_head}
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 32px auto; line-height: 1.45; }}
    nav, footer, aside {{ color: #666; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .product-card {{ border: 1px solid #ddd; padding: 12px; }}
    .price {{ font-weight: 700; }}
  </style>
</head>
<body>
{body}
</body>
</html>""".encode("utf-8")


def product_card(product: dict[str, Any]) -> str:
    return f"""<article class="product-card" data-product-id="{product['id']}">
  <h2 class="product-name">{product['name']}</h2>
  <p class="category">{product['category']}</p>
  <p class="price">${product['price']:.2f}</p>
  <p class="rating">{product['rating']} stars</p>
  <a class="detail-link" href="/product/{product['id']}">View detail</a>
</article>"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "Crawl4AIFixture/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_bytes(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/robots.txt":
            self.send_bytes(
                HTTPStatus.OK,
                b"User-agent: *\nAllow: /\nDisallow: /blocked-by-robots\nCrawl-delay: 1\n",
                "text/plain; charset=utf-8",
            )
            return

        if path == "/":
            body = """<main>
  <h1>Crawl4AI Fixture Site</h1>
  <ul>
    <li><a href="/static/catalog?page=1">Static catalog</a></li>
    <li><a href="/dynamic/catalog">Dynamic catalog</a></li>
    <li><a href="/article/1">Article fixture</a></li>
    <li><a href="/failure/500">Failure fixture</a></li>
  </ul>
</main>"""
            self.send_bytes(HTTPStatus.OK, html_page("Fixture Home", body))
            return

        if path == "/ground-truth.json":
            payload = {"products": PRODUCTS, "article": ARTICLE}
            self.send_bytes(HTTPStatus.OK, json.dumps(payload, indent=2).encode("utf-8"), "application/json")
            return

        if path == "/static/catalog":
            page = int(query.get("page", ["1"])[0])
            per_page = 6
            start = (page - 1) * per_page
            subset = PRODUCTS[start : start + per_page]
            cards = "\n".join(product_card(product) for product in subset)
            next_link = '<a class="next-page" href="/static/catalog?page=2">Next page</a>' if page == 1 else ""
            body = f"""<nav><a href="/">Home</a> | <a href="/article/1">Research article</a></nav>
<main>
  <h1>Static Product Catalog</h1>
  <section class="grid">{cards}</section>
  {next_link}
</main>
<footer>Footer boilerplate that should not be treated as product data.</footer>"""
            self.send_bytes(HTTPStatus.OK, html_page(f"Static Catalog Page {page}", body))
            return

        if path.startswith("/product/"):
            product_id = int(path.rsplit("/", 1)[-1])
            product = PRODUCTS[product_id - 1]
            body = f"""<main>
  <article class="product-detail" data-product-id="{product['id']}">
    <h1>{product['name']}</h1>
    <dl>
      <dt>Price</dt><dd class="price">${product['price']:.2f}</dd>
      <dt>Rating</dt><dd>{product['rating']} stars</dd>
      <dt>Category</dt><dd>{product['category']}</dd>
    </dl>
  </article>
</main>"""
            self.send_bytes(HTTPStatus.OK, html_page(product["name"], body))
            return

        if path == "/dynamic/catalog":
            body = """<main>
  <h1>Dynamic Product Catalog</h1>
  <p id="status">Loading products...</p>
  <section id="dynamic-products" class="grid"></section>
</main>
<script>
setTimeout(async () => {
  const response = await fetch('/api/dynamic-products');
  const products = await response.json();
  document.querySelector('#status').textContent = 'Loaded ' + products.length + ' products';
  document.querySelector('#dynamic-products').innerHTML = products.map((product) => `
    <article class="product-card" data-product-id="${product.id}">
      <h2 class="product-name">${product.name}</h2>
      <p class="category">${product.category}</p>
      <p class="price">$${Number(product.price).toFixed(2)}</p>
      <p class="rating">${product.rating} stars</p>
    </article>
  `).join('');
}, 450);
</script>"""
            self.send_bytes(HTTPStatus.OK, html_page("Dynamic Catalog", body))
            return

        if path == "/api/dynamic-products":
            payload = PRODUCTS[:8]
            self.send_bytes(HTTPStatus.OK, json.dumps(payload).encode("utf-8"), "application/json")
            return

        if path == "/article/1":
            body = f"""<nav>Home | Products | Pricing | Login</nav>
<main>
  <article>
    <h1>{ARTICLE['title']}</h1>
    <p class="byline">By <span class="author">{ARTICLE['author']}</span> on <time>{ARTICLE['date']}</time></p>
    {"".join(f"<p>{paragraph}</p>" for paragraph in ARTICLE["body_paragraphs"])}
  </article>
</main>
<aside>
  <h2>Related links</h2>
  <a href="/static/catalog?page=1">Static catalog</a>
  <p>Subscribe to our fictional newsletter.</p>
</aside>
<footer>Copyright fixture footer.</footer>"""
            self.send_bytes(HTTPStatus.OK, html_page(ARTICLE["title"], body))
            return

        if path == "/failure/500":
            self.send_bytes(HTTPStatus.INTERNAL_SERVER_ERROR, b"Intentional fixture failure", "text/plain")
            return

        if path == "/failure/429":
            self.send_response(HTTPStatus.TOO_MANY_REQUESTS)
            self.send_header("Retry-After", "2")
            self.end_headers()
            self.wfile.write(b"Intentional fixture rate limit")
            return

        self.send_bytes(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")


@dataclass
class FixtureServer:
    httpd: ThreadingHTTPServer
    thread: threading.Thread
    base_url: str

    def stop(self) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def start_fixture_server() -> FixtureServer:
    port = find_free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="fixture-server", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://127.0.0.1:{port}")


def markdown_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    for attr in ("raw_markdown", "fit_markdown", "markdown"):
        text = getattr(value, attr, None)
        if isinstance(text, str):
            return text
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def product_recall(text: str, products: list[dict[str, Any]]) -> dict[str, Any]:
    found = [product["name"] for product in products if product["name"] in text]
    return {
        "found_count": len(found),
        "expected_count": len(products),
        "recall": round(len(found) / len(products), 4) if products else 0,
        "missing": [product["name"] for product in products if product["name"] not in found],
    }


def parse_extracted_content(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


async def run_tests() -> dict[str, Any]:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig, JsonCssExtractionStrategy
    from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy

    server = start_fixture_server()
    base = server.base_url
    results: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "crawl4ai",
        "crawl4ai_version": importlib.metadata.version("crawl4ai"),
        "python": sys.version,
        "platform": platform.platform(),
        "fixture_base_url": base,
        "tests": {},
    }

    schema = {
        "name": "Fixture products",
        "baseSelector": ".product-card",
        "fields": [
            {"name": "name", "selector": ".product-name", "type": "text"},
            {"name": "category", "selector": ".category", "type": "text"},
            {"name": "price", "selector": ".price", "type": "text"},
            {"name": "rating", "selector": ".rating", "type": "text"},
            {"name": "detail_url", "selector": ".detail-link", "type": "attribute", "attribute": "href"},
        ],
    }

    browser_config = BrowserConfig(headless=True, java_script_enabled=True)
    async with AsyncWebCrawler(config=browser_config) as crawler:
        cases = [
            ("official_quickstart_example_com", "https://example.com", CrawlerRunConfig(cache_mode=CacheMode.BYPASS)),
            ("local_static_markdown", f"{base}/static/catalog?page=1", CrawlerRunConfig(cache_mode=CacheMode.BYPASS)),
            (
                "local_static_css_extraction",
                f"{base}/static/catalog?page=1",
                CrawlerRunConfig(cache_mode=CacheMode.BYPASS, extraction_strategy=JsonCssExtractionStrategy(schema)),
            ),
            (
                "local_dynamic_markdown_wait",
                f"{base}/dynamic/catalog",
                CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for="css:.product-card"),
            ),
            (
                "local_dynamic_css_extraction",
                f"{base}/dynamic/catalog",
                CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    wait_for="css:.product-card",
                    extraction_strategy=JsonCssExtractionStrategy(schema),
                ),
            ),
            ("local_article_markdown", f"{base}/article/1", CrawlerRunConfig(cache_mode=CacheMode.BYPASS)),
            (
                "local_dynamic_screenshot",
                f"{base}/dynamic/catalog",
                CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for="css:.product-card", screenshot=True),
            ),
            ("local_failure_500", f"{base}/failure/500", CrawlerRunConfig(cache_mode=CacheMode.BYPASS)),
            ("public_books_to_scrape", "https://books.toscrape.com/", CrawlerRunConfig(cache_mode=CacheMode.BYPASS)),
            ("public_quotes_js", "https://quotes.toscrape.com/js/", CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for="css:.quote")),
            (
                "public_quotes_js_screenshot",
                "https://quotes.toscrape.com/js/",
                CrawlerRunConfig(cache_mode=CacheMode.BYPASS, wait_for="css:.quote", screenshot=True),
            ),
        ]

        for name, url, config in cases:
            started = time.perf_counter()
            entry: dict[str, Any] = {"url": url}
            try:
                result = await crawler.arun(url=url, config=config)
                elapsed = time.perf_counter() - started
                markdown = markdown_text(getattr(result, "markdown", None))
                extracted = parse_extracted_content(getattr(result, "extracted_content", None))
                entry.update(
                    {
                        "success": bool(getattr(result, "success", False)),
                        "status_code": getattr(result, "status_code", None),
                        "elapsed_seconds": round(elapsed, 3),
                        "markdown_chars": len(markdown),
                        "error_message": getattr(result, "error_message", None),
                        "extracted_type": type(extracted).__name__ if extracted is not None else None,
                    }
                )
                if name.startswith("local_static"):
                    entry["product_recall"] = product_recall(markdown, PRODUCTS[:6])
                if name.startswith("local_dynamic"):
                    entry["product_recall"] = product_recall(markdown, PRODUCTS[:8])
                if name == "local_article_markdown":
                    entry["article_body_hits"] = {
                        "title": ARTICLE["title"] in markdown,
                        "paragraphs_found": sum(paragraph in markdown for paragraph in ARTICLE["body_paragraphs"]),
                        "paragraphs_expected": len(ARTICLE["body_paragraphs"]),
                        "boilerplate_present": "Subscribe to our fictional newsletter" in markdown,
                    }
                screenshot = getattr(result, "screenshot", None)
                if screenshot:
                    screenshot_path = SCREENSHOTS_DIR / f"{name}.png"
                    screenshot_path.write_bytes(base64.b64decode(screenshot))
                    entry["screenshot_path"] = str(screenshot_path)
                    entry["screenshot_bytes"] = screenshot_path.stat().st_size
                write_text(RAW_DIR / f"{name}.md", markdown)
                write_json(
                    RAW_DIR / f"{name}.json",
                    {
                        "summary": entry,
                        "extracted_content": extracted,
                        "markdown_preview": markdown[:1200],
                    },
                )
            except Exception as exc:
                elapsed = time.perf_counter() - started
                entry.update(
                    {
                        "success": False,
                        "elapsed_seconds": round(elapsed, 3),
                        "exception_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
            results["tests"][name] = entry

        multi_started = time.perf_counter()
        multi_urls = [f"{base}/product/{i}" for i in range(1, 7)]
        multi_entry: dict[str, Any] = {"urls": multi_urls}
        try:
            multi_results = await crawler.arun_many(multi_urls, config=CrawlerRunConfig(cache_mode=CacheMode.BYPASS))
            product_hits: list[str] = []
            pages: list[dict[str, Any]] = []
            for item in multi_results:
                item_markdown = markdown_text(getattr(item, "markdown", None))
                for product in PRODUCTS[:6]:
                    if product["name"] in item_markdown:
                        product_hits.append(product["name"])
                pages.append(
                    {
                        "url": getattr(item, "url", None),
                        "success": bool(getattr(item, "success", False)),
                        "status_code": getattr(item, "status_code", None),
                        "markdown_chars": len(item_markdown),
                        "error_message": getattr(item, "error_message", None),
                    }
                )
            multi_entry.update(
                {
                    "success": all(page["success"] for page in pages),
                    "elapsed_seconds": round(time.perf_counter() - multi_started, 3),
                    "pages": pages,
                    "product_detail_recall": {
                        "found_count": len(set(product_hits)),
                        "expected_count": 6,
                        "recall": round(len(set(product_hits)) / 6, 4),
                        "missing": [
                            product["name"]
                            for product in PRODUCTS[:6]
                            if product["name"] not in set(product_hits)
                        ],
                    },
                }
            )
        except Exception as exc:
            multi_entry.update(
                {
                    "success": False,
                    "elapsed_seconds": round(time.perf_counter() - multi_started, 3),
                    "exception_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
        results["tests"]["local_arun_many_product_details"] = multi_entry
        write_json(RAW_DIR / "local_arun_many_product_details.json", multi_entry)

        deep_started = time.perf_counter()
        deep_entry: dict[str, Any] = {"url": base}
        try:
            deep_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=1, include_external=False, max_pages=8),
                scraping_strategy=LXMLWebScrapingStrategy(),
                stream=False,
            )
            deep_results = await crawler.arun(base, config=deep_config)
            pages = []
            depth_counts: dict[str, int] = {}
            for item in deep_results:
                item_markdown = markdown_text(getattr(item, "markdown", None))
                depth = str(getattr(item, "metadata", {}).get("depth", 0))
                depth_counts[depth] = depth_counts.get(depth, 0) + 1
                pages.append(
                    {
                        "url": getattr(item, "url", None),
                        "success": bool(getattr(item, "success", False)),
                        "status_code": getattr(item, "status_code", None),
                        "depth": getattr(item, "metadata", {}).get("depth", 0),
                        "markdown_chars": len(item_markdown),
                        "error_message": getattr(item, "error_message", None),
                    }
                )
            deep_entry.update(
                {
                    "success": any(page["success"] for page in pages),
                    "elapsed_seconds": round(time.perf_counter() - deep_started, 3),
                    "page_count": len(pages),
                    "depth_counts": depth_counts,
                    "pages": pages,
                }
            )
        except Exception as exc:
            deep_entry.update(
                {
                    "success": False,
                    "elapsed_seconds": round(time.perf_counter() - deep_started, 3),
                    "exception_type": type(exc).__name__,
                    "error_message": str(exc),
                }
            )
        results["tests"]["local_bfs_deep_crawl"] = deep_entry
        write_json(RAW_DIR / "local_bfs_deep_crawl.json", deep_entry)

    server.stop()
    results["run_finished_at"] = datetime.now(timezone.utc).isoformat()
    return results


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        results = asyncio.run(run_tests())
        results["total_elapsed_seconds"] = round(time.perf_counter() - started, 3)
        write_json(RAW_DIR / "crawl4ai-test-summary.json", results)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        failure = {
            "run_started_at": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "exception_type": type(exc).__name__,
            "error_message": str(exc),
            "python": sys.version,
            "platform": platform.platform(),
        }
        write_json(RAW_DIR / "crawl4ai-test-runner-failure.json", failure)
        print(json.dumps(failure, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
