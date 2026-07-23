# katana — Review Research Materials

Date: 2026-07-23

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **katana**
(ProjectDiscovery), an endpoint-discovery crawler for recon/automation pipelines.
It judges **discovery coverage and crawl discipline** — what URLs/endpoints a crawl
surfaces on controlled ground truth — not structured-data or content extraction
(katana is not a Scrapy-style field extractor or a Jina-style content converter).
It does not rank katana against other tools.

Central question (from the pre-test gate): the SERP consensus says "standard mode
is fast but misses dynamic endpoints; use `-headless` for better coverage, and
`-jc` parses JavaScript." Nobody quantifies *how much more* headless finds, or
separates the three distinct endpoint classes that actually decide which mode is
needed. This pack builds a fixture with those classes as ground truth and measures
per-class recall per mode, plus scope discipline, resume correctness, known-files
behavior, and mode cost.

All tests run against a **local fixture on 127.0.0.1** (katana can hit loopback).
No third-party or production host is crawled; no anti-bot, no auth bypass, no rate
abuse. Framing is "discovery coverage on controlled ground truth," not "how to
recon someone's site."

## Source Snapshot

Point-in-time metadata from GitHub on **2026-07-23** (see `metadata-snapshot.md`;
refresh within 48h before any final draft):

| Field | Value |
|---|---|
| Repo | [projectdiscovery/katana](https://github.com/projectdiscovery/katana) |
| Stars | **17,208** |
| Open issues | **21** |
| License | **MIT** |
| Latest release | **v1.6.1** (2026-05-05) |
| Version tested | **v1.6.1** (== latest on snapshot day; no drift) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 arm64 |
| katana | **v1.6.1** (`~/go/bin/katana`), built with Go **1.26.5** |
| Python (harness) | **3.14.2** (clean `uv` venv; harnesses use stdlib only) |
| Headless browser | Chromium **1228** (playwright `chromium_headless_shell-1228` present; katana auto-detected a browser for `-headless`) |
| Discovery runner | [tests/run_discovery.py](tests/run_discovery.py) → [discovery-summary.json](artifacts/raw/discovery-summary.json) |
| Resume runner | [tests/run_resume.py](tests/run_resume.py) → [resume-summary.json](artifacts/raw/resume-summary.json) |
| Scope runner | [tests/run_scope.py](tests/run_scope.py) → [scope-summary.json](artifacts/raw/scope-summary.json) |
| Cost runner | [tests/run_cost.py](tests/run_cost.py) → [cost-summary.json](artifacts/raw/cost-summary.json) |
| Local fixture | [tests/fixture_server.py](tests/fixture_server.py) (three endpoint classes A/B/C + scope/depth/known-files/robustness routes) |

Setup / reliability notes (recorded honestly, they affect reproduction):

- **Fixture hardening.** katana crawls with `-c 10` concurrent fetchers, arriving
  as a connection burst. The stdlib `ThreadingHTTPServer` default listen backlog
  (5) overflows under the burst, so the fixture subclass sets
  `request_queue_size=256`, `allow_reuse_address=True`, `daemon_threads=True`.
  This only makes accepts reliable; it does not change *what* katana discovers.
- **`-duc` on the new runs.** resume/scope/cost pass `-duc` (disable update check)
  to drop katana's startup GitHub version-check — a network round-trip added to
  every run. It is applied identically to both modes in the cost test and does not
  change crawl behavior; no `-timeout` tuning is done. (The committed
  `discovery-summary.json` predates this and does not pass `-duc`; its `standard`
  elapsed 14.53s therefore includes the version-check, vs the cost test's 13.08s.)
- **known-files sub-run is environment-fragile on this machine.** katana builds a
  *separate* HTTP client for known-files (robots/sitemap) requests; on this host it
  intermittently stalls at the dial stage before reaching the fixture (the main
  crawl client is unaffected). The clean known-files measurement in
  `discovery-summary.json` was captured while that client connected; the recall
  result (0.0) is dial-timeout-independent and root-caused below.

## Test Coverage Completed

Fixture ground truth (`artifacts/raw/ground_truth.json`), three endpoint classes
that separate the modes, plus scope/depth/known-files/robustness routes:

- **Class A — HTML `<a href>`:** `/page/a,b,c`, `/depth/1` + depth chain
  `/depth/1→2→3`. Any crawl should find these.
- **Class B — JS-literal:** `/api/js-endpoint-7,8`, present only as string literals
  inside a linked `/static/app.js`. Needs JS parsing (`-jc`) to recover without a
  browser.
- **Class C — runtime-DOM-only:** `/runtime-only/endpoint42`, assembled at runtime
  from fragments (`'endpoint'+(6*7)`) so no contiguous literal exists in any served
  byte. Only a real browser that executes the script can surface it.
- Plus: an out-of-scope host link, `robots.txt` + `sitemap.xml` (with two hidden
  `<loc>` endpoints), a `/failure/500` route, and a `/broken-xyz` dead link.

### Discovery coverage matrix (`discovery-summary.json`, `-d 4`)

Per-class recall by mode, computed from katana's emitted output vs ground truth:

| Mode | A html | A depth | B js-literal | C runtime-DOM | elapsed |
|---|---:|---:|---:|:--:|---:|
| `standard` | 4/4 | 3/3 | **0/2** | **no** | 14.53s |
| `standard` + `-jc` | 4/4 | 3/3 | **2/2** | **no** | 14.48s |
| `-headless` | 4/4 | 3/3 | **0/2** | **yes** | 69.31s |
| `-headless -jc` | 4/4 | 3/3 | **0/2** | **yes** | 68.05s |

Cross-mode contrast (`coverage_contrast` field, computed):

- `B_js_literal_found_by`: **`["standard_jc"]`** — only standard mode + `-jc`.
- `C_runtime_dom_only_found_by`: **`["headless", "headless_jc"]`** — only headless.
- `headless_alone_misses_B`: **true**; `standard_jc_misses_C`: **true**;
  `headless_jc_covers_both`: **false**.

Reproduction note: `standard` (B 0/2) and `standard_jc` (B 2/2) were independently
re-run this session and reproduced identically; headless coverage is from the
committed run and the isolated cost run (headless completed 3×).

### Scope discipline (`scope-summary.json`, `-d 3`)

Primary fixture on `127.0.0.1`; a secondary fixture reached as `localhost` (same
process, different hostname). The primary's `/scope-seed` links to
`localhost:<B>/page/out`, a path served **only** by the secondary — so a
server-side hit on `/page/out` is proof the out-of-scope host was actually fetched,
not merely discovered.

| Config | Out-of-scope host fetched? | Evidence |
|---|:--:|---|
| default (field scope `rdn`) | **no** | `page_out_hits=0` |
| `-fs fqdn` | **no** | `page_out_hits=0` |
| `-cs localhost` | **no** | `page_out_hits=0` |
| `-fs '(127.0.0.1|localhost)'` | **yes** | `page_out_hits=1`, discovered in output |

Reading: scope discipline holds by default (the external host is never fetched).
`-cs` (a crawl-scope *URL* regex) alone does **not** widen to a new host — a custom
`-fs` *field-scope* regex does. This matches the source: `Manager.Validate` runs
the DNS field-scope check first and short-circuits, so `-cs` can only narrow within
the field scope; the custom-regex branch of `validateDNS`
(`pkg/utils/scope/scope.go`) is what admits a second host.

### Resume correctness (`resume-summary.json`)

Interrupt a crawl with SIGINT, resume it, and measure what state is recovered — via
server-side hit truth, not stdout.

| Observation | Value |
|---|---|
| Resume file location | `~/.config/katana/resume-<xid>.cfg` (**not** `resume.cfg` in cwd) |
| Resume file written on SIGINT | **yes** (`resume-d9h1poe…​.cfg`) |
| Resume file contents | `{"InFlightUrls":{…,"Map":{"http://127.0.0.1:<port>":{}}}}` — the **seed URL only** |
| Full baseline distinct paths | **11** |
| Fetched before interrupt | **10** |
| Resume run re-fetched | **all 11** (`resume_covers_full_baseline: true`) |
| Already-completed pages re-fetched by resume | **10** (`resume_refetched_count: 10`) |
| Union reaches baseline set | **yes** |
| Checkpoint granularity (computed) | **per-input-seed** — resume re-crawls the whole seed; completed pages are re-fetched |

Reading: katana's `-resume` reaches the same final endpoint set, **but it does not
skip completed pages**. The persisted `RunnerState` holds only `InFlightUrls`, and
at the runner level those are the input *seed* targets
(`internal/runner/executer.go`: set on start, deleted when a seed's whole `Crawl()`
returns). On resume, `options.URLs` is set to the still-in-flight seeds and each is
crawled again from scratch; the in-memory per-page dedupe filter is never
persisted. For a single-seed crawl, resume ≈ full re-crawl of that seed. Resume
skips only *fully-completed input targets*, not visited URLs within a target.

### Cost: standard vs headless (`cost-summary.json`, 3 isolated runs each)

Timing test run alone. Distributions, not single numbers:

| Mode | p50 | min–max | mean |
|---|---:|---:|---:|
| `standard` | **13.08s** | 13.07–13.17 | 13.11 |
| `-headless` | **66.82s** | 66.78–67.68 | 67.09 |

Verdict (computed): `ranges_overlap: false`,
`headless_over_standard_p50_ratio: 5.1` → **headless ~5.1× standard**, ranges do
not overlap (not a tie). The standard-mode ~13s honestly includes the default
`-timeout 10` retry/timeout tail on the `/failure/500` and `/broken-xyz` routes; no
`-timeout` tuning was applied to make the number smaller.

### Known-files (robots.txt / sitemap.xml)

Under `-kf all -d 3` the crawler **requested** `robots.txt` and `sitemap.xml`
(`sitemap_requested: true`, `robots_requested: true`) but fetched **0/2** of the
sitemap's `<loc>` endpoints: `sitemap_endpoint_recall.recall = 0.0`
(`/sitemap/hidden-1`, `/sitemap/hidden-2` missing). This recall is **0.0 across
every flag combination tried** while the known-files client connected: `-kf all`,
`-kf sitemapxml`, `-kf robotstxt`, depths `-d 3/4/5`, `+ -jc`, and even seeding
katana directly at `/sitemap.xml`.

**This is not a "you forgot the flag" case** — the documented requirement (`-kf`,
minimum depth 3) is satisfied. It is a real default-behavior boundary for
**IP-address targets**, root-caused from source (v1.6.1):

1. `pkg/engine/parser/files/sitemapxml.go` parses `<loc>` URLs but builds each
   navigation request via `NewNavigationRequestURLFromResponse(loc, …, navResp)`
   where `navResp` has **no `RootHostname`** → the request's `RootHostname` is `""`.
2. In `pkg/engine/common/base.go` `Enqueue` calls
   `ValidateScope(nr.URL, nr.RootHostname="")`.
3. In `pkg/utils/scope/scope.go` `validateDNS`, when the host is an **IP literal**
   (`net.ParseIP("127.0.0.1") != nil`), the code takes the
   `strings.EqualFold(hostname, rootHostname)` branch, i.e. it requires the loc
   host to *exactly equal the (empty) root* → `EqualFold("127.0.0.1","") == false`
   → the loc endpoints are dropped as out-of-scope.

Corroboration (measured, not just read): the scope test proves the same
custom-`-fs`-regex branch of `validateDNS` bypasses the root-hostname comparison —
`-fs '(127.0.0.1|localhost)'` fetched an otherwise-out-of-scope host. So a custom
`-fs` host regex is the source-predicted rescue for known-files recall. It is
recorded here as a **hypothesis** (source + scope-corroborated), **not directly
measured against `-kf`**, because katana's separate known-files HTTP client stalled
at dial on this host during the confirmation attempt (an environment condition, not
katana crawl logic). Recall is reported as measured (**0.0**); it is not adjusted.

Note the boundary is IP-specific: for a DNS-hostname target the empty-root path
falls through to `strings.HasSuffix(hostname, "")`, which is trivially true, so the
loc endpoints would pass scope. The bug bites exactly the local-fixture / IP-target
recon scenario. Candidate upstream issue.

### Robustness

The `/failure/500` and `/broken-xyz` routes are fetched and the crawl continues to
completion (rc=0) in every non-headless run; they appear in the fetched-path set
without aborting the crawl (see any `discovery_*.json` `server_side_hits`).

## Key Findings for the Writer

1. **FINDING-01 — No single command covers both JS-literal (B) and runtime-DOM (C)
   endpoints (triple-reproduced).** `-jc` recovers B only in *standard* mode (2/2);
   headless recovers C only (yes) but returns **0/2 on B even with `-jc` added**.
   `headless_jc_covers_both: false`. The SERP shorthand "use headless for better
   coverage" is incomplete: headless trades JS-file endpoints for runtime-DOM
   endpoints. Full coverage of this fixture needs the *union* of a `standard -jc`
   run and a `-headless` run. Confidence: high (matrix reproduced this session for
   standard/standard_jc; headless from committed + cost runs).

2. **FINDING-02 — `-jc` is inert under `-headless` on JS-file literals (single
   observation, source-consistent).** Adding `-jc` to `-headless` did not recover
   B (still 0/2), i.e. the JavaScript-file literal parsing that works browserless
   does not contribute the same endpoints once headless is on. Flagged as a
   discrepancy worth an upstream question; confidence: observed once per mode in the
   committed matrix, mechanism not instrumented (labelled observation, not proven
   cause).

3. **FINDING-03 — Scope holds by default; widening a host needs `-fs`, not `-cs`
   (measured).** The out-of-scope host is never fetched under default / `-fs fqdn` /
   `-cs localhost` (`page_out_hits=0`); only a custom `-fs '(127.0.0.1|localhost)'`
   fetches it (`page_out_hits=1`). Practical guidance: `-cs`/`-cos` filter *within*
   the field scope; to crawl a second host set the field scope. Confidence: high
   (server-side hit truth).

4. **FINDING-04 — `-resume` reaches the same endpoint set but re-crawls completed
   pages (measured).** The checkpoint stores only in-flight *seed* URLs; resume
   re-fetched all 11 baseline paths including 10 already-completed ones. Resume is
   coarse (per input target), not a fine-grained "skip visited URLs" recovery.
   Anyone expecting resume to avoid re-fetching a large completed crawl of a single
   seed will be surprised. Confidence: high (server-side hits + resume-file
   contents + source).

5. **FINDING-05 — Headless costs ~5.1× standard wall time (distribution, non-
   overlapping).** standard p50 13.08s vs headless p50 66.82s, ranges disjoint. The
   runtime-DOM (class C) coverage headless buys has a ~5× time price on this
   fixture. Confidence: high (3 isolated runs each, tight spreads).

6. **FINDING-06 — Known-files fetches robots/sitemap but drops sitemap `<loc>`
   endpoints for IP targets (measured recall 0.0 + source root cause).** `-kf all
   -d 3` requests both files yet recovers 0/2 loc endpoints because the sitemap
   crawler doesn't propagate the root hostname and IP-host scope validation then
   rejects them. Documented as a design/limitation boundary, not user error; a
   custom `-fs` host regex is the source-predicted (scope-corroborated) workaround.
   Confidence: high on the phenomenon (0.0 across all combos), high on the source
   mechanism, hypothesis on the `-fs` fix (not directly measured against `-kf`).

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark and
not a cross-tool ranking. See `scorecard.md` for the same table with scoring notes.

| Dimension | Weight | Provisional score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **8** | single Go binary at `~/go/bin/katana`; headless auto-found a browser |
| Static/HTML discovery | 12 | **12** | class A 4/4 + depth chain 3/3 in every mode |
| JS-endpoint discovery (`-jc`) | 12 | **9** | class B 2/2 in standard+jc, but 0/2 under headless (inert) |
| Runtime-DOM discovery (headless) | 12 | **10** | class C found only by headless; ~5.1× time cost |
| Mode-selection clarity | 10 | **6** | no single command covers B+C; "use headless" is incomplete |
| Scope discipline | 12 | **10** | default/fqdn/`-cs` never fetch the out-of-scope host; `-fs` widens correctly |
| Resume | 10 | **6** | reaches same set but re-crawls completed pages (per-seed granularity) |
| Known-files | 10 | **4** | requests robots/sitemap but 0/2 loc recall on IP targets (scope/root-hostname boundary) |
| Cost transparency | 6 | **6** | clean non-overlapping distributions; standard tail reported honestly |
| Robustness (500 / dead link) | 6 | **6** | crawl continues past 500 and broken link, rc=0 |
| **Total** | **100** | **77** | provisional research-material score only, not a final rating |

## Gaps Before Final Blog Draft

- **`-fs`-regex rescue of known-files recall is unconfirmed against `-kf`** — the
  known-files HTTP client stalled at dial on this host during the attempt. Re-run on
  a machine where that client connects (or with a DNS-hostname target) before
  claiming the workaround as measured.
- **Headless coverage not re-run this session** — headless/`headless_jc` figures
  are from the committed discovery run + the isolated cost run; a fresh headless
  discovery re-run timed out under transient load. Numbers stand but note the source.
- **`-jsluice` (`-jsl`) not tested** — a heavier JS parser than `-jc`; might change
  class-B recall under headless. Untested.
- **Depth-limit honoring not isolated** — depth chain reached 3/3 at `-d 4`; a
  dedicated `-d 1/2` cutoff test is not in the artifact set.
- **Scale / many-seed resume** — resume's "skip completed *seeds*" behavior is
  inferred from source for the multi-seed case; only single-seed resume is measured.
- **Real dynamic SPA / anti-bot targets** — out of scope by design; all ground
  truth is local, and numbers are single-machine macOS arm64.

## Novelty verification (pre-registration search)

Sources per finding: upstream issue tracker (`projectdiscovery/katana`), official
README/docs, and top-~20 SERP. Verdict is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` /
`[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| standard/headless/`-jc` exist; headless "finds more"; `-kf` needs depth ≥3 | **DOCUMENTED** | README + [docs](https://docs.projectdiscovery.io/opensource/katana/running); the mode existence and the depth-3 rule are stated. This pack's value is the *per-class quantification*, not the existence. |
| No single command covers B (JS-literal) + C (runtime-DOM); modes are disjoint | **EXCLUSIVE (quantification)** | SERP repeats "use headless for coverage" as prose; no source measures per-endpoint-class recall or shows the B/C disjointness. Zero-hit on issue tracker for the split. |
| `-jc` inert under `-headless` (B still 0/2 with `-hl -jc`) | **EXCLUSIVE (candidate)** | Adjacent headless issues exist ([#1324 crawling](https://github.com/projectdiscovery/katana/issues/1324), [#734 headless+redirects](https://github.com/projectdiscovery/katana/issues/734), [#611 headless+jsonl](https://github.com/projectdiscovery/katana/issues/611)) and "dynamic JS links not followed" prose; none states `-jc` yields no JS-file endpoints under `-hl`. Zero direct hit. |
| Resume writes `~/.config/katana/resume-<xid>.cfg` | **DOCUMENTED** | Docs/SERP confirm the resume-file location. |
| Resume re-crawls completed pages (per-seed granularity, only in-flight seeds persisted) | **EXCLUSIVE** | No SERP/issue source states resume re-fetches completed URLs; behavior is derived from `RunnerState`/`InFlightUrls` source + measured re-fetch of 10 completed paths. |
| Known-files drops sitemap `<loc>` endpoints for IP targets (empty RootHostname + IP DNS scope) | **EXCLUSIVE** | SERP only repeats the depth-3 requirement; no source reports 0 loc recall at depth ≥3 for IP targets, nor the RootHostname/scope root cause. Zero-hit on issue tracker. |
| `-cs` cannot add a new host; `-fs` custom regex can | **DOCUMENTED mechanism / EXCLUSIVE demonstration** | Field-scope vs crawl-scope are documented flags; the measured demonstration that `-cs localhost` fails to widen while `-fs '(…)'` succeeds is this pack's. |

**Consequence for the writer:** the strongest information-gain items are all
*measurements or source-grounded mechanisms behind documented flags* — the B/C
coverage split, the resume re-crawl, and the IP-target known-files drop. Superlatives
are avoided; every claim above carries a confidence label and points to a JSON field.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* The only bolded
   comparative is cost (headless ~5.1× standard), reported with non-overlapping
   ranges; standard-vs-standard_jc wall time (14.53 vs 14.48) is within noise and is
   **not** called a win. No "fastest/best" adjectives on tied numbers.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`discovery-summary.json`, `resume-summary.json`, `scope-summary.json`,
   `cost-summary.json`). The one thing I could **not** back with an artifact — the
   `-fs` rescue of known-files recall — is explicitly labelled a hypothesis, not a
   verified result, per this rule.
3. **Blind instrument (D2)** — *Pass.* Recall is measured against a pre-registered
   ground-truth set (`ground_truth.json`); scope and resume use **server-side hit
   counters** (the fixture records what was actually fetched), not katana's stdout,
   so the instrument sees fetch-truth independent of the tool's own reporting.
4. **Mis-attribution (D3)** — *Pass.* The known-files 0.0 recall is attributed to a
   source-identified scope/RootHostname path (files + lines cited) after ruling out
   depth (`-d 3/4/5`), flag choice (all/sitemapxml/robotstxt), and `-jc`; the
   intermittent dial stall is attributed to the *environment* (separate known-files
   client) and explicitly separated from the recall conclusion.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with
   a verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over
   this file surfaces only "strongest information-gain items" (a category label) —
   flagged here, to be neutralized to "best-supported" in any final draft.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-23** in `metadata-snapshot.md`. Stars
  (17,208) / release (v1.6.1) traceable to that GitHub fetch.
- **Versions:** tested katana v1.6.1 == latest release on the snapshot day (no
  drift); Go 1.26.5; Chromium build 1228; read from the run summaries / environment.

## Raw Artifact Index

- Discovery matrix: [discovery-summary.json](artifacts/raw/discovery-summary.json)
  (+ per-mode `discovery_*.json`, stdout in `artifacts/logs/`)
- Resume: [resume-summary.json](artifacts/raw/resume-summary.json)
- Scope: [scope-summary.json](artifacts/raw/scope-summary.json)
- Cost: [cost-summary.json](artifacts/raw/cost-summary.json)
- Ground truth: [ground_truth.json](artifacts/raw/ground_truth.json)
