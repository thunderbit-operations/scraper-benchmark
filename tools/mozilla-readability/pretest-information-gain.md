# mozilla-readability — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (a measurable, mechanism-tied gap exists that the one public
Readability benchmark does not cover; see "Information-gain verdict").

Broad keyword: **`@mozilla/readability`** (Firefox Reader View's extraction library).
Article boundary: `@mozilla/readability` is a **standalone JS port of Firefox Reader
View's main-content extractor** — a rule-based scorer that, given a DOM (here supplied
by **jsdom** under Node), returns the single subtree it judges to be the article
(`Readability.parse()`), plus a cheap pre-flight predictor `isProbablyReaderable()`.
This pack judges **article recovery and boilerplate failure boundaries against
ground truth**: given a page where every text block is pre-labeled ARTICLE or
BOILERPLATE(type), what fraction of the article does Readability recover (recall),
which boilerplate classes leak into the output (the precision side), and **where the
documented heuristics break** — the `charThreshold=500` short-content cliff, the
sibling-append inclusion rule, semantic-tag sensitivity, and `isProbablyReaderable`'s
threshold behavior. It is **not** a scoring of jsdom, nor a real-world-corpus
replacement for the existing public benchmark (see novelty note), nor a structured-
field extractor (Readability hands you one article subtree; anything finer is your
code). Cross-tool axis: the repo already has a **trafilatura** pack (the other main
content extractor); this pack reuses an *article-vs-boilerplate annotated fixture* so a
**same-testbed Readability-vs-trafilatura** contrast is possible (bonus, reported per
axis, honestly).

## SERP / official / issue scan (≈20 results, README, source, issue tracker)

### What the results repeat (consensus, mostly documented or qualitative)

- **Rule-based scorer, "Reader View algorithm."** Every intro repeats the pipeline:
  strip "unlikely candidates" by class/id regex, score `p/td/pre/h2-h6/section` nodes
  by text length + commas, propagate score to ancestors, pick the top candidate, then
  append qualifying siblings. Documented in source; summarized by DeepWiki and the
  WebcrawlerAPI write-ups. **Qualitative** — none quantify what leaks or drops.
- **`isProbablyReaderable(doc, {minContentLength=140, minScore=20})`.** README-documented
  as "quick-and-dirty … likely to produce both false positives and false negatives."
  The score formula is public (`score += Math.sqrt(textContentLength - minContentLength)`
  over visible `p, pre, article` + `div>br` parents; return `true` once score > minScore).
  Existence + defaults are **DOCUMENTED**; the *shape* of its false-negative boundary is
  not measured anywhere.
- **`charThreshold` default 500.** README lists it ("Minimum characters required to
  return results"); the retry-and-maybe-`null` behavior below 500 is in source but its
  boundary is not measured in public.
- **Known failure reports.** Real-page misses are logged as issues: first/opening
  paragraphs dropped ([#437](https://github.com/mozilla/readability/issues/437),
  [#901](https://github.com/mozilla/readability/issues/901)), content before a table
  ignored ([#922](https://github.com/mozilla/readability/issues/922)), wrong subtree
  chosen ([#844](https://github.com/mozilla/readability/issues/844)),
  `isProbablyReaderable` false-negative when content is in `<li>`/`<article>` with short
  paragraphs ([#662](https://github.com/mozilla/readability/issues/662)). These are
  **KNOWN-ISSUE** anchors — anecdotal, on live third-party pages, not controlled.

### The one public quantitative source (must be honest about this)

- **scrapinghub/article-extraction-benchmark** reports Readability.js **word-level
  P=0.853, R=0.924, F1=0.887** (± ~0.01) on ~181 real pages, alongside trafilatura and
  others. So **aggregate word-F1 on a real corpus is DOCUMENTED, not novel.** This pack
  must NOT claim "Readability has precision/recall" as a finding, nor present synthetic-
  fixture numbers as beating/replacing that benchmark.

### What is NOT measured anywhere (the actual gap)

1. **Per-boilerplate-class leakage decomposition.** The public word-F1 is a single
   scalar over whole articles; it never says *which* chrome class leaks (nav vs ad vs
   sidebar vs footer vs a long low-link "related/promo" blob vs comments). The
   controlled, per-class leak rate is unmeasured.
2. **The sibling-append inclusion boundary as an adversarial precision failure.**
   Source line ~1471: a sibling `<p>` with `innerText.length > 80 && linkDensity < 0.25`
   is **appended to the article** regardless of whether it is article prose. Nobody
   demonstrates that a **neutrally-classed** long, low-link promotional/related blob
   (i.e. one that dodges the `related|sidebar|footer|comment` unlikely-regex) therefore
   **leaks**, while the *same* text made link-dense (>0.25) is dropped. This is a
   constructible counter-example to "Readability removes boilerplate."
3. **The `charThreshold=500` short-content cliff, quantified.** No source sweeps article
   length across the 500-char boundary to show `parse()` degrades/returns `null` below
   it, nor that the cliff *moves* when you pass a different `charThreshold` (proving the
   mechanism, not a fixture artifact).
4. **Semantic-tag / structural sensitivity, quantified.** "Readability likes `<article>`"
   is folklore; nobody measures the recall/selection delta when the *same* content loses
   its `<article>`/`<main>` tags and gets neutral class names.
5. **`isProbablyReaderable` false-negative boundary, swept.** The README admits false
   negatives; nobody sweeps `minScore` to locate the crossover for a page whose real
   content lives in `<li>` (the [#662] shape) or in many sub-140-char paragraphs, and
   contrasts the predictor's verdict with whether `parse()` actually succeeds.
6. **Non-prose recall (tables / `<pre>` / short lines / captions).** Scoring ignores
   any paragraph `< 25` chars and is tuned for prose; which *legitimate* article content
   (data tables, code blocks, figure captions, one-line paragraphs) gets dropped is
   unmeasured on controlled ground truth.

### Source evidence

- Official: [README](https://github.com/mozilla/readability/blob/main/README.md),
  [Readability.js](https://github.com/mozilla/readability/blob/main/Readability.js),
  [Readability-readerable.js](https://github.com/mozilla/readability/blob/main/Readability-readerable.js).
  Exact constants read from the installed source (v0.6.0):
  `DEFAULT_CHAR_THRESHOLD=500`, `DEFAULT_N_TOP_CANDIDATES=5`,
  `DEFAULT_TAGS_TO_SCORE="section,h2,h3,h4,h5,h6,p,td,pre"`; score =
  `1 + (commas+1) + min(floor(len/100),3)`, paragraphs `<25` chars uncounted; sibling
  append gate `nodeLength>80 && linkDensity<0.25`; `linkDensity = Σ(linkTextLen·coef)/textLen`
  (coef 0.3 for `#` hrefs); `unlikelyCandidates` regex includes
  `related|comment|sidebar|footer|menu|sponsor|social|…`.
- Public benchmark: [scrapinghub/article-extraction-benchmark](https://github.com/scrapinghub/article-extraction-benchmark)
  (Readability.js F1 0.887).
- Issues to cite at execution: [#437], [#901], [#922], [#844], [#662].
- Representative SERP: [DeepWiki mozilla/readability](https://deepwiki.com/mozilla/readability),
  [WebcrawlerAPI algorithm write-up](https://webcrawlerapi.com/blog/mozilla-readability-algorithm-readabilityjs).

## Testable information-gain hypotheses

- **H1 (article recovery + per-class boilerplate precision, main):** On an annotated
  fixture (every block labeled ARTICLE or BOILERPLATE(nav/ad/aside/footer/related-promo/
  comments), each carrying a unique sentinel), measure **article recall** (sentinel
  present in extracted text) and **per-class leak rate** (boilerplate sentinel present).
  Prediction from mechanism: unlikely-regex classes (nav/footer/sidebar/comments) strip
  cleanly; the long low-link "related/promo" blob is the leak risk. Report token-level
  P/R/F1 too, scoped as a controlled-fixture number (not the real-corpus benchmark).
- **H2 (adversarial precision failure — the sibling-append boundary):** A **neutrally-
  classed** boilerplate `<p>` that is (a) `>80` chars and (b) `linkDensity<0.25`, placed
  as a sibling of the top candidate, is **appended to the article** (leaks); the *same
  block* made link-dense (`linkDensity>0.25`) is **dropped**. Measure leak vs the
  0.25 boundary + the 80-char boundary. This is a constructed counter-example to
  "removes boilerplate."
- **H3 (adversarial recall failure — the `charThreshold=500` cliff):** Sweep a genuine
  single-article page's body length `{~120, 300, 460, 520, 800, 1500}` chars and record
  `parse()` → `null` / degraded below ~500; then re-run at `charThreshold ∈ {200, 500,
  1000}` to show the cliff **moves with the option** (mechanism proof, not fixture
  artifact).
- **H4 (structural sensitivity):** The *same* article, once with `<article>/<main>` +
  descriptive ids, once fully neutralized to `<div class="x">`, measured for article
  recall + which subtree is chosen. Prediction: recall/selection degrades without the
  semantic scaffold.
- **H5 (`isProbablyReaderable` false-negative boundary):** For pages whose real content
  is in `<li>` (the [#662] shape) or in many sub-140-char paragraphs, record
  `isProbablyReaderable()` (default) vs whether `parse()` actually returns a good
  article, and **sweep `minScore`** to locate the true/false crossover. Prediction:
  predictor says *not* readerable while `parse()` succeeds → false negative.
- **H6 (non-prose recall):** An article whose legitimate content includes a data
  `<table>`, a `<pre>` code block, figure captions, and sub-25-char one-line paragraphs;
  measure which are recovered. Prediction: sub-25-char lines + some table/caption text
  are dropped (scoring is prose-tuned).

## Test matrix (tied to hypotheses)

| # | Test | Fixture | Measures | H |
|---|---|---|---|---|
| 1 | article recall (well-formed) | F1 canonical (`<article>`) | ARTICLE sentinels recovered / total | H1 |
| 2 | nav leak | F1 | nav sentinel in output? | H1 |
| 3 | ad leak | F1 | ad sentinel in output? | H1 |
| 4 | sidebar/aside leak | F1 | aside sentinel? | H1 |
| 5 | footer leak | F1 | footer sentinel? | H1 |
| 6 | comments leak | F1 | comments sentinel? | H1 |
| 7 | related-promo (neutral class) leak | F1 | promo sentinel? | H1/H2 |
| 8 | token-level P/R/F1 | F1 | word-overlap vs GT article tokens | H1 |
| 9 | sibling-append: long low-link, neutral class | F2-adv | leaks (appended)? | H2 |
| 10 | sibling-append: same block, link-dense >0.25 | F2-adv | dropped? | H2 |
| 11 | sibling-append: short (<80) low-link | F2-adv | dropped (below 80)? | H2 |
| 12 | charThreshold cliff sweep (len gradient) | F3-short | parse null/degraded by length | H3 |
| 13 | charThreshold option sweep | F3-short | cliff moves with charThreshold | H3 |
| 14 | recall with semantic tags | F4-sem (semantic) | ARTICLE recall | H4 |
| 15 | recall neutralized (no `<article>`, neutral class) | F4-sem (neutral) | ARTICLE recall delta | H4 |
| 16 | isProbablyReaderable on `<li>`-only content | F5-ipr | predictor false vs parse success | H5 |
| 17 | isProbablyReaderable many-short-paras | F5-ipr | predictor false vs parse | H5 |
| 18 | isProbablyReaderable minScore sweep | F5-ipr | true/false crossover score | H5 |
| 19 | non-prose: `<table>` recovery | F6-nonprose | table sentinel recovered? | H6 |
| 20 | non-prose: `<pre>` code recovery | F6-nonprose | code sentinel? | H6 |
| 21 | non-prose: sub-25-char one-line paras | F6-nonprose | short-line sentinels? | H6 |
| 22 | non-prose: figure captions | F6-nonprose | caption sentinels? | H6 |
| 23 | determinism | all | identical extraction across 3 reps | all |
| 24 | jsdom malformed-HTML sensitivity | F1 vs F1-malformed | recall delta on misnested tags | jsdom |
| 25 | trafilatura same-testbed (bonus) | F1, F2-adv, F4-sem | same metrics, other extractor | H1/H2/H4 |

Ground truth: each labeled block embeds a **unique sentinel token** (e.g.
`ART01_TOKEN`, `NAVBOILER_TOKEN`), so "recovered/leaked" is exact substring membership
in the extracted text — never fuzzy-matched, never guessed. Token-level P/R/F1 uses one
declared tokenizer (lowercase, split on non-alphanumeric) over Readability's
`textContent` vs the union of ARTICLE-unit tokens, matching the public benchmark's
word-overlap口径; it is reported with the caveat that shared common words inflate token
precision, which is exactly why the **sentinel unit-level metrics are the headline** and
token-level is the literature-comparable secondary.

## Harness design (Node extractor + Python metrics, anti-hardcoding split)

- `tests/build_fixtures.mjs` (Node) — single source of truth: writes
  `tests/fixtures/*.html` **and** `tests/fixtures/ground_truth.json` (per-unit label +
  type + sentinel + text), so HTML and labels can never drift.
- `tests/run_readability.mjs` (Node, jsdom) — per fixture, fresh jsdom per run, calls
  `Readability.parse()` + `isProbablyReaderable()` (incl. option sweeps), dumps **raw**
  extracted `textContent`/content-HTML/length/title/byline + predictor booleans/scores →
  `artifacts/raw/readability_raw.json`. **No metric is computed here.**
- `tests/run_trafilatura.py` (Python venv) — runs trafilatura on the same fixture HTML,
  dumps raw extracted text → `artifacts/raw/trafilatura_raw.json` (bonus arm).
- `tests/metrics.py` (Python) — reads `ground_truth.json` + both raw dumps, computes
  unit-level recall/leak + token-level P/R/F1 with **one** tokenizer, for both tools →
  `artifacts/raw/*_metrics.json` + `comparison.json`. **Precision/recall are computed
  from raw extracted text vs labels — no result constant is hand-written** (闸门 3).
- `_redact`: `$HOME`→`~` **and** `$TMPDIR`/`/var/folders` temp paths (the selenium-pack
  lesson) before any JSON is written.

## Information-gain verdict: PROCEED

Not parked. One public number exists (scrapinghub word-F1 0.887) and the algorithm's
constants are documented — so the pack is disciplined to treat *aggregate P/R and the
heuristics' existence as DOCUMENTED*. What no public source provides, and what is
measurable here on a credential-free local fixture: (1) **per-boilerplate-class** leak
decomposition; (2) the **sibling-append** adversarial precision counter-example at the
`80`-char / `0.25`-link-density boundary; (3) the **`charThreshold=500`** recall cliff
that moves with the option; (4) the **semantic-tag** recall delta; (5) the
**`isProbablyReaderable`** false-negative crossover; (6) **non-prose** recall drops — all
tied to source-level mechanism, plus a same-testbed trafilatura contrast the repo can
reuse. Each is a quantification or constructed demonstration behind documented behavior —
the EXCLUSIVE-eligible core — while existence claims stay DOCUMENTED and the real-page
misses stay KNOWN-ISSUE.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on **local, self-authored fixtures** (no network at runtime for the
  Readability arm; the trafilatura arm also reads the saved HTML). No third-party host,
  no anti-bot, no auth, no rate abuse. Readability is a content extractor, framed as
  "extraction fidelity on controlled ground truth."
- No credentials anywhere. `_redact` scrubs `$HOME`→`~` and `$TMPDIR`/`/var/folders`.
- Record exact `@mozilla/readability` + `jsdom` + Node + trafilatura versions in
  metadata; fixtures + `package-lock.json` committed; `node_modules/` and `.venv/`
  gitignored, never shipped.
- Determinism asserted (3 reps identical) before any single-run number is used.
- Novelty honesty: rule-based scoring, `isProbablyReaderable` thresholds, `charThreshold`
  existence, and aggregate word-F1 are **DOCUMENTED**; the real-page paragraph-drop /
  predictor-false reports are **KNOWN-ISSUE** ([#437]/[#901]/[#922]/[#844]/[#662]). Only
  the controlled per-class leak decomposition, the sibling-append boundary demonstration,
  the charThreshold-cliff sweep, the semantic-tag delta, the `minScore` crossover, and
  the non-prose recall table are candidates for EXCLUSIVE.

[#437]: https://github.com/mozilla/readability/issues/437
[#901]: https://github.com/mozilla/readability/issues/901
[#922]: https://github.com/mozilla/readability/issues/922
[#844]: https://github.com/mozilla/readability/issues/844
[#662]: https://github.com/mozilla/readability/issues/662
