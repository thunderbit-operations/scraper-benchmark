# scrapy-playwright — Review Research Materials

Date: 2026-07-23

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **scrapy-playwright**,
the download-handler integration that lets a Scrapy project render selected
requests with Playwright. It reuses the exact local fixture (products, article,
JSON API, 500 route, crawl graph) from the standalone Scrapy pack so the two are
cross-comparable on identical ground truth. It does not rank scrapy-playwright
against other tools.

Central question (from the pre-test gate): should a Scrapy project render only
selected routes with Playwright, and what does that selective path actually cost?
The interesting answer is not "does JavaScript appear" — that is settled — but the
readiness policy, the memory that Scrapy's own stats cannot see, and the lifecycle
boundaries the README documents but reviews rarely exercise on a live process.

## Source Snapshot

Point-in-time metadata fetched from GitHub + PyPI on **2026-07-23** (see
`metadata-snapshot.md`; refresh within 48h before any final draft):

| Field | Value |
|---|---|
| Repo | [scrapy-plugins/scrapy-playwright](https://github.com/scrapy-plugins/scrapy-playwright) |
| Stars | **1,434** |
| Open issues | **15** |
| License | **BSD-3-Clause** |
| Latest release | **v0.0.48** (2026-07-10) |
| PyPI version tested | **0.0.48** |
| Python requirement | **>=3.10** |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 arm64 |
| Python | **3.12.13** (clean `uv` venv) |
| Scrapy | **2.17.0** |
| scrapy-playwright | **0.0.48** |
| playwright (Python) | **1.61.0** |
| Chromium | headless shell **149.0.7827.55** (playwright build v1228) |
| Correctness runner | [tests/run_correctness.py](tests/run_correctness.py) → [correctness-summary.json](artifacts/raw/correctness-summary.json) |
| Resource runner | [tests/run_resource.py](tests/run_resource.py) → [resource-summary.json](artifacts/raw/resource-summary.json) |
| Lifecycle runner | [tests/run_lifecycle.py](tests/run_lifecycle.py) → [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json) |
| Shared fixture | [tests/fixture_server.py](tests/fixture_server.py) (mirrors the Scrapy pack) |

Setup notes:

- Clean venv install of `scrapy scrapy-playwright playwright` succeeded; `playwright
  install chromium` downloaded the headless shell (~94 MiB compressed; the
  `ms-playwright` cache totals ~346 MB with the full chromium build present). This
  browser download is the real install cost over plain Scrapy.
- All correctness runs are fresh `scrapy runspider` subprocesses (avoids Twisted
  reactor reuse). Every conclusion field is computed from run output, not written
  as a constant.

## Test Coverage Completed

Local fixture ground truth: paginated static catalog (12 products), a
JavaScript-rendered catalog populated after a configurable delay (8 products via
`/api/dynamic-products`), an article with boilerplate, a 500 route, a crawl graph,
plus two adversarial routes (selector never appears; late DOM mutation).

### Correctness & behavior (15 runs, all rc=0)

| Test | Result | Runtime | Material value |
|---|---:|---:|---|
| Official quickstart (static Quotes/humor) | success, **12 items** | 0.6s | minimal public spider path |
| Local static catalog | **12/12 recall** | 1.2s | HTTP static path unchanged |
| Native dynamic **without** rendering | **0 cards** (expected gap) | 0.36s | reproduces the exact JS gap, same fixture |
| Native JSON API replay | **8/8 recall** | 0.40s | the no-browser workaround still works |
| Local 500 | status **500** captured | 0.37s | error path explicit |
| **Playwright + selector-wait** | **8/8 cards** | 1.9s | **the gap closed** |
| Readiness: no explicit wait | **0 cards** | 0.70s | render ≠ ready |
| Readiness: fixed wait 100ms (< 450ms) | **0 cards** | 0.84s | too-short fixed wait misses it |
| Readiness: fixed wait 1200ms (> 450ms) | **8 cards** | 1.9s | fixed wait works only if long enough |
| Adversarial: selector never appears | **bounded `TimeoutError` errback** | 4.0s | clean, bounded failure |
| Adversarial: late DOM append | **1 card** (first paint), late node missed | 0.74s | selector-wait readiness nuance |
| Selective crawl graph | **11 pages, 1 rendered**, in-scope, depth 0/1/2 = 1/3/7 | 1.8s | browser only where needed |
| Full-page screenshot | **8 cards**, PNG **73,877 B** | 1.6s | visual proof of render |
| Public Quotes JS **with** Playwright | **10 quote nodes** | 5.9s | native pack saw 0 here |

Screenshot artifact: [dynamic_catalog_rendered.png](artifacts/screenshots/dynamic_catalog_rendered.png)
("Loaded 8 products" + 8 rendered cards matching ground truth).

### Resource & reliability (3 isolated runs per condition)

Selective vs full rendering, **same extraction asserted** (identical url→cards map
after trailing-slash canonicalization — parity holds):

| Metric | Selective (browser only on `/dynamic/`) | All (browser on every request) | Verdict |
|---|---:|---:|---|
| Elapsed p50 (min–max) | **1.78s** (1.78–2.18) | **1.84s** (1.79–1.85) | **tie** (ranges overlap, 3.2% gap) |
| Peak tree RSS p50 (min–max) | **661 MB** (652–661) | **852 MB** (849–880) | **selective lower** (28.9%, non-overlapping) |

Reading: on this small graph, rendering everything is **not** meaningfully slower
in wall time — the browser is already launched and the extra light pages are cheap.
The real cost of over-rendering is **memory** (~29% higher peak), not time. This
corrects the common assumption that selective rendering is primarily a speed win.

Memory visibility (same all-render workload; frequent memusage sampling):

| Instrument | memusage/max (3 runs) | What it sees |
|---|---:|---|
| Scrapy default `MemoryUsage` extension | **~75 MB** (75.4 / 75.8 / 75.8) | the Python process only |
| `ScrapyPlaywrightMemoryUsageExtension` | **~738 MB** (738.6 / 738.6 / 738.2) | Python + browser processes |
| External psutil peak of the whole process tree | **~850 MB** (865 / 841 / 845) | ground truth |

Reading: Scrapy's default memory stat reports **~75 MB while the real
browser-inclusive footprint is ~850 MB** — it sees under one tenth of the truth
(~11× blind spot). The documented replacement extension recovers most of it (~738
MB ≈ 87% of the external tree peak), though it still trails the externally sampled
peak by ~13%. Numbers are macOS arm64, single machine; browser RSS varies run to
run, so the distribution — not a single number — is the artifact.

### Scheduler / lifecycle / backpressure

| Test | Observation |
|---|---|
| Page concurrency vs `CONCURRENT_REQUESTS` (8 pages) | wall time falls **8.0s → 2.5s → 1.6s** at concurrency **1 / 4 / 8** |
| `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT=2`, concurrency 8 | max concurrent pages capped at **2**, yet **all 8 still render** (pages close → slots free) |
| `PLAYWRIGHT_MAX_CONTEXTS=1`, concurrency 8 | single context (ctx max concurrent **1**), **all 8 render** |
| Auto-close path (no `include_page`) | `page_count` **6** == `page_count/closed` **6**, no leak |
| **Unclosed pages under cap=2** (held open, never closed) | exactly **2 render** (side-channel), then the crawl **wedges**; `closespider_timeout` cannot clean up the downloads stuck on the page semaphore; the process **required an external kill** |

The unclosed-page wedge is the concrete reason the README insists on closing
pages: under a page cap, leaked pages don't merely warn — they can stall the crawl
past `CLOSESPIDER_TIMEOUT` and defeat graceful shutdown entirely.

## Key Findings for the Writer

1. **The gap closes, but the decision is the readiness policy, not "does JS run."**
   Native Scrapy saw 0 cards on the dynamic catalog (and 0 on public Quotes/JS);
   Playwright with a `wait_for_selector` returned 8/8 (and 10 on Quotes/JS). But
   the readiness matrix on the *same* fixture shows render success is entirely
   about the wait condition: no-wait → 0, fixed 100ms → 0, fixed 1200ms → 8,
   selector-wait → 8. "Works on a JS page" is an incomplete claim; the correct
   readiness condition is the whole game.

2. **Scrapy's memory stats have a browser-sized blind spot, quantified.** The
   default extension reports ~75 MB against a real ~850 MB tree peak — an ~11×
   under-count. The documented `ScrapyPlaywrightMemoryUsageExtension` recovers most
   of it (~738 MB), and even it trails the external tree peak by ~13%. Anyone
   sizing a Playwright-backed Scrapy deployment off the default `memusage/max` will
   under-provision by an order of magnitude.

3. **Selective vs full rendering: the cost is memory, not wall time.** With
   extraction held identical, wall time was a tie (1.78s vs 1.84s) while peak RSS
   was 29% lower for the selective path (661 vs 852 MB). Render only what needs a
   browser — the payoff shows up in memory headroom, not obviously in speed.

4. **Selective rendering lives cleanly inside a normal Scrapy crawl.** One crawl
   reached 11 pages, rendered only the single `/dynamic/` route, and kept Scrapy's
   depth limit, scope, dedupe, and JSON/CSV export intact. The answer to "add
   Playwright to my Scrapy project?" is: yes, per-route, without giving up the
   framework.

5. **Page/context caps are real ceilings that still finish the job.** cap=2 held
   concurrent pages at 2 while all 8 rendered; contexts=1 kept a single context.
   These are backpressure controls, not failure modes — as long as pages close.

6. **Unclosed pages are a hard operational hazard, not a warning.** Held open under
   a cap, they wedged the crawl past `CLOSESPIDER_TIMEOUT` and needed an external
   kill. The README's page-close discipline is load-bearing.

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark.

| Dimension | Weight | Provisional score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **7** | clean venv install; extra cost is the chromium download (~94 MiB) |
| Static extraction (inherited) | 10 | **10** | HTTP path unchanged: 12/12 static, 8/8 JSON API |
| Dynamic rendering | 14 | **12** | 8/8 local + 10 public with correct readiness; 0 with wrong/no wait |
| Readiness ergonomics | 10 | **7** | success hinges on choosing the wait condition; easy to get 0 silently |
| Selective-render efficiency | 10 | **8** | same result, 29% lower peak RSS; wall-time tie |
| Memory observability | 10 | **6** | default stat 11× blind; documented extension needed and still ~13% short |
| Lifecycle / backpressure | 12 | **8** | caps behave; unclosed pages wedge the crawl |
| Crawl control (inherited) | 8 | **8** | depth/scope/dedupe/export intact under selective rendering |
| Adversarial robustness | 8 | **7** | bounded timeout errback; late-DOM readiness nuance surfaced |
| License/compliance fit | 8 | **7** | BSD-3-Clause; proxy is launch-level (documented boundary), no anti-bot framing |
| **Total** | **100** | **80** | provisional research-material score only, not a final rating |

## Gaps Before Final Blog Draft

- **No per-request proxy** — documented as a browser-launch/context option, not a
  per-request setting. Recorded as an untested documented boundary, **not bypassed**.
- **Restart / browser-disconnect behavior** — not reproduced (would require killing
  the browser mid-crawl); README documents it, pack did not test it.
- **`JOBDIR` pause/resume with Playwright requests** — untested.
- **Large-scale crawl (100–1,000 pages)** — memory growth over time and page-pool
  churn not measured; only a small graph tested.
- **AutoThrottle interaction with rendered requests** — untested.
- **Real anti-bot / protected sites** — explicitly out of scope; no bypass framing.
- **Memory numbers are single-machine macOS arm64**; report as platform-scoped.

## Novelty verification (pre-registration search)

Sources per finding: upstream issue tracker (`scrapy-plugins/scrapy-playwright`
**and** its engine, `microsoft/playwright`), the official README/docs, and the top
~20 SERP results. Verdict is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Capability / finding | Verdict | Prior record |
|---|---|---|
| Selective per-request rendering via `meta["playwright"]` | **DOCUMENTED** | The integration's core, specified in the README. Verified (11-page crawl, 1 rendered), not a discovery. |
| Readiness via `PageMethod("wait_for_selector"/"wait_for_timeout")` | **DOCUMENTED mechanism / EXCLUSIVE quantification** | `PageMethod` and the wait helpers are documented; the *quantified readiness matrix* on one controlled delayed-DOM fixture (no-wait 0 / fixed-100 0 / fixed-1200 8 / selector 8) is this pack's measurement, not found pre-quantified in SERP tutorials. |
| Browser memory invisible to default `MemoryUsage`; replacement extension exists | **DOCUMENTED (existence) / EXCLUSIVE (magnitude)** | The README documents the separate memory extension. The **11× under-count (75 MB vs ~850 MB) and the extension's residual ~13% shortfall vs external RSS** are this pack's measurements; no SERP source quantifies them. |
| Selective-vs-full cost is memory not wall-time (parity-asserted) | **EXCLUSIVE** | No SERP/issue source runs a same-extraction parity comparison; the wall-time tie + 29% RSS gap is novel measurement. |
| `PLAYWRIGHT_MAX_PAGES_PER_CONTEXT` / `MAX_CONTEXTS` as caps | **DOCUMENTED** | Documented settings; verified behavior (cap=2 → max 2 pages, all complete). |
| Unclosed `include_page` pages leak / must be closed | **DOCUMENTED boundary / EXCLUSIVE consequence** | The README warns to close pages. That leaked pages under a cap **wedge the crawl past `CLOSESPIDER_TIMEOUT` and require an external kill** is this pack's reproduced consequence, not stated in the docs. |
| No per-request proxy | **DOCUMENTED** | Documented boundary; recorded untested, not bypassed. |

**Consequence for the writer:** the strongest information-gain items are all
*quantifications of documented mechanisms* — the 11× memory blind spot, the
readiness matrix, and the memory-not-time cost of over-rendering. Nothing here is a
new capability; the value is measured numbers where SERP has only prose. No
superlative beyond what the distributions support.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* Elapsed selective-vs-all
   is reported as a **tie** (overlapping ranges); no "selective is faster" claim.
   The only bolded winner is RSS, which is non-overlapping (661 vs 852).
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a summary JSON or
   screenshot. Parity is an asserted equality of the two extraction maps, stored in
   `resource-summary.json`. No un-backed "cross-verified" prose.
3. **Blind instrument (D2)** — *Pass.* The RSS sampler was cross-checked against the
   memusage extension and against the default extension on the same runs; the three
   numbers (75 / 738 / 850) are reported together so the instrument's own coverage
   is visible. Each RSS run is a fresh subprocess (no prior-high-load contamination).
4. **Mis-attribution (D3)** — *Pass.* The 0-card readiness results are attributed to
   the wait condition (no-wait / too-short fixed), not to "Playwright can't render"
   — the selector-wait run on the same fixture returns 8. The unclosed-page wedge is
   attributed to leaked pages under a cap, reproduced with a side-channel counter,
   not inferred.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present;
   `grep -iE 'honest|independent|strongest|trustworthy'` over this file finds only
   "strongest information-gain items" (a category label, to be neutralized to
   "best-supported" in the final draft) — flagged, not silently kept.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-23** in `metadata-snapshot.md` with a
  refresh-within-48h note. Stars (1,434) / version (0.0.48) traceable to that fetch.
- **Versions:** tested scrapy-playwright 0.0.48 / Scrapy 2.17.0 / playwright 1.61.0
  / Chromium 149.0.7827.55, all read from `correctness-summary.json` → `versions`.
  Tested release == latest release on the snapshot day; no drift.

## Raw Artifact Index

- Correctness summary: [correctness-summary.json](artifacts/raw/correctness-summary.json)
- Resource summary: [resource-summary.json](artifacts/raw/resource-summary.json)
- Lifecycle summary: [lifecycle-summary.json](artifacts/raw/lifecycle-summary.json)
- Ground truth: [local_fixture_ground_truth.json](artifacts/raw/local_fixture_ground_truth.json)
- Rendered screenshot: [dynamic_catalog_rendered.png](artifacts/screenshots/dynamic_catalog_rendered.png)
- Per-run JSON + logs under [artifacts/raw/](artifacts/raw/) and [artifacts/logs/](artifacts/logs/)
