# unstructured — metadata snapshot

Fetched: **2026-07-24** (as-of). Refresh within 48h before any final draft.

| Field | Value |
|---|---|
| Repo | [Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured) |
| License | **Apache-2.0** |
| Version tested | **0.24.1** (`uv pip install "unstructured[docx,md]"` resolved 0.24.1) |
| Install extras used | `[docx,md]` (base + python-docx + Python-Markdown) |

Environment actually used (from the run summaries / host):

| Item | Value |
|---|---|
| unstructured | **0.24.1** |
| unstructured-client (transitive) | 0.45.0 |
| python-docx | **1.2.0** |
| Markdown (Python-Markdown) | **3.10.2** |
| lxml | **6.1.1** |
| spaCy | **3.8.14** |
| beautifulsoup4 | **4.15.0** |
| Python | **3.12.13** (uv venv) |
| Platform | **macOS 26.5.2 (25F84) arm64** |
| Test date | **2026-07-24** |

## System dependencies — ABSENT on this host (→ BLOCKED paths, not tested)

Recorded here; these paths produce **no numbers** in this pack:

| Dependency | Status | Gated paths |
|---|---|---|
| **tesseract** | **ABSENT** (`tesseract not found`) | all OCR; `strategy="ocr_only"`; image text |
| **poppler** (`pdftoppm`/`pdfinfo`) | **ABSENT** | PDF rasterization; `strategy="hi_res"` for scanned PDF |
| **libmagic** | **ABSENT** (`magic.Magic()` → "failed to find libmagic") | the auto-sniffing `partition()` entry (degraded) |
| **unstructured_inference / torch** | **not installed** | `partition_pdf` (ALL strategies — imported at module load in 0.24.1); `hi_res` layout models |

**Electronic-PDF text-layer note:** even `strategy="fast"` (which conceptually needs only
`pdfminer.six`) will not import in 0.24.1 because importing `partition/pdf.py` pulls
`unstructured_inference` at module load — via the top-level runtime import `pdf.py` **L55**
→ `pdf_image/pdfminer_processing.py` **L11** (`from unstructured_inference.config import
inference_config`), **not** the `pdf.py` L83-85 `TYPE_CHECKING` block — *before* strategy
dispatch. Reproduced dependency chain when attempting to enable it: `partition_pdf` →
`No module named 'pdfminer'`
→ (install) → `No module named 'pi_heif'` → (install) → `No module named
'unstructured_inference'` (pulls torch/onnx + runtime model downloads). The pack stopped
there — **no torch installed, no PDF number claimed.**

## In-scope surface (verified importable AND runnable with none of the above)

`partition_html`, `partition_text`, `partition_md`, `partition_docx` — all four ran on this
host with no tesseract / poppler / libmagic / torch. That is the entire scope.

## Classification mechanism constants (read from installed 0.24.1 source)

Read from `.venv/.../unstructured/partition/text_type.py`, `partition/text.py`,
`partition/html/parser.py`, `partition/md.py`, `partition/docx.py` (documented; cited so
the mechanism claims are grounded):

- **Text heuristic (`.txt`, and body `<p>` in every carrier).** Dispatch order in
  `_text_to_element`: `is_bulleted_text` → `is_possible_numbered_list` →
  `is_possible_narrative_text` → `is_possible_title` → base `Text`(`UncategorizedText`).
- `is_possible_title`: `title_max_word_length = 12`; rejects if `sentence_count > 1`
  (`sentence_min_length = 5`); rejects `non_alpha_ratio ≥ 0.5`; rejects all-caps **only**
  when it also ends in punctuation; rejects trailing comma; requires an English word.
- `is_possible_narrative_text`: rejects `cap_ratio > 0.5` (`cap_threshold = 0.5`); rejects
  `non_alpha_ratio ≥ 0.5` (`non_alpha_threshold = 0.5`); **requires a verb** (POS `VB*`)
  when the block has `< 2` sentences. All thresholds overridable via `UNSTRUCTURED_*` env
  vars.
- `is_bulleted_text` = `UNICODE_BULLETS_RE.match(...)`; `is_possible_numbered_list` =
  `NUMBERED_LIST_RE.match(...)`.
- **Sentence/verb tokenization** runs through unstructured's **vendored**
  `unstructured/nlp/tokenize.py` (`sent_tokenize` / `word_tokenize` / `pos_tag`); a
  standalone top-level `nltk` package is **not** required or installed on this host, and
  the verb check was calibrated (True on a verb sentence, False on a verbless one).
- **HTML (`.html`).** `h1..h6` → `Title` (category_depth = heading level); `li` →
  `ListItem` (list nesting); `table` → `Table`; a `<p>`/free text runs
  `is_possible_narrative_text` → `NarrativeText` else `UncategorizedText`.
- **Markdown (`.md`).** Markdown → HTML via **Python-Markdown 3.10.2** → the HTML path;
  pipe-tables enabled → `Table`. Block structure obeys Python-Markdown's rules (a list not
  preceded by a blank line is folded into the preceding paragraph).
- **DOCX (`.docx`).** `STYLE_TO_ELEMENT_MAPPING` on paragraph style names + numbering
  (`numPr`) / bullet-text detection → `Title` / `ListItem`; body paragraphs fall through to
  the text heuristic. On 0.24.1 all three bullet authorings (style / numPr / manual dash)
  resolve to `ListItem`.

## Exact commands run

Everything is offline (fixtures are local, self-authored).

```bash
cd tools/unstructured

# 0) venv + deps (pinned surface: unstructured 0.24.1 + docx + md)
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "unstructured[docx,md]"

# 1) build the annotated fixtures (4 carriers each) + shared ground truth
.venv/bin/python tests/build_fixtures.py     # -> tests/fixtures/*.{html,md,txt,docx} + ground_truth.json

# 2) raw extraction (element categories + determinism; NO metrics computed here)
.venv/bin/python tests/run_partition.py      # -> artifacts/raw/partition_raw.json

# 3) derive per-type P/R + confusion matrix + cross-format agreement from raw vs labels
.venv/bin/python tests/metrics.py            # -> artifacts/raw/metrics.json + cross_format.json

# 4) per-format resource cost (isolated subprocess each; p50 + cold/warm + peak RSS)
.venv/bin/python tests/resource_cost.py      # -> artifacts/raw/resource_cost.json

# 5) mechanism probe: verb-presence vs word-count for Title-vs-NarrativeText in plain text
.venv/bin/python tests/probe_title_mechanism.py   # -> artifacts/raw/probe_title_mechanism.json
```

## Reproducibility notes

- **Anti-hardcoding split.** `run_partition.py` returns only raw `element.category` + class
  + text + determinism; **all P/R, the confusion matrix, and cross-format agreement are
  computed in `metrics.py`** from that raw output vs `ground_truth.json`. No metric constant
  is written by hand.
- **Ground truth is generated with the bytes.** `build_fixtures.py` emits all four carrier
  renderings and `ground_truth.json` together; every block carries a unique sentinel, so
  "recovered / mistyped / merged / dropped" is exact (case-insensitive) sentinel membership.
- **Fair heuristic exercise.** Fixtures use real English prose (real verbs) so
  `NarrativeText` is earned, not gamed by gibberish.
- **Determinism** asserted (3 reps identical `(category,text)` sequence on all 23 runs)
  before any single-run number is used.
- **Isolated RSS.** `resource_cost.py` runs one subprocess per format so peak RSS is not
  cross-contaminated; timing is reported as warm-median + interval and **not** used to rank
  formats (single session, possible sibling-worker contamination).
- **Redaction.** `$HOME`→`~` and `$TMPDIR` / `/var/folders` → `<TMP>` in every written JSON;
  verified no host path remains in `artifacts/`.
- **Not shipped:** `.venv/`, model/NLP caches, `__pycache__`, and the **generated `.docx`**
  (regenerated deterministically by `build_fixtures.py`; its zip-internal timestamps vary,
  and only extracted elements are asserted) — all gitignored. The `.html` / `.md` / `.txt`
  fixtures and `ground_truth.json` are committed.
- **Version pin note:** the pack tests **0.24.1** specifically; the `main`-branch source
  may differ (e.g. the older docx-bullet issues, refuted here, were filed against earlier
  versions). All mechanism claims were read from the *installed* 0.24.1 source.
