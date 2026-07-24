# easyocr — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (measurable, mechanism-tied gaps exist that the public EasyOCR
accuracy sources do not cover; see "Information-gain verdict").

Broad keyword: **`easyocr`** (JaidedAI's ready-to-use OCR: CRAFT text detector + CRNN
recognizer on PyTorch). Article boundary: EasyOCR is a **two-stage OCR pipeline** — a
**CRAFT** detector locates text boxes, then a **CRNN** recognizer (ResNet/VGG feature
extraction → BiLSTM → CTC decode) reads each box; `readtext()` returns
`[(bbox, text, confidence), …]`. This pack judges **image/screenshot text fidelity
against known ground truth** (queue #16: "image/screenshot text fidelity and resource
tradeoffs"): given synthetic images rendered from text **we define** (so the ground truth
is exact, not annotated), what is the **character/word error rate (CER/WER)** on clean
printed text, and **where does it collapse** as font size shrinks, contrast drops, the
image rotates, or the background gets busy — plus the **resource cost** (model download
footprint, CPU single-image latency distribution, peak memory). It is **not** a scoring of
PyTorch/CRAFT internals, **not** a handwriting benchmark (README lists handwriting as "what's
coming next"), **not** a multilingual accuracy study (English `english_g2` recognizer only),
and **not** a real-photo-corpus replacement for the public academic benchmarks (which are
cited as DOCUMENTED). Cross-tool axis is deferred: no other OCR pack exists in the repo yet
(tesseract/poppler are not installed and EasyOCR does not need them), so this pack is
single-tool with an internal **default-vs-tuned** contrast/rotation contrast instead of a
sibling-tool arm.

## SERP / official / issue scan (README, jaided.ai docs, issue tracker, ≈20 SERP)

### What the results repeat (consensus, mostly documented or qualitative)

- **Two-stage architecture, "ready-to-use."** Every intro repeats: CRAFT detection +
  CRNN recognition (ResNet/VGG + LSTM + CTC), 80+ languages, `pip install easyocr`,
  `Reader(['en']).readtext(img)`. Documented in the
  [README](https://github.com/JaidedAI/EasyOCR) and jaided.ai docs. **Qualitative** — none
  give a controlled CER/WER-vs-degradation curve.
- **`gpu=True` default; "much faster with a GPU."** The README/console explicitly warn
  `Using CPU. Note: This module is much faster with a GPU`. That CPU is slower than GPU is
  **DOCUMENTED**; the actual CPU single-image latency *distribution* and memory peak on a
  given host are not published as a reproducible number.
- **Parameter surface is documented.** jaided.ai lists `readtext()` defaults:
  `detail=1`, `paragraph=False`, `decoder='greedy'`, `beamWidth=5`, `batch_size=1`,
  `min_size=10`, `rotation_info=None`, `contrast_ths=0.1`, `adjust_contrast=0.5`,
  `text_threshold=0.7`, `low_text=0.4`, `link_threshold=0.4`, `mag_ratio=1`,
  `canvas_size=2560`. Existence + defaults are **DOCUMENTED**; the *effect size* of each
  on error rate is not measured publicly.
- **The `contrast_ths` / `adjust_contrast` auto-recovery mechanism.** Docs: "Text box with
  contrast lower than `contrast_ths` will be passed into the recognizer **twice** — once
  with the original image and once with contrast adjusted to `adjust_contrast`; the more
  confident result is kept." The *mechanism* is DOCUMENTED; whether it actually rescues
  low-contrast rendered text, and at what contrast floor it stops working, is unmeasured.

### Known failure reports (issue tracker — KNOWN-ISSUE anchors)

- **Rotated text.** [#168](https://github.com/JaidedAI/EasyOCR/issues/168) "cannot read
  image rotated 90 degrees"; the documented workaround is `rotation_info=[90,180,270]`
  (tries each rotation, keeps the best). Anecdotal on a live image, not a swept angle
  curve.
- **Screenshot / rendered-text quality.** [#460](https://github.com/JaidedAI/EasyOCR/issues/460)
  "quality issues" — recognition on app/web screenshots and rendered text is reported as
  weaker; the detector is reported to **miss single letters / very short tokens**.
- **Small text.** `min_size=10` filters text boxes under 10 px by default, so small fonts
  drop out — a documented parameter, but the size threshold at which real rendered text
  is lost is not quantified.
- **CPU speed.** [#1206](https://github.com/JaidedAI/EasyOCR/issues/1206),
  [#108](https://github.com/JaidedAI/EasyOCR/issues/108),
  [#1176](https://github.com/JaidedAI/EasyOCR/issues/1176): CPU inference "slow" (tens of
  seconds on large invoices), model-dependent; anecdotal, host-specific, not a
  distribution on a stated machine.

### Public quantitative sources (must be honest about these)

- Academic benchmarks use EasyOCR as a baseline on **real / script-specific corpora**:
  Devanagari stress-test, low-resource-script LLM-OCR comparisons, historical newspaper
  OCR. These report **aggregate CER/chrF++ on real images for specific scripts** — so
  "EasyOCR has a CER on real corpora" is **DOCUMENTED**, and this pack must NOT present
  synthetic-fixture numbers as beating/replacing them. What none of them provide is a
  **controlled, single-variable CER/WER-vs-degradation curve on rendered Latin text** with
  the exact crash thresholds and the paired resource cost.

### What is NOT measured anywhere (the actual gap)

1. **Clean-text CER/WER floor on rendered printed text**, per font, on ground truth we
   control (not a noisy real corpus) — the best-case baseline and the CER=0 cases.
2. **The font-size collapse threshold**: at what rendered px height does CER jump from ~0
   to catastrophic, tied to the `min_size=10` detector filter (mechanism, not folklore).
3. **The contrast floor + whether `adjust_contrast` rescues it**: sweep foreground→background
   luminance, measure CER, and test the documented double-pass recovery mechanism at the
   floor.
4. **The rotation-angle CER curve + `rotation_info` remediation**, quantified: small angles
   {5…45°} and orthogonal {90,180,270}, default vs `rotation_info` (issue #168's workaround
   turned into a measured recovery number).
5. **Screenshot/UI per-element fidelity**: a rendered multi-element "app screenshot"
   (title, buttons, table cells, mixed sizes/panels) measured for **per-element detection
   recall + CER** (issue #460's "screenshot quality" turned into ground truth).
6. **Resource tradeoff, paired**: exact model download footprint, CPU single-image latency
   **distribution** (p50 + range over ≥15 warm runs, concurrency-noted), peak RSS, and the
   `detail=0/1` + cold(model-load)/warm split — the cost side of the fidelity.

## Testable information-gain hypotheses

- **H1 (clean-text fidelity floor, baseline):** On a fixed canonical string
  (letters+digits+punctuation) rendered black-on-white at a readable size across 7 system
  fonts, measure CER/WER. Prediction from mechanism: near-0 CER on clean high-contrast
  printed Latin; some fonts (Impact/Comic Sans) worse. Establishes the floor + the CER=0
  cases.
- **H2 (adversarial degradation curves — the crash points, CORE):** Sweep, one variable at
  a time on the same string: (a) **font size** {8,10,12,16,20,28,40,64} px; (b) **contrast**
  (foreground gray {0,64,110,150,180,200,220} on white); (c) **rotation** {0,5,10,15,20,30,45}°.
  Measure CER at each step and locate the collapse threshold. Predictions: size collapses
  near the `min_size=10` detector floor; contrast degrades toward the background; rotation
  collapses past a small angle (issue #168). Adversarial core — quantifies documented/known
  weaknesses.
- **H3 (contrast auto-recovery mechanism):** At the low-contrast steps where H2 fails,
  compare default (`contrast_ths=0.1, adjust_contrast=0.5`) vs a tuned `adjust_contrast`,
  and vs a pre-brightened image. Prediction: the documented double-pass helps some but has
  a floor. Mechanism-tied (does the documented rescue actually fire?).
- **H4 (rotation remediation — `rotation_info`):** For the orthogonal rotations {90,180,270}
  and the steep small angles where H2 fails at default, re-run with
  `rotation_info=[90,180,270]` and measure CER recovery. KNOWN-ISSUE (#168) → quantified
  remediation (how much the documented workaround buys, and what it does NOT fix).
- **H5 (screenshot/UI per-element fidelity):** Render one "app screenshot" — a titled panel
  with buttons, labels, and a small data table, each element carrying a distinct known
  string at mixed sizes on mixed-color panels. Match recognized boxes to ground-truth
  element boxes by IoU; report **per-element detection recall** and **per-element CER**.
  Prediction (issue #460): short tokens / single letters / low-contrast-on-color elements
  are the misses.
- **H6 (resource cost, paired with fidelity):** Measure (a) model download footprint
  (`~/.EasyOCR`); (b) CPU single-image latency **distribution** over ≥15 warm runs on the
  canonical image (p50 + IQR, explicitly noted as measured under possible concurrent worker
  load, median-of-repeats to blunt noise); (c) peak RSS in a **fresh** process (instrument
  isolation); (d) `detail=0` vs `detail=1`; (e) cold (first `readtext`, includes model
  load into RAM) vs warm. Prediction: ~100 MB models, sub-second warm on a small clean
  image but seconds on a busy screenshot; cold ≫ warm.

## Test matrix (tied to hypotheses)

| # | Test | Fixture | Measures | H |
|---|---|---|---|---|
| 1 | clean CER/WER, 7 fonts | `font_*` | CER/WER vs GT string | H1 |
| 2 | CER=0 case identification | `font_*` | which fonts read perfectly | H1 |
| 3 | font-size sweep 8→64 px | `size_*` | CER vs px height | H2 |
| 4 | size collapse threshold | `size_*` | px where CER jumps (min_size=10 tie) | H2 |
| 5 | contrast sweep (fg gray → bg) | `contrast_*` | CER vs Weber/Michelson contrast | H2 |
| 6 | contrast collapse floor | `contrast_*` | contrast where CER jumps | H2 |
| 7 | rotation sweep 0→45° | `rot_*` | CER vs angle (default) | H2 |
| 8 | rotation collapse angle | `rot_*` | angle where CER jumps | H2 |
| 9 | contrast recovery: default vs adjust_contrast | `contrast_*` | CER delta at floor | H3 |
| 10 | contrast recovery: pre-brighten | `contrast_*` | CER delta | H3 |
| 11 | orthogonal rotation 90/180/270 default | `rot_ortho_*` | CER (expect collapse) | H4 |
| 12 | orthogonal rotation + rotation_info | `rot_ortho_*` | CER recovery | H4 |
| 13 | steep angle + rotation_info | `rot_*` | CER recovery / residual | H4 |
| 14 | background: solid color panel | `bg_*` | CER on colored bg | H2/H5 |
| 15 | background: gradient | `bg_*` | CER | H2 |
| 16 | background: photo-like texture/noise | `bg_*` | CER | H2 |
| 17 | screenshot per-element detection recall | `screenshot` | boxes matched / GT boxes (IoU) | H5 |
| 18 | screenshot per-element CER | `screenshot` | CER on matched elements | H5 |
| 19 | screenshot short-token / single-letter miss | `screenshot` | which elements dropped | H5 |
| 20 | model download footprint | — | `~/.EasyOCR` size (detector+recognizer) | H6 |
| 21 | CPU warm latency distribution | canonical | p50 + IQR over ≥15 runs | H6 |
| 22 | peak RSS (fresh process) | canonical | max RSS bytes | H6 |
| 23 | detail=0 vs detail=1 latency/output | canonical | delta | H6 |
| 24 | cold vs warm first readtext | canonical | model-load cost | H6 |
| 25 | determinism | canonical | identical text across 3 reps | all |

Ground truth: **we render the images from strings we define**, so the ground truth *is*
those strings — exact, not human-annotated. `build_fixtures.py` writes every PNG **and**
`ground_truth.json` (per-fixture GT string + variation params; for the screenshot, a list
of element units with GT text + pixel bbox) together, so image and label can never drift.
CER/WER are computed by standard Levenshtein (edit distance) in `metrics.py` from the raw
recognized text vs the GT string — **no error-rate constant is written by hand**
(anti-hardcoding gate 3). Recognized boxes are joined in reading order (line-aware: group
into visual lines by vertical overlap, then left-to-right within each line; single-space
join); the tokenizer / normalization口径 (whitespace-collapse, case-sensitive)
is declared in the metrics script.

## Harness design (Python render + Python OCR runner + Python metrics, anti-hardcoding split)

- `tests/build_fixtures.py` — single source of truth: renders `tests/fixtures/*.png` with
  Pillow **and** writes `tests/fixtures/ground_truth.json` (GT string + params per fixture;
  element list for the screenshot). Deterministic (fixed text, fixed layout).
- `tests/run_easyocr.py` — one `easyocr.Reader(['en'], gpu=False, verbose=False)`; per
  fixture calls `readtext()` (incl. the `rotation_info` / `adjust_contrast` / `detail`
  variants where a hypothesis needs them), dumps **raw** results (bbox + text + confidence),
  per-image timing, and resource stats → `artifacts/raw/easyocr_raw.json`. Latency
  distribution + peak RSS collected here; **no CER is computed here.**
- `tests/metrics.py` — reads `ground_truth.json` + the raw dump, computes **CER/WER**
  (Levenshtein) per fixture, the size/contrast/rotation **collapse thresholds**, the
  screenshot **IoU-matched per-element recall + CER**, and the recovery deltas → 
  `artifacts/raw/easyocr_metrics.json`. **Every error rate is computed from raw text vs
  labels — no metric constant is hand-written** (闸门 3).
- `_redact`: `$HOME`→`~` **and** `$TMPDIR` / `/var/folders` temp paths → `<TMP>` before any
  JSON is written (the selenium-pack lesson).

## Information-gain verdict: PROCEED

Not parked. Public sources give the architecture, the parameter defaults, the "CPU is
slower" warning, qualitative screenshot/rotation/small-text complaints, and aggregate
real-corpus CER for specific scripts — all treated as **DOCUMENTED** / **KNOWN-ISSUE**.
What no public source provides, and what is measurable here on a credential-free local
fixture set: (1) the **clean-text CER/WER floor** per font on exact ground truth; (2) the
**font-size / contrast / rotation collapse thresholds** tied to `min_size` and the CRAFT
detector; (3) whether the documented **`adjust_contrast` double-pass** actually rescues
low-contrast text and its floor; (4) the **`rotation_info` remediation** quantified against
the #168 failure; (5) **screenshot per-element** detection recall + CER (issue #460 turned
into ground truth); (6) the paired **resource** distribution (footprint, CPU latency, peak
RSS). Each is a quantification or constructed demonstration behind documented/known
behavior — the EXCLUSIVE-eligible core — while existence/architecture/parameter claims stay
DOCUMENTED and the rotation/screenshot/CPU-speed complaints stay KNOWN-ISSUE with a cited
issue.

## Boundary / compliance notes

- Evidence phase only; no article, no publish, no git.
- All tests on **local, self-rendered fixtures** (no network at runtime except the one-time
  model download, which is measured then cached). No third-party host, no anti-bot, no
  auth, no rate abuse. EasyOCR is an OCR library, framed as "text fidelity on controlled
  ground truth."
- No credentials anywhere. `_redact` scrubs `$HOME`→`~` and `$TMPDIR`/`/var/folders`.
- Record exact `easyocr` + `torch` + `torchvision` + `opencv` + `numpy` + `Pillow` +
  Python versions and the model file names/sizes in metadata; fixtures + scripts committed;
  `.venv/`, torch caches, `~/.EasyOCR/` models, and any PNG > 1 MB gitignored / never
  shipped.
- Timing is host-specific and measured **under possible concurrent worker load** (parallel
  packs) — reported as p50 + IQR with median-of-repeats, explicitly scoped, never as a
  universal number.
- Determinism asserted (3 reps identical) before any single-run fidelity number is used.
- Novelty honesty: architecture (CRAFT+CRNN), parameter defaults, `contrast_ths` /
  `rotation_info` mechanisms, and "CPU slower than GPU" are **DOCUMENTED**; the
  rotation/screenshot/small-text/CPU-speed complaints are **KNOWN-ISSUE**
  ([#168]/[#460]/[#1206]). Only the controlled CER/WER curves, the exact collapse
  thresholds, the contrast-recovery floor, the `rotation_info` recovery number, the
  screenshot per-element table, and the paired resource distribution are candidates for
  EXCLUSIVE.

[#168]: https://github.com/JaidedAI/EasyOCR/issues/168
[#460]: https://github.com/JaidedAI/EasyOCR/issues/460
[#108]: https://github.com/JaidedAI/EasyOCR/issues/108
[#1176]: https://github.com/JaidedAI/EasyOCR/issues/1176
[#1206]: https://github.com/JaidedAI/EasyOCR/issues/1206
