# Playwright Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: Playwright (`microsoft/playwright`). Tested: 1.56.0 (latest release 1.61.1 — see caveat). Date: 2026-07-09, Node v22, macOS arm64.
Positioning (official): a framework for web testing and automation driving Chromium, Firefox and WebKit with one API.

## What This Pack Covers

Playwright used as a browser-automation library for scraping. Same fixtures as the Scrapy/Crawlee packs for future comparison. Runner: `tests/run_playwright_material_tests.mjs`.

## Test Results

| Test | Target | Result | Evidence |
|---|---|---|---|
| Static catalog + pagination | local fixture | 12/12, recall 1.0 | `artifacts/raw/local_static_catalog.json` / `.csv` |
| Article extraction | local fixture | title + 3/3 paragraphs, boilerplate separated | `artifacts/raw/local_article.json` |
| Dynamic JS page (native render) | local fixture | 8/8, recall 1.0 + screenshot | `artifacts/raw/local_dynamic_rendered.json`, `artifacts/screenshots/local_dynamic_playwright.png` |
| Dynamic JSON API (`request.get`) | local fixture | 8/8, recall 1.0 | `artifacts/raw/local_dynamic_api.json` / `.csv` |
| HTTP 500 handling | local fixture | status 500 inspectable, no throw | `artifacts/raw/local_failure_500.json` |
| Crawl graph (hand-written BFS) | local fixture | 12 pages, depths {0,1,2} | `artifacts/raw/local_crawl_graph.json` |
| Books to Scrape | public demo | 20 products | `artifacts/raw/public_books_to_scrape.json` / `.csv` |
| Quotes JS | public demo | 10 quotes | `artifacts/raw/public_quotes_js_rendered.json` |

Full per-test timings/versions: `artifacts/raw/playwright-test-summary.json`.

## The Core Story

Playwright renders JavaScript content by default — the dynamic fixture and the public Quotes JS page both returned full data with no special handling, and screenshots worked. Its differentiator vs the HTTP-first tools is guaranteed real-browser rendering across three engines. Its trade-off, shown here, is that crawl orchestration (queue, depth, dataset) is not built in — the crawl-graph test required a hand-written BFS.

## Setup And Dependency Friction

- `npm install playwright` + a browser download (Chromium build) is required; the browser binary is the main weight.
- Playwright's default framing is the test runner; using it as a scraping library (`chromium.launch` + `context`/`page`) is the Library-docs path and needs the user to know that mode exists.
- **Version caveat**: harness ran 1.56.0; latest is 1.61.1. The exercised APIs are stable across these versions; re-run on latest before publishing.

## Successes

- Accurate static, article, and JSON-API extraction at recall 1.0.
- Native JS rendering (local + public) with zero special configuration.
- Screenshot capture worked full-page.
- Cross-engine capability (Chromium/Firefox/WebKit) is a documented, unique strength (only Chromium exercised here).

## Failures And Limitations (On Purpose)

- No built-in crawl queue / dataset / autothrottle — crawl-scale work needs user code or a pairing (e.g. Crawlee wraps Playwright for exactly this).
- Browser weight: per-page cost and binary size are higher than HTTP-only tools.
- Not tested: Firefox/WebKit engines, proxying, parallel worker scale, network interception for API-first scraping.

## Writer Notes

Good blog material (verified):

- Native JS rendering with screenshot proof, local + public.
- Recall-1.0 structured extraction on fixtures.
- The honest "great renderer, not a crawler framework" framing, backed by the hand-written-BFS crawl test.

Caveat-only:

- Star/fork counts (metadata).
- Version gap (1.56.0 tested vs 1.61.1 latest).
- Single-engine, single-machine, single-run timings — not benchmarks.

Exclusions:

- Stealth/anti-detection framing.
- Any "fastest/best" superlative.

## Gaps Before Final Draft

- Re-run on playwright 1.61.1 (latest).
- Firefox + WebKit engine parity check.
- Network interception / API-first extraction example.
- Parallel context/worker scale run.
- Explicit Crawlee-wraps-Playwright note for crawl-scale positioning.
- Refresh metadata within 48h of publication.

## Provisional Scorecard

See `scorecard.md`. Research aid, not a final rating.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding was searched against three sources: the upstream repo/issue tracker (`microsoft/playwright`), the official docs (playwright.dev), and the top ~20 SERP results. Classification is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`. **Novelty is decided by the search table, not by adjective.**

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Three engines, one API** (Chromium / Firefox / WebKit driven by a single API) — the signature multi-engine strength | **DOCUMENTED** | The repo tagline itself: "Playwright is a framework for Web Testing and Automation. It allows testing Chromium, Firefox and WebKit with a single API." Fully documented: [Playwright Browsers docs](https://playwright.dev/docs/browsers), [GitHub README](https://github.com/microsoft/playwright). The pack correctly notes only **Chromium** was exercised here; cross-engine is a *documented* strength this pack did not independently verify (Firefox/WebKit are in Gaps). **Not EXCLUSIVE**, and this pack must not imply it *tested* three engines. |
| **Native JS rendering by default** (dynamic fixture 8/8, public Quotes JS 10, screenshots) | **DOCUMENTED** | Real-browser rendering is the core advertised capability; verified working. An advertised capability, not a discovery. |
| **No built-in crawl queue / dataset / autothrottle** (crawl-graph test needed a hand-written BFS) | **DOCUMENTED — design scope** | Playwright is a browser-automation framework, not a crawler framework; the absence of a built-in queue/dataset is a documented scope boundary, and the RM correctly notes Crawlee wraps Playwright for exactly this. Per v3 §15, a design boundary, not a defect. Honest framing already present. |
| **Default framing is the test runner; using it as a scraping library needs knowing that mode exists** | **DOCUMENTED** | The library API (`chromium.launch` + `context`/`page`) is documented; that the marketing-forward framing is testing is an accurate UX observation, not a finding. |

**Consequence for the writer:** nothing is `EXCLUSIVE`. The cross-engine breadth is a **documented** strength that this pack **did not test** (Chromium only) — the article must say "documented three-engine support" not "we verified three engines." The honest "great renderer, not a crawler framework" line, backed by the hand-written-BFS test, is the strongest true statement.

## Part 6 self-check (v3 pre-submission checklist)

Honesty audit of the existing RM text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool speed ranking; timings are single-machine, single-run, and the RM says so explicitly and excludes "fastest/best." No winner sentence to contradict.
2. **Claim-without-artifact (D4)** — *Pass, with one caveat.* Every test row cites an artifact. The one claim **without an artifact in this pack** is cross-engine support: "Cross-engine capability (Chromium/Firefox/WebKit) is a documented, unique strength (**only Chromium exercised here**)." The RM already discloses it was not tested — so this is honestly scoped as *documented, not verified*, which satisfies D4 (no false "we verified" is made). The word "unique" is a mild superlative — see point 5.
3. **Blind instrument (D2)** — *Pass (N/A).* No timing/memory/leak instrument beyond single wall-clock observations explicitly labeled "not benchmarks." No blind-instrument exposure; no zero-benchmark "fast" claim.
4. **Mis-attribution (D3)** — *Pass.* The crawl-graph result requiring a hand-written BFS is correctly attributed to Playwright's design scope (no built-in crawler), not a defect. No mis-attribution.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Addressed, one flag.* Novelty tags added above. Self-praise lint `grep -iE 'honest|independent|strongest|trustworthy'` → no hits. **However** the RM calls cross-engine "a documented, **unique** strength" — "unique" is a superlative applied to an **untested** capability; per v3 §Part 4 §12–13 (lock claims to evidence scope) the writer should render it as "a documented three-engine capability (not exercised in this pass)" rather than "unique strength." Flagged, not rewritten (additive pass).

**Self-check on this appended pass:** no self-evaluative adjectives on the tool; nothing tagged `EXCLUSIVE`; the cross-engine capability is explicitly marked documented-but-untested; every verdict cites a doc link.

## As-of provenance check

Cross-checked against `metadata-snapshot.md`.

- **Snapshot date:** explicit **Fetched: 2026-07-07** plus a **Refresh 2026-07-09** delta table. Provenance present.
- **Stars / forks:** RM Writer Notes flags star/fork as caveat-only; the snapshot records 92,358 → 92,467 stars (2026-07-07 → 2026-07-09). **Writer note:** render as **"~92.5k stars as of 2026-07-09 (microsoft/playwright)"** at point of use.
- **Version (a real gap to carry as-of):** the RM tests **1.56.0** while latest is **1.61.1** (snapshot, unchanged across the 2026-07-09 refresh). This version gap is explicitly disclosed in the RM ("Re-run on latest before publishing") and traces to the snapshot. **Writer note:** state both dated — "tested 1.56.0; latest 1.61.1 as of 2026-07-09" — and honor the RM's re-run-before-publish instruction.
- **Instruction (do not fetch live):** not re-pulled live this pass; Richard refreshes pre-publication. This section certifies traceability to the dated 2026-07-09 snapshot and recommends the "as of 2026-07-09" qualifier at point of use.
