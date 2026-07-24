# easyocr — evidence pack

Independent, reproducible tests for **`easyocr`** (v1.7.2), JaidedAI's ready-to-use OCR — a
**CRAFT** text detector + **CRNN** recognizer (ResNet → BiLSTM → CTC greedy) on PyTorch,
run **CPU-only**. Part of the Thunderbit open-source scraping-tool benchmark. Every number
in `research-materials.md` traces to a script here and a JSON artifact under
`artifacts/raw/`.

Tested (as-of 2026-07-24): easyocr **1.7.2**, torch **2.13.0**, torchvision **0.28.0**,
opencv **5.0.0**, numpy **2.5.1**, Pillow **12.3.0**, Python **3.12.13**; `english_g2`
recognizer; macOS arm64, CPU.

## Headline

Focus (queue #16): **image/screenshot text fidelity and resource tradeoffs**, measured as
CER/WER against **exact ground truth** (images are rendered from strings we define). On 36
synthetic fixtures, **EasyOCR's failure surface is geometry and isolated short tokens, not
contrast or noise**. On clean rendered Latin, **character recall is essentially perfect** —
a full **CER = 0** read occurs at 16 px, and the mean residual CER (0.071 case-sensitive /
**0.024** case-insensitive) is a **case-flip** (`vow→VOW`) plus punctuation, not lost
characters. It stays in that clean band across **all 7 fonts**, **down to Weber contrast
0.14**, and on solid-color / gradient / gaussian-noise backgrounds (noise bg = CER 0) — so
the documented `adjust_contrast` low-contrast rescue is not even needed on clean text
(prediction falsified, honest negative, scoped to noise-free).

Where it **collapses** is geometric: a **hard small-font floor** at the documented
`min_size=10` (CER **0.77 at 8 px**, recovered by 12 px), and **rotation** — skew tolerance
is only **~10°** (collapse ≥ 20°), and the documented `rotation_info=[90,180,270]` workaround
([#168]) is an **asymmetric** fix: it recovers a 270°-rotated image (CER 0.83→**0.10**) but
only partially 180° (→0.67) and **fails 90°** (→0.92, mirror-text). On a rendered
**screenshot**, detection recall is **16/19** — the detector drops the single-letter badge
"A" and the 2-char cells "Q1"/"Q2" (but keeps "Q3"), the ground-truthed form of issue
[#460] — while matched text is near-perfect (mean CER 0.027, 13/16 exact) except a
systematic **`"$"→"S"`** misread. Resource cost: **93.7 MB** of weights (79.3 detector +
14.4 recognizer), **~1 GB** peak RSS, cold init ~1.5 s, and warm **~0.062 s** per clean line
on CPU (host-specific; `detail=0` does not speed recognition). All fidelity numbers are
**identical across two independent process runs**.

## Reproduce

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python easyocr pillow   # torch ~2 GB

.venv/bin/python tests/build_fixtures.py   # 1) render fixtures + ground_truth.json
.venv/bin/python tests/run_easyocr.py      # 2) raw recognition + timing + resource
                                           #    (first run auto-downloads 94 MB of models)
.venv/bin/python tests/metrics.py          # 3) CER/WER/recall/thresholds, computed
```

Requires Python 3.12 + `uv`. No CUDA needed (CPU; slow but fine). tesseract/poppler are
**not** required — EasyOCR carries its own torch models. Outputs land in
`artifacts/raw/*.json`. Fixtures are local (no network at runtime except the one-time model
download). **All CER/WER is computed in `metrics.py` from raw recognized text vs the
rendered ground truth** — no error-rate constant is written by hand (anti-hardcoding).

## What the pack establishes

- **Clean-text floor (H1):** mean CER 0.071 / 0.024 ci across 7 fonts; residual is
  case-flip + punctuation; character recall ~perfect.
- **Small-font collapse (H2):** CER 0.77 @8 px → 0 @16 px; the `min_size=10` filter is the
  mechanism; sweet spot 12–28 px.
- **Contrast robustness (H2/H3):** no collapse to Weber 0.14 on clean text; `adjust_contrast`
  unneeded — scoped to noise-free.
- **Rotation (H2/H4):** skew ≤10°, collapse ≥20°; `rotation_info` asymmetric (270 ok / 180
  partial / 90 fails; nothing for skew).
- **Backgrounds:** color / gradient / gaussian-noise all clean (noise = CER 0).
- **Screenshot (H5):** detection recall 16/19; drops single-letter + 2-char tokens; matched
  CER 0.027; `$→S`.
- **Resource (H6):** 94 MB weights, ~1 GB RSS, cold ~1.5 s, warm p50 ~0.062 s/clean line;
  `detail=0` ≈ `detail=1`.
- **Determinism:** 3-rep identical; all fidelity numbers identical across 2 independent runs.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue scan, hypotheses, matrix,
  PROCEED verdict; treats architecture/params and public real-corpus CER as DOCUMENTED).
- `research-materials.md` — full evidence, per-finding confidence, novelty table, Part-6
  self-check (incl. the reading-order harness bug caught and fixed).
- `scorecard.md` — provisional dimension scores (81/100), evidence-anchored.
- `metadata-snapshot.md` — versions, model files/sizes, algorithm constants, exact commands,
  reproducibility.
- `tests/` — `build_fixtures.py`, `run_easyocr.py`, `metrics.py`, and `fixtures/` (PNGs +
  `ground_truth.json`).
- `artifacts/raw/` — raw recognition + computed metrics JSON.

Evidence phase only: no article, no publishing. `validation.md` (independent audit) is
produced separately and is not part of this worker's deliverable. All numbers are
controlled synthetic-fixture measurements on **English rendered Latin, CPU, macOS arm64**,
and do **not** replace the public academic CER figures on real / non-Latin corpora, which
are cited as the authoritative real-world anchors.

[#168]: https://github.com/JaidedAI/EasyOCR/issues/168
[#460]: https://github.com/JaidedAI/EasyOCR/issues/460
