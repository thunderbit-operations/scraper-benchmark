# mozilla-readability — provisional scorecard

**Provisional.** Based only on the completed material tests (see `research-materials.md`).
Not a final benchmark and not a cross-tool ranking. Weights are pack-local and
pre-registered here; scores are evidence-anchored, each citing a run. All numbers are on
controlled synthetic fixtures (`@mozilla/readability` 0.6.0 + jsdom 29.1.1 + Node
22.22.3, macOS arm64), and are NOT a replacement for the public real-corpus benchmark
(scrapinghub Readability.js word-F1 0.887).

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 8 | 8 | `npm i @mozilla/readability jsdom`; pure JS but needs a DOM implementation (jsdom) supplied at runtime |
| Article recall | 14 | 14 | 74/74 labeled article units recovered, token recall 1.000 across all 22 fixtures (`readability_metrics.json`) |
| Boilerplate precision (leak resistance) | 14 | 9 | leak 5/17 on the adversarial-weighted content-fidelity set; regex-classed chrome (nav/ad/sidebar/footer/comments) strips 5/6 on the realistic page |
| Adversarial precision boundary | 10 | 7 | sibling-append leaks at `linkDensity<0.25 && len>80` (0.143 leak / 0.278 drop) + short-period branch (`readability_raw.json` promo_geometry) |
| Short-content handling | 8 | 7 | no false-null; recovers clean articles to 120 chars, flat across charThreshold 200/500/1000; but returns nav-as-article on content-poor pages |
| Structural robustness | 8 | 8 | neutralized `<div>` article recovered 4/4 = the `<article>/<main>` version (`comparison.json`) |
| Non-prose recall | 8 | 8 | 8/8 tables/code/captions/short lines retained; out-recalls trafilatura (7/8, dropped a `<figcaption>`) |
| `isProbablyReaderable` predictor | 10 | 5 | broad false negatives where `parse()` succeeds: li-only (unfixable by tuning), many-short, one-long (score 16.4<20) |
| Determinism | 6 | 6 | all 22 fixtures returned identical extracted text across 3 reps |
| Cost / parser transparency | 6 | 5 | requires a full jsdom DOM at runtime; extraction timing not collected as a distribution (Gap) |
| Same-testbed comparison completeness | 8 | 7 | trafilatura arm on the identical fixtures; synthetic only, real-corpus deferred |
| **Total** | **100** | **84** | provisional research-material score only, not a final rating |

Scoring notes:

- **Boilerplate precision (9/14)** is docked for the sibling-append leak, but the 5/17
  leak rate is measured on a set that **deliberately overweights** the H2 adversarial
  variants (6 of 11 fixtures). On the single realistic page `f1_canonical`, 5 of 6 chrome
  blocks strip and only the neutral-classed low-link promo leaks. The number is
  worst-case-leaning, not a typical-page rate; the DOCUMENTED real-corpus precision is
  0.853. Not full credit because the leak is a genuine, constructible precision hole.
- **Adversarial precision boundary (7/10):** the append gate is *documented* source
  behavior, but it is exploitable — a long, low-link, neutrally-classed promotional block
  is indistinguishable from article prose to the heuristic and rides along. Points held
  back for the exploitability; not lower because article recall is untouched (4/4) and the
  boundary is clean and predictable (exactly `linkDensity 0.25` / `80` chars).
- **Short-content handling (7/8):** the `charThreshold=500` "cliff" is **soft** — the
  flag-removal sieve recovers short clean articles (no false-null down to 120 chars),
  which is good. Docked one point because the same fallback returns **boilerplate as the
  article** on content-poor pages (the near-empty fixture returned its nav).
- **`isProbablyReaderable` predictor (5/10):** the README admits false positives/negatives,
  but the false-negative surface measured here is broad and, for the li-only shape,
  **unfixable by any threshold** (the predictor never inspects `<li>`), while `parse()`
  succeeds on all of them. A pre-flight gate that rejects real, parseable articles is a
  real quality limit for the "only parse if readerable" usage the README recommends.
- **Structural robustness / Non-prose recall / Article recall / Determinism** score full
  or near-full because the measurements are unambiguous and the tool behaved well:
  100% article recall, semantic-tag independence, full non-prose retention, and perfect
  3-rep determinism.
- **Cost / parser transparency (5/6):** docked because extraction timing was **not**
  collected as a distribution (a deliberate Gap — the pack's focus is fidelity, not
  speed) and because Readability's "pure JS, no dependencies" framing understates the
  runtime need for a full DOM implementation (jsdom here).
- Scores reflect **content-extraction fidelity on controlled ground truth** only;
  Readability is not scored on real-corpus accuracy (deferred to the cited public
  benchmark) or on jsdom's own conformance.
