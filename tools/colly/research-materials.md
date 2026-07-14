# Colly Research Materials

Writer-facing evidence pack. Not a publishable blog draft. Provisional throughout.

Tool: Colly (`gocolly/colly`), module `v2.3.0` (latest; ahead of GitHub release tag v2.2.0). Date: 2026-07-09, Go 1.26.5, macOS arm64.
Positioning (official): elegant scraper and crawler framework for Golang.

## What This Pack Covers

Colly's HTTP crawling + callback extraction on the shared fixtures. HTTP-only (no JS). Runner: `tests/main.go` (self-contained `httptest` server).

## Test Results

| Test | Target | Result | Evidence |
|---|---|---|---|
| Static catalog + pagination | local fixture | 12/12, recall 1.0 | `artifacts/raw/local_static_catalog.json` |
| Article extraction | local fixture | title + 3/3 paragraphs | `artifacts/raw/local_article.json` |
| Dynamic page (no JS) | local fixture | 0 cards (expected limitation) | `artifacts/raw/local_dynamic_page_no_js.json` |
| Dynamic JSON API | local fixture | 8/8, recall 1.0 | `artifacts/raw/local_dynamic_api.json` |
| HTTP 500 handling | local fixture | OnError, status 500 | `artifacts/raw/local_failure_500.json` |
| Crawl graph (MaxDepth 2) | local fixture | 17 pages | `artifacts/raw/local_crawl_graph.json` |
| Books to Scrape | public demo | 20 products | `artifacts/raw/public_books_to_scrape.json` |
| Quotes JS (no render) | public demo | 0 (expected limitation) | `artifacts/raw/public_quotes_js_no_render.json` |

Full details: `artifacts/raw/colly-test-summary.json`.

## The Core Story

Colly is a fast, dependency-light Go HTTP crawler with a clean callback model (`OnHTML`, `OnResponse`, `OnError`) and built-in depth control. Verified recall-1.0 static/article/JSON-API extraction, correct 500 routing to `OnError`, and a depth-limited crawl reaching 17 pages — all compiled into a single static Go binary. Like Scrapy and the HTTP crawlers, it does not run JavaScript (dynamic fixture and public Quotes JS both returned 0).

## Setup And Dependency Friction

- Needs a Go toolchain (installed Go 1.26.5 via Homebrew; the machine had none). Worth noting for non-Go teams.
- `go get github.com/gocolly/colly/v2` resolved cleanly to v2.3.0. No browser, no runtime deps beyond the compiled binary.
- The latest module (v2.3.0) is ahead of the newest GitHub release tag (v2.2.0) — a minor precision caveat.

## Successes

- Recall-1.0 static, article, and JSON-API extraction.
- Correct error handling (`OnError` with status 500).
- Depth-limited crawl (MaxDepth 2) traversed the fixture graph.
- Single static binary, fast, minimal footprint.

## Failures And Limitations (On Purpose)

- No JavaScript execution (dynamic fixture 0, Quotes JS 0). Pair with a browser/renderer for JS pages.
- Crawl-graph depth labels are the harness's own counter, not Colly's internal depth guarantee (report "17 pages under a depth-2 crawl").
- Not tested: async collector, rate limiting/politeness config, proxy rotation, distributed/queue storage backends.

## Writer Notes

Good blog material (verified): fast Go HTTP crawling with clean callbacks; recall-1.0 extraction; depth-limited crawl; single static binary and no runtime deps.

Caveat-only: star/fork metadata; module-vs-release-tag version nuance; crawl depth labels; single-machine run.

Exclusions: JS-rendering claims; "fastest/best" superlatives without a benchmark; proxy framing as anti-bot.

## Gaps Before Final Draft

- Test async collector + rate limiting/politeness.
- Proxy rotation and queue/storage backends (framed operationally).
- A benchmark vs Scrapy for the "fast Go" angle (currently only single-run timings).
- Refresh metadata within 48h of publication.

## Provisional Scorecard

See `scorecard.md`. Research aid, not a final rating.

---

## Novelty verification (pre-registration search)

Added post-hoc (2026-07-14) under methodology v3, §Part 1 Gate 1. Each capability/finding was searched against three sources before a novelty tag was assigned: the upstream issue tracker (`gocolly/colly`), the official docs (go-colly.org / pkg.go.dev), and the top ~20 SERP results. Classification is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`. **Novelty is decided by the search table, not by adjective.**

| Capability / finding | Verdict | Prior record |
|---|---|---|
| **Callback model** (`OnHTML` / `OnResponse` / `OnError`) + `MaxDepth` crawl control | **DOCUMENTED** | Core documented API: [colly pkg.go.dev](https://pkg.go.dev/github.com/gocolly/colly/v2), [go-colly.org docs](https://go-colly.org/docs/). Verified working (recall-1.0 extraction, 500 → `OnError`, depth-2 → 17 pages), but these are advertised primitives, not discoveries. |
| **Async collector / concurrency** (`colly.Async(true)`, `Collector.Wait()`, `LimitRule` parallelism) — the signature "fast Go crawler" angle | **DOCUMENTED** | The async/parallel model and per-domain concurrency limits are documented with official examples: [go-colly parallel example](https://go-colly.org/docs/examples/parallel/), [colly parallel source](https://github.com/gocolly/colly/blob/master/_examples/parallel/parallel.go). The README's ">1k requests/sec on a single core" is a **vendor performance claim** — this pack did **not** benchmark it (single-run timings only; see Gaps), so no measured speed claim is made and none is tagged EXCLUSIVE. |
| **No JavaScript execution** (dynamic fixture 0, Quotes JS 0) | **DOCUMENTED — design boundary** | Colly is an HTTP crawler by design; it is documented as not rendering JS. Per v3 §15 this is a documented capability boundary ("pair with a renderer"), not a defect. |
| **Single static binary / no runtime deps beyond the compiled binary** | **DOCUMENTED** | Inherent to Go compilation; an accurate operational property, not a novel finding. |
| **Module v2.3.0 is ahead of the newest GitHub release tag v2.2.0** | **DOCUMENTED (metadata precision note)** | A verifiable version-provenance nuance (Go module proxy `.../colly/v2` latest = v2.3.0, 2025-12-04, vs GitHub release tag v2.2.0). Worth stating precisely; not a capability finding. |

**Consequence for the writer:** nothing here is `EXCLUSIVE`. The "fast Go crawler" angle is legitimate framing but the ">1k req/sec" figure is the **vendor's** claim, not this pack's measurement — the article must attribute it as such or run a benchmark (a Gap). No speed superlative is supported by this pack's own data.

## Part 6 self-check (v3 pre-submission checklist)

Honesty audit of the existing RM text, not a rewrite.

1. **Self-contradicting winner sentence (D1)** — *Pass.* No head-to-head ranking table; the Writer Notes explicitly exclude "fastest/best superlatives without a benchmark." No bolded winner to contradict.
2. **Claim-without-artifact (D4)** — *Pass.* Every Test Results row cites an `artifacts/raw/*.json`. No "cross-verified with…" sentence lacks a backing file.
3. **Blind instrument (D2)** — *Pass, with a flag for the final draft.* No memory/leak/percentile instrument is used. **But** the Core Story opens "Colly is a **fast**, dependency-light Go HTTP crawler" — a zero-benchmark "fast" adjective. This pack ran only single-run timings, so per v3 §Part 5 the word "fast" must be dropped, attributed to the vendor's ">1k req/sec" claim, or backed by a distribution benchmark before publication. The RM's own Gaps already list "a benchmark vs Scrapy for the 'fast Go' angle (currently only single-run timings)" — consistent with this flag. Flagged, not rewritten (additive pass).
4. **Mis-attribution (D3)** — *Pass.* The crawl-depth "17 pages" is honestly attributed to the harness's own counter, not to a Colly depth guarantee ("report '17 pages under a depth-2 crawl'"). The 0-cards-on-dynamic result is attributed to no-JS-by-design, not a fault. No mis-attribution.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — *Addressed.* Novelty tags added above. Self-praise lint `grep -iE 'honest|independent|strongest|trustworthy'` → no hits in the colly RM. Only residual is the "fast" adjective (point 3). Clean apart from that.

**Self-check on this appended pass:** no self-evaluative adjectives on the tool; nothing tagged `EXCLUSIVE`; the ">1k req/sec" vendor number is explicitly *not* adopted as a measured result; every verdict cites a link.

## As-of provenance check

Cross-checked against `metadata-snapshot.md`.

- **Snapshot date:** explicit **Fetched: 2026-07-07** plus a **Refresh 2026-07-09** delta table. Provenance present.
- **Stars / forks:** RM Writer Notes flags star/fork as "caveat-only"; the snapshot records 25,364 (2026-07-07) → 25,367 (2026-07-09). Traceable. **Writer note:** render as **"~25.4k stars as of 2026-07-09 (gocolly/colly)"** at point of use.
- **Version:** RM's "module v2.3.0 (latest; ahead of GitHub release tag v2.2.0)" traces to the snapshot's 2026-07-09 refresh row (Go module proxy latest v2.3.0 for `.../colly/v2`, vs release tag v2.2.0). No drift; the nuance is documented in both files.
- **Instruction (do not fetch live):** not re-pulled live this pass; Richard refreshes pre-publication. This section certifies traceability to the dated 2026-07-09 snapshot and recommends the "as of 2026-07-09" qualifier at point of use.
