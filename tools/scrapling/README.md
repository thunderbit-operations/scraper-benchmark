# Scrapling pack

Tested version: **0.4.10** (BSD-3-Clause). [Project on GitHub](https://github.com/D4Vinci/Scrapling).

Scrapling is a Python scraping library: a fast lxml-based parser (`Selector`) plus HTTP/browser fetchers. Its headline feature is **adaptive selectors** — after the page markup changes, a saved selector can re-locate the element it was tracking instead of silently returning nothing.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_tests.py
```

Note the `[fetchers]` extra in `requirements.txt`: a bare `pip install scrapling` installs the parser only. The fetchers extra pulls the HTTP/browser stack (curl_cffi → playwright → browserforge), which this harness needs for `Fetcher.get`.

`run_tests.py` starts a local fixture server, exercises the HTTP `Fetcher` against static/dynamic/article/failure fixtures, runs the adaptive-selector re-match test against ground truth, hits two public practice sites, and writes JSON to `artifacts/raw/`. The committed copy of those results lives in `results/`.

## What's in `results/`

- `local_static_catalog.json` — static catalog extraction with pagination (12/12 products)
- `local_article.json` — article title + body paragraphs, byline separated from body
- `local_dynamic_page_no_js.json` — dynamic page over HTTP: **0 cards** (expected — no JS)
- `local_dynamic_api.json` — the backing JSON API instead (8/8 — "reproduce the request")
- `local_failure_500.json` — the intentional HTTP 500, status surfaced cleanly
- `local_adaptive_selector.json` — the adaptive re-match test after a class rename (see caveat)
- `local_fixture_ground_truth.json` — the ground truth the run is scored against
- `public_books_to_scrape.json`, `public_quotes_js_no_render.json` — public practice sites
- `scrapling-test-summary.json` — the full run summary
- `metadata/` — GitHub/PyPI snapshots (2026-07-07 / 2026-07-09)

No `screenshots/` here — the HTTP `Fetcher` renders nothing to capture.

## What the numbers say

- **Static HTTP extraction**: 12/12 products across the two paginated pages.
- **Dynamic JSON API**: 8/8 — the HTTP `Fetcher` does not run JavaScript, so the dynamic *page* returns 0 cards, but pointing it at the backing JSON endpoint recovers all 8. That's "reproduce the request", not render.
- **Adaptive selectors**: after the target class is renamed `product-name` → `product-title`, a plain `.product-name` selector matches **0** elements, while adaptive re-matching re-locates the tracked element. This is the feature working.

## Honest caveats (also in the root METHODOLOGY)

- **Adaptive is resilient tracking, not total recovery.** In the synthetic 3-element test, the plain selector broke (0 hits) and adaptive re-matching recovered **1 of the 3** elements — it re-located the first saved/tracked element, not all three. Treat adaptive selectors as *resilient element tracking* you tune (match percentage / usage) for multi-element cases, not an automatic full re-scrape. Don't read the class-rename win as "recovers everything".
- **`[fetchers]` extra is required.** A bare `pip install scrapling` gives you the parser but not the fetchers this harness calls — hence `scrapling[fetchers]==0.4.10`.
- **No JS in the HTTP `Fetcher`.** The dynamic page returns 0 cards by design; the JSON-API path is how you'd get the data. Scrapling ships a browser-backed `DynamicFetcher` for JS pages, not exercised here.
- **Stealth/undetectable fetchers are a compliance caveat, not a selling point.** Scrapling includes anti-detection fetchers; they are out of scope here and were not exercised. Tests hit only local fixtures and purpose-built public practice sites.

Absolute character/field counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
