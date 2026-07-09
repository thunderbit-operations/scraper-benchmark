#!/usr/bin/env python3
"""Generate raw evaluation material for the Scrapy single-tool pack."""

from __future__ import annotations

import csv
import importlib.metadata
import json
import os
import platform
import socket
import subprocess
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
TESTS_DIR = PROJECT_DIR / "tests"
SPIDERS_DIR = TESTS_DIR / "spiders"
ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
RAW_DIR = ARTIFACTS_DIR / "raw"
LOGS_DIR = ARTIFACTS_DIR / "logs"


PRODUCTS = [
    {
        "id": i,
        "name": f"Scrapy Fixture Product {i:02d}",
        "price": round(15.0 + i * 2.9, 2),
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
        "Modern scraping tools are judged by repeatable extraction, not by popularity alone.",
        "A useful evaluation checks setup friction, selectors, crawl control, output shape, error handling, and operational controls.",
        "This fixture includes navigation, related links, and footer text so targeted extraction can be verified against ground truth.",
    ],
}


def html_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
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
    server_version = "ScrapyFixture/1.0"

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
  <h1>Scrapy Fixture Site</h1>
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
            payload = {"products": PRODUCTS, "article": ARTICLE, "dynamic_products": PRODUCTS[:8]}
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
            self.send_bytes(HTTPStatus.OK, json.dumps(PRODUCTS[:8]).encode("utf-8"), "application/json")
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
    thread = threading.Thread(target=httpd.serve_forever, name="scrapy-fixture-server", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://127.0.0.1:{port}")


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_spider(spider: str, output: Path, log: Path, env: dict[str, str]) -> dict[str, Any]:
    if output.exists():
        output.unlink()
    if log.exists():
        log.unlink()

    command = [
        sys.executable,
        "-m",
        "scrapy",
        "runspider",
        str(SPIDERS_DIR / spider),
        "-O",
        str(output),
        "-s",
        f"LOG_FILE={log}",
        "-s",
        "FEED_EXPORT_ENCODING=utf-8",
    ]
    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, text=True, env=env, cwd=PROJECT_DIR)
    elapsed = round(time.monotonic() - started, 3)
    transcript = {
        "command": command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "output_path": str(output),
        "log_path": str(log),
    }
    transcript_path = RAW_DIR / f"{output.stem}_run.json"
    write_json(transcript_path, transcript)
    if completed.returncode != 0:
        raise RuntimeError(f"{spider} failed; see {transcript_path}")
    return transcript


def export_csv(json_path: Path, csv_path: Path) -> int:
    rows = read_json(json_path)
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return 0
    fieldnames = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def names_recall(rows: list[dict[str, Any]], expected_names: list[str]) -> dict[str, Any]:
    found_names = {row.get("name") or row.get("title") for row in rows}
    missing = [name for name in expected_names if name not in found_names]
    return {
        "found_count": len(expected_names) - len(missing),
        "expected_count": len(expected_names),
        "recall": round((len(expected_names) - len(missing)) / len(expected_names), 3),
        "missing": missing,
    }


def main() -> int:
    for directory in (RAW_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    server = start_fixture_server()
    env = os.environ.copy()
    env["FIXTURE_BASE_URL"] = server.base_url

    ground_truth = {"products": PRODUCTS, "article": ARTICLE, "dynamic_products": PRODUCTS[:8]}
    write_json(RAW_DIR / "local_fixture_ground_truth.json", ground_truth)

    summary: dict[str, Any] = {
        "run_started_at": datetime.now(timezone.utc).isoformat(),
        "tool": "scrapy",
        "scrapy_version": importlib.metadata.version("Scrapy"),
        "python": sys.version,
        "platform": platform.platform(),
        "fixture_base_url": server.base_url,
        "tests": {},
    }

    try:
        runs = [
            ("quickstart_quotes_spider.py", "quickstart_quotes.json", "quickstart_quotes.log"),
            ("local_static_catalog_spider.py", "local_static_catalog.json", "local_static_catalog.log"),
            ("local_article_spider.py", "local_article.json", "local_article.log"),
            ("local_dynamic_page_spider.py", "local_dynamic_page_no_js.json", "local_dynamic_page_no_js.log"),
            ("local_dynamic_api_spider.py", "local_dynamic_api.json", "local_dynamic_api.log"),
            ("local_failure_spider.py", "local_failure_500.json", "local_failure_500.log"),
            ("local_crawl_graph_spider.py", "local_crawl_graph.json", "local_crawl_graph.log"),
            ("public_books_spider.py", "public_books_to_scrape.json", "public_books_to_scrape.log"),
            ("public_quotes_js_spider.py", "public_quotes_js_no_render.json", "public_quotes_js_no_render.log"),
        ]

        transcripts = {}
        for spider, output_name, log_name in runs:
            output = RAW_DIR / output_name
            log = LOGS_DIR / log_name
            transcripts[output_name] = run_spider(spider, output, log, env)

        for json_name in (
            "quickstart_quotes.json",
            "local_static_catalog.json",
            "local_dynamic_api.json",
            "public_books_to_scrape.json",
        ):
            export_csv(RAW_DIR / json_name, RAW_DIR / json_name.replace(".json", ".csv"))

        static_rows = read_json(RAW_DIR / "local_static_catalog.json")
        article_rows = read_json(RAW_DIR / "local_article.json")
        dynamic_page_rows = read_json(RAW_DIR / "local_dynamic_page_no_js.json")
        dynamic_api_rows = read_json(RAW_DIR / "local_dynamic_api.json")
        failure_rows = read_json(RAW_DIR / "local_failure_500.json")
        crawl_graph_rows = read_json(RAW_DIR / "local_crawl_graph.json")
        quickstart_rows = read_json(RAW_DIR / "quickstart_quotes.json")
        books_rows = read_json(RAW_DIR / "public_books_to_scrape.json")
        quotes_js_rows = read_json(RAW_DIR / "public_quotes_js_no_render.json")

        expected_static_names = [product["name"] for product in PRODUCTS]
        expected_dynamic_names = [product["name"] for product in PRODUCTS[:8]]

        article = article_rows[0] if article_rows else {}
        body_paragraphs = article.get("body_paragraphs") or []

        summary["tests"] = {
            "quickstart_quotes": {
                "url": "https://quotes.toscrape.com/tag/humor/",
                "success": True,
                "items": len(quickstart_rows),
                "authors_found": sorted({row.get("author") for row in quickstart_rows if row.get("author")}),
                "elapsed_seconds": transcripts["quickstart_quotes.json"]["elapsed_seconds"],
                "raw_output": "tools/scrapy/artifacts/raw/quickstart_quotes.json",
            },
            "local_static_catalog": {
                "url": f"{server.base_url}/static/catalog?page=1",
                "success": True,
                "items": len(static_rows),
                "product_recall": names_recall(static_rows, expected_static_names),
                "elapsed_seconds": transcripts["local_static_catalog.json"]["elapsed_seconds"],
                "raw_output": "tools/scrapy/artifacts/raw/local_static_catalog.json",
                "csv_output": "tools/scrapy/artifacts/raw/local_static_catalog.csv",
            },
            "local_article": {
                "url": f"{server.base_url}/article/1",
                "success": True,
                "title_found": article.get("title") == ARTICLE["title"],
                "paragraphs_found": sum(1 for paragraph in ARTICLE["body_paragraphs"] if paragraph in body_paragraphs),
                "paragraphs_expected": len(ARTICLE["body_paragraphs"]),
                "boilerplate_available_but_separated": bool(article.get("nav_text") or article.get("footer_text")),
                "elapsed_seconds": transcripts["local_article.json"]["elapsed_seconds"],
            },
            "local_dynamic_page_no_js": {
                "url": f"{server.base_url}/dynamic/catalog",
                "success": True,
                "expected_limitation_observed": dynamic_page_rows[0].get("product_cards_found") == 0 if dynamic_page_rows else False,
                "product_cards_found": dynamic_page_rows[0].get("product_cards_found") if dynamic_page_rows else None,
                "elapsed_seconds": transcripts["local_dynamic_page_no_js.json"]["elapsed_seconds"],
            },
            "local_dynamic_api": {
                "url": f"{server.base_url}/api/dynamic-products",
                "success": True,
                "items": len(dynamic_api_rows),
                "product_recall": names_recall(dynamic_api_rows, expected_dynamic_names),
                "elapsed_seconds": transcripts["local_dynamic_api.json"]["elapsed_seconds"],
            },
            "local_failure_500": {
                "url": f"{server.base_url}/failure/500",
                "success": True,
                "handled_status": failure_rows[0].get("status") if failure_rows else None,
                "elapsed_seconds": transcripts["local_failure_500.json"]["elapsed_seconds"],
            },
            "local_crawl_graph": {
                "url": server.base_url,
                "success": True,
                "pages_seen": len(crawl_graph_rows),
                "depth_counts": {
                    str(depth): sum(1 for row in crawl_graph_rows if row.get("depth") == depth)
                    for depth in sorted({row.get("depth") for row in crawl_graph_rows})
                },
                "elapsed_seconds": transcripts["local_crawl_graph.json"]["elapsed_seconds"],
            },
            "public_books_to_scrape": {
                "url": "https://books.toscrape.com/",
                "success": True,
                "items": len(books_rows),
                "raw_output": "tools/scrapy/artifacts/raw/public_books_to_scrape.json",
                "csv_output": "tools/scrapy/artifacts/raw/public_books_to_scrape.csv",
                "elapsed_seconds": transcripts["public_books_to_scrape.json"]["elapsed_seconds"],
            },
            "public_quotes_js_no_render": {
                "url": "https://quotes.toscrape.com/js/",
                "success": True,
                "expected_limitation_observed": quotes_js_rows[0].get("quote_nodes_found") == 0 if quotes_js_rows else False,
                "quote_nodes_found": quotes_js_rows[0].get("quote_nodes_found") if quotes_js_rows else None,
                "elapsed_seconds": transcripts["public_quotes_js_no_render.json"]["elapsed_seconds"],
            },
        }

        summary["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        write_json(RAW_DIR / "scrapy-test-summary.json", summary)
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
