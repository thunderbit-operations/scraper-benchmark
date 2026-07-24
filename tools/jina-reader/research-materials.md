# jina-reader — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

Evidence base for a single-tool review of **Jina Reader** — the hosted
`https://r.jina.ai/<URL>` service that fetches a live URL server-side and returns
LLM-friendly Markdown. It judges the **service**: (a) the **access** gate
(anonymous vs authenticated), and (b) the **fidelity** of the returned markdown as
a function of the `X-Engine` choice and the cache, on public pages with known
ground truth. It does **not** re-judge Mozilla Readability's extraction algorithm
(Jina runs Readability internally; that library is a *separate* pack in this
series), does **not** test paid tiers / `s.jina.ai` search / `mcp.jina.ai` /
ReaderLM-v2, and does **not** rank Jina against other tools here.

The keyed fidelity matrix runs against **quotes.toscrape.com** — the same public JS
target the Scrapy / scrapy-playwright packs use, a same-target thread across the
series. The access evidence comes from earlier anonymous probes against four public
pages (books/quotes to-scrape, ScrapeThisSite forms, a Wikipedia article).

**Key/credential boundary.** No API key appears in this pack — not in any script,
artifact, log, or commit. The reproduction harness reads the key from a `$JINA_KEY`
environment variable the operator sets at run time (`tests/run_engine_matrix.sh`).
Every response artifact in `artifacts/raw/` is public quotes.toscrape.com content.

## Source Snapshot

Point-in-time GitHub metadata (as-of **2026-07-10**; refresh within 48h before any
final draft — see `metadata-snapshot.md`):

| Field | Value |
|---|---|
| Repo | [jina-ai/reader](https://github.com/jina-ai/reader) |
| Stars | **11,506** |
| Open issues | **25** |
| License | **Apache-2.0** |
| Primary language | **TypeScript** |
| Tagged releases | **0** (continuous deploy from `main`; last commit 2026-05-22) |

This is the profile of a **hosted SaaS with an open-source core**, not a
`pip install` library — "call an API," and the star count understates usage.

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS arm64 |
| Reader endpoint | `https://r.jina.ai/<URL>` (GET prefix) |
| Client | `curl` (system), `Authorization: Bearer $JINA_KEY` from env |
| Keyed fidelity target | [quotes.toscrape.com](https://quotes.toscrape.com/) — `/js` (JS-injected) + `/` (server-rendered) |
| Access-probe targets | books/quotes to-scrape, ScrapeThisSite forms, Wikipedia Web_scraping |
| Engine/cache harness | [tests/run_engine_matrix.sh](tests/run_engine_matrix.sh) → [engine-matrix.ndjson](artifacts/raw/engine-matrix.ndjson) + one `.md` per cell |
| Recall recompute (no network) | [tests/recompute_recall.py](tests/recompute_recall.py) → [recall_recompute.json](artifacts/raw/recall_recompute.json) |
| Anonymous access log | [jina_quotes_toscrape_response.txt](artifacts/raw/jina_quotes_toscrape_response.txt) (+ 3 sibling `.txt`) |
| Engine-matrix test date | **2026-07-24** |
| Anonymous-probe date | **2026-07-10** |

**Ground truth.** quotes.toscrape.com page 1 shows 10 quotes from **8 distinct
authors**. `/js` injects them via JavaScript at runtime; `/` (root) server-renders
them. Recall = distinct authors recovered / 8. The `/js/page/N/` deeper pages are
**not** scored — their behind-a-proxy fetch was unreliable and the main loop
dropped them; only page 1's 8 authors are used.

**Anti-hardcoding.** The harness writes only raw response bytes (`.md`) plus
`curl`-measured http/time/size; `recompute_recall.py` **re-derives** byte size,
author recall, and Jina's self-reported degradation flags ("cached snapshot" /
"not fully loaded") from those `.md` files with **no network and no key**, and
asserts they equal the shipped matrix. `recall_recompute.json` records
`consistent_with_shipped_matrix = true`. No recall/byte constant is hand-typed.

## Test Coverage Completed

### The engine × cache matrix (all keyed; `engine-matrix.ndjson`, re-derived by `recompute_recall.py`)

Recall and bytes below are the **recomputed** values (they equal the shipped
matrix cell-for-cell); `time_s` is the single-run `curl` wall time from that
matrix row. All calls carry the key; the only variables are the page (JS vs
static), the `X-Engine` header, and whether the cache is bypassed.

| Cell | Page | `X-Engine` | Cache | Recall /8 | Bytes | time_s (1 run) |
|---|---|---|---:|:--:|---:|---:|
| `nc_js_default` | `/js` | *auto* (default) | bypass | **8** | 1193 | **4.81** |
| `nc_js_browser` | `/js` | browser | bypass | **8** | 1193 | 1.94 |
| `nc_js_browser_wait` | `/js` | browser +`X-Wait-For-Selector:.quote` | bypass | **8** | 1193 | 1.77 |
| `nc_js_direct` | `/js` | **direct** | bypass | **0** | **348** | **0.99** |
| `nc_static_default` | `/` | *auto* | bypass | 8 | 1787 | 1.69 |
| `nc_static_direct` | `/` | **direct** | bypass | **8** | 1787 | **0.94** |
| `cached_js` | `/js` | *auto* | **warm** | 8 | 1193 | 0.96 |

Four independent readings come out of this grid.

### H2 verdict — SUPPORTED. `X-Engine: direct` is JS-blind (0/8); `browser`/`auto` recover 8/8 on the same URL

On the JS page with cache bypassed, `direct` returns **0 of 8** authors in **348
bytes** — the raw markdown ([nc_js_direct.md](artifacts/raw/nc_js_direct.md)) is
nav chrome only ("Login", "Next →", "Made with ❤ by Zyte"); the ten quotes never
appear because `direct` does not execute the page's JavaScript. `browser` and the
default `auto` both return **8/8 in 1193 bytes**, byte-identical to each other.
`direct` = `curl`-value in the docs. Confidence: **high** (recomputed, deterministic).

Nuance that makes this a *characterization* rather than a "gotcha": see H3.

### H3 verdict — SUPPORTED. `direct` is a **pure HTTP fetch**, not a lossy engine: 8/8 on the server-rendered twin

Run `direct` against the **static** root page (`/`, same content server-rendered)
and it returns **8/8 in 1787 bytes** — byte-identical fidelity to `auto` on that
page ([nc_static_direct.md](artifacts/raw/nc_static_direct.md) == fidelity of
`nc_static_default`, differing only in `time_s`). So `direct` is **not** worse in
general; it is a plain HTTP GET that is perfect on server-rendered HTML and **blind
only to client-side-JS-injected content**. This isolates the failure precisely: the
0/8 is a rendering-mode mismatch, **by design**, not an extraction defect. And
because the **default is `auto`, which already renders JS (8/8)**, a user who never
touches headers is safe; the silent-loss trap fires **only if you explicitly set
`X-Engine: direct`/`curl`** (e.g. chasing speed) on a JS page. Confidence: **high**.

### FINDING — timing reversal: `auto` (default) is the **slowest** engine while producing output identical to `browser`

On the JS page, no-cache, single run: `direct` 0.99s < `browser` 1.94s ≈
`browser+wait` 1.77s < **`auto` 4.81s**. `auto` is ~**2.5×** slower than pinning
`browser` and ~**4.9×** slower than `direct`, yet `auto` and `browser` return the
**exact same 1193 bytes / 8 authors**. Pinning `browser` is therefore strictly
faster than the default at zero fidelity cost on this page. The mechanism is
visible in the cache column: warm-cache `auto` (`cached_js`) returns in **0.96s**,
so the 4.81s is specifically the **cold, no-cache fresh-render** path `auto` takes;
`browser` on the same cold path is faster. Even on the static page `auto` (1.69s)
trails `direct` (0.94s). Confidence: **medium** — the in-pack matrix is **one run
per cell**; the operator observed this ordering hold across **3 no-cache reps**
(`browser` ~1.7–4.4s, `auto` ~4.8–9.5s; the two bands do not cross), but the full
per-run raw is not all shipped here, so magnitudes are directional, not a
distribution. This is reported as a finding, **not** used to crown a "fastest."

### H1 verdict — SUPPORTED by decomposition (the pack's core headline): the key buys **access**, not **fidelity**

The composite claim is that the API key changes **whether you get content**, not
**what content you get**. Two legs:

1. **Access (H4).** From this datacenter egress the anonymous prefix returns a hard
   **HTTP 401 `AuthenticationRequiredError`** (`status 40103`, *"blocked from
   performing anonymous queries due to bad network reputation"*) on **every** target,
   all four shipped anonymous GET probes (single datacenter egress) — verbatim in
   [jina_quotes_toscrape_response.txt](artifacts/raw/jina_quotes_toscrape_response.txt).
   No markdown is produced anonymously; the key flips 401 → 200.
2. **Fidelity (H2/H3 + cache).** With the key held **constant** across the whole
   matrix, fidelity varies **entirely** by the `X-Engine` header (0/8 vs 8/8) and
   the cache — never by anything the key controls. Fidelity is thus a function of
   *engine + cache*, orthogonal to the key.

Access denied when anonymous + fidelity governed by engine/cache when keyed ⇒ the
key's role is **isolated to access**. Confidence: **medium-high**, with one honest
limit: because anonymous is 401 from this egress, we could **not** run the cleanest
possible test — a keyed-vs-anonymous **byte-diff of the same page both can fetch** —
so H1 rests on the decomposition above, not on a direct anon/keyed fidelity A/B.
That direct A/B needs a residential IP where anonymous returns 200 (a Gap).

### H4 verdict — SUPPORTED (quantified). Anonymous datacenter access is a hard 401, not a degraded fetch

The access outcome is **binary**, not a low-fidelity fetch: anonymous datacenter =
401 refusal (0 bytes of content, 371-byte error body), keyed = 200. This cleanly
separates *"cannot fetch"* (anonymous) from *"fetched, fidelity depends on engine"*
(keyed). Corroborated by two independent egress points and by docs describing
anonymous traffic as the lowest-trust pool. The error blames **AS7922 (Comcast)**
while the real egress was **AS25820 (IT7 Networks)** — flag as a *"don't trust the
error's ASN"* sidebar, **not** a bug claim (likely an upstream-hop/stale-label
resolution). Confidence: **high** for the 401 result (reproduced on all 4 shipped probes); **low** for
the ASN mechanism (single observation, not attributed).

### H5 verdict — DOWNGRADED to a Gap. Anonymous-vs-keyed header gating is untestable from this egress

The pretest asked which fidelity headers (`X-Target-Selector`, `X-Respond-With`,
`X-Retain-Links`) take effect **anonymously vs keyed**. Since anonymous is 401 from
this egress, "does header X work anonymously" is **unanswerable** here. Keyed, we
confirmed three headers *take effect*: `X-No-Cache` (fresh vs warm timing/​bytes
differ), `X-Engine` (0/8 vs 8/8), and `X-Wait-For-Selector: .quote` (accepted;
`browser+wait` 8/8, ~same as plain `browser`). The anon-vs-keyed **gating**
question is moved to Gaps.

### Cache — honest degradation note, NOT a headline

Jina's docs say the default path may serve a cached snapshot and it self-reports a
*"cached snapshot"* / *"not fully loaded"* warning when it does. The operator
**observed once** a cold cache return an empty/stale quote-less snapshot (0/8), but
after the cache warmed this could **not** be cleanly reproduced: the shipped
`cached_js` cell is **warm and full (8/8, 1193 B, no warning flag)** —
`recompute_recall.py` confirms `cached_snapshot=false` on it. Therefore this pack
makes **no** "cache trap A/B" claim (there is no shipped artifact of a stale cache
hit). What is supported: (i) `X-No-Cache: true` reliably forces a fresh fetch;
(ii) warm-cache `auto` (0.96s) is far faster than cold no-cache `auto` (4.81s), so
the default's latency is dominated by whether it renders fresh; (iii) Jina *can*
return a cached snapshot and *does* flag it — treat a missing `X-No-Cache` as
"you may get a snapshot, check the flag." Confidence: **high** for (i)/(ii)
(matrix); **single-observation, not reproduced** for the stale 0/8 hit.

## Key Findings for the Writer

1. **FINDING-01 — The API key buys ACCESS, not FIDELITY (core headline).** Anonymous
   datacenter calls are refused with a hard 401; with a key, what content you get is
   determined by `X-Engine` + cache, never by the key. Say this plainly: a key does
   **not** make the markdown better, it makes the request *allowed*. Confidence:
   medium-high (decomposition; direct anon/keyed byte-diff blocked by the 401).
   Novelty: **DOCUMENTED** that anonymous is throttled / key recommended;
   **EXCLUSIVE** as a measured access-vs-fidelity decomposition.

2. **FINDING-02 — `X-Engine: direct` returns 0/8 on a JS page (348 B of nav only);
   `browser`/`auto` return 8/8 (1193 B) on the same URL.** The `direct`/`curl`
   engine does not run JavaScript. Confidence: high (recomputed). Novelty:
   DOCUMENTED that `browser` renders JS; **EXCLUSIVE** as the 0/8-vs-8/8
   ground-truth recall quantification.

3. **FINDING-03 — `direct` is a pure HTTP fetch, not a lossy engine: 8/8 on the
   server-rendered twin, byte-identical to `auto`.** The 0/8 is a rendering-mode
   mismatch by design; the default `auto` renders JS so header-free users are safe;
   the loss fires only if you *explicitly* pick `direct` on a JS page. Confidence:
   high. Novelty: **EXCLUSIVE** (the static-8/8 isolation showing `direct` isn't
   "worse," just JS-blind).

4. **FINDING-04 — Timing reversal: the default `auto` engine is the SLOWEST (4.81s
   cold) while returning output identical to `browser` (1.94s); `direct` fastest
   (0.99s).** Pinning `browser` is ~2.5× faster than the default at no fidelity cost;
   the cold no-cache render is the cost (warm `auto` = 0.96s). Confidence: medium
   (in-pack single run per cell; operator saw the ordering across 3 reps, bands
   `browser` 1.7–4.4s / `auto` 4.8–9.5s non-overlapping). Novelty: **EXCLUSIVE**
   (counterintuitive quantified timing; no source says `auto` is multiples slower
   than a pinned `browser`).

5. **FINDING-05 — Anonymous datacenter access is a hard 401 (`AuthenticationRequiredError`),
   not a degraded fetch; the error's ASN is misattributed.** Binary access outcome,
   reproduced on all 4 shipped anonymous GET probes (single datacenter egress). Confidence: high
   for the 401; low for the ASN mechanism (flag, don't claim). Novelty:
   **KNOWN-ISSUE** ([#1222]) for anonymous-block behavior; the exact status/error
   quantification is this pack's, the ASN note stays a caveat.

## Provisional Scorecard

Provisional, based only on the completed engine/access material. Not a final
benchmark, not a cross-tool ranking. See `scorecard.md` for scoring notes. Scoped
to the tested public targets and the fetch dates (Jina's server behavior can change;
reported as-of).

| Dimension | Weight | Score | Evidence |
|---|---:|---:|---|
| Setup and first run | 10 | **5** | "just add a prefix" is trivial in theory, but anonymous datacenter calls 401 — real first run needs a key |
| Access model (anon vs keyed) | 12 | **7** | binary 401→200; documented low-trust pool; key is the intended path, not optional from a server |
| JS-render fidelity (default) | 14 | **12** | default `auto` recovers 8/8 on the JS page; header-free users get full content |
| Engine correctness / predictability | 12 | **9** | `direct` 0/8 JS but 8/8 static (pure HTTP, by design); `browser`/`auto` 8/8; predictable once understood |
| Latency / engine efficiency | 10 | **6** | default `auto` slowest (4.81s cold) for identical output; `browser` ~2.5× faster; single-run in-pack |
| Cache behavior / control | 8 | **6** | `X-No-Cache` forces fresh; default may serve a flagged snapshot; one unreproduced stale 0/8 hit |
| Output cleanliness | 8 | **7** | returned markdown is clean (title + quotes, minimal chrome); boilerplate precision not exhaustively scored |
| Developer experience | 8 | **7** | maximally simple API shape (URL prefix + headers); docs clear that a key is intended |
| Operations (hosted) | 8 | **6** | nothing to run; hard dependency on Jina reputation gating + key for server use |
| Maintenance / ecosystem | 6 | **6** | active repo to 2026-05-22, Apache-2.0, MCP + ReaderLM; 0 tagged releases makes pinning awkward |
| Reproducibility of this pack | 4 | **3** | full harness shipped, key from env; timing single-run, anon-path residential retest deferred |
| **Total** | **100** | **74** | provisional research-material score only, not a final rating |

## Gaps Before Final Blog Draft

- **Direct anon-vs-keyed fidelity byte-diff not run.** The cleanest H1 test needs a
  residential IP where anonymous returns 200; from this datacenter egress anonymous
  is 401, so H1 rests on decomposition. Retest from a home connection to close it.
- **Timing is not a distribution.** The shipped matrix is one run per cell; the 3-rep
  ranges are operator-observed, not fully shipped. A ≥3-run harness with reported
  variance would harden FINDING-04.
- **Cache stale-hit not reproduced.** The one cold 0/8 snapshot could not be
  re-captured after warming; no artifact, so no headline — needs a cold-cache-forcing
  method to reproduce cleanly.
- **H5 header gating (anon vs keyed) unanswered** — blocked by the 401; and
  `X-Target-Selector` / `X-Respond-With` / `X-Retain-Links` effect not exhaustively
  measured keyed.
- **Boilerplate precision not scored against ground truth.** Recall is measured; a
  precision study (real content wrongly dropped) on richer pages (Wikipedia tables,
  the forms page's 1 table) is deferred — ground-truth HTML metrics already captured
  in the prior pass.
- **Single engine matrix, single machine, one JS fixture** (quotes.toscrape.com);
  paid tier / `s.jina.ai` / MCP / ReaderLM-v2 all out of scope.

## Novelty verification (pre-registration search)

Per-finding verdict against the reader issue tracker, the Reader API docs (`X-Engine`,
`X-No-Cache`, `X-Wait-For-Selector`), and the top-~20 SERP. `[EXCLUSIVE]` requires
zero prior quantified record.

| Finding | Verdict | Prior record |
|---|---|---|
| `X-Engine` values (`auto`/`browser`/`direct`|`curl`) exist; `browser` renders JS, `curl`/`direct` doesn't | **DOCUMENTED** | Reader API header docs; existence + qualitative direction, not this pack's value |
| anonymous traffic is rate-limited / lowest-trust; key recommended | **DOCUMENTED** | Reader API page; Elastic search-labs tutorial |
| anonymous block returns 401 `AuthenticationRequiredError` | **KNOWN-ISSUE** | [jina-ai/reader #1222] |
| `direct` 0/8 vs `browser`/`auto` 8/8 ground-truth author recall on the same URL | **EXCLUSIVE (quantification)** | no public per-engine ground-truth recall; zero-hit |
| `direct` = pure HTTP: 8/8 on the server-rendered twin (isolates JS-blindness as by-design, not lossy) | **EXCLUSIVE** | no source measures `direct` on a static twin to isolate it |
| timing reversal: default `auto` slowest (4.81s) for output identical to `browser` (1.94s); `direct` fastest | **EXCLUSIVE (quantification)** | docs never state `auto` is multiples slower than a pinned `browser`; zero-hit |
| access-vs-fidelity decomposition (key = access, engine+cache = fidelity) | **EXCLUSIVE (framing + measurement)** | every source treats the key purely as a quota lever; none decomposes fidelity from access |
| error ASN misattributed (AS7922 vs real AS25820) | **caveat, not claimed** | single observation, mechanism not attributed |
| default may serve a flagged cached snapshot; `X-No-Cache` forces fresh | **DOCUMENTED** | Reader API cache docs; the one stale 0/8 hit is reported as not reproduced |

[jina-ai/reader #1222]: https://github.com/jina-ai/reader/issues/1222

**Consequence for the writer:** the information-gain items are measurements behind
documented behavior — the per-engine recall (0/8 vs 8/8), the `direct`-on-static
isolation, the `auto`-slowest timing reversal, and the access-vs-fidelity
decomposition. Existence/qualitative claims stay DOCUMENTED; the anonymous-block
stays KNOWN-ISSUE; the cache stale-hit stays not-reproduced; the ASN note stays a
caveat.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* No "fastest/best" crown:
   FINDING-04 reports the timing ordering with the honest medium-confidence n=1
   caveat and the non-overlapping operator ranges, and explicitly says `browser`
   pins faster *at identical output* rather than declaring a winner. 8/8 ties across
   engines are stated as ties.
2. **Claim-without-artifact (D4)** — *Pass.* Every recall/byte number is re-derived
   by `recompute_recall.py` from the shipped `.md` and asserted equal to the matrix
   (`recall_recompute.json: consistent = true`). The one thing I could **not**
   reproduce — the stale-cache 0/8 hit — is reported as **not reproduced**, no
   artifact, no headline. The anon-vs-keyed fidelity A/B I did **not** run is listed
   as a Gap, not asserted.
3. **Blind instrument (D2)** — *Pass.* The recall counter registers **both** presence
   and absence on known signal: it reads 0/8 on `direct`-JS (nav only) and 8/8 where
   the eight named authors actually appear — a "found" requires the real author
   token, and the 0 vs 8 split proves the instrument is not stuck-on.
4. **Mis-attribution (D3)** — *Pass.* The 0/8 on `direct`-JS is **not** attributed to
   a Jina defect: the `direct`-on-static 8/8 control isolates it as a by-design
   rendering-mode mismatch (harness/engine-choice, not extraction failure). The ASN
   mismatch is explicitly held as a caveat, not a bug claim.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table carries a
   verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over
   this file surfaces only rule-required "honest" transparency labels, not
   self-praise on the tool.

## As-of provenance check

- **Engine-matrix test date:** **2026-07-24** (in `metadata-snapshot.md`); recall/
  bytes traceable to `artifacts/raw/*.md` + `recall_recompute.json`.
- **Anonymous-probe date:** **2026-07-10** (in the `.txt` logs' headers).
- **GitHub metadata:** as-of **2026-07-10** (stars 11,506, 0 tagged releases) —
  flagged for 48h refresh before any final draft; not re-fetched in this pass.

## Raw Artifact Index

- Engine/cache matrix (curl-measured): [engine-matrix.ndjson](artifacts/raw/engine-matrix.ndjson)
- Recomputed recall/bytes (no network): [recall_recompute.json](artifacts/raw/recall_recompute.json)
- Per-cell responses: [nc_js_default.md](artifacts/raw/nc_js_default.md), [nc_js_browser.md](artifacts/raw/nc_js_browser.md), [nc_js_browser_wait.md](artifacts/raw/nc_js_browser_wait.md), [nc_js_direct.md](artifacts/raw/nc_js_direct.md), [nc_static_default.md](artifacts/raw/nc_static_default.md), [nc_static_direct.md](artifacts/raw/nc_static_direct.md), [cached_js.md](artifacts/raw/cached_js.md)
- Anonymous 401 access logs (2026-07-10): [jina_quotes_toscrape_response.txt](artifacts/raw/jina_quotes_toscrape_response.txt), [jina_books_toscrape_response.txt](artifacts/raw/jina_books_toscrape_response.txt), [jina_scrapethissite_forms_response.txt](artifacts/raw/jina_scrapethissite_forms_response.txt), [jina_wikipedia_web_scraping_response.txt](artifacts/raw/jina_wikipedia_web_scraping_response.txt)
