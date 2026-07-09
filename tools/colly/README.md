# Colly pack

Tested version: **v2.3.0** (Apache-2.0). [Project on GitHub](https://github.com/gocolly/colly).

Colly is a fast, dependency-light Go HTTP scraping framework. You register `OnHTML` / `OnResponse` / `OnError` callbacks and control crawl reach with a depth setting; it compiles to a single static binary. It does **not** execute JavaScript.

## Run it

```bash
go run main.go
```

Needs a Go toolchain (this pack was exercised with Go 1.26.5). There is no `requirements.txt` — Go resolves dependencies from `go.mod` / `go.sum` on first build. `main.go` starts a local `httptest` fixture server, runs the static/article/dynamic/failure/crawl tests plus two public practice sites, and writes JSON to `results/`.

## What's in `results/`

- `local_static_catalog.json` — static catalog extraction via `OnHTML` (12/12 products across 2 paginated pages)
- `local_article.json` — article extraction (title + 3/3 body paragraphs, byline skipped)
- `local_dynamic_page_no_js.json` — the JS-rendered catalog seen over plain HTTP: 0 cards (see caveat)
- `local_dynamic_api.json` — the catalog's backing JSON endpoint read via `OnResponse` (8/8 products)
- `local_failure_500.json` — the intentional HTTP 500, routed to `OnError` with status code confirmed
- `local_crawl_graph.json` — 17 pages under a depth-2 crawl (`colly.MaxDepth(2)` + `AbsoluteURL`)
- `local_fixture_ground_truth.json` — the ground truth the tests check against
- `public_books_to_scrape.json`, `public_quotes_js_no_render.json` — public practice sites
- `colly-test-summary.json` — machine-readable roll-up of every test
- `metadata/` — GitHub / Go module snapshots (2026-07-07 and 2026-07-09)

## Honest caveats (also in the root METHODOLOGY)

- **No JavaScript rendering.** Colly is HTTP-only. The JS-injected dynamic catalog returned 0 cards, and the public `quotes.toscrape.com/js` page returned 0 quote nodes. The 8 dynamic products were recovered only by reading the page's backing JSON API directly (`OnResponse`), i.e. reproducing the request — not rendering.
- **Depth labels are the harness's counter, not a Colly guarantee.** The crawl reached 17 pages under a depth-2 crawl; the per-page depth numbers are computed by this test harness, not a value Colly enforces.
- **Module version leads the release tag.** The exercised `github.com/gocolly/colly/v2` module is `v2.3.0`, ahead of the tagged GitHub release `v2.2.0`.

Absolute character counts here are a within-tool signal only — see the [comparability boundary](../../METHODOLOGY.md#the-comparability-boundary).
