# trafilatura Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: trafilatura (`adbar/trafilatura`), version 2.1.0 (= latest). Date: 2026-07-09, Python 3.14, macOS arm64.
Positioning (official): Python & CLI tool to gather text and metadata on the web — crawling, scraping, extraction; output as CSV/JSON/HTML/MD/TXT/XML.

## What This Pack Covers

trafilatura as a main-content / article extraction library. Fixtures target its actual value (boilerplate-stripped article text + metadata) and its boundary (structured catalogs). Runner: `tests/run_trafilatura_material_tests.py`.

## Test Results

| Test | Target | Result | Evidence |
|---|---|---|---|
| Article extraction + boilerplate removal | local fixture | title + 3/3 paragraphs, **boilerplate cleanly removed**, author+date extracted | `artifacts/raw/local_article.txt` / `.md` / `.json` |
| Structured catalog boundary | local fixture | 12 names in text, **0 structured rows** (478 chars) | `artifacts/raw/local_catalog_extraction.txt` |
| HTTP 500 handling | local fixture | `fetch_url` returned None, no throw | `artifacts/raw/local_failure_500.json` |
| Public demo (Books product page) | public demo | 1,324 chars clean text + markdown | `artifacts/raw/public_books_product.txt` / `.md` |

Full details: `artifacts/raw/trafilatura-test-summary.json`.

## The Core Story

trafilatura's job is HTML → clean article text/markdown with boilerplate gone. Verified: from a page deliberately wrapped in nav/aside/footer noise, it returned only the title + body paragraphs, dropped every unique boilerplate marker, and pulled author + date metadata. Multi-format output (txt/markdown/json) makes it a natural "LLM-ready text" step. The honest boundary, also shown: on a product catalog it recovers the visible text but not structured rows — it is not a selector-based catalog scraper, and it does not run JavaScript.

## Setup And Dependency Friction

- `pip install trafilatura` in a venv was clean (Python 3.14, one package tree). Lightweight vs browser tools — no binary download.
- Version tested equals the current release (2.1.0) — no version caveat.

## Successes

- Clean article extraction: title + 3/3 paragraphs, boilerplate fully removed.
- Metadata extraction: author + date correct.
- Multi-format output: txt, markdown, json all saved.
- Graceful error handling (`fetch_url` → None on 500).
- Public prose extraction worked (1,324 chars).

## Failures And Limitations (On Purpose)

- Not a structured scraper: catalog test returned 0 structured rows (text only). Use a selector/parser tool for typed records.
- No JavaScript rendering: consumes static HTML; pair with a renderer for JS pages.
- Not tested here: the built-in crawl/sitemap spider, CSV/XML output formats, and a genuine news-article public example (toscrape has no news pages).

## Writer Notes

Good blog material (verified): boilerplate-stripped article extraction with a clean before/after; author+date metadata; multi-format (markdown/json) "LLM-ready" output; lightweight install.

Caveat-only: star/fork metadata; public test used a product-description block, not a news article; single-machine run.

Exclusions: any "structured scraping" or "JS rendering" claim — the evidence contradicts both; "best/fastest" superlatives.

## Gaps Before Final Draft

- Add a genuine news/article public example (outside toscrape).
- Test the built-in crawl/sitemap spider and feed formats (CSV/XML).
- Compare markdown output quality vs Crawl4AI's markdown for the LLM-ready angle.
- Refresh metadata within 48h of publication.

## Provisional Scorecard

See `scorecard.md`. Research aid, not a final rating. Dimensions are kept from the shared rubric for comparability, with content-extraction context noted.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding was searched against three sources: the upstream issue tracker (`adbar/trafilatura`), the official docs (trafilatura.readthedocs.io), and the top ~20 SERP results. Classification is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`. **Novelty is decided by the search table, not by adjective.**

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Main-content / boilerplate-stripped article extraction** (title + body only, nav/aside/footer dropped) + author/date metadata + multi-format output (txt/md/json) | **DOCUMENTED** | The advertised core: "gather text and metadata on the Web… output as CSV, JSON, HTML, MD, TXT, XML." Verified (all boilerplate markers dropped, author+date pulled). Advertised capability, not a discovery. |
| **Extraction *accuracy* is competitive with / ahead of other open-source extractors** (the implicit "why trafilatura" angle) | **DOCUMENTED — with strong external corroboration the writer should cite** | Not measured in this pack, but heavily documented externally: trafilatura's own [Evaluation docs](https://trafilatura.readthedocs.io/en/latest/evaluation.html); the [ScrapingHub article-extraction-benchmark](https://github.com/scrapinghub/article-extraction-benchmark) where trafilatura reports the top open-source F1 (~0.945) vs readability-lxml (~0.887); and the peer-reviewed [ACM empirical comparison of web content-extraction algorithms](https://dl.acm.org/doi/pdf/10.1145/3539618.3591920) plus the [WCXB multi-type benchmark](https://arxiv.org/pdf/2605.21097). **Not EXCLUSIVE**, and this pack did not re-run the benchmark — so the writer must attribute the accuracy figures to those external sources with dates, not present them as this pack's measurement. |
| **Not a structured/catalog scraper** (catalog test: 12 names in text but 0 structured rows) | **DOCUMENTED — design boundary** | trafilatura is a content-extraction (boilerplate-removal) tool, not a selector-based record extractor; recovering visible text but not typed rows is its documented scope. Per v3 §15, a design boundary ("use a selector/parser tool for typed records"), not a defect. Honest framing already present. |
| **No JavaScript rendering** (consumes static HTML) | **DOCUMENTED — design boundary** | trafilatura processes static HTML; pairing with a renderer for JS pages is the documented pattern. A documented boundary, not a bug. |
| **Lightweight install** (pip, no binary download) vs browser tools | **DOCUMENTED** | An accurate operational property (pure-Python dependency tree), not a novel finding. |

**Consequence for the writer:** nothing is `EXCLUSIVE`. The strongest true statements are (a) the verified clean before/after boilerplate removal + author/date metadata on the fixture, and (b) the **externally-documented** accuracy leadership (ScrapingHub F1 ~0.945; ACM/WCXB studies) — which must be cited to those sources with dates, not claimed as this pack's own benchmark. The "not a structured scraper / no JS" limitations are documented design boundaries.

## Part 6 self-check (v3 pre-submission checklist)

Honesty audit of the existing RM text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool ranking in this pack; the Writer Notes exclude "best/fastest" superlatives. The external benchmark's "most efficient open-source library" is a *third-party* result, not a claim this pack constructs — and must be attributed as such (see point 5). No self-built winner table to contradict.
2. **Claim-without-artifact (D4)** — *Pass.* Every test row cites an artifact (`local_article.txt`/`.md`/`.json`, `local_catalog_extraction.txt`, etc.). The accuracy-benchmark numbers are **not** in this pack's artifacts — and are correctly NOT presented as this pack's measurement; they belong in the article only with external citations (now linked in the Novelty table). No un-backed "we measured accuracy" sentence exists.
3. **Blind instrument (D2)** — *Pass (N/A).* No timing/memory/leak instrument; no speed claim. The RM avoids "fast" as a claim (Writer Notes exclude "fastest"). No blind-instrument exposure.
4. **Mis-attribution (D3)** — *Pass.* The catalog "0 structured rows" is correctly attributed to trafilatura's design scope (content extractor, not structured scraper), not a fault. The 500-handling `None` return is attributed to `fetch_url` behavior, correctly. No mis-attribution.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Addressed.* Novelty tags added above. Self-praise lint `grep -iE 'honest|independent|strongest|trustworthy'` → no hits in the trafilatura RM. The one discipline to enforce in the final draft: any accuracy-leadership language must be sourced to ScrapingHub/ACM/WCXB **with dates**, framed as external benchmark evidence, not as this pack's own result. Flagged for the writer.

**Self-check on this appended pass:** no self-evaluative adjectives on the tool; nothing tagged `EXCLUSIVE`; the accuracy figures are explicitly attributed to external benchmarks (not to this pack) with links; every verdict cites a link.

## As-of provenance check

Cross-checked against `metadata-snapshot.md`.

- **Snapshot date:** explicit **Fetched: 2026-07-07** plus a **Refresh 2026-07-09** delta table. Provenance present.
- **Stars / forks:** RM Writer Notes flags star/fork as caveat-only; the snapshot records 6,247 → 6,258 stars (2026-07-07 → 2026-07-09). **Writer note:** render as **"~6.26k stars as of 2026-07-09 (adbar/trafilatura)"** at point of use — and note this is a much smaller repo than the browser/crawler tools, which is context, not a quality signal.
- **Version:** RM tests 2.1.0 "= latest"; the snapshot confirms PyPI 2.1.0 / GitHub release v2.1.0 (2026-06-07), unchanged across the 2026-07-09 refresh (no version gap). Traceable.
- **External-benchmark provenance (extra care):** the accuracy F1 figures (e.g. ~0.945) come from the ScrapingHub benchmark and are tied to specific trafilatura versions in those sources (e.g. the reported 0.945 is for an older 0.5.1 line); the writer must **date and version-qualify** any imported benchmark number to its source, not attach it to the 2.1.0 tested here without checking the source's version. Flagged.
- **Instruction (do not fetch live):** star/version not re-pulled live this pass; Richard refreshes pre-publication. This section certifies traceability to the dated 2026-07-09 snapshot and recommends the "as of 2026-07-09" qualifier at point of use.

---

## Real-article extraction fidelity demo (bonus, 2026-07-14)

Added post-hoc (2026-07-14) as a **capability demonstration with a reproducible artifact** — deliberately **not** a scored benchmark. It fills the gap the original pack flagged twice ("add a genuine news/article public example (outside toscrape)"; the earlier public test used a Books-to-Scrape *product-description block*, not a real article). Runner: `tests/run_trafilatura_fidelity_demo.py`. trafilatura 2.1.0, Python 3.14, macOS arm64, same venv. **No timing was performed** (the machine runs concurrent workloads; timing would be meaningless here — this measures extraction *fidelity*, not speed). The runner reads saved fixtures from disk and does **not** touch the network, so it is deterministic and re-runnable offline.

### Method

Two real article pages were fetched **once each** (rate-limited, single request each) and saved as offline fixtures. For each, trafilatura's core path was run — `extract(..., output_format="txt" / "markdown" / "json", with_metadata=True, include_comments=False)` — and the following were recorded from the run output (not hand-typed): raw-HTML bytes vs extracted-body bytes; which known site-chrome markers were dropped vs leaked; which metadata fields were populated vs null; and a runtime SHA-256 cross-check against the recorded fixture hash.

### Fixtures (source + date + hash)

| Fixture | Kind | Source URL | Fetched | SHA-256 (raw HTML) |
|---|---|---|---|---|
| `news_wikipedia_web_scraping` | encyclopedic article | https://en.wikipedia.org/wiki/Web_scraping | 2026-07-14 | `b0d7e4117f4f1d365bc88bc7c09f2a1d8b748a06b47cb734096a77c1741c92cd` |
| `news_wikinews_7th_heaven` | news article (archived) | `https://en.wikinews.org/wiki/"7th_Heaven"_television_series_comes_to_an_end` | 2026-07-14 | `074c414c411f6d7a9f599ae0df7a70c616c5dbb90c124c92b0cd84ab8918ce7c` |

Fixtures under `artifacts/fixtures/`; fetch log `artifacts/logs/fidelity-fetch.log`. Both were chosen for long-term stability and genuine boilerplate (nav bar, sidebar/infobox, "Powered by MediaWiki" footer, edit/privacy chrome). The Wikinews page is in `Category:Archived` (frozen). A block-page signature scan was clean (the substring "captcha" appears only inside MediaWiki's `wgConfirmEdit…` edit-form JS config and, on the Wikipedia page, in the article's own prose about CAPTCHA — not an anti-bot challenge).

### Results (from `artifacts/results/trafilatura-fidelity-summary.json`)

| Fixture | Raw HTML bytes | Extracted body bytes | Body/raw ratio | Chrome markers dropped | Title | Date | Hostname | Author | Sitename |
|---|---:|---:|---:|---|---|---|---|---|---|
| Wikipedia `Web_scraping` | 230,049 | 26,673 | 0.116 | 4/4 | ✓ | 2005-09-17 | wikipedia.org | null | null |
| Wikinews `7th Heaven…` | 79,716 | 2,200 | 0.028 | 5/5 | ✓ | 2005-11-29 | wikinews.org | null | null |

On both pages every checked site-chrome marker ("Jump to content", "Privacy policy", "Powered by MediaWiki", "This page was last edited", plus "free news source" on Wikinews) was absent from the extracted body, and the expected article-body phrases survived. Per-fixture extraction outputs: `artifacts/raw/fidelity_<name>.txt` / `.md` / `.json`.

### Boundaries and honest notes

- **Not a benchmark.** The body/raw ratio measures how much markup + chrome was stripped, **not** extraction accuracy. There is no gold-standard corpus here, so **no F1 / precision / recall is computed or implied**. This demo neither confirms nor scores any accuracy figure.
- **The external accuracy figures are unchanged and still external.** The ~0.945 F1 cited elsewhere in this pack remains attributed to the **ScrapingHub article-extraction-benchmark** and is version-qualified there (that reported figure is for an older 0.5.1 line, **not** the 2.1.0 tested here). This bonus demo does **not** re-run that benchmark and must not be read as corroborating any specific F1 number.
- **Metadata misses reported, not hidden.** On both MediaWiki pages `author` and `sitename` came back null; those are recorded as misses in the summary JSON. `title`, `date`, and `hostname` were populated. (The extracted `date` reflects trafilatura's date detection on these pages — 2005 dates consistent with the articles' original publication — and is reported as-returned, not independently verified against a ground-truth publish date.)
- **What "body" includes.** Extracted body contains article-embedded content such as Wikipedia's reference/citation list and a "needs more citations" maintenance banner. That is article content, not site chrome — consistent with content extraction, and noted so the byte ratio is not over-read.
- **Scope of the fixtures.** Two MediaWiki-family pages (one encyclopedic, one news). They exercise real boilerplate removal on genuine articles but are a small, single-CMS sample; this is a demonstration, not a representative corpus.

### Novelty classification (this section)

`[DOCUMENTED]`. Main-content/boilerplate-stripped article extraction plus title/date metadata is trafilatura's advertised core capability. This section adds a *reproducible artifact on real article pages*; it does **not** claim any exclusive or undocumented behavior.

### Part 6 self-check (this appended section only)

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool ranking and no "fastest/best" claim; no timing at all. The only comparative numbers are within-fixture byte ratios, explicitly labeled as compression, not accuracy.
2. **Claim-without-artifact (D4)** — *Pass.* Every quantitative value (byte counts, ratios, marker-drop counts, metadata hits) is emitted by `tests/run_trafilatura_fidelity_demo.py` into `artifacts/results/trafilatura-fidelity-summary.json` and the per-fixture `artifacts/raw/fidelity_*` files; SHA-256s are cross-checked at runtime. The external ~0.945 F1 is *not* presented as this section's measurement — it is re-flagged as external and version-qualified.
3. **Blind instrument (D2)** — *Pass (N/A).* No timing/memory/leak instrument is used; no speed or resource claim is made. The one instrument (byte-length + substring drop-check) is trivially self-evident and its raw inputs (the `.txt` outputs) are saved for inspection.
4. **Mis-attribution (D3)** — *Pass.* Null `author`/`sitename` are attributed to trafilatura returning no value on these MediaWiki pages (reported as misses), not spun as a defect; the maintenance banner and citation list in the body are attributed to article content, not to a boilerplate-removal failure.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Pass.* Section tagged `[DOCUMENTED]`; `grep -iE 'honest|independent|strongest|trustworthy|best|fastest|unique'` over this section finds no self-evaluative adjective applied to the tool (the word "honest" appears only as a subsection label describing disclosure discipline, not as a claim about trafilatura).
