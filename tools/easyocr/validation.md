# easyocr — Independent Audit (validation)

**VERDICT: PASS WITH FIXES** (one cosmetic method-description drift in `metrics.py` /
`easyocr_metrics.json` flagged for the worker, plus two cosmetic narrative-hygiene notes.
No headline / score / ground-truth / evidence-integrity fix required. Nothing auto-edited;
the pack was restored byte-identical after my runs.)

Every headline was reproduced independently against the pack's own harness using the shipped
`.venv` (easyocr **1.7.2** + torch **2.13.0** + torchvision **0.28.0** + opencv **5.0.0** +
numpy **2.5.1** + Pillow **12.3.0**, Python **3.12.13**, CPU, macOS arm64; models in
`~/.EasyOCR`, 83,152,330 + 15,143,997 = 98,296,327 bytes = 93.74 MiB — matches
`metadata-snapshot.md` exactly). I re-ran `build_fixtures.py` → `run_easyocr.py` →
`metrics.py`. The deterministic fixture rebuild is **byte-identical** to the committed
copies (35 PNG + screenshot + `ground_truth.json`, all shas match), the full independent
OCR re-run reproduced **every** raw prediction (0 text mismatches over 35 fixtures; 0
bbox+text mismatches over all 60 fixture/variant box-sets — the CRAFT detector is
deterministic across independent processes), and a metrics recompute on the committed raw
came out **byte-identical to `easyocr_metrics.json`** (modulo the `computed_at` timestamp),
proving no error rate is hardcoded. The pack's artifact JSONs were restored to their
committed sha after my runs; the pyc cache I generated was removed; `.venv` (862 MB) and
`~/.EasyOCR` (94 MB) were never touched or copied.

---

## Fixture ground-truth fairness — the audit core: FAIR (no OCR-friendliness bias)

The CER/WER numbers rest entirely on `ground_truth.json`. Two facts make them auditable:

1. **Labels are code-generated, not annotated.** `build_fixtures.py` renders every PNG from
   the string `"Sphinx of black quartz, judge my vow. 1234567890"` and writes the GT in the
   same pass — the GT *is* the rendered string, so image and label can never drift. My
   deterministic rebuild is byte-identical to the committed fixtures; auditing the labels =
   auditing the generator, which I read line by line.
2. **The rendering is not rigged for an easy (or a hard) read.** I eyeballed `screenshot.png`,
   `size_08`, `size_16`, `contrast_220`, `rot_ortho_270`: each contains exactly its GT text.
   The font set (Arial/Times/Courier/Georgia/Verdana/**Comic Sans**/**Impact**) is a neutral-
   to-adversarial spread — it *includes* the hard fonts (Impact, Comic Sans, monospace
   Courier, which scored worst at 0.1042), not a cherry-picked OCR-friendly subset. The
   `contrast_220` fixture is genuinely faint gray-220-on-white (Weber 0.14), `size_08` is
   genuinely 8 px, and the dashboard's missed tokens ("A", "Q1", "Q2") are genuinely the
   small isolated ones while "Q3" is genuinely present — the difficulty is real, not staged.
   **Conclusion: the ground truth is exact and the fixtures are fair.**

---

## Independent reproduction (my re-runs)

### Fixture determinism — CONSISTENT
`build_fixtures.py` rebuild: 36 PNG + `ground_truth.json` **byte-identical** to committed
(per-file sha compare, zero mismatches). Ground truth is code-generated, not hand-tuned.

### Raw-prediction reproduction — CONSISTENT
Full `run_easyocr.py` re-run: **0/35** single-line text mismatches, **0/60** full box
(bbox+text) mismatches vs the committed raw, screenshot boxes identical, `determinism.
all_identical=true`, model bytes identical. Only timing varies (my warm mid-sample ~0.059 s
vs committed p50 0.0616 s — within the stated IQR). The committed raw predictions are
genuine, reproducible EasyOCR output.

### Metrics are computed, not hardcoded — CONSISTENT
`metrics.py` on committed raw → recomputed `easyocr_metrics.json` **byte-identical** to
committed (modulo `computed_at`). The only numeric literals in `metrics.py` are the declared
thresholds `COLLAPSE_CER=0.30 / CLEAN_CER=0.05 / IOU_MATCH=0.30` (method params, documented
in the `method` block and 口径) and the `0.5*smaller_h` line-grouping overlap — no metric
result is written by hand. **Anti-hardcoding lint: PASS.**

### Headlines verified against raw predictions
- **H1 clean floor** — mean CER **0.0714** / **0.0238** ci; `perfect_fonts_ci=['georgia']`;
  per-font CERs match the table. Residual is the `vow→VOW` case-flip + period→`:`/`_`,
  confirmed in the raw strings. **CONSISTENT.**
- **H2 size** — CER **0.7708 @8 px** (n_boxes 2), **0.0 @16 px**, first_collapse=8 px,
  clean_values=[12,16,20,28]. **CONSISTENT.**
- **H2 contrast FALSIFIED (honest negative)** — verified *not powdered*: the
  `adjust_contrast_hi` CER column is **identical to default** at every step (0.0833→0.0417),
  first_collapse=`None`. The rescue "makes no difference because the default already
  succeeds" is literally true in the artifact, not spin. **CONSISTENT.**
- **rotation asymmetry (the reverse-intuitive headline)** — reproduced per-angle from the
  **raw predictions**, not a metrics artifact:
  | angle | default | rotation_info | raw rotation_info prediction |
  |---:|---:|---:|---|
  | 90° | 0.8125 | **0.9167 (worse)** | `1234567890 MOA my judge 'zuuenb black of Sphinx` — reversed + **mirror** (`VOW→MOA`, `quartz→zuuenb`) |
  | 180° | 0.8542 | 0.6667 (partial) | `1234567890 1 Sphinx of black quartz, judge` — **`my vow.` dropped** |
  | 270° | 0.8333 | **0.1042 (recovers)** | `Sphinx of black quartz judge my MOA 1234567890` |
  The 270-recovers / 90-worsens / 180-partial asymmetry is genuine EasyOCR output. **CONSISTENT.**
- **H5 screenshot** — recall **16/19=0.8421**, missed=`badge(A) / cell_q1(Q1) / cell_q2(Q2)`,
  **Q3 kept**, mean matched CER **0.0268**, 13/16 exact, systematic `$→S` on `$57,912 /
  $18,330 / $25,178` (`$12,004` correct). All confirmed per-element. **CONSISTENT.**
- **H6 resource** — 93.7 MiB, cold 1.7163 s, warm p50 0.0616 s, RSS 984.5 MiB, det identical.
  **CONSISTENT.**

---

## D3 — the join fix: FAIR, and the "harness bug" narrative is TRUE

The highest-risk claim: the worker says a naive y-then-x join inflated clean CER to ~0.375
and was replaced by a line-aware (vertical-overlap) join. I verified both that the bug was
real **and** that the fix does not over-merge to mask errors:

- **The bug is real.** On `font_arial` the CRAFT detector splits the single line into a
  words-box (y-center 31.0) + a digits-box (y-center **29.0**); a naive y-then-x sort puts
  the digits **first** → CER **0.5417**, while the line-aware join orders them correctly →
  **0.0833**. I reproduced this on every multi-box clean fixture (naive is worse by 0.4–0.8
  CER almost everywhere). The naive join would have **unfairly penalized** EasyOCR; the fix
  makes the measurement fairer, not rosier.
- **It cannot mask an OCR error.** `join_boxes` only *reorders* boxes — it adds/removes no
  characters. Every misread survives the join (`VOW`, `$→S`, mirror-text `MOA/zuuenb` all
  persist), so the fix cannot turn a wrong read into a right one.
- **It cannot over-merge separate lines.** All 35 join-using fixtures have a single-line GT,
  so grouping fragments onto one line is correct by construction; the multi-line screenshot
  uses per-element **IoU matching**, not `join_boxes`, so recall/CER there are immune to the
  join.
- **The collapse headlines are robust to the join choice.** For the collapsed cases
  (rot_ortho_90/270, size_08, rot ≥20°) line-aware CER ≈ naive CER — the fix does not
  manufacture a false "clean" or false "collapse". **D3: PASS.**

---

## Four-class leak audit (Part 6)

- **D1 self-contradicting winner: PASS.** Single-tool pack, no cross-tool "wins." Scorecard
  weights sum to **100**, scores to **81** (re-added). The headline pairs "essentially
  perfect on clean Latin" with the geometry/short-token collapses in the same breath;
  internal default-vs-variant comparisons report the side where the variant is **worse**
  (rotation_info 90° 0.81→0.92, 10° skew 0.021→0.083). No over-rosy sentence is contradicted
  by the 8 px 0.77 / 90° fail / screenshot drops.
- **D2 blind instrument: PASS.** The metric registers CER=0 reads (16 px, noise bg) **and**
  CER 0.77–0.92 collapses, and the outcome **flips with the swept variable** (size/angle) —
  positive+negative control, exercised in my re-run. GT is the exact rendered string, so a
  "correct" read requires the real characters. Peak RSS is measured in a fresh subprocess
  (isolation).
- **D3 mis-attribution: PASS.** The caught reading-order trap is real and the fix is fair
  (section above). Rotation asymmetry and screenshot misses were verified against raw
  strings, and the rotation *cause* is explicitly labeled a **hypothesis** (Pillow-CCW vs
  retry), not asserted.
- **D4 claim-without-artifact: PASS.** Spot-checked 5 headlines to fields:
  mean CER 0.071/0.024 → `H1_font_floor.mean_cer/mean_cer_ci`; 0.77@8px →
  `H2_size_sweep.steps`; 270° 0.83→0.10 → `H2_H4_rotation.orthogonal_steps`; recall 16/19 +
  `$→S` → `H5_screenshot.elements`; warm p50 / RSS → `resource`. All resolve. The "tens of
  seconds on CPU" figure is correctly reported as **KNOWN-ISSUE, NOT reproduced**.

---

## Novelty classification (three-gate) — Gate-1 CLEAN

Disciplined; no EXCLUSIVE sits on a documented qualitative fact.
- CRAFT+CRNN architecture, `readtext` params, `min_size`/`contrast_ths`/`rotation_info`
  mechanisms, "CPU slower than GPU", real/non-Latin aggregate CER → **DOCUMENTED**
  (README/jaided.ai/academic). Correct — none claimed as this pack's.
- Per-font clean CER floor, exact size-collapse px boundary + CER=0 point, scoped
  contrast-robustness negative, **asymmetric** `rotation_info` recovery, screenshot per-
  element recall+CER+`$→S`, paired resource distribution → **EXCLUSIVE**, each scoped to a
  quantification/measurement, none to a qualitative discovery.
- Small-text / rotation / screenshot / CPU-slow complaints → **KNOWN-ISSUE** with cited
  issues (#168 / #460 / #1206 / #108) + EXCLUSIVE only on the quantified boundary. The
  "tens of seconds" scalar → **KNOWN-ISSUE, NOT reproduced.** Correctly credits prior art;
  EXCLUSIVE is confined to numbers. **Gate-1 CLEAN.**

---

## Secret / abspath / cleanliness scan: CLEAN

- **Credentials:** no `sk-`/`ghp_`/`AKIA`/`Bearer`/private-key/`api_key=` patterns in any
  publish-bound file (`*.md`, `tests/*.py`, `tests/fixtures/*.{png,json}`,
  `artifacts/raw/*.json`, `.gitignore`).
- **Absolute paths:** no `/Users/richardli` in any publish-bound file. The only path-like
  string in the JSON artifacts is `~/.EasyOCR/model` (correctly `$HOME`→`~` redacted). The
  `/var/folders` strings in the md are **prose describing the redaction mechanism**, not
  leaked paths. `/System/Library/Fonts/...` appears **only** in `build_fixtures.py` (needed
  to render; system font paths, not user-identifying; never written to any JSON).
- **`.venv` (862 MB) / `~/.EasyOCR` (94 MB) / `*.pth` / `__pycache__` / `artifacts/logs/`:**
  all covered by `.gitignore`; no file > 1 MB exists outside `.venv`. The pack is not yet a
  git repo (like the readability pack), so nothing is committed; on publish the `.gitignore`
  keeps the models/venv/logs out.
- **Self-praise lint:** `grep -iE 'honest|independent|strongest|trustworthy'` surfaces only
  the rule-required "**honest negative**" transparency labels (permitted by methodology
  Part 4/6) and method descriptors ("Independent, reproducible tests", "Reproducibility
  notes (honest)"). **No quality adjective is awarded to EasyOCR.** Neutralize the
  descriptors in the final blog draft; not an evidence-pack blocker.

---

## Required fixes before publishing

**None at headline / score / ground-truth / evidence-integrity level.** Three cosmetic
notes, flagged not auto-edited (matching the readability auditor's posture — I do not want to
half-edit source out of sync with the committed artifact).

### F1 — COSMETIC (worker): `metrics.py` / `easyocr_metrics.json` join description is stale-wrong
`metrics.py` line 7 (module docstring) and line 338 (the `method.join` string written into
`easyocr_metrics.json`) both say **"boxes sorted by bbox y-center then x-center,
single-space"** — the **old naive** join the pack explicitly abandoned. The actual
`join_boxes` implementation (and its own function docstring, line 87) is **line-aware
vertical-overlap grouping**, and the prose (`research-materials.md` 口径, README, scorecard)
correctly says line-aware. A reader auditing the method from the artifact would be told the
buggy method was used. **No number is affected** (the real join is line-aware; all metrics
recompute correctly). Fix: update both strings to the line-aware description and re-run
`metrics.py` so the JSON `method.join` field syncs.

### F2 — COSMETIC (worker): `pretest-information-gain.md` line 171 also states the naive join
"…joined in reading order (sort by y then x, single-space join)". This is a design doc
written pre-fix, but it is stale vs the shipped harness. Reconcile or annotate.

### F3 — COSMETIC (final-draft, not a blocker): neutralize self-descriptors
"Independent, reproducible tests" (README l.3), "Reproducibility notes (honest)"
(`metadata-snapshot.md` l.89) — neutral phrasing in the final blog draft per Part 4. The
"honest negative" labels are rule-required and should stay.

_Note: the on-disk `artifacts/logs/run.log` (gitignored, will not ship) contains 2 local
abspaths; harmless as long as `.gitignore` is respected on publish._

---

## Residual gaps the writer must not overclaim (the pack lists these; keep them)
1. **All numbers are controlled synthetic rendered Latin, single machine / version, CPU.**
   The public academic real/non-Latin CER figures are the authoritative real-world anchors,
   cited not reproduced. Keep it framed that way.
2. **Contrast robustness is scoped to noise-free.** Low-contrast **+** noise/JPEG is a Gap;
   never present Weber-0.14 robustness as blanket low-light strength (the pack does not).
3. **Rotation cause is a hypothesis; timing is host-specific and not a cross-machine/GPU/
   large-document distribution; handwriting and 80+ languages untested.** Keep as stated.

---

_Audit re-ran the full pipeline (`build_fixtures` → `run_easyocr` → `metrics`) in the pack's
own layout on 2026-07-24 using the shipped `.venv`; fixtures rebuilt byte-identical to the
committed ground truth, all raw predictions reproduced with zero mismatches, and the computed
metrics reproduced byte-identical to `easyocr_metrics.json`. The pack's artifacts were
restored to their committed sha afterward and the generated pyc cache removed; `.venv` and
model cache untouched. No git repo under the pack, so nothing is committed._

**Net status: PASS WITH FIXES.** All headlines reproduced; the fixture ground truth is
code-generated, exact, and fairly rendered (hard fonts included, difficulty not staged); the
H2-contrast falsification is a genuine un-powdered honest negative; the reverse-intuitive
rotation asymmetry is real EasyOCR output verified per-angle in the raw predictions; the D3
line-aware join fix is fair (corrects a real harness artifact, reorders only, cannot mask
errors or over-merge, and leaves the collapse headlines invariant); D1–D4 clean; novelty
Gate-1 clean (EXCLUSIVE confined to quantification); anti-hardcoding, secret, and abspath
scans clean; models/venv not shippable. The three required changes are **cosmetic** (a stale
join-method description in `metrics.py`/`easyocr_metrics.json`, a matching stale line in the
pretest, and two self-descriptors for the final draft) — none touches a number, score, or
label. The **81/100** is the honest arithmetic of evidence-anchored dimension scores.
