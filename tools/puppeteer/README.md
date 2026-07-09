# Puppeteer pack

Tested version: **24.16.0** (Apache-2.0). [Project on GitHub](https://github.com/puppeteer/puppeteer).

Puppeteer is a Chrome/Chromium browser-automation library for Node. It drives a real headless browser, so JavaScript-rendered content is available natively — but it is an automation library, not a crawler, so there is no built-in crawl queue.

## Run it

```bash
npm install
npx puppeteer browsers install chrome    # downloads a matched Chrome build — sizeable
node run_tests.mjs
```

`run_tests.mjs` starts a local fixture server, exercises static/dynamic catalog extraction, an article page, an intentional 500, a hand-written BFS link crawl, and the dynamic JSON API path, plus two public practice sites, and writes JSON to `results/`.

## What's in `results/`

- `local_static_catalog.json` — static catalog extraction (recovered 12/12 products across 2 paginated pages)
- `local_dynamic_rendered.json` — JS-rendered catalog via the real browser (recovered 8/8 dynamic products)
- `local_dynamic_api.json` — the backing JSON endpoint the dynamic page fetches (8/8, the "reproduce the request" path)
- `local_article.json` — article extraction (title + body vs nav/aside/footer boilerplate)
- `local_failure_500.json` — the intentional HTTP 500 (returned a response object, not a thrown exception)
- `local_crawl_graph.json` — the hand-written BFS link crawl (12 pages)
- `local_fixture_ground_truth.json` — the ground-truth structure the run was checked against
- `public_books_to_scrape.json`, `public_quotes_js_rendered.json` — public practice sites (books.toscrape.com, quotes.toscrape.com/js; the JS page yielded 10 quotes)
- `puppeteer-test-summary.json` — the per-test summary rollup
- `screenshots/` — rendered-page proof; `metadata/` — GitHub/npm snapshots (2026-07-07 and 2026-07-09)

## Honest caveats (also in the root METHODOLOGY)

- **JS renders natively.** Static 12/12 and dynamic 8/8 locally; the public quotes JS page returned 10 — Puppeteer runs a real Chrome, so client-side rendering is available without extra config.
- **The intentional 500 returned cleanly.** Puppeteer handed back a response object with status 500 rather than throwing — a sign of mature, robust error handling, not a failure.
- **No built-in crawl queue.** The link-graph test needed a hand-written BFS (12 pages walked manually); Puppeteer automates a browser, it does not crawl for you.
- **Chrome-first.** Puppeteer targets Chrome/Chromium; it does not offer the cross-engine breadth of Playwright's three-engine (Chromium/Firefox/WebKit) coverage.
- **Version trailed latest.** This pack exercised **24.16.0**; latest at write time was **25.3.0** — one major version behind. Re-run against current, or read the numbers with that gap in mind.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
