# Crawlee pack

Tested version: **3.17.0** (Apache-2.0). [Project on GitHub](https://github.com/apify/crawlee).

Crawlee is a Node.js/TypeScript crawling framework with one interface over two engines: `CheerioCrawler` (fast HTTP, no JavaScript) and `PlaywrightCrawler` (a real headless browser). The same crawler API, request queue, and storage back both — you switch engines, not code style.

## Run it

```bash
npm install
npx playwright install        # separate browser download (~80 MiB) — PlaywrightCrawler needs it
node run_tests.mjs
```

`npm install crawlee` pulls the framework but **not** a browser. `PlaywrightCrawler` will not run until `npx playwright install` fetches Chromium (~80 MiB), so that second step is mandatory, not optional.

`run_tests.mjs` starts a local fixture server, then runs the same fixtures through both engines: static catalog with pagination, article vs. boilerplate, the dynamic catalog with and without JS, the dynamic JSON API, an intentional HTTP 500, an internal-link crawl graph, plus two public practice sites. It writes JSON to `results/`.

## What's in `results/`

- `local_static_catalog.json` — 12/12 static products via CheerioCrawler, following `.next-page` pagination
- `local_article.json` — article title + 3/3 body paragraphs, with nav/aside/footer kept in separate fields
- `local_dynamic_page_no_js.json` — CheerioCrawler on the JS catalog: **0 cards** (HTTP engine does not run JavaScript — expected)
- `local_dynamic_api.json` — 8/8 dynamic products by reproducing the underlying JSON request (no browser)
- `local_dynamic_playwright.json` — **same JS catalog, 8/8** products once PlaywrightCrawler renders it
- `local_failure_500.json` — intentional HTTP 500 routed cleanly to `failedRequestHandler`
- `local_crawl_graph.json` — internal-link crawl, 11 pages across depths {0:1, 1:3, 2:7}
- `local_fixture_ground_truth.json` — the fixture's expected products/article/dynamic set
- `public_books_to_scrape.json`, `public_quotes_js_no_render.json`, `public_quotes_js_playwright.json` — public practice sites (Cheerio saw **0** rendered quotes; Playwright recovered **10** at the same URL)
- `crawlee-test-summary.json` — the full run summary (per-test crawler, counts, recall, timings)
- `screenshots/` — rendered-page proof; `metadata/` — GitHub/npm snapshots (2026-07-07 baseline, 2026-07-09 refresh)

## Honest caveats (also in the root METHODOLOGY)

- **The core story is the two-engine switch.** Same URL, same pack: `CheerioCrawler` extracts 0 items from the JS catalog while `PlaywrightCrawler` extracts 8/8 (locally) and 10 (public Quotes JS) — a painless engine swap, not a code rewrite.
- **The hidden cost is that 80 MiB browser.** `npm install crawlee` does not include it; `npx playwright install` is a separate, easy-to-miss step before any browser crawl works.
- Do **not** read `CheerioCrawler` as capable of rendering JavaScript — the empty result is expected evidence of the HTTP-only engine.
- Star counts and single-run timings are metadata / within-tool signals, not cross-tool rankings. Fingerprinting/proxy features exist in Crawlee but are out of scope here and are **not** exercised or claimed as an anti-detection selling point.

Absolute counts and timings here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
