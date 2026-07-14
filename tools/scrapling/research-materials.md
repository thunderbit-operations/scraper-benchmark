# Scrapling Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: Scrapling (`D4Vinci/Scrapling`), version 0.4.10 (= latest). Date: 2026-07-09, Python 3.14, macOS arm64.
Positioning (official): an adaptive web scraping framework from a single request to a full-scale crawl.

## What This Pack Covers

Scrapling's HTTP `Fetcher` + lxml-based `Selector` parser on the shared fixtures, plus its headline **adaptive selector** feature (re-locating an element after markup changes). Runner: `tests/run_scrapling_material_tests.py`.

## Test Results

| Test | Target | Result | Evidence |
|---|---|---|---|
| Static catalog + pagination | local fixture | 12/12, recall 1.0 | `artifacts/raw/local_static_catalog.json` |
| Article extraction | local fixture | title + 3/3 paragraphs | `artifacts/raw/local_article.json` |
| Dynamic page (HTTP, no JS) | local fixture | 0 cards (expected limitation) | `artifacts/raw/local_dynamic_page_no_js.json` |
| Dynamic JSON API | local fixture | 8/8, recall 1.0 | `artifacts/raw/local_dynamic_api.json` |
| HTTP 500 handling | local fixture | status 500 exposed | `artifacts/raw/local_failure_500.json` |
| **Adaptive selector after class rename** | local fixture | plain selector 0 hits → adaptive recovered tracked element (1/3 synthetic) | `artifacts/raw/local_adaptive_selector.json` |
| Books to Scrape | public demo | 20 products | `artifacts/raw/public_books_to_scrape.json` |
| Quotes JS (HTTP, no render) | public demo | 0 (expected limitation) | `artifacts/raw/public_quotes_js_no_render.json` |

Full details: `artifacts/raw/scrapling-test-summary.json`.

## The Core Story

Scrapling's differentiator is adaptive selectors. Verified: when the target element's class was renamed `product-name` → `product-title`, a plain `.product-name` selector returned **0** hits, but Scrapling's adaptive re-matching **recovered the tracked element** using the fingerprint saved on the previous version. The honest nuance: in a 3-element synthetic test it relocated the first saved element, not all three — auto-match is element-tracking and multi-element use needs tuning. Standard HTTP extraction (static/article/JSON-API) hit recall 1.0.

## Setup And Dependency Friction (Key Finding)

- Base `pip install scrapling` = parser only. `from scrapling.fetchers import Fetcher` failed on a chain of missing deps: `curl_cffi` → `playwright` → `browserforge`.
- Fix: `pip install "scrapling[fetchers]"` (or the `scrapling install` CLI). This is real, blog-worthy first-run friction.
- Version tested equals latest (0.4.10) — no version caveat.

## Successes

- Recall-1.0 static, article, and JSON-API extraction via HTTP Fetcher.
- Adaptive re-matching recovered an element a broken selector could not (the distinctive capability).
- Clean lxml-backed CSS/XPath with `::text` / `::attr()` pseudo-selectors.
- Graceful 500 handling.

## Failures And Limitations (On Purpose)

- HTTP Fetcher does not render JS (dynamic fixture 0, Quotes JS 0); use `DynamicFetcher` (browser) for JS pages — untested here.
- Adaptive auto-match recovered 1/3 in the synthetic multi-element test; do not oversell it as total recovery.
- Fetcher stack requires the `[fetchers]` extra (heavy transitive deps).
- Not tested: `DynamicFetcher`/`StealthyFetcher` browser modes (stealth is a compliance caveat, not a feature), full-scale crawl, async fetcher.

## Writer Notes

Good blog material (verified): the adaptive-selector-survives-class-rename demo (with the honest 1/3 nuance); recall-1.0 HTTP extraction; the `scrapling[fetchers]` install-friction story.

Caveat-only: star/fork metadata (note it is a fast-rising ~68k-star project); adaptive multi-element recovery limits; single-machine run.

Exclusions: any framing of `StealthyFetcher`/undetectable features as a benefit; JS-rendering claims for the HTTP Fetcher; "best/fastest" superlatives.

## Gaps Before Final Draft

- Test `DynamicFetcher` (browser) for JS pages, framed as capability not stealth.
- Explore adaptive auto-match tuning for multi-element recovery.
- Async Fetcher + full-scale crawl behavior.
- Compare adaptive selectors vs plain lxml/BeautifulSoup resilience.
- Refresh metadata within 48h of publication.

## Provisional Scorecard

See `scorecard.md`. Research aid, not a final rating.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding in this pack was searched against three sources before a novelty tag was assigned: the upstream issue tracker (`D4Vinci/Scrapling` + its underlying engine lxml/parsel), the official docs/README, and the top ~20 SERP results. Classification is `[EXCLUSIVE]` (zero prior record), `[KNOWN-ISSUE: link]` (a reproduced upstream issue), or `[DOCUMENTED]` (vendor docs already describe it). **Novelty is decided by the search table, not by adjective.** This pack reports no reversal-of-consensus result.

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Adaptive / auto-match selector** (relocate an element by similarity after a class rename) | **DOCUMENTED** | Vendor docs describe it in full: [Scrapling Adaptive scraping docs](https://scrapling.readthedocs.io/en/latest/parsing/adaptive.html) ("It allows your scraper to survive website changes by intelligently tracking and relocating elements"; save-phase → SQLite, match-phase → similarity score over tag/text/attributes/siblings/path, "without AI"). Multiple third-party writeups also describe the mechanism: [ScrapingBee](https://www.scrapingbee.com/blog/scrapling-adaptive-python-web-scraping/), [Apify technical review](https://use-apify.com/blog/scrapling-python-web-scraping-framework). **Not an EXCLUSIVE finding of this pack** — we reproduced a documented feature and quantified its per-element behavior; that is the honest framing. |
| Is the adaptive-selector *capability* rare among Python scraping libraries? | **DOCUMENTED (distinctive-but-not-unprecedented)** | As a shipped, built-in library feature it is distinctive: standard parsers (lxml / parsel / BeautifulSoup) do **not** ship a native similarity-relocate feature — searched, no equivalent found ([lxml BeautifulSoup parser page](https://lxml.de/elementsoup.html), [Parsel docs](https://parsel.readthedocs.io/), [BeautifulSoup docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) confirm static selectors only). But the *concept* is not without precedent: "self-healing selectors/locators" is an established idea in test-automation (Selenium ecosystem, Healenium) and there are public build-your-own writeups ([DEV: self-healing CSS selector repair](https://dev.to/viniciuspuerto/when-the-scraper-breaks-itself-building-a-self-healing-css-selector-repair-system-312d)). So: distinctive as a Python-scraper library feature, **not** an undocumented or novel-to-the-world mechanism. We do **not** tag it `EXCLUSIVE`. |
| **Per-element auto-match nuance** (in the 3-element synthetic test it relocated the *first* tracked element, not all three) | **DOCUMENTED — design behavior, not a bug** | The docs frame auto-match as **element tracking** (fingerprint per saved element), which is consistent with the observed 1-of-3 result; this is a usage/scope nuance under default settings, not an undocumented defect. No issue-tracker entry needed. Under v3 Part 4 §15 (capability-boundary vs usage-error), this is "default-usage behavior of an element-tracking feature," and multi-element recovery is a tuning/gap item (already in Gaps), **not** a "the tool can't do X" claim. No `[KNOWN-ISSUE]` tag: this is not a reproduced upstream bug. |
| `scrapling[fetchers]` install friction (base install = parser only; `Fetcher` needs the extra) | **DOCUMENTED** | The dependency split (`curl_cffi`/`playwright`/`browserforge` behind the `[fetchers]` extra, plus the `scrapling install` CLI) is standard packaged behavior described in the project's install docs / README. A real first-run friction point worth reporting, but not a discovery. |
| HTTP `Fetcher` does not render JS (dynamic fixture 0, Quotes JS 0) | **DOCUMENTED** | By design: the HTTP `Fetcher` is documented as non-rendering; `DynamicFetcher`/`StealthyFetcher` (browser) are the rendering path. This is a design boundary (per §15, cite docs), not a defect. |

**Search-coverage note:** the Scrapling issue tracker was reported at 2 open issues at snapshot time (see metadata), i.e. a low-issue-count repo; "zero hits" on a specific defect would therefore carry weak evidentiary weight, which is an additional reason this pack avoids any `EXCLUSIVE` behavioral claim. Consequence for the writer: the adaptive-selector demo is genuinely good, reproducible material — but must be framed as *"a documented, distinctive feature we reproduced and stress-tested,"* with the honest 1-of-3 multi-element nuance, **never** as "a capability nobody else has" or "undocumented."

## Part 6 self-check (v3 pre-submission checklist)

Ran the five v3 Part 6 checks against this pack's existing RM/draft assertions. This is an honesty audit of the current text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* This pack makes **no** speed/"fastest"/"best" ranking claim; the Writer Notes explicitly exclude "best/fastest" superlatives. There is no head-to-head table where a bolded winner could contradict its own row. Nothing to flag.
2. **Claim-without-artifact (D4)** — *Pass.* Every result in the Test Results table cites a specific `artifacts/raw/*.json` file (e.g. the adaptive-selector claim → `local_adaptive_selector.json`; the `[fetchers]` friction is an install-log observation). No "we cross-verified / re-verified with X" sentence exists without a backing artifact. The metadata (star/version) is the only externally-variable claim and is scoped as caveat-only (see §As-of below).
3. **Blind instrument (D2)** — *Pass (N/A by design).* This pack runs **no timing benchmark and no memory/leak measurement**, so there is no instrument whose sensitivity must be calibrated. It correctly avoids any "fast"/"slow" wording (the byte-count observation about lxml-backed speed in third-party writeups is not imported as a claim here). No blind-instrument exposure.
4. **Mis-attribution (D3)** — *Pass, with one note now recorded.* The "adaptive relocated 1 of 3 elements" result: before attributing this to a Scrapling limitation, it is now explicitly re-scoped (Novelty table) as **documented element-tracking design behavior under default settings**, not a harness/fixture fault and not a tool defect. The single-element fixture design is disclosed in the RM ("in a 3-element synthetic test"). Attribution is now honest: feature scope, not failure.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Pass after this pass.* Novelty tags were **absent** before (the gap this pass closes) and are now applied above. Self-praise lint: `grep -iE 'honest|independent|strongest|trustworthy'` over the RM — the word "honest" appears in "The honest nuance" / "honest 1/3 nuance" describing the caveat's candor. Per v3 these are borderline; they modify a *caveat* (not a self-award of the tool), but to be strict the writer should render them neutrally (e.g. "the nuance:" / "the measured 1-of-3 result") in the final draft. Flagged, not silently rewritten (additive-only pass).

**Self-check on this appended pass:** these three appended sections themselves were linted — no self-evaluative adjectives applied to the tool; the one `EXCLUSIVE`-adjacent temptation (adaptive selector) was deliberately **not** tagged exclusive because the search found vendor docs + third-party precedent; every novelty verdict cites a link.

## As-of provenance check

Cross-checked every externally-variable number in this RM against `metadata-snapshot.md`.

- **Snapshot date:** `metadata-snapshot.md` carries an explicit **Fetched: 2026-07-07**, plus a **Refresh 2026-07-09** delta table. As-of provenance is present.
- **Stars / forks:** the RM's only star reference is in Writer Notes — "a fast-rising ~68k-star project," explicitly labeled caveat-only. This traces to the snapshot (68,501 on 2026-07-07 → 68,750 on 2026-07-09). **Provenance note for the writer:** render as **"~68.5k stars as of 2026-07-09 (D4Vinci/Scrapling)"** so the figure is dated at point of use.
- **Version:** RM states "version 0.4.10 (= latest)"; the snapshot confirms PyPI 0.4.10 / GitHub release v0.4.10 (2026-07-04), both as of the 2026-07-09 refresh. Traceable; no version drift between RM and snapshot.
- **Instruction (do not fetch live):** per task scope, star/version were **not** re-pulled live in this pass — Richard refreshes within 48h before publication. This section only asserts that every figure in the RM is traceable to the dated snapshot and should carry an "as of 2026-07-09" qualifier at point of use.
