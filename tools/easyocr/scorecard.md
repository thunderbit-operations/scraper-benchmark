# easyocr — provisional scorecard

**Provisional.** Based only on the completed material tests (see `research-materials.md`).
Not a final benchmark and not a cross-tool ranking (no other OCR pack exists in the repo
yet). Weights are pack-local and pre-registered here; scores are evidence-anchored, each
citing a run. All numbers are on controlled synthetic **rendered Latin** fixtures (easyocr
1.7.2 + torch 2.13.0, **CPU**, macOS arm64, `english_g2` recognizer), and are NOT a
replacement for the public academic CER figures on real / non-Latin corpora.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 8 | 7 | `uv pip install easyocr` pulls torch (~2 GB); first `readtext` auto-downloads 94 MB of models; then `Reader(['en']).readtext()` works |
| Clean-text fidelity floor | 14 | 13 | mean CER **0.071** (case-sensitive) / **0.024** (case-insensitive); CER=0 achievable (16 px; georgia case-insensitive); residual = case-flip + punctuation (`H1_font_floor`) |
| Small-font robustness | 10 | 6 | hard collapse under `min_size=10`: CER **0.77 @8 px**, clean by 12 px, CER=0 @16 px (`H2_size_sweep`) |
| Contrast robustness | 10 | 9 | no collapse to Weber **0.14** on clean text; `adjust_contrast` rescue unneeded — scoped to noise-free (`H2_contrast_sweep`) |
| Rotation robustness | 10 | 5 | skew ≤10° only, collapse ≥20°; `rotation_info` asymmetric — recovers 270° (0.10), fails 90° (0.92) (`H2_H4_rotation`) |
| Background robustness | 6 | 6 | solid color / gradient / gaussian-noise all clean; noise background = CER 0 (`backgrounds`) |
| Screenshot / UI fidelity | 12 | 9 | detection recall **16/19**; drops single-letter "A" + 2-char "Q1"/"Q2"; matched CER 0.027; systematic `$→S` (`H5_screenshot`) |
| Resource footprint | 8 | 6 | 94 MB weights (79 detector + 14 recognizer) + ~1 GB RSS; torch ~2 GB dependency (`resource`) |
| CPU latency | 8 | 6 | warm p50 **~0.062 s** on a clean 48-char line; cold init ~1.5 s; host-specific, single machine (`resource`) |
| Determinism / reproducibility | 8 | 8 | 3-rep identical + all fidelity numbers identical across 2 independent process runs (`resource.determinism`) |
| Anti-hardcoding / method rigor | 6 | 6 | raw/metrics split; CER computed from raw vs rendered GT; a reading-order harness bug was caught and fixed before drawing conclusions |
| **Total** | **100** | **81** | provisional research-material score only, not a final rating |

Scoring notes:

- **Clean-text fidelity floor (13/14):** near-full because character recall on clean
  rendered Latin is essentially perfect — a **CER = 0** read exists (16 px), and the mean
  residual (0.071) is dominated by a specific **case-flip** (`vow→VOW`) plus punctuation,
  which case-insensitive CER (0.024) confirms. Docked one point only because it never
  reaches a clean-case CER=0 *floor* across all fonts (the case-flip is consistent), and
  `$→S` recurs on symbols.
- **Small-font robustness (6/10):** the collapse under the documented `min_size=10` filter
  is real and abrupt (CER 0.77 at 8 px). Not lower because it is **fully recovered by
  12 px** and the mechanism is documented and predictable, not a mystery failure — but a
  10 px floor is a genuine limit for dense/small UI text.
- **Contrast robustness (9/10):** strong, evidence-backed — no collapse to Weber 0.14 on
  clean text — but held one point because it is **scoped to noise-free** rendered contrast;
  the harder real case (low contrast **+** noise/JPEG) is a Gap, so this is not a blanket
  "great in low light."
- **Rotation robustness (5/10):** the weakest fidelity axis. Skew tolerance is only ~10°,
  collapse by 20°, and the documented `rotation_info` workaround is **asymmetric** — it
  rescues one orthogonal orientation (270°) but makes another (90°) worse and does nothing
  for skew. A user who assumes `rotation_info` "fixes rotation" will be wrong for half the
  cases. Not lower because ≤10° skew and the 270° recovery are genuinely clean.
- **Screenshot / UI fidelity (9/12):** high because matched-element text is near-perfect
  (mean CER 0.027, 13/16 exact) — titles, labels, buttons, comma-grouped numbers all CER 0.
  Docked for the **detector dropping isolated short tokens** (single letter + two 2-char
  cells → recall 0.842) and the systematic `$→S` symbol misread, both of which matter for
  data-table / badge screenshots.
- **Resource footprint (6/8) & CPU latency (6/8):** middling by nature — ~94 MB of weights
  and ~1 GB resident memory is a real deployment cost, and the torch dependency is ~2 GB;
  warm CPU latency on a *clean single line* is fast (~0.062 s) but this is the easy case and
  the number is host-specific and concurrency-noted (single machine, no GPU/large-document
  figure). Scored on the measured easy case, not extrapolated.
- **Determinism (8/8):** full — outputs are deterministic in-process and **every fidelity
  headline is byte-identical across two independent process runs**; only timing varies.
- **Anti-hardcoding / method rigor (6/6):** full — the runner returns only raw boxes and
  timings; all error rates are computed in `metrics.py` from raw text vs the rendered ground
  truth; and a reading-order harness bug (which had inflated clean-text CER to 0.375) was
  caught via a raw-prediction sanity check and fixed before any conclusion was drawn.
- Scores reflect **OCR fidelity + resource cost on controlled rendered ground truth** only;
  EasyOCR is not scored on real-photo accuracy, non-Latin scripts, handwriting, or GPU
  throughput (all deferred / cited).
