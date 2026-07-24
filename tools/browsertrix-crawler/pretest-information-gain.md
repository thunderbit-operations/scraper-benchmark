# Browsertrix Crawler — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design only.

Broad keyword: **`Browsertrix Crawler`** (Webrecorder `webrecorder/browsertrix-crawler`).
Article boundary: Browsertrix Crawler is a **real-browser web archiver** (drives
Chromium via Puppeteer, records everything the browser fetched into WARC/WACZ). It
is not a structured-data extractor (Scrapy) nor a discovery-only recon crawler
(katana). This pack judges **dynamic-capture fidelity and archival artifact cost**:
what a real-browser archiver actually writes into the archive on controlled ground
truth, what it misses, and how many archive bytes that fidelity costs.

## SERP scan (first ~20 results, official docs, README, npm)

### What the results repeat (consensus, mostly unmeasured)

- Browsertrix uses a **real browser** (Chromium/Puppeteer) so it captures
  JS-rendered / SPA / lazy-loaded / dynamic content that raw-HTML crawlers miss;
  output is **high-fidelity WARC**, optionally bundled **lossless into WACZ**.
- Default **link extraction queries the rendered DOM**: "extract all `href`
  properties from all `<a>` tags" via selector `a[href]->href`
  ([common-options docs](https://crawler.docs.browsertrix.com/user-guide/common-options/)).
- Default **behaviors**: `autoplay,autofetch,autoscroll,siteSpecific`; `autofetch`
  grabs `img` srcset / stylesheets / `data-*` URLs; `autoclick` is opt-in
  ([behaviors docs](https://crawler.docs.browsertrix.com/user-guide/behaviors/)).
- Output tree: `collections/<name>/archive/*.warc.gz`, `pages/pages.jsonl` +
  `extraPages.jsonl`, CDX under `warc-cdx/`, and a `<name>.wacz`
  ([outputs docs](https://crawler.docs.browsertrix.com/user-guide/outputs/)).

### What is NOT measured anywhere (the gap)

1. **"Captures dynamic content" is asserted, never decomposed.** No source
   separates the distinct dynamic behaviours an archiver treats differently: a link
   *injected into the DOM* (found only via rendered-DOM link extraction) vs a
   *fetch() actually issued* by page JS (captured as ordinary network traffic) vs a
   URL literal *referenced but never executed* (never fetched at all). These have
   opposite outcomes for an archiver and nobody measures the split.
2. **Archiver coverage is the inverse of a static JS parser — undocumented.** A
   static parser (katana `-jc` / jsluice) recovers URL literals out of `.js` files;
   a real-browser archiver records only what the browser *did*. So the exact class a
   static parser catches (unexecuted literal) is the class an archiver drops, and
   vice-versa. No source quantifies this against the same ground truth.
3. **Archival artifact cost is unquantified.** "WARC files can be large" is repeated;
   no source reports archive bytes per captured response byte, per page, or the WARC
   record-type composition (how much of the archive is response payload vs
   request/metadata/index/screenshot overhead) on controlled ground truth.
4. **Replay fidelity of runtime-injected content is asserted, not shown.** Whether a
   runtime-injected endpoint actually lands in the archive as a replayable response
   record is taken on faith.

### Source evidence

- Official: [browsertrix-crawler docs](https://crawler.docs.browsertrix.com/),
  [outputs](https://crawler.docs.browsertrix.com/user-guide/outputs/),
  [common-options](https://crawler.docs.browsertrix.com/user-guide/common-options/),
  [behaviors](https://crawler.docs.browsertrix.com/user-guide/behaviors/),
  [intro blog](https://webrecorder.net/blog/2021-02-22-introducing-browsertrix-crawler/).
- Upstream issues to scan at execution: `github.com/webrecorder/browsertrix-crawler/issues`
  and `webrecorder/browsertrix-behaviors`.
- Parity axis (same-fixture siblings in this benchmark): `tools/katana`
  (static crawl misses runtime-DOM class), `tools/chromedp`, `tools/rod`,
  `tools/playwright-mcp` (CDP-family real browsers capture runtime-injected DOM).

## Testable information-gain hypotheses

- **H1 (core, parity/dynamic capture):** On a controlled fixture, browsertrix (real
  browser) captures **class C** (runtime-injected DOM `<a href>`, enqueued via
  rendered-DOM link extraction → fetched → WARC response record) and **class D**
  (runtime `fetch()` issued by page JS, captured as network traffic). Both are what a
  static crawl (katana) misses; measure per-class capture from WARC response records
  + server-side hit truth. Parity: katana static misses this class; CDP-family catch
  it; browsertrix — a real browser — should too.
- **H2 (adversarial, the real boundary):** An archiver captures what the browser
  **executed**, not what code **references**. **Class B** (two URL literals inside an
  *uncalled* function in a linked `app.js`) is never fetched → **no** response record,
  **no** server hit — even though `app.js` itself is archived and the literals are
  present in its archived bytes. So browsertrix's endpoint coverage is the inverse of
  a static JS parser (katana `-jc` recovers B; browsertrix does not). "Real browser =
  captures everything JS" is over-stated: it captures executed traffic, not
  references.
- **H3 (archival artifact cost):** Quantify on-disk **WARC.gz** and **WACZ** size vs
  captured HTTP response payload bytes and page count, plus WARC **record-type
  composition** (response vs request vs warcinfo/metadata/resource/screenshot). Gives
  archive-bytes-per-page and archive-bytes-per-response-byte and the overhead share —
  the price of high-fidelity capture, on ground truth.
- **H4 (replay fidelity):** The dynamically-produced endpoints (C injected link, D
  runtime fetch) land in the archive as **response records** (so a WACZ replay could
  serve them). Verified by response-record presence + rendered nav-response presence;
  full pywb/replayweb.page replay is heavier infra and reported as done or PARKED
  honestly, not faked.
- **H5 (adversarial, scope):** Under default `--scopeType prefix`, an out-of-scope
  **host** (a different hostname alias resolving to the same fixture) is **not**
  archived (no server hit with that Host header); `--scopeType any` **does** fetch it
  — proving the negative is real scope discipline, not a missed link.

## Test matrix (tied to hypotheses)

| # | Test | Fixture behaviour | Measures | H |
|---|---|---|---|---|
| 1 | capture: class A (HTML `<a href>`) | plain links | response record + server hit per endpoint | H1 |
| 2 | capture: class C (runtime DOM link) | JS appends `<a href>` assembled at runtime | enqueued+fetched? response record? | H1 |
| 3 | capture: class D (runtime fetch) | JS calls `fetch()` on load, path assembled | response record captured as traffic? | H1 |
| 4 | boundary: class B (uncalled literal) | literals in an uncalled `app.js` function | NOT fetched, yet present in archived app.js bytes | H2 |
| 5 | archival cost | full crawl | WARC.gz + WACZ bytes, record-type composition, per-page/per-response ratios | H3 |
| 6 | replay fidelity | C/D endpoints | response records exist + rendered nav responses in archive | H4 |
| 7 | scope: prefix vs any | out-of-scope hostname alias link | out-of-scope host fetched = 0 (prefix) vs >0 (any) | H5 |
| 8 | robustness | 500 route + dead link | crawl completes, archive still valid | robustness |

Fixture (local, container reaches host via `host.docker.internal`): four endpoint
classes — (A) `<a href>` in HTML, (B) URL literals in an *uncalled* JS function,
(C) runtime-injected DOM `<a href>` (assembled from fragments, no literal anywhere),
(D) runtime `fetch()` (path assembled from fragments). B/C/D are the archiver-
specific split. Server-side hit counter records `(host, path)` so capture and scope
are proven independent of browsertrix's own logs.

## Boundary / compliance notes

- Evidence phase only; no article, no publish;串行 single tool.
- All tests on the **local fixture**; the "out-of-scope host" is a hostname alias
  (`--add-host`) that resolves to the same fixture — **no real-internet traffic**, no
  third-party host, no anti-bot, no auth.
- Container→host networking recorded honestly (image tag + digest, `--add-host`
  method).
- Report archive cost as measured bytes on this tiny fixture; do **not** extrapolate
  to production-scale archives (single-machine, ground-truth-sized).
- Runtime-injected capture depends on browsertrix defaults (link extraction +
  behaviors) — record the exact flags/behaviors the run used.
