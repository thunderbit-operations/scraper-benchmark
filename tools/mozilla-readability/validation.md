# mozilla-readability — Independent Audit (validation)

**VERDICT: PASS WITH FIXES** (one cosmetic prose↔artifact number drift flagged for the
writer, plus one cosmetic metadata note. No headline / score / ground-truth / evidence-
integrity fix required. Nothing auto-edited.)

Every headline reproduced independently against the pack's own harness on a clean full
re-run (@mozilla/readability **0.6.0** + jsdom **29.1.1** / Node **v22.22.3**; comparison
arm trafilatura **2.1.0** / Python **3.12.13** uv venv; macOS arm64). I re-ran the entire
pipeline — `build_fixtures.mjs` → `run_readability.mjs` → `run_trafilatura.py` →
`metrics.py` — and the three **computed** metric files (`readability_metrics.json`,
`trafilatura_metrics.json`, `comparison.json`) came out **byte-identical to the committed
artifacts** (modulo the `computed_at` timestamp); `readability_raw.json` is byte-identical
modulo `elapsed_ms`/timestamps. The H1 recall matrix, the H2 sibling-append density
boundary, the H3/H4/H6 falsified-prediction honest negatives, the H5 predictor sweeps, and
the trafilatura contrast all reproduce. Anti-hardcoding lint is clean, secret/abspath scan
is clean, the scorecard is arithmetically self-consistent (weights = 100, total = 84), and
the novelty three-classification correctly keeps every EXCLUSIVE scoped to
"(quantification)"/"(demonstration)" while the algorithm's documented behavior stays
DOCUMENTED and the #662 / real-page misses stay KNOWN-ISSUE.

**The pack's original artifact JSONs were restored after my runs** (my reproduction values
are recorded below and match); `tests/fixtures/*` were regenerated deterministically and
diff **byte-identical** to the committed copies, proving the ground truth is code-generated,
not hand-edited. No git repo exists under this pack, so nothing is committed;
`node_modules/` (26M) and `.venv/` (80M) are gitignored and were never shippable.

---

## Fixture ground-truth fairness — the audit core: FAIR (no systematic bias)

The precision/recall numbers rest entirely on the article-vs-boilerplate labels in
`ground_truth.json`. Two independent facts make them auditable and fair:

1. **Labels are code-generated, not hand-placed.** `build_fixtures.mjs` writes the HTML and
   `ground_truth.json` from one deterministic pass. I re-ran it and the fixtures + ground
   truth are **byte-identical** to the committed copies — there is no room for a
   hand-tuned label that drifts from the HTML. Auditing the labels = auditing the generator,
   which I did line by line.

2. **The one adversarial labeling choice is structurally justified and harsh on
   Readability, not lenient.** The H2/`f1-promo` "leak" blocks are labeled BOILERPLATE.
   They are `<p class="teaser">`/`class="teaser-block"` siblings placed **outside** the
   `<article>` element (direct children of `#page`, next to the article, described as
   "related/promo"). A promotional teaser sitting outside the article body is boilerplate by
   the standard content-extraction convention **and** by Readability's own "return the
   article, remove boilerplate" contract — so appending it is a genuine precision leak.
   Crucially, this label makes Readability look **worse** (it lowers its precision); the pack
   does this to itself and then repeatedly discloses the set as adversarial. There is **no**
   label in the reverse direction — no real boilerplate is tagged ARTICLE to inflate recall,
   and no real article is tagged boilerplate to deflate it. Every ARTICLE unit is genuine
   in-container article text (F1 A1–A4 inside `<article>`; F6 all inside `<article>`; F3
   blurb is the only content; F4 the four paras; F5 the li/p content). So the 100% recall is
   real and the 0.294 leak is, if anything, an adversarially-harsh self-penalty — the
   opposite of precision-gaming.

Would a human call the leaked block boilerplate? Yes — a teaser/related widget outside the
article is not article prose. The synthetic vocabulary means the block's *semantics* can't
be judged, but its *structural role* (out-of-article teaser) is unambiguous and is what
defines the label. **Conclusion: the ground truth is fair and, on the adversarial axis,
tilted against the tool, not for it.**

---

## Required fixes before publishing

**None at headline / score / ground-truth / evidence-integrity level.** Two cosmetic
writer-notes, flagged not auto-edited (matching the rod/selenium auditors' posture on
numeric/provenance drift — editing quoted numbers across three docs risks desyncing prose
from the artifact and substituting my rounding for the writer's).

### F1 — COSMETIC (flagged): prose H2 link-density / length values are stale vs the committed artifact
The committed `readability_raw.json` `promo_geometry` (which I reproduced exactly) says:

| fixture | artifact len | artifact link_density | outcome |
|---|---:|---:|:--:|
| `f2_sib_len120_ld000` | **126** | **0.0000** | LEAK |
| `f2_sib_len120_ld015` | **126** | **0.1429** | LEAK |
| `f2_sib_len120_ld029` | **126** | **0.2778** | drop |
| `f2_sib_len120_ld050` | **126** | **0.4762** | drop |
| `f2_sib_len60_period` | **60** | 0.0000 | LEAK |
| `f2_sib_len60_noperiod` | **59** | 0.0000 | drop |

But the prose quotes **len 128** (rows 1–4), **len 56** (noperiod), and density **0.141
leaks / 0.273 drops** (rounds of an earlier fixture iteration — 0.1429→0.143, 0.2778→0.278,
not 0.141/0.273). This drift appears in `research-materials.md` (H2 table lines 118–123,
FINDING-02 line 272, Part-6 line 388), `README.md` (lines 21, 30, 58), and `scorecard.md`
(line 15). **The finding is fully intact**: the gate still straddles exactly `0.25`
(0.1429 < 0.25 < 0.2778), still `len > 80`, and the short-period second branch still leaks
where the no-period one drops. Only the quoted decimals/lengths need to match the artifact
(0.141→0.143, 0.273→0.278, 128→126, 56→59) in the final draft.

### C1 — COSMETIC (flagged): metadata Python version
`metadata-snapshot.md` / `research-materials.md` state the comparison+metrics Python is
**3.14.2**; the shipped `.venv` is **3.12.13**. Affects **no headline** — trafilatura 2.1.0
reproduced every comparison number verbatim on 3.12.13. Either the venv was rebuilt after
the metadata was written or the version is a typo; reconcile in the final draft.

---

## Independent reproduction (my re-runs)

### H1 — article recall (the recall headline) — CONSISTENT
Unit article recall **74/74 = 1.000** across all 22 fixtures (every fixture's
`article_units_recovered == article_units`), and **token recall 1.000** micro-averaged over
the 11-fixture content-fidelity set — both reproduced exactly. Note (accurate as written):
the "token recall 1.000" is the **CF-set micro-average**; three F5 fixtures show per-fixture
token recall < 1.0 (0.9902 / 0.99 / 0.9655 — a stray token, unit still recovered), and they
are **not** in the CF set, so the headline is internally consistent. Readability never
dropped a labeled article unit on these fixtures → "the failure surface is precision, not
recall" holds. **CONSISTENT.**

### H2 — sibling-append density boundary (the precision headline, must-run) — CONSISTENT
Reproduced from my fresh raw output (identical to committed):

| fixture | link_density | >80 | leaked (mine) | leaked (worker) |
|---|---:|:--:|:--:|:--:|
| len120_ld000 | 0.0000 | yes | **LEAK** | LEAK |
| len120_ld015 | **0.1429** | yes | **LEAK** | LEAK |
| len120_ld029 | **0.2778** | yes | **drop** | drop |
| len120_ld050 | 0.4762 | yes | drop | drop |
| len60_period | 0.0000 | no | **LEAK** | LEAK |
| len60_noperiod | 0.0000 | no | **drop** | drop |

The leak flips **at the 0.25 gate** (0.1429 in, 0.2778 out) with `len > 80`, plus the second
branch `len < 80 && ld === 0 && has period` (60-char sentence leaks, 56/59-char no-period
drops). The mechanism is genuinely **bound to `linkDensity < 0.25 && nodeLength > 80`**, not
a coincidence — the density sweep isolates it and article recall stays **4/4** in every arm.
**CONSISTENT** (only the prose's decimals are stale — see F1).

### H3 / H4 / H6 — falsified predictions reported as honest negatives — CONSISTENT
The prompt's key concern: are these genuine measured negatives or powdered into positives?
My re-run confirms they are honest negatives, explicitly labeled "**Prediction falsified
(honest negative)**":
- **H3 charThreshold soft:** `parse_ok = true` and identical extracted length **flat across
  charThreshold {200,500,1000}** for every body length 120→1500; no false-null. The
  near-empty `f3_empty` returns **non-null nav-as-article** (`"…zzemptynav… zzemptyblurb
  hi."`). The true null boundary is "no extractable text," exactly as claimed.
- **H4 semantic robustness:** `f4_semantic` 4/4 == `f4_neutral` 4/4, 0 leak both. Stripping
  `<article>/<main>/<h1>` did not reduce recall — no drop, honestly reported (with the
  competing-block tie-break explicitly left a Gap).
- **H6 non-prose:** 8/8 retained (prose, table cells, `<pre>`, sub-25-char lines,
  figcaption). Reported as a negative that also happens to be a **win vs trafilatura** —
  stated with the exact 8/8 vs 7/8, not inflated.

None is spun. **CONSISTENT.**

### H5 — isProbablyReaderable false-negative surface — CONSISTENT
`ipr_default = false` while `parse_ok = true` on all three shapes, with the lever separation
reproduced exactly: **li-only** false at *every* minScore (1–80) **and** every
minContentLength (40–200) → structurally unfixable; **many-short** false at all minScore but
**true at minContentLength ≤ 100**, false ≥ 140 → the lever is minContentLength, not
minScore; **one-long** true ≤ 10, **false ≥ 20** (score ≈ sqrt(408−140) ≈ 16.4) → minScore
lever; **normal** control true. **CONSISTENT.**

### trafilatura contrast — CONSISTENT, not cherry-picked
Micro over the CF set, reproduced exactly: leak **0.2941 (5/17)** vs **0.0588 (1/17)**;
token precision 0.9017 vs 0.9394; **token-F1 0.9483 vs 0.9688**; f6 non-prose **8/8 vs 7/8**
(trafilatura drops `f6-cap-01`, the `<figcaption>`); very-short `f3_short_120` **F1 0.800 vs
0.571**. trafilatura's single leak is the **shared empty-page nav** (both tools return it),
not a hand-picked win. "Neither dominates" is the honest read — trafilatura cleaner on
boilerplate precision, Readability higher on short/non-prose recall — and it agrees in
direction with the DOCUMENTED real-corpus ranking. **No "Readability sweeps / is crushed"
sentence exists.** CONSISTENT.

---

## Four-class leak audit (Part 6)

**D1 — self-contradicting winner: PASS.** Scorecard weights sum to 100, scores to 84
(re-added by hand). The comparison reports a **split**, no unqualified "wins"; 100% recall is
paired with the leak in the same headline sentence; token-recall ties are not framed as wins.

**D2 — blind instrument: PASS.** The metric registers **both** presence (recall 1.0) and
absence (leaks 5/17), and the leak side **flips** across the constructed density boundary
(0.1429 leak → 0.2778 drop) — positive+negative control, exercised in my re-run. Sentinels
are runtime-unique, disjoint tokens, so a "found" requires the actual extracted text.

**D3 — mis-attribution: PASS.** The two fixture-artifact traps the worker claims to have
fixed are real and verified: (a) the **#page-wins masking** trap — in the DROP arms
(`ld050`, `len60_noperiod`) I confirmed article recall **4/4 with 0 leak**, which is only
possible if the `<article>` is the top candidate and the sibling gate is being isolated (if
`#page` were winning, the promo would ride along and leak in every arm); (b) **H3/H4/H6
forced-failure → honest negatives**, verified above. The H2 leak is attributed to the source
gate and validated by the density sweep, not asserted from source-reading.

**D4 — claim-without-artifact: PASS (with the F1 cosmetic drift).** Spot-checked: leak 5/17
→ `micro_avg…unit_boilerplate_leak_rate`; density boundary → `readability_raw…promo_geometry`;
f6 8/8 vs 7/8 → `…per_fixture.f6_nonprose.unit_level`; short-F1 0.800/0.571 →
`…f3_short_120.token_level.f1`; nav-as-article → `readability_raw.f3_empty.default`. All
resolve. The only prose↔artifact mismatch is the cosmetic decimal/length drift (F1); the
KNOWN-ISSUE real-page drops (#437/#901/#922) are correctly reported as **not reproduced**.

### The 0.294 "adversarial set" framing — honestly labeled, not misleading
The 0.294 leak rate is disclosed as adversarially-weighted (6 of 11 CF fixtures are the H2
variants) in **all four** documents — README ("adversarial-weighted set"), scorecard
("deliberately overweights… worst-case-leaning, not a typical-page rate; DOCUMENTED
real-corpus precision 0.853"), research-materials (blockquote scope note), and pretest. The
one place it appears bare (README comparison sentence "leak 0.059 vs 0.294") is immediately
followed by "neither dominates… direction agrees with the public real-corpus benchmark."
A reader is not led to believe Readability leaks 29% in the wild; nor is 0.294 spun into
"Readability is bad" (the pack stresses 5/6 chrome strips on the realistic page and recall
is untouched). Both directions threaded correctly.

---

## Novelty classification (three-gate) — Gate-1 CLEAN
Disciplined; no EXCLUSIVE sits on a documented qualitative fact.
- Rule-based scoring, unlikely-regex, sibling-append gate, `charThreshold=500`,
  `isProbablyReaderable` thresholds **exist** → **DOCUMENTED** (README/source). Correct.
- Aggregate real-corpus word-P/R/F1 → **DOCUMENTED** (scrapinghub 0.887), explicitly *not*
  claimed/replaced. Correct — the exact "don't crown a documented benchmark" discipline.
- 100% controlled per-unit recall, semantic-tag robustness, non-prose 8/8, soft-charThreshold
  correction → **EXCLUSIVE (quantification/correction)** — each scoped to a measurement, none
  to a qualitative discovery.
- Sibling-append leak → **DOCUMENTED gate / EXCLUSIVE demonstration** (the gate is source; the
  neutral-classed boundary demo is the pack's). Correctly split — this is the exact place a
  weaker pack would mislabel, and it does not.
- `isProbablyReaderable` false negatives → **KNOWN-ISSUE (#662) + EXCLUSIVE** lever-separation.
  Correctly credits prior art.
- Real-page paragraph/before-table drops → **KNOWN-ISSUE, NOT reproduced.** Honest.

## Anti-hardcoding lint: PASS
Every precision/recall/leak value in `metrics.py` is **computed** (`tp/ex_total`,
`boiler_leak/boiler_units`, sentinel-in-text membership) — no metric constant is written by
hand. `run_readability.mjs` returns raw text only and computes `promo_geometry.leaked` /
`link_density` as **derived** DOM measurements (a substring check + the exact link-density
formula), not stored results — so the anti-hardcoding *split for the headline P/R metrics*
holds (nuance: the probe is not literally "zero measurement logic," but nothing it computes
is a hardcoded conclusion, and the `leaked` boolean agrees with metrics.py's unit-level
count). The only numeric literal `0.887` is the cited public benchmark in a docstring/caveat.
Fixture `btype` labels like `sibling-len120-ld0.29` are descriptive names; the *measured*
density (0.2778) is computed at runtime, not read from the name.

## Secret / abspath / cleanliness scan: CLEAN
- **Credentials:** no `sk-`/`ghp_`/`Bearer`/`AKIA`/`API_KEY`/private-key patterns in any
  publish-bound file (`*.md`, `tests/*.{mjs,py}`, `tests/fixtures/*.{html,json}`,
  `artifacts/raw/*.json`, `package*.json`), excluding `node_modules`/`.venv`.
- **Absolute paths:** no `/Users/richardli`, no real `/var/folders/<hash>` or `/private/var`
  temp path anywhere. The `$TMPDIR`/`/var/folders` strings that appear are **prose describing
  the redaction mechanism**, not leaked paths. Redaction is live: `run_readability.mjs` and
  the Python arms map `$HOME→~`, `$TMPDIR`/`/var/folders`→`<TMP>` before writing. The only
  URL in the artifacts is the synthetic `http://fixture.local/article`.
- **Self-praise lint:** `grep -iE 'honest|independent|strongest|trustworthy'` surfaces only
  the "honest negative" transparency labels (rule-required), methodology "Independent…
  reproducible / independent audit", and the Part-6 line quoting the lint command itself
  ("strongest/trustworthy" appear **only** inside that quoted pattern). No quality adjective
  is awarded to Readability. Neutralize the transparency labels in the final draft; not a
  blocker.
- **node_modules / .venv:** gitignored; no git repo under the pack, so nothing was committed
  or rsynced. On-disk only, isolated, not shippable.

---

## Residual gaps the writer must not overclaim (the pack lists these; keep them)
1. **All numbers are controlled synthetic fixtures, single machine / version.** The public
   real-corpus figure (scrapinghub word-F1 0.887 / P 0.853) is the authoritative real-world
   ranking and is cited, not reproduced. Keep it framed that way.
2. **0.294 is adversarially weighted.** Never present it as a typical-page leak rate (the
   pack does not).
3. **Competing-block tie-break untested (H4 Gap), timing not a distribution, real-page misses
   (#437/#901/#922) not reproduced.** Keep as stated.

---

_Audit re-ran the full pipeline (`build_fixtures` → `run_readability` → `run_trafilatura` →
`metrics`) in the pack's own layout on 2026-07-24; the three computed metric files and the
raw dump reproduced byte-identical (modulo timestamps/`elapsed_ms`), and the deterministic
fixture rebuild is byte-identical to the committed ground truth. The pack's original
artifact JSONs were restored afterward; no stray files left, backup removed._

**Net status: PASS WITH FIXES.** All headlines reproduced; the fixture ground truth is
code-generated, fair, and (on the adversarial axis) harsh-on-Readability not lenient; the
H2 density boundary is a real mechanism-bound measurement; H3/H4/H6 are genuine honest
negatives; the trafilatura contrast is balanced and not cherry-picked; D1–D4 clean; novelty
Gate-1 clean (no EXCLUSIVE-on-documented mislabel); anti-hardcoding, secret, and abspath
scans clean; node_modules not committed. The single required change (F1) is a **cosmetic
prose↔artifact number drift** (quoted link-density/length values slightly stale vs the
artifact — conclusion unaffected), flagged for the writer, plus a cosmetic Python-version
note (C1). The 84/100 is the honest arithmetic of evidence-anchored dimension scores.
