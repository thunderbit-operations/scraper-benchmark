# easyocr — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a final
blog draft and must not be published as-is.

## Material Boundary

Evidence base for a single-tool review of **`easyocr`** (v1.7.2), JaidedAI's ready-to-use
OCR: a **CRAFT** text detector + **CRNN** recognizer (ResNet features → BiLSTM → CTC greedy)
on PyTorch. It judges **image/screenshot text fidelity against exact ground truth** (queue
#16): on images we **render** from strings we define, it measures **character/word error
rate (CER/WER)** on clean printed text and **where fidelity collapses** as font size
shrinks, contrast drops, the image rotates, or the background gets busy — plus a rendered
**screenshot** measured per-element, and the paired **resource cost** (model footprint, CPU
latency distribution, peak RSS). It does **not** score PyTorch/CRAFT internals, is **not** a
handwriting benchmark (README lists handwriting as "coming next"), is **English-recognizer
only** (`english_g2`), is **CPU-only**, and does **not** replace the public academic CER
figures on real / other-script corpora (cited as DOCUMENTED). All numbers are **synthetic
rendered Latin** on macOS arm64.

All tests run on **local, self-rendered fixtures** (no network at runtime except the
one-time model download, measured then cached). The public quantitative anchors — academic
benchmarks that use EasyOCR as a baseline and report **aggregate CER/chrF++ on real images
for specific scripts** (Devanagari stress-tests, low-resource-script LLM-OCR comparisons,
historical-newspaper OCR) — are treated as **DOCUMENTED**; this pack's value is the
**controlled single-variable CER-vs-degradation curves, the exact collapse thresholds, and
the paired resource cost** that an aggregate real-corpus scalar cannot show, not a
replacement for it.

## Source Snapshot

Point-in-time metadata (see `metadata-snapshot.md`; refresh within 48h before any final
draft):

| Field | Value |
|---|---|
| Repo | [JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) |
| Stars | **29,812** |
| Open issues | **528** |
| License | **Apache-2.0** |
| Latest release / PyPI latest | **1.7.2** (release 2024-09-24) |
| Version tested | **1.7.2** (`uv pip install easyocr` resolved 1.7.2) |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 arm64 |
| easyocr / torch / torchvision | **1.7.2 / 2.13.0 / 0.28.0** |
| opencv / numpy / Pillow | **5.0.0 / 2.5.1 / 12.3.0** |
| Python | **3.12.13** (uv venv) |
| Compute | **CPU** (`gpu=False`); MPS available but unused by EasyOCR on non-CUDA |
| Fixture generator | [tests/build_fixtures.py](tests/build_fixtures.py) → `tests/fixtures/*.png` + `tests/fixtures/ground_truth.json` |
| OCR runner | [tests/run_easyocr.py](tests/run_easyocr.py) → [easyocr_raw.json](artifacts/raw/easyocr_raw.json) |
| Metrics | [tests/metrics.py](tests/metrics.py) → [easyocr_metrics.json](artifacts/raw/easyocr_metrics.json) |

Fixtures: **36** PNGs — **35** single-line (7 fonts, 8 sizes, 7 contrasts, 7 skew angles,
3 orthogonal rotations, 3 backgrounds) + **1** screenshot (**19** labeled elements). GT
string: `"Sphinx of black quartz, judge my vow. 1234567890"` (48 chars: full pangram +
digits + comma/period, mixed case).

Method notes (they affect reproduction):

- **Ground truth is rendered, not annotated.** `build_fixtures.py` writes each PNG and its
  GT string together, so image and label can never drift and CER/WER is never subjective.
- **Anti-hardcoding split.** The runner returns only raw boxes (`bbox+text+conf`) + timing +
  resource; **all CER/WER, collapse thresholds, and screenshot IoU/recall are computed in
  `metrics.py`** from raw text vs labels. No error-rate constant is hand-written.
- **口径.** Boxes joined in **line-aware reading order** (group by vertical overlap, then
  left-to-right); normalization = whitespace-collapse + strip, **case-sensitive**, with a
  case-insensitive CER reported alongside. CER = Levenshtein(chars)/len(gt); WER =
  Levenshtein(words)/len(gt words); "collapse" = CER ≥ 0.30, "clean" = CER ≤ 0.05.
- **Determinism / cross-run.** 3 reps identical in-process; **every CER/recall headline is
  byte-identical across two independent process runs** — only timing varies.
- **Instrument isolation.** Peak RSS measured in a **fresh subprocess**; timing is a
  20-sample warm distribution measured under possible concurrent worker load.
- **Redaction.** `$HOME`→`~` and `$TMPDIR`/`/var/folders`→`<TMP>` before any JSON is written.

## Test Coverage Completed

### H1 — clean-text CER/WER floor per font (`easyocr_metrics.json` → `H1_font_floor`)

Canonical string, black-on-white, 32 px, 7 system fonts:

| Font | CER (case-sensitive) | CER (case-insensitive) | exact (ci) |
|---|---:|---:|:--:|
| georgia | 0.0625 | **0.0000** | ✓ |
| times | 0.0417 | 0.0417 | |
| comicsans | 0.0417 | 0.0208 | |
| arial | 0.0833 | 0.0208 | |
| verdana | 0.0833 | 0.0208 | |
| impact | 0.0833 | 0.0208 | |
| courier | 0.1042 | 0.0417 | |
| **mean** | **0.0714** | **0.0238** | |

**Reading: character recall on clean rendered Latin is essentially perfect; the residual
CER is case + punctuation, not lost characters.** Case-insensitive CER is **0.024** (georgia
is a perfect read once case is normalized). The dominant error is a **case-flip**: EasyOCR's
`english_g2` renders the lowercase word `vow` as `VOW` in 6 of 7 fonts (comicsans: `Vow`);
`impact` also flips `of`→`Of`. Punctuation is the other error: the sentence period is read
as `:` or `_` in several fonts. Confidence: high (deterministic, cross-run identical).
Novelty: EXCLUSIVE (per-font controlled floor); the *existence* of OCR error is DOCUMENTED.

### H2 — font-size collapse at the `min_size=10` floor (`H2_size_sweep`) [adversarial]

Arial, black-on-white, sweeping rendered px height:

| px | CER | n_boxes | reading |
|---:|---:|:--:|---|
| 8 | **0.7708** | 2 | **collapsed** — boxes below the 10 px `min_size` filter are dropped; only fragments survive |
| 10 | 0.1458 | 3 | degraded (right at the filter floor; detector fragments the line) |
| 12 | 0.0417 | 1 | recovered |
| 16 | **0.0000** | 1 | **perfect read (CER 0)** |
| 20 | 0.0208 | 1 | clean |
| 28 | 0.0208 | 2 | clean |
| 40 | 0.0625 | 1 | clean (case-flip reappears) |
| 64 | 0.0625 | 1 | clean (case-flip) |

**Reading: there is a hard small-font floor and a clean "sweet spot."** CER jumps from
~0.04 to **0.77** once the rendered glyph height falls under the documented `min_size=10`
detector filter (derived first-collapse value = **8 px**), and the best fidelity is
**12–28 px** where a full **CER = 0** occurs at 16 px. Above ~40 px CER *rises* again — not
from character loss but because the `vow→VOW` case-flip reappears. Confidence: high
(monotone, mechanism-tied to `min_size`). Novelty: KNOWN-ISSUE (small text) + EXCLUSIVE
(the exact px collapse boundary + the CER=0 sweet spot).

### H2 — contrast: NO collapse on clean rendered text (`H2_contrast_sweep`) [honest negative]

Arial 32 px, foreground gray → white background; `weber = (255−g)/255`:

| fg gray | Weber contrast | CER (default) | CER (adjust_contrast=1.0) | CER (pre-brighten ×2.2) |
|---:|---:|---:|---:|---:|
| 0 (black) | 1.000 | 0.0833 | 0.0833 | 0.0625 |
| 64 | 0.749 | 0.0833 | 0.0833 | 0.0625 |
| 110 | 0.569 | 0.0833 | 0.0833 | 0.0833 |
| 150 | 0.412 | 0.1042 | 0.1042 | 0.0833 |
| 180 | 0.294 | 0.0625 | 0.0625 | 0.0833 |
| 200 | 0.216 | 0.0417 | 0.0417 | 0.0833 |
| 220 | 0.137 | 0.0417 | 0.0417 | 0.0625 |

**Prediction falsified (honest negative).** On clean, noise-free rendered text EasyOCR is
**contrast-robust down to Weber 0.14** (faint gray-220 on white): CER never leaves the
0.04–0.10 clean band, and there is **no** collapse (derived first-collapse contrast =
`None`). The documented `contrast_ths`/`adjust_contrast` double-pass and a manual
pre-brighten make **no meaningful difference** — because the default already succeeds, so
the rescue mechanism never needs to fire. **Scope (important):** this is *solid-color,
noise-free* contrast; it does **not** speak to low-contrast **plus** sensor noise / JPEG
artifacts / textured backgrounds, where real low-contrast OCR usually fails. Confidence:
high for the tested (clean) shape; explicitly not generalized. Novelty: EXCLUSIVE
(quantified robustness that refutes a naive "low contrast breaks OCR" reading, scoped).

### H2 + H4 — rotation: skew tolerance ≤10°, and `rotation_info` is an ASYMMETRIC fix (`H2_H4_rotation`)

Small skew angles (Arial 32 px), default vs `rotation_info=[90,180,270]`:

| angle | CER (default) | CER (rotation_info) |
|---:|---:|---:|
| 0° | 0.0833 | 0.0833 |
| 5° | 0.0417 | 0.0417 |
| 10° | 0.0208 | 0.0833 |
| 15° | 0.2917 | 0.3750 |
| 20° | **0.7500** | 0.7708 |
| 30° | 0.8958 | 0.8750 |
| 45° | 0.8958 | 0.8750 |

Orthogonal rotations:

| angle | CER (default) | CER (rotation_info) | recovered? |
|---:|---:|---:|:--:|
| 90° | 0.8125 | **0.9167** | **no** (worse) |
| 180° | 0.8542 | 0.6667 | partial |
| 270° | 0.8333 | **0.1042** | **yes** |

**Reading — two separate results.** (1) Default EasyOCR tolerates **skew up to ~10°**
(CER ≤ 0.083), degrades at **15°** (0.29), and **collapses at ≥ 20°** (derived first-collapse
= 20°). `rotation_info` does **not** help skew (it only tries 90/180/270, so 15–20° stay
broken or get slightly worse). (2) For orthogonal rotation, the documented `rotation_info`
workaround ([#168]) is **asymmetric**: it recovers the **270°** image cleanly (CER
0.83 → **0.10**), the **180°** image only partially (0.85 → 0.67, with `my vow.` dropped),
and **fails the 90°** image (0.81 → **0.92**, producing mirror-text `VOW→MOA`,
`quartz→zuuenb`). This asymmetry is genuine EasyOCR output (verified in the raw predictions,
not a join artifact). **Mechanism (hypothesis, not proven):** Pillow renders positive angles
**counter-clockwise**, and only the 270°-rendered case lines up with an upright retry that
the recognizer handles; the mirror-text on 90° shows the best-scoring retry landed on a
flipped orientation. Confidence: high on the measured outcome; the cause is labeled a
hypothesis. Novelty: KNOWN-ISSUE ([#168]) + EXCLUSIVE (the swept skew boundary + the
quantified, **asymmetric** `rotation_info` recovery — the workaround is not a symmetric fix).

### Backgrounds — robust to color / gradient / noise (`backgrounds`)

Arial 32 px black text on non-white backgrounds:

| background | CER |
|---|---:|
| solid light-blue panel | 0.0833 |
| vertical gradient (255→145) | 0.0208 |
| gaussian noise (μ200, σ22) | **0.0000** |

**Reading:** none of these degraded recognition (the noise background was a **perfect
read**). Combined with H2-contrast, the picture is consistent: EasyOCR's CRAFT+CRNN is
robust to *background variation and low contrast on clean rendered glyphs*; its failure
surfaces are **geometry** (small size, rotation) and **isolated short tokens**, not color or
moderate noise. Confidence: high (deterministic). Novelty: EXCLUSIVE (per-background CER).

### H5 — screenshot per-element fidelity (`H5_screenshot`) [issue #460]

One rendered "Sales Dashboard" window (header/title, three KPI panels, three buttons, a
2×3 table, a single-letter badge), 19 labeled elements matched to recognized boxes by IoU
(≥ 0.30):

| Metric | Value |
|---|---|
| Detection recall | **16 / 19 = 0.842** |
| Missed elements | `badge` ("A"), `cell_q1` ("Q1"), `cell_q2` ("Q2") |
| Mean CER on matched elements | **0.0268** |
| Exact matched | **13 / 16** |

**Reading: the detector drops isolated short tokens; the recognizer is otherwise near-perfect
on screenshot text.** The three misses are the **single-letter badge "A"** and two **2-char
cells "Q1"/"Q2"** — while the *third* cell **"Q3" was detected** (recall is
token-length-sensitive but not deterministic on 2-char tokens). This is the concrete,
ground-truthed form of issue [#460] ("screenshot quality," detector misses single letters).
On the 16 matched elements, text is exact except a **systematic `"$"→"S"` misread** on 3 of
4 dollar amounts (`$57,912→S57,912`, `$18,330→S18,330`, `$25,178→S25,178`; `$12,004` read
correctly), which is what pulls mean matched-CER off zero. Titles, labels, buttons, and the
comma-grouped numbers are all CER 0. Confidence: high (deterministic, per-element ground
truth). Novelty: KNOWN-ISSUE ([#460]) + EXCLUSIVE (per-element detection recall + CER +
the `$→S` substitution on ground truth).

### H6 — resource cost, paired with fidelity (`resource`)

| Metric | Value |
|---|---|
| Model download footprint | **93.7 MiB** (CRAFT detector 79.30 + `english_g2` recognizer 14.44) |
| Cold `Reader()` init (models disk→RAM, int8-quantized) | **1.3–1.7 s** (across two runs) |
| Warm latency, clean 48-char line (p50) | **~0.062 s** (p25–p75 **0.059–0.067 s**, min 0.058 / max 0.076; 20 samples) |
| `detail=0` vs `detail=1` | **~equal** (median 0.062 vs 0.063 s — output verbosity, not compute) |
| Peak RSS (fresh process) | **~985–1116 MiB** (across two runs) |
| Determinism | 3 reps identical; all fidelity numbers identical across 2 runs |

**Reading:** the cost is **~94 MB of weights and ~1 GB of resident memory**, not the torch
install (~2 GB, separate). A clean single line is **sub-0.1 s warm** on CPU here — but this
is the *easy* case (one short high-contrast line); the public complaints of "tens of seconds
on CPU" ([#1206]) are large multi-region documents at full `canvas_size`, not this fixture,
and are cited, not reproduced. Cold start (~1.5 s) is dominated by loading + quantizing the
recognizer. `detail=0` does **not** speed recognition (it only strips bbox/confidence from
the return). Confidence: medium for timing (host-specific, concurrency-noted, single
machine); high for footprint/RSS/determinism. Novelty: KNOWN-ISSUE (CPU-slow) + EXCLUSIVE
(the paired footprint + warm distribution + RSS on a stated host).

## Key Findings for the Writer

1. **FINDING-01 — On clean rendered Latin, character recall is essentially perfect; the
   residual CER (mean 0.071 case-sensitive, 0.024 case-insensitive) is a case-flip
   (`vow→VOW`) + punctuation, not lost characters.** georgia is a perfect read once case is
   normalized. Confidence: high. Scope: synthetic, English `english_g2`. Novelty: EXCLUSIVE
   (per-font floor) over DOCUMENTED (OCR-has-error).

2. **FINDING-02 — Hard small-font floor at the documented `min_size=10`: CER jumps to 0.77
   at 8 px, recovers by 12 px, and hits CER = 0 at 16 px; the fidelity sweet spot is
   12–28 px.** Above ~40 px CER rises only because the case-flip reappears. Confidence: high
   (mechanism-tied). Novelty: KNOWN-ISSUE + EXCLUSIVE (exact px boundary + CER=0 point).

3. **FINDING-03 — No contrast collapse on clean, noise-free rendered text down to Weber
   0.14; the documented `adjust_contrast` rescue is not even needed.** Prediction falsified
   (honest negative). **Explicitly scoped**: does not cover low-contrast + noise/JPEG real
   photos. Confidence: high for the clean shape. Novelty: EXCLUSIVE (scoped quantification).

4. **FINDING-04 — Skew tolerance is ≤ 10° (collapse ≥ 20°); the `rotation_info` workaround
   is an ASYMMETRIC fix — it recovers a 270° image (CER 0.10) but only partially 180°
   (0.67) and fails 90° (0.92, mirror-text), and does nothing for skew.** The workaround is
   not the symmetric cure the issue thread implies. Confidence: high on outcome; cause is a
   hypothesis (Pillow CCW vs EasyOCR retry). Novelty: KNOWN-ISSUE ([#168]) + EXCLUSIVE
   (swept boundary + asymmetric recovery).

5. **FINDING-05 — On a rendered screenshot, detection recall is 16/19: the detector drops
   the single-letter badge "A" and the 2-char cells "Q1"/"Q2" (but keeps "Q3"); matched
   text is near-perfect (mean CER 0.027, 13/16 exact) except a systematic `"$"→"S"`
   misread.** The concrete, ground-truthed form of issue [#460]. Confidence: high. Novelty:
   KNOWN-ISSUE ([#460]) + EXCLUSIVE (per-element recall + CER + `$→S`).

6. **FINDING-06 — The resource cost is ~94 MB of weights and ~1 GB RSS; a clean single line
   is sub-0.1 s warm on CPU (p50 ~0.062 s) but cold start is ~1.5 s; `detail=0` does not
   speed recognition.** The "tens of seconds on CPU" complaints are large documents, cited
   not reproduced. Confidence: medium (timing host-specific), high (footprint/RSS). Novelty:
   KNOWN-ISSUE + EXCLUSIVE (paired numbers on a stated host).

## Provisional Scorecard

Provisional, based only on the completed material tests. Not a final benchmark. See
`scorecard.md` for scoring notes.

| Dimension | Weight | Score | Evidence |
|---|---:|---:|---|
| Setup and first run | 8 | **7** | `uv pip install easyocr` (torch ~2 GB) + one-time 94 MB model auto-download; then `Reader(['en']).readtext()` works |
| Clean-text fidelity floor | 14 | **13** | mean CER 0.071 / 0.024 ci; CER=0 achievable (16 px, georgia-ci); residual is case+punctuation |
| Small-font robustness | 10 | **6** | hard collapse under the `min_size=10` floor (CER 0.77 @8 px); clean ≥12 px |
| Contrast robustness | 10 | **9** | no collapse to Weber 0.14 on clean text; scoped (noise-free only) |
| Rotation robustness | 10 | **5** | skew ≤10° only, collapse ≥20°; `rotation_info` asymmetric (270 ok / 90 fails) |
| Background robustness | 6 | **6** | color/gradient/gaussian-noise all clean (noise = CER 0) |
| Screenshot/UI fidelity | 12 | **9** | detection recall 16/19 (drops single-letter + 2-char tokens); matched CER 0.027; `$→S` |
| Resource footprint | 8 | **6** | 94 MB weights + ~1 GB RSS; torch ~2 GB dependency |
| CPU latency | 8 | **6** | warm p50 ~0.062 s clean line; cold ~1.5 s; host-specific, single machine |
| Determinism / reproducibility | 8 | **8** | 3-rep identical + all fidelity numbers identical across 2 independent runs |
| Anti-hardcoding / method rigor | 6 | **6** | raw/metrics split; CER computed from raw vs rendered GT; line-aware join bug caught + fixed |
| **Total** | **100** | **81** | provisional research-material score only |

## Gaps Before Final Blog Draft

- **English recognizer only.** `english_g2`; the 80+ language claim and non-Latin scripts
  (where the public academic CER figures live) are not tested here.
- **Handwriting not tested** (README lists it as not-yet-supported).
- **Low-contrast + noise interaction not tested.** H3 shows clean-contrast robustness only;
  the harder real case (faint text *plus* sensor/JPEG noise) is a Gap.
- **Real-photo corpus not run.** All fixtures are synthetic rendered text; the public
  real-corpus / other-script CER figures are cited, not reproduced.
- **Timing is single-machine, CPU-only, concurrency-noted.** No GPU number, no cross-machine
  distribution, no large-document (`canvas_size`) latency (the [#1206] "slow CPU" shape).
- **Single version / platform.** easyocr 1.7.2 + torch 2.13.0, macOS arm64.

## Novelty verification (pre-registration search)

Sources per finding: EasyOCR README + jaided.ai docs + issue tracker, top-~20 SERP, and the
academic benchmark corpus. Verdict is `[EXCLUSIVE]` / `[KNOWN-ISSUE: link]` / `[DOCUMENTED]`.

| Finding | Verdict | Prior record |
|---|---|---|
| CRAFT+CRNN architecture, `readtext` params, `min_size`/`contrast_ths`/`rotation_info` mechanisms, "CPU slower than GPU" | **DOCUMENTED** | README + jaided.ai docs; existence, not this pack's value |
| aggregate CER/chrF++ on real / non-Latin corpora | **DOCUMENTED** | academic benchmarks use EasyOCR as a baseline; this pack does NOT claim to replace them |
| clean-text CER floor per font + case-flip decomposition | **EXCLUSIVE (quantification)** | no public per-font controlled CER floor on rendered text; zero-hit |
| font-size collapse at `min_size=10` (CER 0.77 @8 px, CER=0 @16 px) | **KNOWN-ISSUE (small text) + EXCLUSIVE** | small-text weakness known; the exact swept px boundary + CER=0 sweet spot is this pack's |
| contrast robustness to Weber 0.14 on clean text (no collapse; rescue unneeded) | **EXCLUSIVE (scoped quantification)** | folklore "low contrast breaks OCR"; the flat clean-contrast sweep refutes it for the clean shape; zero-hit |
| skew ≤10°, collapse ≥20°; `rotation_info` asymmetric (270 ok / 180 partial / 90 fails) | **KNOWN-ISSUE ([#168]) + EXCLUSIVE** | #168 reports the 90° failure + the workaround; the swept boundary + the **asymmetric** recovery quantification is this pack's |
| screenshot detection recall 16/19 (drops single-letter + 2-char) + `$→S` | **KNOWN-ISSUE ([#460]) + EXCLUSIVE** | #460 reports weak screenshot / dropped single letters; per-element recall + CER + `$→S` on ground truth is this pack's |
| paired resource: 94 MB weights, ~1 GB RSS, warm p50 ~0.062 s, cold ~1.5 s | **KNOWN-ISSUE (CPU-slow) + EXCLUSIVE** | #1206 "slow CPU" anecdotal; the paired footprint + warm distribution + RSS on a stated host is this pack's |
| the "tens of seconds on CPU" figure | **KNOWN-ISSUE, NOT reproduced** | [#1206]/[#108] — large documents; this fixture is a single clean line, reported as not reproduced |

**Consequence for the writer:** the information-gain items are measurements or constructed
demonstrations behind documented/known behavior — the per-font CER floor, the `min_size` size
collapse, the scoped contrast-robustness negative, the asymmetric `rotation_info` recovery,
the screenshot per-element table, and the paired resource distribution. Existence /
architecture / parameter claims stay DOCUMENTED; the rotation / screenshot / CPU-speed
complaints stay KNOWN-ISSUE and cite an issue; the real-corpus / non-Latin CER figures are
cited, never claimed.

## Part 6 self-check (v3 pre-submission checklist)

1. **Self-contradicting winner sentence (D1)** — *Pass.* No cross-tool "wins" claim (this is
   a single-tool pack; no OCR sibling in the repo). Internal comparisons (default vs
   `rotation_info`, default vs `adjust_contrast`) are reported with the exact CER on both
   sides, including where the variant is **worse** (rotation_info 90° 0.81→0.92, 10° skew
   0.021→0.083). Falsified predictions (contrast, some rotation recovery) are labeled honest
   negatives, not spun.
2. **Claim-without-artifact (D4)** — *Pass.* Every number cites a JSON field
   (`easyocr_metrics.json` H1/H2/H4/H5/resource, `easyocr_raw.json` boxes). The "tens of
   seconds CPU" figure I did **not** reproduce is reported as **not reproduced**, not
   asserted. The `$→S` and case-flip claims are grounded in the raw predicted strings.
3. **Blind instrument (D2)** — *Pass.* The metric registers both success and failure: it
   records CER = 0 cases (16 px, noise bg) **and** CER = 0.77–0.92 collapses (8 px, ≥20°
   rotation), and the collapse flips with the swept variable (size, angle), proving it is
   not blind to either outcome. Ground truth is the exact rendered string, so a "correct"
   read requires the actual characters. Peak RSS is measured in a **fresh process**
   (instrument isolation), not shared with the main run's load.
4. **Mis-attribution (D3)** — *Pass, and one trap caught.* The **first metrics pass reported
   CER 0.375 on clean black Arial** — traced to a **harness reading-order bug** (a naive
   y-then-x join scrambled a single line the detector split into a words-box + a digits-box),
   **not** OCR failure; fixed with a line-aware (vertical-overlap) join, after which clean
   fonts resolved to CER ~0.04–0.10 and the digits ordered correctly. The rotation asymmetry
   and screenshot misses were verified against **raw predicted strings** to confirm they are
   genuine EasyOCR output, not join artifacts. The rotation cause is explicitly a
   **hypothesis** (no rotation-convention experiment run).
5. **Novelty-tag coverage + self-praise lint (D7/D12)** — Novelty table present with a
   verdict per finding; `grep -iE 'honest|independent|strongest|trustworthy'` over this file
   surfaces only "honest negative" labels flagging falsified predictions (rule-required
   transparency), not self-praise on the tool.

## As-of provenance check

- **Snapshot date:** explicit **2026-07-24** in `metadata-snapshot.md`. Stars (29,812) /
  latest release (1.7.2) traceable to that GitHub/PyPI fetch.
- **Versions:** easyocr 1.7.2 (== PyPI latest / latest release); torch 2.13.0; torchvision
  0.28.0; opencv 5.0.0; numpy 2.5.1; Pillow 12.3.0; Python 3.12.13 — read from the run meta.

## Raw Artifact Index

- Ground truth (rendered strings + params + screenshot element bboxes): [tests/fixtures/ground_truth.json](tests/fixtures/ground_truth.json)
- EasyOCR raw recognition + timing + resource: [easyocr_raw.json](artifacts/raw/easyocr_raw.json)
- Computed CER/WER/recall/thresholds: [easyocr_metrics.json](artifacts/raw/easyocr_metrics.json)

[#168]: https://github.com/JaidedAI/EasyOCR/issues/168
[#460]: https://github.com/JaidedAI/EasyOCR/issues/460
[#108]: https://github.com/JaidedAI/EasyOCR/issues/108
[#1206]: https://github.com/JaidedAI/EasyOCR/issues/1206
