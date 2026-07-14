# Crawlee Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: Crawlee (`apify/crawlee`), version 3.17.0.
Tested: 2026-07-09, Node v22.22.3, macOS arm64.
Positioning (official): a web scraping and browser automation library for Node.js/TypeScript to build reliable crawlers, with a single interface over HTTP crawling (Cheerio/JSDOM) and headless browser crawling (Playwright/Puppeteer).

## What This Pack Covers

A reproducible local + public-demo test of Crawlee's two main crawler classes, run from one harness:

- `CheerioCrawler` — fast HTTP crawling, no JavaScript execution.
- `PlaywrightCrawler` — real Chromium browser, JavaScript rendering + screenshots.

Fixtures mirror the Scrapy pack (same products, article, dynamic set, 500 page, crawl graph) for future apples-to-apples comparison. Runner: `tests/run_crawlee_material_tests.mjs` + `tests/fixture-server.mjs`.

## Test Results

| Test | Crawler | Target | Result | Evidence |
|---|---|---|---|---|
| Static catalog + pagination | CheerioCrawler | local fixture | 12/12 products, recall 1.0 | `artifacts/raw/local_static_catalog.json` / `.csv` |
| Article extraction | CheerioCrawler | local fixture | title + 3/3 paragraphs, boilerplate separated | `artifacts/raw/local_article.json` |
| Dynamic page, no JS | CheerioCrawler | local fixture | 0 cards (expected limitation) | `artifacts/raw/local_dynamic_page_no_js.json` |
| Dynamic JSON API | CheerioCrawler | local fixture | 8/8 products, recall 1.0 | `artifacts/raw/local_dynamic_api.json` / `.csv` |
| HTTP 500 handling | CheerioCrawler | local fixture | status 500 confirmed, failedRequestHandler fired | `artifacts/raw/local_failure_500.json` |
| Internal-link crawl graph | CheerioCrawler | local fixture | 11 pages, depths {0:1,1:3,2:7} | `artifacts/raw/local_crawl_graph.json` |
| Dynamic page, with JS | PlaywrightCrawler | local fixture | 8/8 rendered, recall 1.0 + screenshot | `artifacts/raw/local_dynamic_playwright.json`, `artifacts/screenshots/local_dynamic_playwright.png` |
| Books to Scrape | CheerioCrawler | public demo | 20 products | `artifacts/raw/public_books_to_scrape.json` / `.csv` |
| Quotes JS, no render | CheerioCrawler | public demo | 0 quotes (expected limitation) | `artifacts/raw/public_quotes_js_no_render.json` |
| Quotes JS, rendered | PlaywrightCrawler | public demo | 10 quotes | `artifacts/raw/public_quotes_js_playwright.json` |

All test dates, versions, and per-test timings are in `artifacts/raw/crawlee-test-summary.json`.

## The Core Story (Reproducible)

Crawlee's headline claim — one framework, HTTP or browser — held up in a controlled way:

- The **local** dynamic fixture returned **0** cards under CheerioCrawler and **8/8** under PlaywrightCrawler.
- The **public** Quotes JS page returned **0** quotes under CheerioCrawler and **10** under PlaywrightCrawler.

Switching engines was a class swap in the same API surface (`requestHandler`, `run()`, `enqueueLinks`), not a rewrite. This is the most defensible thing a blog can say about Crawlee, and it is backed by raw files here.

## Setup And Dependency Friction

- `npm install crawlee playwright` installed cleanly (0 vulnerabilities, 85 packages funded).
- **Non-obvious step**: `PlaywrightCrawler` needs a separate browser download via `npx playwright install chromium` (~81.7 MiB). `npm install crawlee` alone does not fetch a browser. A first-time user who skips this will hit a launch error. Good, honest blog friction.
- Crawlee writes to a local `storage/` directory by default; the harness redirects it to a scratch temp dir and disables persistence to keep the pack clean. Worth mentioning that default runs leave a `storage/` folder behind.

## Successes

- HTTP extraction (static catalog, article, JSON API) was accurate at recall 1.0 on the fixtures.
- Pagination via `enqueueLinks({ selector: '.next-page' })` and same-hostname crawl with depth control worked as documented.
- Browser rendering recovered 100% of JS-injected content the HTTP crawler missed, and screenshots worked.
- Public demo sites (Books to Scrape, Quotes JS) behaved consistently with the local fixtures.

## Failures And Limitations (Documented On Purpose)

- CheerioCrawler cannot see JavaScript-rendered content (0 cards / 0 quotes). This is by design, but it is a real limitation a reader must understand before choosing the HTTP path.
- Browser crawling carries the ~80 MiB+ binary and higher per-page cost (Playwright dynamic run ~timed in summary vs sub-second Cheerio runs).
- Not tested this pack: proxy rotation, session pools, large-scale (100–1,000 page) runs, RequestQueue persistence/resume across restarts, Puppeteer engine, and Crawlee's Dataset/KeyValueStore export ergonomics. See gaps.

## Writer Notes

Good blog material (verified, reproducible):

- The "single interface, two engines" contrast with concrete 0 → full-data numbers on both a local fixture and a public site.
- The hidden `npx playwright install` browser-download friction.
- Accurate HTTP extraction + pagination + depth-controlled crawl on fixtures.
- Screenshot proof for the browser path.

Caveat-only material (do not overstate):

- Star/fork counts (metadata, drifts; +53 stars in 2 days).
- Any claim about scale, proxy, or anti-blocking behavior — untested here.
- Timings are single-machine, single-run; not benchmarks.

Exclusions (keep out of the blog):

- Framing fingerprinting/proxy rotation as anti-bot bypass. Present only as operational/compliance context if mentioned at all.
- Any "fastest/best/easiest" superlative — this pack does not support it.

## Gaps Before Final Draft

- Scale run: 100–1,000 page fixture to test autoscaling and stability.
- RequestQueue persistence + resume-after-crash behavior.
- Dataset → JSON/CSV export ergonomics (used manual writes here).
- Puppeteer engine parity check vs Playwright.
- Proxy/session configuration documented as compliance caveat, not as a feature.
- Refresh metadata within 48 hours of publication.

## Provisional Scorecard

See `scorecard.md`. It is a research aid, not a final rating.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding was searched against three sources: the upstream issue tracker (`apify/crawlee`), the official docs (crawlee.dev), and the top ~20 SERP results. Classification is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`. **Novelty is decided by the search table, not by adjective.**

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Unified interface, two engines** (same API across `CheerioCrawler` HTTP and `PlaywrightCrawler` browser; `requestHandler` / `run()` / `enqueueLinks` identical) — the pack's headline | **DOCUMENTED** | Explicitly vendor-documented: since Crawlee 3.0.0 (Aug 2022) all main crawler classes share the same `BasicCrawler` base and the same `enqueueLinks` / `pushData` interface — [Crawlee Quick Start](https://crawlee.dev/js/docs/quick-start), [CheerioCrawler API](https://crawlee.dev/js/api/cheerio-crawler/class/CheerioCrawler), [PlaywrightCrawler API](https://crawlee.dev/js/api/playwright-crawler/class/PlaywrightCrawler). The repo tagline itself advertises "Works with Puppeteer, Playwright, Cheerio, JSDOM, and raw HTTP." Verified here as a class-swap (0 cards Cheerio → 8/8 Playwright, 0 → 10 on public Quotes JS), which is a genuinely good **reproduction** of the documented claim — **not** an EXCLUSIVE discovery. |
| **Unified queue / storage** (`RequestQueue`, `Dataset`, `KeyValueStore`, `enqueueLinks` depth control) | **DOCUMENTED** | Pluggable storage, `RequestQueue`/`RequestList`, autoscaling, and proxy rotation are documented features ([Crawlee README](https://github.com/apify/crawlee), Quick Start). The pack exercised `enqueueLinks` + depth control (11 pages, depths {0:1,1:3,2:7}); persistence/resume was **not** tested (Gaps). Documented capability, partially exercised. |
| **Hidden browser-download step** (`npx playwright install chromium` ~81.7 MiB; `npm install crawlee` alone does not fetch a browser) | **DOCUMENTED — expected packaging behavior** | Playwright's separate browser download is standard, documented Playwright behavior that Crawlee inherits. A real first-run friction point worth reporting, but not a defect or discovery. |
| **Default `storage/` directory left behind** on default runs | **DOCUMENTED** | Crawlee's local storage default is documented behavior; the harness redirects it to a temp dir. An operational note, not a finding. |
| CheerioCrawler cannot see JS-rendered content (0 cards / 0 quotes) | **DOCUMENTED — design boundary** | By design: HTTP crawling does not execute JS; the browser crawlers are the documented rendering path. Per v3 §15, a documented boundary, not a bug. |

**Consequence for the writer:** nothing is `EXCLUSIVE`. The "single interface, two engines" story is the strongest material and is a clean reproduction of a **documented** claim with concrete 0→full-data numbers on both a local fixture and a public site — frame it exactly that way ("we verified the documented unified-API claim"), not as a unique discovery.

## Part 6 self-check (v3 pre-submission checklist)

Honesty audit of the existing RM text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool ranking; timings are single-machine and the RM explicitly says "not benchmarks" and excludes "fastest/best/easiest." No winner sentence to contradict.
2. **Claim-without-artifact (D4)** — *Pass.* Every Test Results row cites an artifact (JSON/CSV/PNG). The headline unified-API claim is backed by the paired Cheerio/Playwright result files. No un-backed "cross-verified" sentence.
3. **Blind instrument (D2)** — *Pass (N/A).* No memory/leak/percentile instrument; the browser-vs-HTTP cost is described qualitatively ("higher per-page cost … Playwright dynamic run ~timed in summary vs sub-second Cheerio runs") and explicitly as single-run, not a benchmark. No blind-instrument exposure; no zero-benchmark "fast" superlative (the RM avoids the word as a claim).
4. **Mis-attribution (D3)** — *Pass.* The 0-cards CheerioCrawler result is correctly attributed to no-JS-by-design ("This is by design"), not a Crawlee fault. The engine swap recovering 100% is attributed to browser rendering, correctly. No mis-attribution.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Addressed.* Novelty tags added above. Self-praise lint `grep -iE 'honest|independent|strongest|trustworthy'` → "the most defensible thing a blog can say" and "Good blog material (verified, reproducible)" — these describe the *evidence quality*, not self-awarded tool praise, and are borderline-acceptable; "the most defensible" could be neutralized to "the best-supported claim" in the final draft. Flagged, not rewritten (additive pass).

**Self-check on this appended pass:** no self-evaluative adjectives on the tool; nothing tagged `EXCLUSIVE`; the unified-API headline is explicitly framed as a reproduction of a documented claim; every verdict cites a link.

## As-of provenance check

Cross-checked against `metadata-snapshot.md`.

- **Snapshot date:** explicit **Fetched: 2026-07-07** plus a **Refresh 2026-07-09** delta table. Provenance present.
- **Stars / forks / open issues:** RM Writer Notes flags star counts as caveat-only and even notes drift ("+53 stars in 2 days"); the snapshot records 24,543 → 24,596 stars (2026-07-07 → 2026-07-09). Traceable, and the RM's drift note is consistent with the snapshot delta. **Writer note:** render as **"~24.6k stars as of 2026-07-09 (apify/crawlee)"** at point of use.
- **Version:** RM tests 3.17.0; snapshot confirms npm 3.17.0 / GitHub release v3.17.0 (2026-06-04), unchanged across the 2026-07-09 refresh. Traceable, no drift.
- **Instruction (do not fetch live):** not re-pulled live this pass; Richard refreshes pre-publication. This section certifies traceability to the dated 2026-07-09 snapshot and recommends the "as of 2026-07-09" qualifier at point of use.

---

## PuppeteerCrawler engine-parity (third engine) — additive bonus pass, 2026-07-14

Additive supplement under methodology v3. This section extends the Batch B unified-API finding (Cheerio ↔ Playwright) to a **third engine, `PuppeteerCrawler`**. It is **non-timed** — no throughput, latency, or startup measurement — a class-structure + API-surface parity check only. Nothing above this line is changed.

### What was checked (and what was not)

- **Checked:** whether `PuppeteerCrawler` shares the same `BasicCrawler` base and the same crawler/queue/storage/router API as `CheerioCrawler` and `PlaywrightCrawler`, via (a) runtime prototype introspection of the installed `crawlee` 3.17.0 and (b) the official docs.
- **Not checked (out of scope, honest boundary):** no live Puppeteer crawl was run — the `puppeteer` peer dependency is an *optional* peer of `@crawlee/puppeteer` and is **not installed** in this pack (probe records `puppeteer_peer_installed: false`), and running one would require a browser download (the same friction the RM already documents for Playwright). So the parity claim below is verified at the **class-structure / API-surface** level, not by an executed `PuppeteerCrawler.run()`. No timing was taken by design.

### Probe (programmatic, zero timing, no browser)

- Script: `puppeteer_parity_api_surface.mjs` — imports `CheerioCrawler`, `PlaywrightCrawler`, `PuppeteerCrawler` from the top-level `crawlee` package and introspects prototype chains + public method sets. No browser launch, no chromium download, no network navigation. Every field is computed at runtime (anti-hardcode).
- Artifact: `results/crawlee_puppeteer_parity_api_surface.json` (measured `2026-07-14`, Node v22.22.3, crawlee 3.17.0).

All three engine classes are exported from the same top-level `crawlee` package (all `typeof === "function"`), alongside `RequestQueue`, `Dataset`, `KeyValueStore`, `Router`, and the four router factories `createCheerioRouter` / `createPlaywrightRouter` / `createPuppeteerRouter` / `createBasicRouter`. `PuppeteerCrawler` imports and introspects cleanly **even with the `puppeteer` peer absent**, which is itself the point: class structure and API surface do not depend on the browser runtime.

### Prototype chains (from the probe, `per_engine[*].prototype_chain`)

| Crawler | Prototype chain | Extends `BasicCrawler`? |
|---|---|---|
| `CheerioCrawler` | `CheerioCrawler → HttpCrawler → BasicCrawler` | yes |
| `PlaywrightCrawler` | `PlaywrightCrawler → BrowserCrawler → BasicCrawler` | yes |
| `PuppeteerCrawler` | `PuppeteerCrawler → BrowserCrawler → BasicCrawler` | yes |

`PuppeteerCrawler` and `PlaywrightCrawler` route through the **same** intermediate `BrowserCrawler`; `CheerioCrawler` routes through `HttpCrawler`. All three converge on `BasicCrawler`.

### Shared vs engine-specific API surface (from `parity` block)

- **24 public prototype methods are shared by all three** engines, including the queue/storage/routing operations the Batch B story rests on: `run`, `addRequests`, `pushData`, `getData`, `getDataset`, `exportData`, `getRequestQueue`, `useState`, `stop`, `teardown`, plus `enqueueLinksWithCrawlDepth`, `getKeyValueStore` (via context, see below), and the robots/skip/proxy helpers.
- **`PuppeteerCrawler` and `PlaywrightCrawler` have *identical* public prototype method sets** (`puppeteer_playwright_prototype_methods_identical: true`; both = 25 methods = the 24 shared + `containsSelectors`). The only cross-engine deltas are: `CheerioCrawler` adds `use` (HTTP middleware) and lacks the browser-only `containsSelectors`; the two browser crawlers add `containsSelectors` and lack `use`. That is the full method-level difference — small and along the HTTP-vs-browser seam, not the queue/storage seam.

### Handler-context parity and its boundary (from `handler_context_from_type_defs`)

The API a user's `requestHandler` actually touches is the crawling context, injected at runtime. Read statically from the installed `@crawlee/*` type definitions (structural, not executed):

- **Shared base — `RestrictedCrawlingContext`** (the context every engine's handler receives) declares `request`, `pushData`, `enqueueLinks`, `addRequests`, `useState`, `getKeyValueStore`, `log` — confirmed present for all engines. This is the "business-code-unchanged" surface: enqueue links, push data, keep state, log — same names, same shapes, regardless of engine.
- **Browser base — `BrowserCrawlingContext`** (shared by Playwright + Puppeteer) adds `page`, `response`, `browserController`, parameterized by engine. `PuppeteerCrawlingContext extends BrowserCrawlingContext<PuppeteerCrawler, Page, HTTPResponse, PuppeteerController, …>`; `PlaywrightCrawlingContext extends BrowserCrawlingContext<PlaywrightCrawler, Page, Response, PlaywrightController, …>` — **same base interface, different engine type parameters** (the Puppeteer `Page`/`HTTPResponse`/`PuppeteerController` vs the Playwright equivalents).
- **Engine-specific handle — the real, honest boundary:** the content handle differs. `CheerioCrawlingContext` exposes `$` (a static parsed Cheerio DOM) plus `parseWithCheerio` / `waitForSelector`; the browser contexts expose a live `page` object from their respective library. Crawlee's own type doc says `parseWithCheerio` is present on all "to unify the crawler API … use it only if you are abstracting your workflow to support different context types in one handler" — i.e. the vendor itself scopes the parity to the unified operations and names the content handle as the thing that varies.

### Boundary, restated (do not overstate as "zero difference")

Parity is real at the **crawler class, queue/storage/router, and shared-context** level: swapping `CheerioCrawler` → `PuppeteerCrawler` keeps `run` / `enqueueLinks` / `pushData` / `useState` / `getRequestQueue` / `getDataset` / `router` identical, so the surrounding business/orchestration code structure is unchanged. It is **not** zero-difference inside the handler body: you move from `$('selector')` (static DOM) to `await page.$(…)` / `await page.title()` (live browser), and — per crawlee.dev's own guidance — Puppeteer requires explicit waiting for elements whereas Playwright auto-waits. Those are engine-specific and expected, not a Crawlee defect.

### Novelty verdict

`[DOCUMENTED]` — not exclusive. Vendor-documented parity, independently reproduced here at the API-surface level:

- crawlee.dev Quick Start states, verbatim, **"All classes share the same interface for maximum flexibility when switching between them,"** listing CheerioCrawler / PuppeteerCrawler / PlaywrightCrawler and noting the `$()` vs `page` content-access difference — [Quick Start](https://crawlee.dev/js/docs/quick-start).
- crawlee.dev PuppeteerCrawler API page shows the hierarchy `BrowserCrawler → PuppeteerCrawler` and marks `run` / `addRequests` / `pushData` / `getData` / `getDataset` / `exportData` / `useState` / `getRequestQueue` / `stop` as **inherited** — [PuppeteerCrawler API](https://crawlee.dev/js/api/puppeteer-crawler/class/PuppeteerCrawler).
- crawlee.dev JS-rendering guide names the engine-specific caveat: **"Playwright will automatically wait for elements to appear, whereas in Puppeteer, you have to explicitly wait for them."** — [JavaScript rendering](https://crawlee.dev/js/docs/guides/javascript-rendering).
- Version anchor: verified against installed `crawlee` **3.17.0** (matches `metadata-snapshot.md`), Node v22.22.3, on 2026-07-14. Docs not re-pulled live for metadata; treat doc-link content with the "as of 2026-07-14" qualifier and refresh pre-publication.

**Consequence for the writer:** the Batch B "single interface, N engines" story generalizes cleanly to Puppeteer — frame it as **"we verified the documented unified-API claim across a third engine (class hierarchy + 24 shared methods + shared handler-context), API-surface only, no live Puppeteer run,"** not as a unique discovery and not as "identical everywhere" (the `$` vs `page` handle and Puppeteer's explicit-wait behavior are the documented seams).

### Gaps (this pass)

- No executed `PuppeteerCrawler.run()` — API-surface/type-structure parity only (peer + browser not installed, non-timed by design). A future pass could install the `puppeteer` peer and repeat the Batch B 0→full-data recovery test on the same fixtures for a third data point.
- Constructor-option parity was checked at the class/export level, not field-by-field against every option name.
- `RequestQueue` persistence/resume across restarts still untested (pre-existing gap, unchanged).

### Part 6 self-check (this appended section only)

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool ranking and no "best/fastest" claim; parity is framed as a documented-claim reproduction, and the `$`-vs-`page` / explicit-wait seams are stated explicitly, so there is no "identical everywhere" sentence to contradict.
2. **Claim-without-artifact (D4)** — *Pass.* Prototype chains, the 24-method shared set, and the Puppeteer==Playwright identity all cite `results/crawlee_puppeteer_parity_api_surface.json`; context facts cite the same artifact's `handler_context_from_type_defs`; every vendor claim cites a crawlee.dev link with the 3.17.0 / 2026-07-14 anchor.
3. **Blind instrument (D2)** — *Pass (N/A).* Zero timing; no perf/memory/percentile instrument exists in this pass, so none can be blind. The only instrument is structural introspection, whose output is the artifact.
4. **Mis-attribution (D3)** — *Pass.* The `$`-vs-`page` difference and Puppeteer's explicit-wait requirement are attributed to engine design (and to crawlee.dev's own words), **not** presented as a Crawlee flaw; the "no live run" limitation is attributed to the absent optional peer, not to any tool failure.
5. **Novelty-tag + self-praise lint (D7/D12)** — *Pass.* Tagged `[DOCUMENTED]`, explicitly "not exclusive." `grep -iE 'honest|independent|strongest|trustworthy|best|fastest'` over this section → "honest boundary" / "honest boundary, restated" describe the *boundary-labeling discipline*, not tool praise; no super-formative adjective is applied to Crawlee itself.
