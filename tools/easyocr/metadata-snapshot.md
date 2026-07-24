# easyocr — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) |
| Stars | **29,812** |
| Open issues | **528** |
| License | **Apache-2.0** |
| Default branch | **master** |
| Last push | **2025-12-05T12:23:12Z** |
| Latest GitHub Release | **v1.7.2** (published **2024-09-24**) |
| PyPI `latest` | **1.7.2** |
| Version tested | **1.7.2** (`uv pip install easyocr` resolved 1.7.2) |

Environment actually used (from the run meta / host):

| Item | Value |
|---|---|
| easyocr | **1.7.2** |
| torch | **2.13.0** |
| torchvision | **0.28.0** |
| opencv (cv2) | **5.0.0** |
| numpy | **2.5.1** |
| Pillow | **12.3.0** |
| Python | **3.12.13** (uv venv) |
| Platform | **macOS 26.5.2 arm64** (`macOS-26.5.2-arm64-arm-64bit`) |
| Compute | **CPU** (`gpu=False`); `cuda_available=False`, `mps_available=True` but EasyOCR uses CPU on non-CUDA by default |
| `torch.get_num_threads()` | **8** |
| Test date | **2026-07-24** |

## Models auto-downloaded (the "resource" side)

First `readtext()` downloads the models into `~/.EasyOCR/model/` (one-time; then cached).
Measured on this host:

| File | Role | Bytes | MiB |
|---|---|---:|---:|
| `craft_mlt_25k.pth` | CRAFT text **detector** | 83,152,330 | 79.30 |
| `english_g2.pth` | CRNN **recognizer** (`recog_network='standard'`, gen-2, English) | 15,143,997 | 14.44 |
| **total** | | **98,296,327** | **93.74** |

(torch itself is a ~2 GB install dependency, separate from these model weights; gitignored,
never shipped.)

## Architecture + algorithm facts read from the library (DOCUMENTED)

- **Two stages**: **CRAFT** detector locates text boxes → **CRNN** recognizer reads each
  box. CRNN = ResNet/VGG feature extraction → BiLSTM → **CTC greedy** decode
  (README-documented).
- On CPU the recognizer runs **dynamically quantized (int8)** — the run emits
  `torch.quantize_per_tensor(...)` from EasyOCR's own `quantize=True` default path; noted
  because it affects both the memory footprint and the CPU latency.
- **`readtext()` defaults** (jaided.ai docs, used here unless a hypothesis overrides):
  `detail=1`, `paragraph=False`, `decoder='greedy'`, `beamWidth=5`, `batch_size=1`,
  `min_size=10`, `rotation_info=None`, `contrast_ths=0.1`, `adjust_contrast=0.5`,
  `text_threshold=0.7`, `low_text=0.4`, `link_threshold=0.4`, `mag_ratio=1`,
  `canvas_size=2560`.
- **`min_size=10`** filters detected boxes shorter than 10 px — the mechanism behind the
  small-font collapse (H2).
- **`contrast_ths=0.1` / `adjust_contrast=0.5`**: a box whose contrast is below
  `contrast_ths` is recognized **twice** (original + contrast-boosted to `adjust_contrast`),
  keeping the more confident result — the documented low-contrast rescue tested in H3.
- **`rotation_info`** (default `None`): a list of angles to also try, keeping the best —
  the documented rotation workaround ([#168]) tested in H4.

## Exact commands run

Everything is offline at runtime except the one-time model download (measured, then cached).

```bash
cd tools/easyocr

# 0) deps — torch ~2 GB + easyocr; versions pinned by the resolver, recorded above
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python easyocr pillow

# 1) render the annotated fixtures + ground truth (single source of truth)
.venv/bin/python tests/build_fixtures.py     # -> tests/fixtures/*.png + ground_truth.json

# 2) raw EasyOCR recognition + timing + resource (NO metrics); first run downloads models
.venv/bin/python tests/run_easyocr.py        # -> artifacts/raw/easyocr_raw.json

# 3) compute CER/WER/recall/thresholds from raw text vs labels (anti-hardcoding)
.venv/bin/python tests/metrics.py            # -> artifacts/raw/easyocr_metrics.json
```

## Reproducibility notes (honest)

- **Ground truth is generated with the images.** `build_fixtures.py` renders every PNG with
  Pillow **and** writes `ground_truth.json` in the same pass; because the images are
  rendered from strings we define, the ground truth **is** those strings — exact, not
  human-annotated, so CER/WER is never a subjective judgment.
- **Anti-hardcoding split.** `run_easyocr.py` returns only raw boxes (`bbox + text + conf`)
  + timings + resource stats; **all CER/WER, collapse thresholds, and screenshot
  recall/IoU are computed in `metrics.py`** from that raw text vs the labels. No error-rate
  constant is written by hand.
- **口径.** Recognized boxes are joined in **line-aware reading order** (group by vertical
  overlap, then left-to-right within a line — a naive y-then-x sort scrambles a single
  visual line the detector split into two boxes, which is a *harness* concern, not OCR
  fidelity). Normalization: collapse whitespace, strip, **case-sensitive**; a
  case-insensitive CER is reported alongside because the dominant clean-text error is a
  case-flip.
- **Determinism / cross-run stability.** Recognition is deterministic — 3 reps identical
  in-process (`determinism.all_identical=true`), and **every CER/recall headline number is
  byte-identical across two fully independent process runs**. Only host-specific **timing**
  varies run-to-run (reported as ranges).
- **Timing is host-specific and measured under possible concurrent worker load** (parallel
  packs). Reported as a 20-sample warm distribution (p25/p50/p75) + range across two runs,
  **never** as a universal benchmark. Cross-machine / GPU timing is a Gap.
- **Peak RSS is measured in a FRESH subprocess** (instrument isolation — the high-water
  mark is not shared with the main run's prior load).
- **Redaction.** `$HOME`→`~` and `$TMPDIR` / `/var/folders` temp paths → `<TMP>` in every
  written JSON.
- **`.venv/`, torch caches, and `~/.EasyOCR/` models are NOT shipped** (gitignored);
  `uv pip install easyocr` + the one-time auto-download reproduce them. Fixtures (all
  < 130 KB) and scripts are committed.
- **Scope.** English `english_g2` recognizer only, CPU only, macOS arm64, synthetic
  rendered Latin text. Not a handwriting, multilingual, or real-photo-corpus benchmark; the
  public academic CER figures on real/other-script corpora are cited, not reproduced.

[#168]: https://github.com/JaidedAI/EasyOCR/issues/168
