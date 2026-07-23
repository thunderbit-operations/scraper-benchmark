#!/usr/bin/env python3
"""Shared local fixture server for the Scrapy-Playwright evidence pack.

Design goal: same-fixture parity with the existing single-tool Scrapy pack so
the two packs are cross-comparable on identical ground truth. PRODUCTS and
ARTICLE mirror tools/scrapy/tests/run_scrapy_material_tests.py exactly.

Extra routes added for scrapy-playwright hypotheses:
  /dynamic/catalog?delay_ms=N   configurable delayed-DOM render (ground truth = 8 cards)
  /dynamic/never                renders, but the awaited selector is NEVER inserted
  /dynamic/late?delay_ms=N      a late DOM mutation after the initial paint
The classic routes (/, /static/catalog, /product/<id>, /article/1,
/api/dynamic-products, /failure/500, /ground-truth.json, /robots.txt) are
byte-for-byte compatible with the Scrapy pack.
"""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


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

# Ground truth for the dynamic catalog: the first 8 products, rendered by JS only.
DYNAMIC_PRODUCTS = PRODUCTS[:8]


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


def _dynamic_script(delay_ms: int) -> str:
    # Renders product cards into #dynamic-products after delay_ms via fetch.
    return f"""<script>
setTimeout(async () => {{
  const response = await fetch('/api/dynamic-products');
  const products = await response.json();
  document.querySelector('#status').textContent = 'Loaded ' + products.length + ' products';
  document.querySelector('#dynamic-products').innerHTML = products.map((product) => `
    <article class="product-card" data-product-id="${{product.id}}">
      <h2 class="product-name">${{product.name}}</h2>
      <p class="category">${{product.category}}</p>
      <p class="price">$${{Number(product.price).toFixed(2)}}</p>
      <p class="rating">${{product.rating}} stars</p>
    </article>
  `).join('');
  document.querySelector('#dynamic-products').setAttribute('data-loaded', 'true');
}}, {delay_ms});
</script>"""


class FixtureHandler(BaseHTTPRequestHandler):
    server_version = "ScrapyPlaywrightFixture/1.0"

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
  <h1>Scrapy-Playwright Fixture Site</h1>
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
            payload = {"products": PRODUCTS, "article": ARTICLE, "dynamic_products": DYNAMIC_PRODUCTS}
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

        # Configurable delayed-DOM dynamic catalog. Ground truth = 8 cards after delay.
        if path == "/dynamic/catalog":
            delay_ms = int(query.get("delay_ms", ["450"])[0])
            body = f"""<main>
  <h1>Dynamic Product Catalog</h1>
  <p id="status">Loading products...</p>
  <section id="dynamic-products" class="grid"></section>
</main>
{_dynamic_script(delay_ms)}"""
            self.send_bytes(HTTPStatus.OK, html_page("Dynamic Catalog", body))
            return

        # Renders, but the awaited selector (.product-card) is NEVER inserted.
        if path == "/dynamic/never":
            body = """<main>
  <h1>Dynamic Catalog (broken)</h1>
  <p id="status">Loading products...</p>
  <section id="dynamic-products" class="grid"></section>
</main>
<script>
setTimeout(() => {
  document.querySelector('#status').textContent = 'Failed to load products';
}, 200);
</script>"""
            self.send_bytes(HTTPStatus.OK, html_page("Dynamic Catalog Broken", body))
            return

        # Late DOM mutation: an extra card appended well after the first paint.
        if path == "/dynamic/late":
            delay_ms = int(query.get("delay_ms", ["1500"])[0])
            body = f"""<main>
  <h1>Late Update Catalog</h1>
  <section id="dynamic-products" class="grid">
    <article class="product-card" data-product-id="1"><h2 class="product-name">Scrapy Fixture Product 01</h2></article>
  </section>
</main>
<script>
setTimeout(() => {{
  const el = document.createElement('article');
  el.className = 'product-card';
  el.setAttribute('data-product-id', '99');
  el.innerHTML = '<h2 class="product-name">Late Product 99</h2>';
  document.querySelector('#dynamic-products').appendChild(el);
  document.querySelector('#dynamic-products').setAttribute('data-late', 'true');
}}, {delay_ms});
</script>"""
            self.send_bytes(HTTPStatus.OK, html_page("Late Update Catalog", body))
            return

        if path == "/api/dynamic-products":
            self.send_bytes(HTTPStatus.OK, json.dumps(DYNAMIC_PRODUCTS).encode("utf-8"), "application/json")
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


def start_fixture_server(port: int | None = None) -> FixtureServer:
    port = port or find_free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), FixtureHandler)
    thread = threading.Thread(target=httpd.serve_forever, name="sp-fixture-server", daemon=True)
    thread.start()
    return FixtureServer(httpd=httpd, thread=thread, base_url=f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    # Manual smoke: serve on a fixed port for local inspection.
    server = start_fixture_server(8899)
    print(f"Serving fixtures at {server.base_url}")
    try:
        server.thread.join()
    except KeyboardInterrupt:
        server.stop()
