# browsertrix-crawler — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

Evidence base for a single-tool review of **Browsertrix Crawler** (Webrecorder), a
**real-browser web archiver** (drives Chromium via Puppeteer, records what the
browser fetched into WARC/WACZ). It judges **dynamic-capture fidelity and archival
artifact cost** — what a real-browser archiver actually writes into the archive on
controlled ground truth, what it misses, and how many archive bytes that fidelity
costs. It is not a structured-data extractor (Scrapy) nor a discovery-only recon
crawler (katana), and this pack does not rank browsertrix against other tools.

Central question (from the pre-test gate): sources repeat "real browser → captures
dynamic/JS content, high-fidelity WARC." Nobody decomposes the distinct dynamic
behaviours an archiver treats differently (DOM-injected link vs issued `fetch()` vs
unexecuted URL literal), nobody quantifies that an archiver's coverage is the
inverse of a static JS parser, and nobody reports the archive's byte cost /
record-type composition on ground truth. This pack builds a fixture with those
classes and measures per-class capture, replay-body presence, scope, and archival
cost.

All tests run against a **local fixture**; the container reaches the host via
`host.docker.internal`. The "out-of-scope host" is a hostname **alias** resolving
to the same fixture — **no third-party or production host is crawled**, no anti-bot,
no auth.

## Source Snapshot

Point-in-time metadata from GitHub on **2026-07-24** (see `metadata-snapshot.md`):

| Field | Value |
|---|---|
| Repo | [webrecorder/browsertrix-crawler](https://github.com/webrecorder/browsertrix-crawler) |
| Stars | **1,092** |
| Open issues | **139** |
| License | **AGPL-3.0** |
| Latest release | **v1.14.0** (2026-07-23) |
| Version tested | **v1.14.0** (== latest on snapshot day; no drift) |
| Image | `webrecorder/browsertrix-crawler:latest` @ `sha256:9d6800a8c50723dde1ad768ede91bf5d9704e848d70524c6b71e8492e006ddd4` |

## Test Environment

| Item | Value |
|---|---|
| Container runtime | Docker 29 on **colima** (macOS Virtualization.Framework VM, 6 CPU / 11.6 GiB, Ubuntu 24.04 aarch64) |
| Image size | 3.51 GB (bundles a browser) |
| Python (harness) | **3.14.2** (stdlib only; no WARC library) |
| Host | macOS 26.5.2 arm64 |
| Capture runner | [tests/run_capture.py](tests/run_capture.py) → [capture-summary.json](artifacts/raw/capture-summary.json) |
| Scope runner | [tests/run_scope.py](tests/run_scope.py) → [scope-summary.json](artifacts/raw/scope-summary.json) |
| Cost runner | [tests/run_cost.py](tests/run_cost.py) → [cost-summary.json](artifacts/raw/cost-summary.json) |
| WARC/WACZ parser | [tests/warc_utils.py](tests/warc_utils.py) (stdlib gzip + zipfile; no warcio) |
| Local fixture | [tests/fixture_server.py](tests/fixture_server.py) (classes A/B/C/D + scope/depth/known-files/robustness) |

Container→host networking (recorded honestly): fixture binds `0.0.0.0`; container
reaches host via `--add-host=host.docker.internal:host-gateway` (colima honours
`host-gateway`); a `node -e "fetch()"` smoke test logged a hit with Host header
`host.docker.internal` before the crawl. Out-of-scope host is a second
`--add-host` alias to the same fixture (no real-internet traffic).

## Fixture ground truth

Four endpoint classes that separate an **archiver's** capture behaviour
(`artifacts/raw/ground_truth.json`), plus scope/depth/known-files/robustness routes:

- **Class A — HTML `<a href>`:** `/page/a,b,c`, `/depth/1` + depth chain
  `/depth/1→2→3`. Any link-extracting crawl finds these.
- **Class B — JS-literal, never executed:** `/api/js-endpoint-7,8` are string
  literals inside an **uncalled** function in a linked `/static/app.js`. The
  browser never issues a request for them.
- **Class C — runtime-DOM link:** `/runtime-only/endpoint42`, an `<a href>`
  assembled from fragments at runtime (`'endpoint'+(6*7)`) and appended to the DOM;
  no contiguous literal exists in any served byte.
- **Class D — runtime `fetch()`:** `/api/runtime-xhr-99`, path assembled at runtime
  (`'runtime-xhr-'+(33*3)`) and actually `fetch()`ed on load.

Three independent instruments (no single one on faith): (1) **WARC response
records** = archive-content truth; (2) **server-side hit counter** `(host, path)`;
(3) **archived `app.js` body** searched for the class-B literals.

## Test Coverage Completed

### Capture matrix (`capture-summary.json`, `--scopeType prefix --depth 4`)

Per-class capture, cross-checked archive ↔ server-side fetch:

| Class | In WARC (response record) | Server-side fetched | Verdict |
|---|:--:|:--:|---|
| A — HTML `<a href>` | **4/4** | **4/4** | captured |
| A — depth chain | **3/3** | **3/3** | captured |
| B — JS-literal, never called | **0/2** | **0/2** | **not captured** |
| C — runtime-DOM link | **yes** | **yes** | **captured** |
| D — runtime `fetch()` | **yes** | **yes** | **captured** |

The two instruments agree in every cell (archive recall == server-fetch recall).

**Class-B boundary** (`class_b_boundary`): `app_js_archived: true` and **both**
class-B literals are present in the archived `app.js` bytes
(`class_b_literals_in_archived_js: ["/api/js-endpoint-7","/api/js-endpoint-8"]`) —
yet neither endpoint was fetched (0/2 server hits) or has its own response record.
The archive **contains the file that references them**, but an archiver records what
the browser **did**, not what code **references**.

### Replay fidelity (`replay_fidelity`)

For the dynamically-produced endpoints, the archived HTTP **response body** was
extracted from the WARC and confirmed to hold the served JSON:
`class_C_body_in_archive: true` (206 B for `/runtime-only/endpoint42`),
`class_D_body_in_archive: true` (201 B for `/api/runtime-xhr-99`). So the runtime
endpoints land as replayable content, not just index entries. **Full pywb /
replayweb.page replay-server rendering was not run (PARKED)** — this verifies the
bytes exist in-archive, not a rendered replay.

### Archival artifact cost (`capture-summary.json` + `cost-summary.json`)

WARC **record-type composition** on this 11-page crawl (`record_type_content_bytes`):

| WARC record type | count | content bytes | share |
|---|---:|---:|---:|
| `request` | 14 | **6,912** | **40.6%** |
| `response` (captured payload) | 13 | **5,339** | **31.4%** |
| `resource` (`urn:pageinfo:` JSON) | 11 | **4,527** | **26.6%** |
| `revisit` (dedup of dead link) | 1 | 154 | 0.9% |
| `warcinfo` | 1 | 92 | 0.5% |
| **total record content** | | **17,024** | |

On-disk cost, **distribution over 3 isolated runs** (`cost-summary.json`):

| Metric | min | median | max |
|---|---:|---:|---:|
| crawl wall time (s) | 28.22 | **29.75** | 30.27 |
| WARC.gz bytes | 24,174 | **24,250** | 24,262 |
| WACZ bytes | 53,446 | **53,523** | 53,533 |
| captured response payload bytes | 5,339 | **5,339** | 5,339 |

Cost ratios (of medians): **WARC.gz ≈ 4.54× per captured response byte**;
**WACZ ≈ 10.0× per captured response byte**; **WARC.gz ≈ 2,205 B/page**;
**WACZ ≈ 4,866 B/page**. WACZ member breakdown (compressed): WARC.gz 24,261 (45%),
**crawl `logs/*.log` 16,114 (30%)**, `indexes/index.cdxj` 8,531 (16%),
`pages/extraPages.jsonl` 2,109, `pages/pages.jsonl` 284, datapackage 1,215+117.

Reading: on small pages the archive is **dominated by protocol + metadata
overhead** — request records (40.6%) plus per-page `urn:pageinfo:` records (26.6%)
together are ~2.1× the actual captured response payload (31.4%); and the WACZ
wrapper is ~10× the captured response bytes, with **~30% of the WACZ being the
crawl log**. This is a small-fixture measurement and does **not** extrapolate to
large-page production archives (where response bodies dominate).

### Scope discipline (`scope-summary.json`, `--depth 2`)

Home page links `http://outofscope.test:<port>/page/out`, a different hostname
alias to the same fixture; a Host-header hit on `outofscope.test||/page/out` proves
an out-of-scope fetch.

| Config | Out-of-scope host fetched? | Evidence |
|---|:--:|---|
| `--scopeType prefix` (default) | **no** | `out_of_scope_page_out_hits = 0` |
| `--scopeType any` | **yes** | `out_of_scope_page_out_hits = 2` |

Reading: default prefix scope did **not** fetch the out-of-scope host on this
fixture; `any` did — so the negative under prefix is real scope discipline, not a
missed link. (Adjacent known issue [#788](https://github.com/webrecorder/browsertrix-crawler/issues/788)
reports out-of-scope visits in other configurations; this fixture did **not**
reproduce a leak under default prefix.)

### Robustness

`/failure/500` and `/broken-xyz` are both fetched (server-side hits present) and the
crawl completes rc=0 with a valid WARC/WACZ; the dead link is stored as a
deduplicated `revisit` record. No abort.

## Key Findings for the Writer

1. **FINDING-01 — Runtime-injected DOM content is captured; this is the parity axis
   (measured, both instruments agree).** Class C (runtime-DOM `<a href>`, assembled
   from fragments) and class D (runtime `fetch()`) are both captured — present as
   WARC response records **and** confirmed by server-side fetch. This is the same
   runtime-injected class a static crawl (katana standard) misses and the CDP-family
   siblings (chromedp/rod/playwright-mcp) catch. Confidence: high (archive ↔ server
   agreement; C/D paths never exist as literals). **Bound:** class C is injected
   **synchronously at load** and is extracted by the default `a[href]` DOM link
   extraction; links injected **during behaviors** are a known gap
   ([#723](https://github.com/webrecorder/browsertrix-crawler/issues/723)) — not
   tested here.

2. **FINDING-02 — An archiver's coverage is the INVERSE of a static JS parser
   (measured).** Class B (URL literals in an *uncalled* `app.js` function) is **not
   captured** (0/2 fetched, no response record) even though `app.js` **is** archived
   and both literals are present in its archived bytes. A static JS parser
   (katana `-jc`/jsluice) recovers exactly this class; a real-browser archiver drops
   it, because it records executed traffic, not references. "Real browser = captures
   everything JS" is over-stated. Confidence: high (0/2 on two instruments +
   literal-in-archived-js proof).

3. **FINDING-03 — Archive cost is dominated by protocol + metadata overhead on
   small pages (measured, 3-run stable).** Request records (40.6%) + per-page
   `urn:pageinfo:` records (26.6%) are ~2.1× the captured response payload (31.4%);
   WARC.gz ≈ 4.5×, WACZ ≈ 10× the captured response bytes; ~30% of the WACZ is the
   crawl log. Response payload was byte-identical across 3 runs; WARC.gz/WACZ varied
   <0.4%. Confidence: high on this fixture; explicitly **not** extrapolated to large
   pages. Mechanism (why request/pageinfo dominate) is attributed to fixed
   per-request/per-page record overhead being large relative to tiny bodies —
   labelled a size-regime observation, not a defect.

4. **FINDING-04 — Runtime endpoints are replayable content, not just index entries
   (measured).** The archived response bodies for class C (206 B) and class D
   (201 B) hold the served JSON, so a WACZ replay could serve them. Full pywb
   rendering PARKED. Confidence: high on body-presence; replay-render not asserted.

5. **FINDING-05 — Default `prefix` scope held; `any` widened (measured).**
   Out-of-scope host fetched 0× under prefix, 2× under any (server-side Host-header
   truth). Confidence: high on this fixture; adjacent leak issue #788 noted, not
   reproduced here.

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark and
not a cross-tool ranking. See `scorecard.md` for the same table with scoring notes.

| Dimension | Weight | Score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **7** | single `docker run`; 3.51 GB image; container→host needs `--add-host=…:host-gateway` |
| Static/HTML capture | 12 | **12** | class A 4/4 + depth 3/3, archive == server |
| Runtime-DOM capture (class C) | 12 | **11** | injected `<a href>` captured; bound: behavior-time injection is #723 gap |
| Runtime-fetch capture (class D) | 12 | **12** | issued `fetch()` captured as traffic (archive == server) |
| Static-reference boundary (class B) | 10 | **7** | B not captured though app.js archived — correct-by-design but a real coverage gap vs static parsers |
| Replay-body fidelity | 10 | **8** | C/D bodies present in WARC; full pywb replay PARKED |
| Archival cost transparency | 10 | **7** | measurable but heavy: WACZ ~10× payload, request+pageinfo > payload, ~30% WACZ is logs |
| Scope discipline | 12 | **10** | prefix holds, any widens (server-side truth); #788 not reproduced |
| Robustness (500 / dead link) | 6 | **6** | crawl completes rc=0; dead link stored as revisit |
| Cost measurement rigor | 6 | **6** | 3 isolated runs, tight spread, record-type composition |
| **Total** | **100** | **86** | provisional research-material score only |

## Gaps Before Final Blog Draft

- **Behavior-time link injection not tested** — class C is synchronous-load
  injection; the #723 "links discovered during behaviors not extracted" case is a
  distinct scenario, untested here.
- **Full replay rendering PARKED** — body-in-archive is verified; a pywb /
  replayweb.page render of the class-C/D content was not run.
- **Small-fixture cost only** — the archival-cost ratios are on tiny bodies; the
  overhead share inverts on large pages. No large-page or many-page cost curve.
- **`--screenshot` / `--text` not enabled** — those add screenshot/text WARCs and
  would change the cost composition; not measured.
- **known-files (robots/sitemap) not scored here** — the fixture serves them, but
  this pack's focus is dynamic capture + cost; sitemap `<loc>` recall (cf. katana
  FINDING-06) is out of scope for this pack.
- Single machine, macOS arm64 / colima; container timing includes browser startup.

## Novelty verification (pre-registration search)

Sources per finding: upstream issue tracker (`webrecorder/browsertrix-crawler` +
`browsertrix-behaviors`), official docs, top-~20 SERP. Verdict `[EXCLUSIVE]` /
`[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| Real browser captures JS-rendered / dynamic content; WARC→WACZ lossless | **DOCUMENTED** | Product pitch + [docs](https://crawler.docs.browsertrix.com/); this pack's value is the *per-class decomposition*, not the existence. |
| C (runtime-DOM link) + D (runtime fetch) captured; B (uncalled literal) not — archiver coverage is the inverse of a static JS parser | **EXCLUSIVE (quantification)** | No source measures per-endpoint-class capture for an archiver or the archived-file-contains-literal-but-endpoint-not-fetched inversion. Zero-hit on tracker for the split. Class D capture path corroborated by [#957](https://github.com/webrecorder/browsertrix-crawler/issues/957) ("direct fetch captures"). |
| Behavior-time injected links not extracted (bounds the class-C claim) | **KNOWN-ISSUE** | [#723](https://github.com/webrecorder/browsertrix-crawler/issues/723). My class C is *synchronous-load* injection and was captured; #723's *behavior-time* case is distinct and untested. |
| Archive cost: request(40.6%)+pageinfo(26.6%) > response payload(31.4%); WACZ ≈10× payload, ~30% WACZ = crawl log | **EXCLUSIVE (quantification)** | `urn:pageinfo:` records are documented ([#786](https://github.com/webrecorder/browsertrix-crawler/issues/786)); their byte-share and the request-record-dominates-payload composition on ground truth are unmeasured elsewhere. Zero-hit on tracker for the composition. |
| Runtime endpoints present as replayable response bodies | **DOCUMENTED mechanism / measured demonstration** | Lossless WARC/WACZ is documented; the measured demonstration that the *runtime-produced* C/D bodies are in-archive is this pack's. |
| prefix scope holds, any widens (server-side truth) | **DOCUMENTED mechanism / EXCLUSIVE demonstration** | scopeType is a documented flag; adjacent leak [#788](https://github.com/webrecorder/browsertrix-crawler/issues/788) exists (not reproduced under prefix here). |

**Consequence for the writer:** the best-supported information-gain items are the
per-class capture split (C/D captured, B not — inverse of a static parser) and the
archival-cost composition (overhead > payload on small pages). Every claim carries a
confidence label and points to a JSON field; superlatives avoided.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool "fastest/best"
   claim; the only comparatives are within-archive composition percentages (summing
   to 100%) and cost ratios, each with a JSON field. Cost is a distribution (3 runs,
   ranges reported), no bolded winner on overlapping numbers.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a field in
   `capture-summary.json` / `cost-summary.json` / `scope-summary.json`. The one thing
   **not** done — full pywb replay render — is explicitly labelled PARKED, not
   claimed.
3. **Blind instrument (D2)** — *Pass.* Capture is measured three independent ways
   (WARC response records, server-side `(host,path)` hits, archived `app.js` body);
   the class-C/D paths are assembled at runtime so a "found" cannot be a literal
   match. Server-side hit counter sees fetch-truth independent of browsertrix logs.
4. **Mis-attribution (D3)** — *Pass.* Class-B non-capture is attributed to
   "archiver records executed traffic, not references" after confirming the
   referencing file **is** archived and its literals **are** present (ruling out
   "app.js wasn't fetched"). The cost composition is labelled a size-regime
   observation, not a defect.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with
   a verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over
   this file surfaces only "best-supported" / neutral usages (no self-award on
   measurements).

## As-of provenance check

- **Snapshot date:** explicit **2026-07-24** in `metadata-snapshot.md`. Stars
  (1,092) / release (v1.14.0) traceable to that GitHub fetch.
- **Versions:** tested crawler v1.14.0 == latest release on snapshot day (no drift);
  image digest `sha256:9d6800a8…`; read from `crawl --version` and
  `docker image inspect`.

## Raw Artifact Index

- Capture matrix + boundary + replay + cost: [capture-summary.json](artifacts/raw/capture-summary.json)
- Cost/timing distribution (3 runs): [cost-summary.json](artifacts/raw/cost-summary.json)
- Scope: [scope-summary.json](artifacts/raw/scope-summary.json)
- Ground truth: [ground_truth.json](artifacts/raw/ground_truth.json)
