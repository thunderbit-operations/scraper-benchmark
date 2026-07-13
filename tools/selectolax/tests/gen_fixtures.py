#!/usr/bin/env python3
"""Generate synthetic HTML fixtures of controlled sizes for benchmarking.

Sizes targeted: ~1KB, ~10KB, ~100KB, ~1MB, ~10MB.
Also generates a 100k-node "wide" page for throughput testing.
Deterministic (fixed seed) so runs are reproducible.
"""
import os
import random
import sys

random.seed(42)
FIXTURES = os.environ.get("SLX_SYNTH_DIR") or os.path.join(
    os.path.dirname(__file__), "..", "artifacts", "fixtures", "synthetic")
os.makedirs(FIXTURES, exist_ok=True)

WORDS = ("lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod "
         "tempor incididunt ut labore et dolore magna aliqua enim ad minim veniam").split()


def sentence(n=12):
    return " ".join(random.choice(WORDS) for _ in range(n))


def product_card(i):
    return (
        f'<div class="product-card" data-id="{i}" data-sku="SKU-{i:05d}">'
        f'<h3 class="title">Product {i}</h3>'
        f'<span class="price" data-currency="usd">${random.randint(5, 500)}.{random.randint(0,99):02d}</span>'
        f'<p class="desc">{sentence(20)}</p>'
        f'<a class="link" href="/product/{i}" rel="nofollow">Details {i}</a>'
        f'<ul class="tags"><li>tag-{i%7}</li><li>tag-{i%3}</li></ul>'
        f'</div>'
    )


def build_page(n_cards):
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<title>Synthetic Catalog</title>',
        '<meta name="description" content="A synthetic test page for benchmarking">',
        '</head><body>',
        '<header><nav><a href="/">Home</a><a href="/about">About</a></nav></header>',
        '<main id="content"><h1>Catalog</h1><div class="grid">',
    ]
    for i in range(n_cards):
        parts.append(product_card(i))
    parts.append('</div></main><footer><p>Footer boilerplate</p></footer></body></html>')
    return "".join(parts)


def build_to_target_bytes(target_bytes):
    """Grow card count until HTML byte length >= target."""
    n = max(1, target_bytes // 400)
    html = build_page(n)
    while len(html.encode("utf-8")) < target_bytes:
        n = int(n * 1.3) + 1
        html = build_page(n)
    return html, n


def main():
    targets = {
        "1kb": 1_000,
        "10kb": 10_000,
        "100kb": 100_000,
        "1mb": 1_000_000,
        "10mb": 10_000_000,
    }
    manifest = {}
    for name, tgt in targets.items():
        html, n = build_to_target_bytes(tgt)
        path = os.path.join(FIXTURES, f"page_{name}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        b = len(html.encode("utf-8"))
        # store a relative basename in the manifest so downstream artifacts don't
        # embed an absolute local path (keeps the public repo clean)
        manifest[name] = {"path": f"page_{name}.html", "bytes": b, "cards": n}
        print(f"{name}: {b:,} bytes, {n} cards -> {path}")

    # 100k-node wide page: flat list of simple nodes
    parts = ['<!doctype html><html><body><ul>']
    N = 100_000
    for i in range(N):
        parts.append(f'<li class="item" data-i="{i}"><a href="/x/{i}">n{i}</a></li>')
    parts.append('</ul></body></html>')
    wide = "".join(parts)
    path = os.path.join(FIXTURES, "wide_100k_nodes.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(wide)
    # count of element nodes ~ 1 ul + N li + N a = 2N+1
    manifest["wide_100k"] = {"path": "wide_100k_nodes.html", "bytes": len(wide.encode("utf-8")),
                             "li_nodes": N, "a_nodes": N, "approx_element_nodes": 2 * N + 3}
    print(f"wide_100k: {len(wide.encode('utf-8')):,} bytes, {N} li -> {path}")

    import json
    with open(os.path.join(FIXTURES, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print("manifest written")


if __name__ == "__main__":
    main()
