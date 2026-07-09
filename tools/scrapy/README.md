# Scrapy pack

Tested version: **2.17.0** (BSD-3-Clause). [Project on GitHub](https://github.com/scrapy/scrapy).

Scrapy is an explicit Python crawling framework: you write spiders, and it handles scheduling, requests, item pipelines, feed exports (JSON/CSV/XML), and rate control via AutoThrottle. It is HTTP-first and does **not** render JavaScript by design.

## Run it

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run_tests.py
```

`run_tests.py` starts a local fixture server, then runs one spider per test (via `scrapy runspider`) against known ground truth: a static catalog, an article page, a JS-rendered catalog and its backing JSON API, an intentional HTTP 500, and an internal-link crawl graph — plus two public practice sites. It writes JSON + CSV to `artifacts/raw/`; the raw outputs captured for this pack are in `results/`.

## What's in `results/`

- `local_static_catalog.{json,csv}` — static catalog extraction (12/12 products across 2 paginated pages)
- `local_article.json` — article extraction (title + 3/3 body paragraphs, boilerplate separated)
- `local_dynamic_page_no_js.json` — the JS-rendered catalog scraped **without** rendering → **0** product cards (expected: Scrapy does not run page JS)
- `local_dynamic_api.{json,csv}` — the JSON API the dynamic page fetches → **8/8** products ("reproduce the request", not render)
- `local_failure_500.json` — the intentional HTTP 500, handled cleanly (status 500 recorded)
- `local_crawl_graph.json` — internal-link crawl: 11 pages seen across depth 0–2 (1 / 3 / 7)
- `quickstart_quotes.{json,csv}`, `public_books_to_scrape.{json,csv}` — public practice sites
- `public_quotes_js_no_render.json` — `quotes.toscrape.com/js` scraped without rendering → **0** quote nodes (same JS limitation)
- `local_fixture_ground_truth.json` — the fixture's ground truth for reference
- `*_run.json` — per-spider run transcripts (command, return code, timing); paths relativized
- `scrapy-test-summary.json` — the aggregated run summary
- `metadata/` — GitHub / PyPI snapshots (2026-07-07)

## Honest caveats (also in the root METHODOLOGY)

- **No JavaScript rendering, by design.** The dynamic catalog page returned **0 nodes** because Scrapy fetches HTML and does not execute page scripts. This is not a failure — it is Scrapy's worldview: reproduce the underlying request. The backing JSON API returned **8/8** cleanly.
- The dynamic worldview shows up twice: the public `quotes.toscrape.com/js` page also returned 0 quote nodes for the same reason. Rendering-dependent pages need a middleware like `scrapy-playwright`, which is out of scope here.
- **Larger dependency stack.** Installing Scrapy pulls in Twisted, lxml, and parsel — a heavier footprint than a plain HTTP client.
- Depth labels in the crawl graph come from Scrapy's own `depth` request meta.
- Only small local fixtures and two purpose-built public practice sites were exercised.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
