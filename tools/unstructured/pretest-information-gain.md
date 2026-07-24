# unstructured — pre-test information-gain brief

Date: 2026-07-24. Gate document (TESTING-STANDARD). Design only.
Decision: **PROCEED** (a measurable, mechanism-tied gap exists: element-type
classification quality vs labeled ground truth, and *cross-format consistency* of that
classification, are unmeasured in public; the divergence is already visible in a smoke
test — see "Information-gain verdict").

Broad keyword: **`unstructured`** (`Unstructured-IO/unstructured`, the document
partitioning / element-extraction library).
Article boundary: `unstructured` ingests a document of some type and returns an ordered
list of **typed elements** — `Title`, `NarrativeText`, `ListItem`, `Table`,
`Header`/`Footer`, `UncategorizedText`, etc. (`partition_*` per format, or the sniffing
`partition()` entry). This pack judges, on documents whose every block is pre-labeled
with its **intended element type** and a unique sentinel token: (1) **per-type
classification precision / recall** (does a heading come back `Title`, a body paragraph
`NarrativeText`, a bullet `ListItem`, a data grid `Table`), and (2) **cross-format
consistency** — the *same logical document* rendered as **HTML, Markdown, plain-text, and
DOCX**, measuring where the four partitioners agree with the intended labels and with each
other, and **which carrier loses structure**. Plus (3) **resource cost** (partition wall
time + peak RSS) per format on matched content.

It is **not** an OCR / scanned-document evaluation, **not** a layout-detection / table-
structure-recovery evaluation, and **not** a real-corpus accuracy benchmark. Cross-tool
axis: the repo already has **markitdown** and **docling** packs (other document→structure
converters); this pack's fixtures are reusable for a same-testbed contrast (out of scope
here, noted for the parent).

## System-dependency reality (scoping, honest up front)

Confirmed absent on this host and recorded as **BLOCKED**, not tested:

- **tesseract ❌** (`tesseract not found`) and **poppler ❌** (`pdftoppm`/`pdfinfo` not
  found). These gate every **OCR path** and every **rasterized / scanned-PDF-image**
  path (`strategy="hi_res"`, `strategy="ocr_only"`, `partition_image`). → tagged
  `BLOCKED_SYSTEM_DEP(tesseract/poppler missing)`.
- **The electronic-PDF text-layer path is *also* blocked here, but for a different
  reason.** In **0.24.1**, importing `unstructured/partition/pdf.py` pulls
  `unstructured_inference` at module load — **not** via the `pdf.py` L83-85 block (that is
  under `if TYPE_CHECKING:` and does not execute), but via the top-level runtime import
  `pdf.py` **L55** `from unstructured.partition.pdf_image.pdfminer_processing import (…)`,
  and `pdfminer_processing.py` **L11** `from unstructured_inference.config import
  inference_config`. This runs *before* strategy dispatch, so **even `strategy="fast"`**
  (which conceptually needs only `pdfminer.six`) will not import without the heavy inference
  stack. Reproduced install chain: `partition_pdf` first demanded `pdfminer`
  (installed), then `pi_heif` (installed), then `No module named 'unstructured_inference'`
  — which pulls **torch/onnx + model downloads at runtime**. That is over this pack's
  resource line and requires network model fetches. → tagged
  `BLOCKED_HEAVY_DEP(unstructured_inference/torch) + BLOCKED_SYSTEM_DEP(hi_res/ocr需
  poppler+tesseract)`. **No torch installed; no PDF numbers claimed.**
- **libmagic ❌** — `python-magic` imports but `magic.Magic()` raises `failed to find
  libmagic`. So the **auto-sniffing `partition()`** entry is degraded on this host. This
  pack deliberately drives the **format-specific** partitioners (`partition_html`,
  `partition_text`, `partition_md`, `partition_docx`), which is the documented, supported
  way to bypass content sniffing; the libmagic gap is recorded, not worked around
  silently.

**In-scope, verified importable *and* runnable on this host (the pack):**
`partition_html`, `partition_text`, `partition_md`, `partition_docx`. All four ran in a
smoke test with **no** tesseract / poppler / libmagic / torch. That is the entire
credential-free, system-dep-free surface, and it is exactly where the classification
question lives.

## SERP / official / issue scan (≈20 results, docs, source, issue tracker)

### What the results repeat (consensus — mostly documented or qualitative)

- **Element typing is heuristic.** The docs and every write-up describe `partition`
  returning typed elements; the classifier is a **heuristic** pipeline
  (`unstructured/partition/text_type.py`) of regex + capitalization / non-alpha ratios +
  NLTK/spaCy sentence & verb checks. Multiple third-party posts note it is imperfect:
  "short paragraphs are often mislabeled Title," "single-line list items can land in
  UncategorizedText." **Qualitative / DOCUMENTED** — none quantify a confusion matrix.
- **Per-format partitioners use *different* mechanisms.** Read from the installed 0.24.1
  source:
  - `partition_text` (.txt): **pure heuristic**, no structure. Dispatch order in
    `_text_to_element` (text.py L128-156): `is_bulleted_text` → `is_possible_numbered_list`
    → `is_possible_narrative_text` → `is_possible_title` → else base `Text`.
  - `partition_html` (.html): **tag-structural** — `h1..h6` → `Title` (parser.py, class
    with `_ElementCls = Title`, `category_depth` from heading level), `li` → `ListItem`
    (list-nesting depth), and a `<p>`/free text still runs
    `derive_element_type_from_text` → `is_possible_narrative_text(text)` → `NarrativeText`
    else `UncategorizedText` (parser.py L935-936).
  - `partition_md` (.md): Markdown → HTML via the **Python-Markdown** library → then the
    HTML path. So md fidelity is gated by **Python-Markdown's block rules** (which are
    *not* CommonMark — a list not preceded by a blank line is absorbed into the preceding
    paragraph).
  - `partition_docx` (.docx): **paragraph-style-name mapping** (`STYLE_TO_ELEMENT_MAPPING`)
    — `List Bullet` / `List Number` styles → `ListItem`; unstyled/`numPr`-only bullets or
    manual "- " text fall through to the text heuristic.
- **Heuristic constants (installed 0.24.1, `text_type.py`)** — DOCUMENTED, cited so
  mechanism claims are grounded: `title_max_word_length = 12`, `sentence_min_length = 5`,
  `cap_threshold = 0.5`, `non_alpha_threshold = 0.5`; `is_possible_narrative_text`
  requires a **verb** (POS `VB*`) when the block has < 2 sentences; `is_bulleted_text`
  matches `UNICODE_BULLETS_RE`. All overridable by `UNSTRUCTURED_*` env vars.

### Known failure reports (KNOWN-ISSUE anchors — anecdotal, uncontrolled)

- **md short list block → `Title`** when list lines are short
  ([#3280](https://github.com/Unstructured-IO/unstructured/issues/3280), v0.14.5, open).
- **docx bullets → `NarrativeText`/`Title`, not `ListItem`**
  ([#768](https://github.com/Unstructured-IO/unstructured/issues/768),
  [#1320](https://github.com/Unstructured-IO/unstructured/issues/1320),
  [#3455](https://github.com/Unstructured-IO/unstructured/issues/3455)/
  [#3463](https://github.com/Unstructured-IO/unstructured/issues/3463)).
- **code blocks → `NarrativeText`**
  ([#771](https://github.com/Unstructured-IO/unstructured/issues/771)).

These are **KNOWN-ISSUE** — real-page anecdotes on specific inputs, not a controlled,
labeled, cross-format measurement.

### What is NOT measured anywhere (the actual gap)

1. **A per-type classification confusion matrix on labeled ground truth.** No public
   source labels every block of a document with its intended type and reports
   precision/recall for `Title` / `NarrativeText` / `ListItem` / `Table` / etc.
2. **Cross-format consistency, quantified.** The *same logical content* rendered four ways
   (HTML/MD/TXT/DOCX) → per-block agreement rate, element-count divergence, and *which
   format loses which structure*. Folklore ("docx bullets misfire," "txt is heuristic")
   is never turned into a same-content agreement number.
3. **The mechanism-tied divergence boundaries as controlled demonstrations:** the
   **verb-first dispatch** (a verb-bearing heading is claimed by `is_possible_narrative_text`,
   checked *before* `is_possible_title`, so in plain text it becomes `NarrativeText` — the
   `title_max_word_length = 12` limit is never reached; the word-count boundary only governs
   Title-vs-Text for *verbless* lines), the **verb requirement** (a real, verbless body
   sentence fails `is_possible_narrative_text` → becomes `UncategorizedText`, not
   `NarrativeText`), the Python-Markdown **blank-line-before-list** rule (list collapses into
   one block), and docx **style-vs-manual** bullet fall-through — each shown to *move* with
   the input, proving mechanism not fixture.
4. **Resource cost per format on matched content.** Partition wall time + peak RSS for the
   heuristic path (spaCy/NLTK load) vs the structural path — unmeasured side by side.

### Smoke-test evidence that the gap is real (already observed, pre-pack)

Same logical doc — `Title` + intro + a section header + a 5-item short list — fed to all
four partitioners on 0.24.1 (verbatim from the smoke run, deterministic over 5 reps):

| logical block | .md | .txt | .html |
|---|---|---|---|
| "header 1" | `Title` | **`NarrativeText`** | `Title` |
| "header 2" | `Title` | `Title` | `Title` |
| "My list" + 5 items | **one `UncategorizedText` (list collapsed)** | `Title` + 5×`ListItem` | `UncategorizedText` + 5×`ListItem` |
| element count | **4** | 10 | 9 |

Three carriers of *identical intent* produce three different element structures; the
Markdown list fully collapsed (Python-Markdown lazy-list rule), the plain-text path called
the first "header 1" `NarrativeText` while "header 2" was `Title` (a heuristic artifact,
**deterministic** 5/5). This is the pack in miniature.

### Source evidence

- Official docs: [Partitioning](https://docs.unstructured.io/open-source/core-functionality/partitioning),
  [Document elements](https://docs.unstructured.io/open-source/concepts/document-elements).
- Installed 0.24.1 source (read directly): `partition/text_type.py`, `partition/text.py`,
  `partition/html/parser.py`, `partition/md.py`, `partition/docx.py`, `partition/pdf.py`.
- Issues to cite at execution: [#3280], [#768], [#1320], [#3455]/[#3463], [#771].
- Representative SERP: DeepWiki Unstructured-IO/unstructured, saeedesmaili.com
  "Demystifying Text Data with the unstructured Python Library."

## Testable information-gain hypotheses

- **H1 (per-type classification P/R on labeled ground truth, main):** On fixtures where
  every block is labeled `Title`/`NarrativeText`/`ListItem`/`Table`/… with a unique
  sentinel, measure per-type **precision/recall + a confusion matrix**, per format.
  Prediction from mechanism: structural formats (html, well-styled docx) recover
  `Title`/`ListItem` from tags/styles; the txt heuristic path mislabels
  verbless/short/long-heading blocks; `Table` is recoverable only where the carrier has a
  table construct (html/docx/md-tables), never in plain txt.
- **H2 (cross-format consistency, main):** The **same logical document** in
  HTML/MD/TXT/DOCX → per-block **agreement with the intended label** and **pairwise
  format agreement**; report element-count divergence and *which format loses which
  structure*. Prediction: html ≈ docx (structural) > md (Python-Markdown block quirks) >
  txt (pure heuristic); the biggest single loss is md list collapse and docx manual-bullet
  fall-through.
- **H3 (adversarial heuristic boundaries — precision failures):** Constructed blocks —
  a **verb-bearing heading**, an **ALL-CAPS heading**, a **verbless real body sentence**, a
  **high-non-alpha** line — fed as txt vs html/docx. Prediction: the txt path mis-types
  them (a verb-bearing heading → `NarrativeText`, because `is_possible_narrative_text` is
  dispatched before `is_possible_title`; a verbless paragraph → `UncategorizedText`), while
  the structural formats hold because the tag/style overrides the heuristic. A 2×2
  word-count×verb probe separates the verb trigger from the `title_max_word_length=12` limit
  (the latter only governs Title-vs-Text for verbless lines). (mechanism proof).
- **H4 (Markdown list-collapse boundary):** The `#3280`-shape short list, rendered md
  **without** vs **with** a blank line before the list. Prediction: without a blank line
  the whole list collapses into one non-`ListItem` block; with a blank line it recovers to
  N `ListItem`s — proving the loss is the **Python-Markdown block rule**, not unstructured
  mis-classifying (rules out a fixture artifact).
- **H5 (docx list mechanism):** The same list authored three ways in docx — `List Bullet`
  **style**, a `numPr`-only paragraph, and a manual **"- " text** paragraph. Prediction:
  only the `List Bullet` style reliably yields `ListItem`; the others fall through to
  `NarrativeText`/`Title` (the #768/#1320 shape), quantified.
- **H6 (resource cost per format):** Partition **wall time (p50 over ≥5 reps, interval
  reported)** and **peak RSS (separate subprocess)** for a matched ~large document across
  the four formats, plus the **one-time model-load** cost (first call vs warm). Prediction:
  the heuristic path (txt) pays a spaCy/NLTK load the structural paths partly share;
  reported as distribution, timing-contamination caveated.

## Test matrix (tied to hypotheses)

| # | Test | Fixture (× formats) | Measures | H |
|---|---|---|---|---|
| 1 | canonical doc, all 4 formats | D1 canonical | per-type P/R, confusion | H1/H2 |
| 2 | per-block label agreement | D1 | intended-label hit per format | H1/H2 |
| 3 | pairwise format agreement | D1 | html/md/txt/docx agreement | H2 |
| 4 | element-count divergence | D1 | #elements per format vs intended | H2 |
| 5 | Table recovery | D2 table doc | `Table` present per format | H1 |
| 6 | 13-word heading | D3 adversarial | Title→? at word 12/13 boundary | H3 |
| 7 | ALL-CAPS heading | D3 | type per format | H3 |
| 8 | verbless body sentence | D3 | NarrativeText vs UncategorizedText | H3 |
| 9 | high-non-alpha line | D3 | type per format | H3 |
| 10 | md list, no blank line | D4 short list | list collapse? | H4 |
| 11 | md list, with blank line | D4 | list recovers to N ListItem? | H4 |
| 12 | txt/html same short list | D4 | ListItem recovery | H4/H1 |
| 13 | docx List Bullet style | D5 docx bullets | ListItem? | H5 |
| 14 | docx numPr-only | D5 | ListItem vs Narrative | H5 |
| 15 | docx manual "- " text | D5 | ListItem vs Narrative | H5 |
| 16 | numbered list, all formats | D1/D6 | ListItem via is_possible_numbered_list | H1/H2 |
| 17 | determinism | all | identical type-sequence across 3 reps | all |
| 18 | partition wall time p50 | D7 large | time per format (≥5 reps) | H6 |
| 19 | peak RSS per format | D7 large | ru_maxrss in isolated subprocess | H6 |
| 20 | cold vs warm first-call | D1 | model-load one-time cost | H6 |
| 21 | title_max_word_length env override | D3 | boundary moves with env var | H3 |
| 22 | non-alpha / cap ratio boundary | D3 | ratio threshold demonstration | H3 |

Ground truth: each labeled block embeds a **unique sentinel token** (e.g. `zztitle01`,
`zznarr01`), and — as in the mozilla-readability pack — every word in a block begins with
that block's sentinel prefix, so token sets across blocks are **disjoint**. An extracted
element is matched back to its intended block by exact sentinel substring membership; the
produced `element.category` is then compared to the intended label. "Recovered / mistyped"
is exact, never fuzzy. The build script emits **all four format renderings + the shared
`ground_truth.json` together**, so labels can never drift from the rendered bytes.

## Harness design (single-source fixtures + anti-hardcoding split)

- `tests/build_fixtures.py` (Python) — **single source of truth**: for each logical
  document writes `tests/fixtures/<doc>.html`, `.md`, `.txt`, and `.docx` (docx via
  `python-docx`) **and** `tests/fixtures/ground_truth.json` (per-block: `id`, intended
  `type`, `sentinel`, `text`, plus the docx list-authoring variant). Deterministic content
  (fixed strings, no randomness); the binary `.docx` is regenerated (its internal zip
  timestamps are not asserted — only extracted elements are).
- `tests/run_partition.py` (Python venv) — per fixture × format, calls the format-specific
  partitioner, dumps **raw** `[{category, class_name, text}]` + element count + 3-rep
  determinism + timing → `artifacts/raw/partition_raw.json`. **No metric computed here.**
- `tests/resource_cost.py` (Python) — spawns an **isolated subprocess per (format)** that
  partitions the D7 large fixture, reporting wall-time p50 over ≥5 reps + peak RSS
  (`resource.ru_maxrss`), cold-vs-warm first call, one format per process so RSS is not
  cross-contaminated (methodology Part 2 §6) → `artifacts/raw/resource_cost.json`.
- `tests/metrics.py` (Python) — reads `ground_truth.json` + `partition_raw.json`, computes
  **per-type precision/recall + confusion matrix per format**, per-block cross-format
  agreement, pairwise agreement, element-count divergence → `artifacts/raw/metrics.json` +
  `cross_format.json`. **Every number derived from raw category vs labels — no result
  constant hand-written** (闸门 3).
- `_redact`: `$HOME`→`~` **and** `$TMPDIR` / `/var/folders` temp paths → `<TMP>` before any
  JSON is written (the selenium-pack lesson).

## Information-gain verdict: PROCEED

Not parked. The *existence* of heuristic typing and its imperfection is **DOCUMENTED**;
the specific misfires (md short-list→Title, docx bullets→NarrativeText, code→narrative)
are **KNOWN-ISSUE**. What no public source provides, and what is measurable here on a
credential-free, system-dep-free local fixture: (1) a **per-type confusion matrix / P-R**
on labeled ground truth; (2) a **quantified cross-format consistency** number for the same
logical content across HTML/MD/TXT/DOCX with a "which format loses which structure"
decomposition; (3) **mechanism-tied boundary demonstrations** (the verb-first dispatch that
mis-types verb-bearing headings in plain text, the verb requirement, the Python-Markdown
blank-line rule that collapses lists, the docx style-vs-manual bullet fall-through) each
shown to move with the input; (4) **resource cost per format**. The mechanisms themselves
(rule order, thresholds) are DOCUMENTED source behavior; the EXCLUSIVE-eligible contribution
is the *measured per-format misfire rates + the controlled isolations*, while existence
claims stay DOCUMENTED and the real-page misfires stay KNOWN-ISSUE. The PDF/OCR surface is
**BLOCKED** (system deps + heavy inference stack) and excluded, not faked.

## Boundary / compliance notes

- Evidence phase only; **no article, no publish, no git**.
- All tests on **local, self-authored fixtures** (no network at runtime). No third-party
  host, no anti-bot, no auth, no rate abuse. unstructured is a local parser.
- No credentials anywhere. `_redact` scrubs `$HOME`→`~` and `$TMPDIR`/`/var/folders`.
- Record exact `unstructured` + `python-docx` + `markdown` + `lxml` + spaCy/NLTK + Python
  versions in metadata; **record tesseract/poppler/libmagic ABSENT → OCR / hi_res /
  electronic-PDF / auto-sniff paths NOT tested (BLOCKED)**; fixtures + `ground_truth.json`
  committed; `.venv/`, model caches, `__pycache__`, generated `.docx` gitignored, never
  shipped.
- Determinism asserted (3 reps identical type-sequence) before any single-run number.
- Novelty honesty: heuristic classification, per-format mechanism, and the constants are
  **DOCUMENTED**; the misfire anecdotes are **KNOWN-ISSUE** ([#3280]/[#768]/[#1320]/
  [#3455]/[#771]). Only the controlled confusion matrix, the cross-format agreement
  numbers, the boundary demonstrations, and the per-format resource cost are candidates for
  **EXCLUSIVE**.

[#3280]: https://github.com/Unstructured-IO/unstructured/issues/3280
[#768]: https://github.com/Unstructured-IO/unstructured/issues/768
[#1320]: https://github.com/Unstructured-IO/unstructured/issues/1320
[#3455]: https://github.com/Unstructured-IO/unstructured/issues/3455
[#3463]: https://github.com/Unstructured-IO/unstructured/issues/3463
[#771]: https://github.com/Unstructured-IO/unstructured/issues/771
