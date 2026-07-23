# mozilla-readability — evidence pack

Independent, reproducible tests for **`@mozilla/readability`** (v0.6.0), the standalone
JS port of Firefox Reader View's main-content extractor, driven under Node with **jsdom**.
Part of the Thunderbit open-source scraping-tool benchmark. Every number in
`research-materials.md` traces to a script here and a JSON artifact under `artifacts/raw/`.

Tested (as-of 2026-07-24): @mozilla/readability **0.6.0**, jsdom **29.1.1**, Node
**22.22.3**; comparison arm trafilatura **2.1.0** (Python 3.12.13); macOS arm64.

## Headline

On 22 annotated fixtures (91 labeled units; every block tagged ARTICLE or
BOILERPLATE(type) with a unique sentinel), **Readability's failure surface is precision,
not recall**: it recovered **100% of article units** (74/74; token recall 1.000) and is
robust to malformed HTML, loss of semantic tags, and non-prose content — but it **leaks
boilerplate through the documented sibling-append gate**. A neutrally-classed sibling `<p>`
that is `> 80` chars and `linkDensity < 0.25` is **appended to the article** (measured
boundary: density **0.143 leaks, 0.278 drops** — exactly the `0.25` gate; the short
`< 80`-char + period branch also leaks), so a long, low-link promotional/related blob that
dodges the `related|sidebar|footer|comment` class regex rides along as "article."

Secondary, measured findings: the `charThreshold = 500` "cliff" is **soft** — short clean
articles are recovered (no false-`null` down to 120 chars, identical across charThreshold
200/500/1000), and a near-empty page returns its **nav as the article**; `isProbablyReaderable`
has a broad **false-negative** surface where `parse()` still succeeds (content in `<li>` is
false at *every* threshold; many-short is fixable only via `minContentLength`; a lone
paragraph needs ≥ 540 chars to clear the default `minScore = 20`). Same-testbed vs
trafilatura on the identical bytes: **trafilatura has cleaner boilerplate precision**
(leak 0.059 vs 0.294), **Readability higher short/non-prose recall** (non-prose 8/8 vs
7/8) — neither dominates, and the direction agrees with the public real-corpus benchmark.

## Reproduce

```bash
npm install                          # @mozilla/readability 0.6.0 + jsdom 29.1.1 (locked)
node tests/build_fixtures.mjs        # 1) annotated fixtures + ground_truth.json
node tests/run_readability.mjs       # 2) Readability raw extraction + ipr sweeps

# comparison arm (optional but recommended) + metrics
uv venv .venv && uv pip install --python .venv/bin/python trafilatura   # 2.1.0
.venv/bin/python tests/run_trafilatura.py   # 3) trafilatura raw extraction (same bytes)
.venv/bin/python tests/metrics.py           # 4) precision/recall for BOTH, computed
```

Requires Node 20+ and (for the comparison arm) Python 3 + `uv`. Outputs land in
`artifacts/raw/*.json`. The fixtures are local (no network at runtime); every labeled unit
carries a unique sentinel, so recall/leak is exact membership — never guessed. **All
precision/recall is computed in `metrics.py` from raw extracted text vs the labels** — no
metric constant is written by hand (anti-hardcoding).

## What the pack establishes

- **Article recall (main):** 74/74 units recovered across all 22 fixtures; token recall
  1.000. The problem is never dropped article text on these fixtures.
- **Sibling-append precision leak:** neutrally-classed low-link prose siblings leak at the
  documented `linkDensity < 0.25 && len > 80` gate (+ the short-period branch); measured
  boundary 0.143 leak / 0.278 drop. On the realistic page, regex-classed chrome
  (nav/ad/sidebar/footer/comments) strips 5/6 and only this promo leaks.
- **charThreshold is soft:** no false-`null` on short clean articles; nav-as-article on
  content-poor pages. `null` requires literally no extractable text.
- **Structural robustness:** neutralized `<div>` article recovered 4/4 = the
  `<article>/<main>` version.
- **`isProbablyReaderable` false negatives:** li-only (unfixable by tuning), many-short
  (fix via `minContentLength`), one-long (needs ≥540 chars) — all with `parse()` succeeding.
- **Non-prose:** tables/code/captions/short lines retained 8/8 (beats trafilatura's 7/8).
- **Determinism:** all 22 fixtures 3-rep identical.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue scan, hypotheses, matrix,
  PROCEED verdict; treats the public word-F1 0.887 as DOCUMENTED).
- `research-materials.md` — full evidence, per-finding confidence, novelty table,
  Part-6 self-check.
- `scorecard.md` — provisional dimension scores (84/100), evidence-anchored.
- `metadata-snapshot.md` — versions, algorithm constants, exact commands, reproducibility.
- `tests/` — `build_fixtures.mjs`, `run_readability.mjs`, `run_trafilatura.py`,
  `metrics.py`, and `fixtures/` (HTML + `ground_truth.json`).
- `artifacts/raw/` — raw extraction + computed metrics + comparison JSON.

Evidence phase only: no article, no publishing. `validation.md` (independent audit) is
produced separately and is not part of this worker's deliverable. All numbers are
controlled-fixture measurements and do **not** replace the public real-corpus benchmark
(scrapinghub Readability.js word-F1 0.887), which is cited as the authoritative real-world
figure.
