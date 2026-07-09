# Playwright pack

Tested version: **1.56.0** (Apache-2.0). [Project on GitHub](https://github.com/microsoft/playwright).

Playwright is a real-browser automation library (Chromium/Firefox/WebKit). JavaScript content renders natively, so client-side catalogs and JS-only pages come back fully populated with zero extra configuration. Its cost is browser weight/speed and the lack of a built-in crawl queue — anything crawl-shaped is code you write yourself.

## Run it

```bash
npm install
npx playwright install     # downloads browser engines
node run_tests.mjs
```

`run_tests.mjs` starts a local fixture server, then exercises static catalog + pagination, article vs. boilerplate separation, a JS-rendered dynamic catalog (native render + screenshot), the backing JSON API via `page.request`, an intentional HTTP 500, a hand-written BFS crawl graph, plus two public practice sites — writing JSON to `results/`.

## What's in `results/`

- `local_static_catalog.json` — static catalog, both paginated pages (12/12 products)
- `local_article.json` — article title + 3 body paragraphs, with nav/footer boilerplate kept separate
- `local_dynamic_rendered.json` — JS-rendered catalog (8/8 products, rendered natively)
- `local_dynamic_api.json` — same 8 products fetched straight from the JSON API (no DOM)
- `local_failure_500.json` — the intentional HTTP 500 (status inspectable, navigation does not throw)
- `local_crawl_graph.json` — hand-written BFS over the internal link graph (12 pages, depth 0–2)
- `local_fixture_ground_truth.json` — the fixture ground truth this pack was scored against
- `public_books_to_scrape.json`, `public_quotes_js_rendered.json` — public practice sites (20 books, 10 JS quotes)
- `playwright-test-summary.json` — the full run summary (versions, per-test recall, timings)
- `screenshots/` — rendered-page proof; `metadata/` — GitHub/npm/PyPI snapshots (2026-07-07 / 2026-07-09)

## Honest caveats (also in the root METHODOLOGY)

- **No built-in crawl queue.** The internal link-graph test needed a hand-written BFS (12 pages). For crawl-scale work you'd pair Playwright with Crawlee.
- **Version trails latest.** This pack exercised **1.56.0**; latest at snapshot time was **1.61.1**. Re-run or disclose the gap before quoting numbers.
- **Chromium only.** Only the Chromium engine was exercised here; Firefox/WebKit were not run.
- Native JS rendering scored full recall on the local dynamic catalog (8/8) and the public Quotes JS page (10) with zero configuration — the trade-off is browser startup weight and per-page cost, not accuracy.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
