# Puppeteer Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: Puppeteer (`puppeteer/puppeteer`). Tested: 24.16.0 (npm latest 25.3.0 — see caveat). Date: 2026-07-09, Node v22, macOS arm64.
Positioning (official): a JavaScript API to control Chrome (and experimentally Firefox).

## What This Pack Covers

Puppeteer as a browser-automation library for scraping, on the same fixtures as the Scrapy/Crawlee/Playwright packs. Runner: `tests/run_puppeteer_material_tests.mjs`.

## Test Results

| Test | Target | Result | Evidence |
|---|---|---|---|
| Static catalog + pagination | local fixture | 12/12, recall 1.0 | `artifacts/raw/local_static_catalog.json` / `.csv` |
| Article extraction | local fixture | title + 3/3, boilerplate separated | `artifacts/raw/local_article.json` |
| Dynamic JS page (native render) | local fixture | 8/8, recall 1.0 + screenshot | `artifacts/raw/local_dynamic_rendered.json`, `artifacts/screenshots/local_dynamic_puppeteer.png` |
| Dynamic JSON API (in-page fetch) | local fixture | 8/8, recall 1.0 | `artifacts/raw/local_dynamic_api.json` / `.csv` |
| HTTP 500 handling | local fixture | status 500 inspectable, no throw | `artifacts/raw/local_failure_500.json` |
| Crawl graph (hand-written BFS) | local fixture | 12 pages, depths {0,1,2} | `artifacts/raw/local_crawl_graph.json` |
| Books to Scrape | public demo | 20 products | `artifacts/raw/public_books_to_scrape.json` / `.csv` |
| Quotes JS | public demo | 10 quotes | `artifacts/raw/public_quotes_js_rendered.json` |

Full timings/versions: `artifacts/raw/puppeteer-test-summary.json`.

## The Core Story

Puppeteer renders JS content natively (dynamic fixture 8/8, public Quotes JS 10) with working screenshots — mature, Chrome-focused browser automation. Like Playwright, it has no built-in crawl orchestration: the crawl-graph test required a hand-written BFS. Its main difference vs Playwright is narrower cross-engine scope (Chrome-first vs Chromium/Firefox/WebKit).

## Setup And Dependency Friction

- `npm install puppeteer` bundles a Chrome download automatically (heaviest install step; clean here, 0 vulnerabilities).
- **Version caveat**: tested 24.16.0 vs npm latest 25.3.0 (major gap). Exercised APIs stable across 24→25; re-run on latest before publishing.

## Successes

- Recall-1.0 static, article, and JSON-API extraction.
- Native JS rendering (local + public), zero special config.
- Screenshot capture worked full-page.
- Robust 500 handling (response object, no throw).

## Failures And Limitations (On Purpose)

- No built-in crawl queue/dataset/throttle — crawl-scale needs user code or a wrapper (e.g. Crawlee PuppeteerCrawler).
- Chrome-first: cross-engine breadth narrower than Playwright.
- Browser weight (bundled Chrome, per-page cost).
- Not tested: Firefox/BiDi engine, proxying, parallel scale, request interception.

## Writer Notes

Good blog material: native rendering + screenshot proof; recall-1.0 extraction; honest "mature Chrome automation, not a crawler framework" framing backed by the hand-written-BFS test.

Caveat-only: star/fork metadata; 24.16.0-vs-25.3.0 version gap; single-machine, single-run timings.

Exclusions: stealth/anti-detection framing; "fastest/best" superlatives.

## Gaps Before Final Draft

- Re-run on puppeteer 25.3.0 (latest).
- Firefox/WebDriver-BiDi engine check.
- Request interception / API-first example.
- Parallel-page scale run.
- Crawlee-wraps-Puppeteer note for crawl-scale positioning.
- Refresh metadata within 48h of publication.

## Provisional Scorecard

See `scorecard.md`. Research aid, not a final rating.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding was searched against three sources: the upstream repo/issue tracker (`puppeteer/puppeteer`), the official docs (pptr.dev), and the top ~20 SERP results. Classification is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`. **Novelty is decided by the search table, not by adjective.**

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Native JS rendering, Chrome-first** (dynamic fixture 8/8, public Quotes JS 10, screenshots) via the Chrome DevTools Protocol (CDP) | **DOCUMENTED** | Puppeteer's positioning is "a JavaScript API to control Chrome (and experimentally Firefox)," driven by CDP — [Puppeteer FAQ/docs](https://pptr.dev/faq). Verified rendering, but an advertised capability, not a discovery. |
| **Cross-engine scope narrower than Playwright** (Chrome-first vs Chromium/Firefox/WebKit) | **DOCUMENTED — with an important nuance the RM should add** | Accurate as stated, but the current landscape is documented and richer: since **Puppeteer v23** it has production-ready **Firefox** support via **WebDriver BiDi** (defaulting to CDP for Chrome to preserve existing automations) — [Puppeteer WebDriver BiDi docs](https://pptr.dev/webdriver-bidi), [Chrome for Developers: Firefox support in Puppeteer](https://developer.chrome.com/blog/firefox-support-in-puppeteer-with-webdriver-bidi), [Mozilla Hacks](https://hacks.mozilla.org/2024/08/puppeteer-support-for-firefox/). The pack tested **24.16.0** (≥23), so "Chrome-first" is right but "Chrome-only" would be wrong — Firefox-via-BiDi is documented and available in the tested version (WebKit is **not** supported, which is the real contrast with Playwright). **Not EXCLUSIVE.** Writer should refine to "Chrome-first (CDP), with documented Firefox support via WebDriver BiDi from v23; no WebKit." |
| **No built-in crawl queue / dataset / throttle** (crawl-graph needed a hand-written BFS) | **DOCUMENTED — design scope** | Puppeteer is browser automation, not a crawler framework; the RM correctly notes Crawlee's PuppeteerCrawler wraps it for crawl-scale. Per v3 §15, a documented boundary, not a defect. |
| **`npm install puppeteer` bundles a Chrome download** (heaviest install step) | **DOCUMENTED** | Standard, documented install behavior. An operational note, not a finding. |

**Consequence for the writer:** nothing is `EXCLUSIVE`. One accuracy refinement is warranted (not a rewrite of the pack, a note): the tested version (24.16.0) **does** have documented Firefox support via WebDriver BiDi, so the Playwright-vs-Puppeteer engine contrast is "Puppeteer: Chrome (CDP) + Firefox (BiDi), no WebKit" vs "Playwright: Chromium + Firefox + WebKit." Frame the breadth difference as WebKit + maturity of cross-engine, not "Chrome-only."

## Part 6 self-check (v3 pre-submission checklist)

Honesty audit of the existing RM text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool speed ranking; timings single-machine/single-run and labeled as such; "fastest/best" excluded. No winner sentence to contradict.
2. **Claim-without-artifact (D4)** — *Pass.* Every test row cites an artifact (JSON/CSV/PNG). No un-backed "cross-verified" sentence. (The cross-engine comparison to Playwright is a documentation statement, not a measured claim — and the accuracy refinement above tightens it.)
3. **Blind instrument (D2)** — *Pass (N/A).* No timing/memory/leak instrument beyond single wall-clock observations, explicitly not benchmarks. No blind-instrument exposure; no zero-benchmark "fast" claim.
4. **Mis-attribution (D3)** — *Pass, with one accuracy note now recorded.* The hand-written-BFS need is correctly attributed to design scope. The one attribution to tighten is **factual, not causal**: "Chrome-first" understated the documented Firefox-via-BiDi support in the tested version — now corrected in the Novelty table (a documentation-accuracy fix, not a harness mis-attribution). No fixture/harness fault mis-blamed on the tool.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Addressed.* Novelty tags added above. Self-praise lint `grep -iE 'honest|independent|strongest|trustworthy'` → "**honest** 'mature Chrome automation, not a crawler framework' framing" (Writer Notes) — modifies the framing's candor, borderline-acceptable; neutralize to "the accurate '…' framing" in the final draft if strict. Flagged, not rewritten (additive pass).

**Self-check on this appended pass:** no self-evaluative adjectives on the tool; nothing tagged `EXCLUSIVE`; the cross-engine claim is corrected toward documentation accuracy (Firefox-via-BiDi exists in the tested version); every verdict cites a doc link.

## As-of provenance check

Cross-checked against `metadata-snapshot.md`.

- **Snapshot date:** explicit **Fetched: 2026-07-07** plus a **Refresh 2026-07-09** delta table. Provenance present.
- **Stars / forks:** RM Writer Notes flags star/fork as caveat-only; the snapshot records 95,285 → 95,307 stars (2026-07-07 → 2026-07-09). **Writer note:** render as **"~95.3k stars as of 2026-07-09 (puppeteer/puppeteer)"** at point of use.
- **Version (a real gap to carry as-of):** the RM tests **24.16.0** while npm latest is **25.3.0** (snapshot, unchanged across the 2026-07-09 refresh — a major-version gap). Explicitly disclosed in the RM ("Re-run on latest before publishing") and traceable to the snapshot. **Writer note:** state both dated — "tested 24.16.0; npm latest 25.3.0 as of 2026-07-09" — and honor the re-run-before-publish instruction.
- **Instruction (do not fetch live):** not re-pulled live this pass; Richard refreshes pre-publication. This section certifies traceability to the dated 2026-07-09 snapshot and recommends the "as of 2026-07-09" qualifier at point of use.
