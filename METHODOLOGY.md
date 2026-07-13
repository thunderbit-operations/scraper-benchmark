# Methodology

How these packs were produced, what's comparable, and where the limits are.

## Fixture design

Every tool is tested against the same **ground-truth page structure**, served from a local fixture server (no network flakiness, fully reproducible):

| Fixture | Ground truth | What it probes |
|---|---|---|
| Static catalog | 12 products across 2 paginated pages | static HTML extraction + recall |
| Dynamic catalog | 8 products injected via JS after ~450ms | JavaScript rendering (client-side fetch) |
| Article page | title + 3 body paragraphs, wrapped in nav/aside/footer boilerplate | content extraction vs boilerplate stripping |
| Failure page | intentional HTTP 500 | error handling |
| Internal-link graph | home → catalog → detail pages | crawl/link-following behavior |
| Dynamic API | JSON endpoint the dynamic page fetches | "reproduce the request" path (for HTTP-only tools) |

Public demo sites ([books.toscrape.com](https://books.toscrape.com/), [quotes.toscrape.com/js](https://quotes.toscrape.com/js/) — both purpose-built for scraping practice) are used only for supplementary real-world checks.

## The comparability boundary

Each pack ships its own mirrored copy of the fixtures. The **structure is identical** (same routes, same CSS class names, same product/dynamic counts), but the **data differs slightly** between packs — product name prefixes, price formulas, and article wording are not byte-identical.

Consequence:
- **Comparable across tools**: recall counts (`8/8`, `12/12`), structural pass/fail, whether JS rendering worked, whether a 500 was handled cleanly.
- **NOT comparable across tools**: absolute markdown character counts. A pack's char count is a within-tool signal only.

This is a deliberate, disclosed limitation of open-sourcing the packs as-run rather than re-running everything against a single canonical fixture. A future revision may unify the fixtures and re-run; until then, the boundary above holds.

## Versions tested

Metadata (stars/releases) drifts — re-check each project before quoting. Versions exercised in this batch:

| Tool | Version tested | Note |
|---|---|---|
| Crawl4AI | 0.9.0 | |
| Crawlee | 3.17.0 | current at test time |
| Playwright | 1.56.0 | trailed latest (1.61.1) — re-run or disclose |
| Puppeteer | 24.16.0 | trailed latest (25.3.0) — re-run or disclose |
| trafilatura | 2.1.0 | = latest |
| Scrapy | 2.17.0 | |
| Colly | v2.3.0 | module ahead of release tag v2.2.0 |
| Scrapling | 0.4.10 | = latest |
| Firecrawl | self-hosted, prebuilt images | AGPL-3.0 — see below |
| selectolax | 0.4.10 | = latest; MIT binding, bundles LGPL-2.1 (Modest) + Apache-2.0 (Lexbor) engines |

## Honest caveats carried per tool

These are documented so nobody reads a happy-path number without its footnote:

- **Crawl4AI** — an intentional 500 page was labeled "anti-bot protection" by a minimal-text heuristic; it was not a real anti-bot wall. Raw markdown includes page boilerplate unless a content filter is configured. Deep crawls do not auto-wait for dynamic pages.
- **Firecrawl** — **AGPL-3.0**; check license implications for commercial use. Two setup workarounds were colima-environment artifacts, not Firecrawl faults. Self-hosted build lacks the cloud anti-block layer.
- **Playwright / Puppeteer** — no built-in crawl queue; the link-graph test needed a hand-written BFS. Versions trailed latest (see table).
- **Scrapy** — no JavaScript rendering by design; the dynamic page returned 0 nodes while its backing JSON API returned 8/8 ("reproduce the request", not render).
- **Colly** — no JavaScript; depth labels are the harness's counter, not a Colly guarantee.
- **Scrapling** — adaptive selectors recovered a tracked element after a class rename, but recovered only 1 of 3 in a synthetic multi-element test. Resilient tracking, not total recovery.
- **trafilatura** — article-text extractor, not a structured scraper; returned product names as text but 0 structured rows on a catalog; no JS.
- **Crawlee** — PlaywrightCrawler needs a separate `npx playwright install` (~80 MiB) not covered by `npm install crawlee`.
- **selectolax** — a CSS-only HTML parser (no XPath, no JS, no crawl). Its pack uses its own parser-benchmark harness, not the shared catalog fixtures, and reports performance as distributions over 3 independent process runs with cross-run spread. Known behaviors surfaced by the pack (all reproduced, none original to it): the Lexbor backend does not descend into `<template>` content (upstream selectolax#146 / lexbor#170); non-UTF-8 bytes are stored raw and later silently corrupt on `.text()` while `.html` raises (related to selectolax#40); `lxml`'s parse step is faster than selectolax's on this machine (counter to most published benchmarks — treated as a single-platform result); the Modest backend aborts the process on `:dir()`. Numbers are macOS arm64 / Python 3.14 only.

## Compliance note

Stealth/anti-detection features present in some tools are out of scope and not exercised as a selling point. Tests hit only local fixtures and purpose-built public practice sites.
