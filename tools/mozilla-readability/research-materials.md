# mozilla-readability — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a
final blog draft and must not be published as-is.

## Material Boundary

Evidence base for a single-tool review of **`@mozilla/readability`** (v0.6.0), the
standalone JS port of Firefox Reader View's main-content extractor, driven under Node
with **jsdom** supplying the DOM. It judges **article recovery and boilerplate failure
boundaries against ground truth**: on fixtures where every text block is pre-labeled
ARTICLE or BOILERPLATE(type) and carries a unique sentinel token, it measures article
recall, per-boilerplate-class leakage (the precision side), and where the documented
heuristics break — the sibling-append inclusion gate, the `charThreshold=500` behavior,
semantic-tag sensitivity, and `isProbablyReaderable`'s false-negative surface. It does
**not** score jsdom, does **not** replace the public real-corpus benchmark (see novelty),
and does **not** rank tools beyond a same-testbed contrast with the repo's trafilatura
pack.

All tests run on **local, self-authored fixtures** (no network at runtime for the
Readability arm). The one public quantitative anchor —
[scrapinghub/article-extraction-benchmark](https://github.com/scrapinghub/article-extraction-benchmark)
reporting Readability.js **word-F1 0.887 (P 0.853 / R 0.924)** on ~181 real pages — is
treated as **DOCUMENTED**; this pack's numbers are controlled-fixture measurements whose
value is the **per-class decomposition and mechanism-level failure boundaries** the
aggregate scalar cannot show, not a replacement for it.

## Source Snapshot

Point-in-time metadata (see `metadata-snapshot.md`; refresh within 48h before any final
draft):

| Field | Value |
|---|---|
| Repo | [mozilla/readability](https://github.com/mozilla/readability) |
| Stars | **11,355** |
| Open issues | **307** |
| License | **Apache-2.0** |
| Latest tag / npm latest | **0.6.0** (no GitHub *Release* object; npm `latest` = 0.6.0, published 2025-03-03) |
| Version tested | **0.6.0** (`npm install @mozilla/readability` resolved 0.6.0) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (25F84) arm64 |
| @mozilla/readability | **0.6.0** |
| jsdom | **29.1.1** |
| Node | **v22.22.3** |
| trafilatura (comparison arm) | **2.1.0** (Python 3.12.13, venv) |
| Fixture generator | [tests/build_fixtures.mjs](tests/build_fixtures.mjs) → `tests/fixtures/*.html` + `tests/fixtures/ground_truth.json` |
| Readability runner | [tests/run_readability.mjs](tests/run_readability.mjs) → [readability_raw.json](artifacts/raw/readability_raw.json) |
| trafilatura runner | [tests/run_trafilatura.py](tests/run_trafilatura.py) → [trafilatura_raw.json](artifacts/raw/trafilatura_raw.json) |
| Metrics (both tools) | [tests/metrics.py](tests/metrics.py) → [readability_metrics.json](artifacts/raw/readability_metrics.json), [trafilatura_metrics.json](artifacts/raw/trafilatura_metrics.json), [comparison.json](artifacts/raw/comparison.json) |

Fixtures: **22** HTML pages, **91** labeled units (**74** article, **17** boilerplate).
The **content-fidelity set** (11 fixtures with ≥1 article AND ≥1 boilerplate unit; 40
article + 17 boilerplate units) is where per-class leak + micro-averaged token metrics
are computed.

Method notes (they affect reproduction):

- **Anti-hardcoding split.** The Node runner returns only *raw* extracted `textContent`
  + `isProbablyReaderable` booleans/sweeps + measured link-density; **all precision/recall
  is computed in `metrics.py`** from that raw text vs the labels. No metric constant is
  written by hand.
- **Unique-per-unit vocabulary.** Every word in a unit begins with that unit's unique
  sentinel prefix, so token sets across units are **disjoint** — an extracted word maps
  to exactly one unit, making token-level precision/recall (and partial-extraction
  detection) meaningful and the Readability-vs-trafilatura contrast fair.
- **One tokenizer** for both tools: lowercase, split on `[^a-z0-9]+` (word-overlap word-F1,
  matching the public benchmark's口径).
- **Fresh DOM per parse.** `Readability.parse()` mutates the DOM, so a new jsdom is built
  for every parse call; determinism is asserted (3 reps, extracted text identical).
- **Redaction.** `$HOME`→`~` and `$TMPDIR` / `/var/folders` temp paths → `<TMP>` before
  any JSON is written (both Node and Python arms).

## Test Coverage Completed

### H1 — article recovery + per-boilerplate-class precision (`readability_metrics.json`, `comparison.json`)

On the canonical fixture `f1_canonical` (`<article>` body + realistically-classed
chrome + one **neutral-classed** long low-link promo) and across the content-fidelity
set:

| Metric (Readability, content-fidelity set) | Value |
|---|---|
| Unit article recall | **40 / 40 = 1.000** |
| Unit boilerplate leak rate | **5 / 17 = 0.294** |
| Token precision (micro) | **0.902** |
| Token recall (micro) | **1.000** |
| Token F1 (micro) | **0.948** |

`f1_canonical` per-class leak: nav / ad / aside / footer / comments — **0/1 each
(stripped)**; **related-promo-neutral — 1/1 (leaked)**. Reading: chrome that carries a
class the `unlikelyCandidates` regex matches (`nav`, `ad-banner`, `sidebar`, `footer`,
`comments`) is stripped cleanly; the **only** leak is the block engineered to dodge that
regex — a neutral-classed, long, low-link paragraph, which enters via the sibling-append
path (H2). So the precision failure surface is not "chrome" in general but specifically
**neutrally-classed low-link prose siblings**.

> Scope: the 0.294 leak rate is on a set that **deliberately overweights** the
> sibling-append cases (6 of 11 fixtures are the H2 adversarial variants). On the single
> realistic page `f1_canonical`, 5 of 6 chrome blocks strip and 1 leaks. This is a
> worst-case-leaning number, not a typical-page rate; the real-corpus precision is the
> DOCUMENTED 0.853.

### H2 — adversarial precision: the sibling-append gate (`readability_raw.json` → `promo_geometry`)

One neutral-classed sibling `<p>` per fixture, decisive 4-paragraph `<article>` as top
candidate, varying only length + link density. Measured link density is the exact
Readability formula (`Σ linkTextLen·coef / textLen`, coef 0.3 for `#` hrefs):

| Fixture | inner-text len | >80 chars | link density | outcome |
|---|---:|:--:|---:|:--:|
| `f2_sib_len120_ld000` | 126 | yes | **0.000** | **LEAK** |
| `f2_sib_len120_ld015` | 126 | yes | **0.143** | **LEAK** |
| `f2_sib_len120_ld029` | 126 | yes | **0.278** | drop |
| `f2_sib_len120_ld050` | 126 | yes | **0.476** | drop |
| `f2_sib_len60_period` | 60 | no | 0.000 | **LEAK** |
| `f2_sib_len60_noperiod` | 59 | no | 0.000 | drop |

Reading: a sibling of the top candidate is **appended to the article** exactly at the
documented gate — `nodeLength > 80 && linkDensity < 0.25` (0.143 leaks, 0.278 drops: the
boundary sits at **0.25**), plus the second branch `nodeLength < 80 && linkDensity === 0
&& contains a period` (the 60-char sentence with a period leaks; the 59-char one without
a period drops). Article recall stays **4/4** in every case. This is a **constructed
counter-example** to "Readability removes boilerplate": a promotional/related blob that
is long, low-link, and neutrally classed is indistinguishable to the heuristic from an
article paragraph and rides along. Confidence: high (mechanism-exact, deterministic).

### H3 — the `charThreshold=500` cliff is SOFT, not a hard null (`readability_raw.json` → `charThreshold_sweep`)

Sweeping a clean single-article page's body length and the `charThreshold` option:

| Body length | parse_ok @ ct=200 | @ ct=500 (default) | @ ct=1000 | extracted len |
|---:|:--:|:--:|:--:|---:|
| 120 | ✓ | ✓ | ✓ | 161 |
| 300 | ✓ | ✓ | ✓ | 342 |
| 460 | ✓ | ✓ | ✓ | 509 |
| 520 | ✓ | ✓ | ✓ | 569 |
| 800 | ✓ | ✓ | ✓ | 841 |
| 1500 | ✓ | ✓ | ✓ | 1555 |

**Prediction falsified (honest negative).** A clean article **below** the 500-char
threshold does **not** return `null`, and the extracted length is **identical across
`charThreshold ∈ {200, 500, 1000}`**. The threshold only triggers the flag-removal
**sieve** (`STRIP_UNLIKELYS` → `WEIGHT_CLASSES` → `CLEAN_CONDITIONALLY`); when the page is
clean there is nothing to strip, so the sieve returns the same content regardless, and
the final fallback returns the longest attempt as long as *any* text exists. The true
`null` boundary is "literally no extractable text" — and even the near-empty `f3_empty`
(a nav + a 4-word blurb) returns a **non-null** "article" that **includes the nav**
(`parse_ok: true`; extracted text = `"…zzemptynav… zzemptyblurb hi."`). So the practical
failure here is not a false-null on short articles but a **precision failure on
content-poor pages**: given no real article, Readability returns boilerplate *as* the
article. Confidence: high (sweep is flat; empty-page fallback observed).

### H4 — structural sensitivity: robust to loss of semantic tags (`comparison.json`)

Identical article text, two skins:

| Fixture | wrapper | article recall | boilerplate leaked |
|---|---|:--:|:--:|
| `f4_semantic` | `<main><article><h1>` + descriptive classes | **4/4** | 0 |
| `f4_neutral` | `<div class="x1">`, no semantic tags, paragraphs as `<div>` | **4/4** | 0 |

**Prediction falsified (honest negative).** Stripping `<article>`/`<main>`/`<h1>` and
neutralizing class names did **not** reduce recall — when the article is clearly the
densest text block, the length/score heuristic finds it with or without semantic
scaffolding. Readability is **not** dependent on semantic tags on a clean single-column
page. (Where semantics would matter is a page with *competing* dense blocks; that
tie-break is a Gap, not measured here.) Confidence: high for the tested shape.

### H5 — `isProbablyReaderable` false-negative surface (`readability_raw.json` → `minScore_sweep` / `minContentLength_sweep`)

`isProbablyReaderable(doc, {minContentLength=140, minScore=20})` vs whether `parse()`
actually succeeds:

| Fixture | ipr default | parse_ok | minScore crossover | minContentLength effect |
|---|:--:|:--:|---|---|
| `f5_ipr_li_only` (content in `<li>`) | **false** | **true** | false at **all** minScore 1–80 | false at all mcl 40–200 |
| `f5_ipr_many_short` (10 × <140-char `<p>`) | **false** | **true** | false at all minScore 1–80 | **true at mcl ≤ 100**, false ≥ 140 |
| `f5_ipr_one_long` (single 408-char `<p>`) | **false** | **true** | true ≤ 10, **false ≥ 20** (score ≈ 16.4) | false at all mcl |
| `f5_ipr_normal` (control) | true | true | false only at ≥ 80 | true at all mcl |

Reading — three distinct false-negative mechanisms, each with `parse()` **succeeding**
where the predictor says "no":

1. **Structural (li-only, the [#662] shape):** the predictor queries only
   `p, pre, article` (+ `div>br` parents); content in `<li>` matches **no** node, so the
   score is 0 and **no threshold tuning** (minScore or minContentLength) recovers it. The
   failure is in node *selection*, not the score.
2. **minContentLength gate (many-short):** each paragraph `< 140` chars is skipped before
   scoring (`textContentLength < minContentLength → continue`), so ten substantial
   paragraphs sum to 0. This one **is** tunable — lowering `minContentLength` to ≤ 100
   flips it to `true` — the lever is `minContentLength`, **not** `minScore`.
3. **minScore bar (one-long):** a single 408-char paragraph scores
   `sqrt(408−140) ≈ 16.4 < 20`, so the default calls it not-readerable; a lone paragraph
   must reach `140 + 20² = 540` chars to clear `minScore=20` alone.

The README already warns the predictor yields false negatives; the contribution is the
**quantified, mechanism-separated boundary** (which lever fixes which case, and that
li-only is unfixable by tuning). Confidence: high (sweeps deterministic).

### H6 — non-prose recall: fully retained (`comparison.json`)

`f6_nonprose` — an `<article>` whose legitimate content includes a data `<table>`, a
`<pre>` code block, sub-25-char one-line `<p>`, and a `<figcaption>`, alongside prose:

| Content type | Readability recovered | trafilatura recovered |
|---|:--:|:--:|
| prose (×2) | ✓ | ✓ |
| table cells (×2) | ✓ | ✓ |
| `<pre>` code | ✓ | ✓ |
| sub-25-char one-line `<p>` (×2) | ✓ | ✓ |
| `<figcaption>` | ✓ | **dropped** |
| **unit recall** | **8/8 = 1.000** | **7/8 = 0.875** |

**Prediction falsified (honest negative), and an axis where Readability WINS.** The
"paragraphs `< 25` chars are uncounted" rule affects candidate **scoring/selection**, not
**retention** — once the `<article>` container is chosen, its non-prose descendants
(short lines, table cells, code, caption) ride along and are all recovered. trafilatura,
by contrast, **dropped the `<figcaption>`** on the same bytes. So on non-prose article
content, Readability's "keep the whole winning subtree" behavior is *higher recall* than
trafilatura's more aggressive cleaning. Confidence: high (deterministic, same fixture).

### Same-testbed comparison (bonus) — Readability vs trafilatura (`comparison.json`)

Micro-averaged over the content-fidelity set (identical HTML bytes; trafilatura uses its
own parser, Readability uses jsdom):

| Metric | @mozilla/readability | trafilatura |
|---|---:|---:|
| Unit article recall | **1.000** | **1.000** |
| Unit boilerplate leak rate | **0.294 (5/17)** | **0.059 (1/17)** |
| Token precision (micro) | 0.902 | **0.939** |
| Token recall (micro) | 1.000 | 1.000 |
| Token F1 (micro) | 0.948 | **0.969** |
| Non-prose recall (`f6`) | **1.000 (8/8)** | 0.875 (7/8) |
| Very-short article F1 (`f3_short_120`) | **0.800** | 0.571 |

Honest split: on this controlled set **trafilatura has cleaner boilerplate precision**
(it resisted all sibling-append leaks except the empty-page nav, which both returned),
while **Readability has higher recall on short and non-prose content**. Neither
dominates. The token-precision gap (0.902 vs 0.939) is driven entirely by Readability's
sibling-append leaks; both tools' absolute token precision is *deflated equally* by the
unlabeled `<h1>` heading text (article-ish content not in the labeled units), so the
clean precision signal is the unit-level leak rate, not the token precision. This is a
**synthetic** contrast — the DOCUMENTED real-corpus ranking (scrapinghub) already puts
trafilatura ahead of Readability on word-F1, consistent in direction with this set.

### Robustness / jsdom sensitivity

`f1_malformed` (unclosed `<p>`, misnested `<b>/<i>`, stray `</div>`) vs `f1_canonical`:
article recall **3/3** on the malformed twin (0 boilerplate leaked), matching the
well-formed page — jsdom's HTML5 tree-builder recovery neutralizes the malformation
before Readability sees it. No parse crash on any fixture. Determinism: **all 22
fixtures** returned identical extracted text across 3 reps
(`determinism.all_identical = true` everywhere).

## Key Findings for the Writer

1. **FINDING-01 — Article recall is 100% on every fixture (74/74 units, token recall
   1.000); Readability's failure surface is precision, not recall.** Across all 22
   fixtures no labeled article unit was ever dropped. Confidence: high. Scope: controlled
   fixtures; the DOCUMENTED real-corpus recall is 0.924.

2. **FINDING-02 — The sibling-append gate leaks neutrally-classed low-link prose at
   exactly `linkDensity < 0.25` (and `len > 80`), a constructed counter-example to
   "removes boilerplate."** Measured boundary: density 0.143 leaks, 0.278 drops; the
   short-paragraph second branch (`<80 && 0 links && has period`) also leaks. The one
   leak on the realistic `f1_canonical` page is exactly this neutral promo; the
   regex-classed chrome (nav/ad/sidebar/footer/comments) all strip. Confidence: high
   (mechanism-exact). Novelty: DOCUMENTED gate, EXCLUSIVE quantified demonstration.

3. **FINDING-03 — `charThreshold=500` is a SOFT boundary: short clean articles are NOT
   nulled (recovered down to 120 chars, identical across charThreshold 200/500/1000);
   `parse()` returns non-null even for a nav-only page, returning the nav AS the
   article.** The practical risk is precision on content-poor pages, not a false-null.
   Confidence: high (flat sweep + empty-page fallback). Novelty: EXCLUSIVE (refutes a
   naive reading of the docs).

4. **FINDING-04 — Robust to loss of semantic tags: a neutralized `<div>` article is
   recovered identically to the `<article>/<main>` version (4/4 both).** Readability does
   not need semantic scaffolding when the article is the densest block. Confidence: high
   for single-column pages; competing-block tie-break is a Gap. Novelty: EXCLUSIVE
   (robustness quantified).

5. **FINDING-05 — `isProbablyReaderable` has a broad false-negative surface with three
   separable mechanisms; `parse()` succeeds where the predictor says no.** li-only
   content is a **structural** false negative unfixable by tuning; many-short is fixable
   only via `minContentLength` (not `minScore`); a lone paragraph needs ≥540 chars to
   clear the default `minScore=20`. Confidence: high (deterministic sweeps). Novelty:
   KNOWN-ISSUE ([#662]) + EXCLUSIVE mechanism-separated quantification.

6. **FINDING-06 — Non-prose article content (tables, code, captions, short lines) is
   fully retained (8/8); on this axis Readability out-recalls trafilatura (7/8, dropped a
   `<figcaption>`).** The "<25-char uncounted" rule affects selection, not retention.
   Confidence: high. Novelty: EXCLUSIVE (per-type non-prose recall on ground truth).

7. **FINDING-07 — Same-testbed: trafilatura has cleaner boilerplate precision
   (leak 0.059 vs 0.294), Readability higher short/non-prose recall; neither dominates.**
   Direction agrees with the DOCUMENTED real-corpus ranking. Confidence: medium (synthetic
   set, adversarially weighted). Novelty: EXCLUSIVE (same-testbed synthetic contrast) but
   scoped as not replacing the public benchmark.

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark. See
`scorecard.md` for scoring notes.

| Dimension | Weight | Score | Evidence |
|---|---:|---:|---|
| Setup and first run | 8 | **8** | `npm i @mozilla/readability jsdom`; needs a DOM impl (jsdom) at runtime |
| Article recall | 14 | **14** | 74/74 units, token recall 1.000 across 22 fixtures |
| Boilerplate precision (leak resistance) | 14 | **9** | leak 5/17 on adversarial-weighted set; regex-classed chrome strips 5/6 on realistic page |
| Adversarial precision boundary | 10 | **7** | leaks at linkDensity<0.25 / >80 chars + short-period branch (documented gate, exploitable) |
| Short-content handling | 8 | **7** | no false-null; recovers to 120 chars; but returns nav-as-article on empty pages |
| Structural robustness | 8 | **8** | neutral-div article recovered 4/4 = semantic |
| Non-prose recall | 8 | **8** | 8/8 tables/code/captions/short lines; beats trafilatura (7/8) |
| `isProbablyReaderable` predictor | 10 | **5** | broad false negatives (li-only unfixable, many-short, one-long) where parse succeeds |
| Determinism | 6 | **6** | all 22 fixtures 3-rep identical |
| Cost / parser transparency | 6 | **5** | requires full jsdom DOM; timing not collected as a distribution (Gap) |
| Same-testbed comparison completeness | 8 | **7** | trafilatura arm on same fixtures; synthetic only, real-corpus deferred |
| **Total** | **100** | **84** | provisional research-material score only |

## Gaps Before Final Blog Draft

- **Real-corpus run not performed.** All numbers are on synthetic controlled fixtures;
  the public real-page benchmark (scrapinghub, F1 0.887) is the authoritative real-world
  figure and is cited, not reproduced here.
- **Competing-block tie-break not tested.** H4 shows robustness on single-column pages;
  where semantics would matter (two dense candidate subtrees) is unmeasured.
- **Timing / cost not a distribution.** Extraction is fast but no p50/range over ≥3 runs
  was collected; the jsdom parse cost dominates and is host-specific.
- **Known real-page misses not reproduced.** First/opening-paragraph drops
  ([#437]/[#901]) and content-before-table drops ([#922]) are deep-nesting/scoring
  artifacts on live pages; the controlled fixtures here did not trigger them (recall was
  100%), so those remain KNOWN-ISSUE anchors, not reproduced.
- **Single machine, single version.** @mozilla/readability 0.6.0 + jsdom 29.1.1 + Node
  22.22.3, macOS arm64.

## Novelty verification (pre-registration search)

Sources per finding: readability issue tracker, README + `Readability.js` /
`Readability-readerable.js` source, top-~20 SERP, and the scrapinghub benchmark. Verdict
is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| rule-based scoring, unlikely-regex, sibling append, `charThreshold=500`, `isProbablyReaderable` thresholds exist | **DOCUMENTED** | README + source; existence, not this pack's value |
| aggregate word-P/R/F1 on real pages | **DOCUMENTED** | [scrapinghub benchmark](https://github.com/scrapinghub/article-extraction-benchmark) — Readability.js F1 0.887; this pack does NOT claim to replace it |
| 100% article recall / recall-not-the-problem on controlled fixtures | **EXCLUSIVE (quantification)** | no public per-unit controlled recall breakdown; zero-hit |
| sibling-append leak at `linkDensity<0.25 && len>80` + short-period branch, measured boundary | **DOCUMENTED gate / EXCLUSIVE demonstration** | source defines the gate; the neutral-classed adversarial leak demonstration + exact 0.25/80 boundary is this pack's |
| `charThreshold=500` is soft (no false-null; nav-as-article on empty) | **EXCLUSIVE (correction + quantification)** | folklore reads it as "under 500 → null"; the flat sweep + empty-page fallback refute it; zero-hit |
| semantic-tag robustness (neutral == semantic recall) | **EXCLUSIVE (quantification)** | "Readability likes `<article>`" is unquantified folklore |
| `isProbablyReaderable` false negatives on li-only / many-short / one-long, lever-separated | **KNOWN-ISSUE + EXCLUSIVE** | [#662] reports li/short false negatives; the mechanism-separated sweep (which lever fixes which; li-only unfixable) is this pack's |
| non-prose retained 8/8; beats trafilatura's 7/8 | **EXCLUSIVE (quantification)** | no public per-type non-prose recall on ground truth |
| real-page first/opening-paragraph + before-table drops | **KNOWN-ISSUE, NOT reproduced** | [#437]/[#901]/[#922] — controlled fixtures did not trigger; reported as not reproduced |

[#437]: https://github.com/mozilla/readability/issues/437
[#901]: https://github.com/mozilla/readability/issues/901
[#922]: https://github.com/mozilla/readability/issues/922
[#662]: https://github.com/mozilla/readability/issues/662

**Consequence for the writer:** the information-gain items are measurements or
constructed demonstrations behind documented behavior — the per-class leak decomposition,
the sibling-append boundary, the soft-charThreshold correction, the semantic-tag
robustness, the lever-separated `isProbablyReaderable` false-negative map, and the
non-prose recall table. Existence claims stay DOCUMENTED; real-page misses stay
KNOWN-ISSUE and are marked not reproduced; the public word-F1 is cited, never claimed.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* The same-testbed comparison
   reports a **split** (trafilatura cleaner precision; Readability higher short/non-prose
   recall) with no unqualified "wins" sentence; where Readability out-recalls trafilatura
   on `f6` it is stated with the exact 8/8 vs 7/8 and the dropped `<figcaption>`. Token
   recall 1.000 ties are not framed as a win.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`readability_metrics.json`, `comparison.json`, `readability_raw.json` sweeps). The
   real-page misses I did **not** reproduce ([#437]/[#901]/[#922]) are reported as **not
   reproduced**, not asserted.
3. **Blind instrument (D2)** — *Pass.* The metric registers **both** presence and absence:
   it records article recovery (1.0) *and* boilerplate leaks (5/17), and the leak side
   flips with the constructed link-density boundary (0.143 leak → 0.278 drop), proving it
   is not blind to either outcome. Sentinels are runtime-unique disjoint tokens, so a
   "found" requires the actual text, not a guess.
4. **Mis-attribution (D3)** — *Pass.* Two fixture-artifact traps were caught and fixed
   before drawing conclusions: (a) the first F2 layout let `#page` win as top candidate so
   *all* children rode along, masking the sibling gate — rebuilt to one promo per fixture
   with a decisive `<article>`, after which the 0.25/80 boundary resolved cleanly; (b) the
   H3/H4/H6 "failure" predictions were **falsified** and reported as honest negatives
   (soft charThreshold, semantic robustness, non-prose retained) rather than forced. The
   sibling-append leak is attributed to the source gate, validated by the density sweep.
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with a
   verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over this
   file surfaces only "honest negative" labels flagging falsified predictions
   (rule-required transparency), not self-praise on the tool.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-24** in `metadata-snapshot.md`. Stars (11,355) /
  latest tag (0.6.0) traceable to that GitHub/npm fetch.
- **Versions:** @mozilla/readability 0.6.0 (== npm latest / latest tag); jsdom 29.1.1;
  Node v22.22.3; trafilatura 2.1.0; read from `package-lock.json` / the run summaries /
  `pip`.

## Raw Artifact Index

- Ground truth (labels + sentinels): [tests/fixtures/ground_truth.json](tests/fixtures/ground_truth.json)
- Readability raw extraction + sweeps: [readability_raw.json](artifacts/raw/readability_raw.json)
- trafilatura raw extraction: [trafilatura_raw.json](artifacts/raw/trafilatura_raw.json)
- Readability metrics (computed): [readability_metrics.json](artifacts/raw/readability_metrics.json)
- trafilatura metrics (computed): [trafilatura_metrics.json](artifacts/raw/trafilatura_metrics.json)
- Same-testbed comparison: [comparison.json](artifacts/raw/comparison.json)
