# unstructured — evidence pack

Reproducible, third-party tests for **`unstructured`** (`Unstructured-IO/unstructured`,
v**0.24.1**), the document partitioning / element-extraction library. Part of the
Thunderbit open-source scraping-tool benchmark. Every number in `research-materials.md`
traces to a script here and a JSON artifact under `artifacts/raw/`.

Focus (queue #15): **structured elements and resource costs across web-retrieved document
types** — i.e. how well `unstructured` classifies blocks into `Title` / `NarrativeText` /
`ListItem` / `Table`, whether that classification is **consistent across formats** (HTML /
Markdown / plain-text / DOCX), and what it costs.

Tested (as-of 2026-07-24): unstructured **0.24.1**, python-docx **1.2.0**, Python-Markdown
**3.10.2**, lxml **6.1.1**, spaCy **3.8.14**; Python 3.12.13; macOS arm64.

## Scope and what is BLOCKED

In scope (runs with **no** system deps): `partition_html`, `partition_text`,
`partition_md`, `partition_docx`.

**BLOCKED and not tested** (recorded, never faked): **tesseract ❌** and **poppler ❌**
(all OCR / `hi_res` / scanned-PDF-image paths); the **electronic-PDF text-layer** path
too, because 0.24.1's `partition_pdf` imports `unstructured_inference` (torch/onnx + model
downloads) even for `strategy="fast"`; and **libmagic ❌**, which disables the auto
`partition()` sniffer (format-specific partitioners used instead). **No PDF or OCR number
appears in this pack.**

## Headline

On a labeled cross-format fixture (9 logical documents rendered as HTML / MD / TXT / DOCX;
every block tagged with its intended element type + a unique sentinel), **`unstructured` is
interchangeable across carriers on clean content but diverges by a per-format mechanism.**
On the well-formed baseline all four carriers produced an **identical 11-element stream,
100% matching intent**. The divergences are localized and mechanism-tied:

- **`Title`** recall is 1.000 for html/md/docx but **0.833 for plain text**: a **verb-bearing
  heading** is claimed by `is_possible_narrative_text` — dispatched *before* the title rule —
  and becomes `NarrativeText`, but *only* in `.txt` (a 2×2 probe confirms the verb, not the
  12-word limit, is the driver); `<h1>`/Heading tags force `Title` in the structured carriers.
- **`NarrativeText` vs `UncategorizedText` is heuristic in *every* format**: a real but
  **verbless** sentence lands in `UncategorizedText` in all four carriers (the
  `is_possible_narrative_text` verb requirement) — structure never rescues body-text typing.
- **`Table`** is recovered by html/md/docx (1.000) and **lost by plain text** (0.000; rows
  become `Title`).
- **`ListItem`** is 1.000 everywhere — including all three DOCX bullet authorings
  (`List Bullet` style, `numPr`-only, manual "- "), **refuting** the older
  docx-bullet issue ([#768]/[#1320]) on 0.24.1.
- **Markdown lazy lists collapse**: a list with no blank line before it folds 6 blocks into
  1 `NarrativeText` (ListItem recall 1.000 → 0.000); a blank line recovers it fully — a
  Python-Markdown block rule, not an unstructured fault.
- **Resource cost is model-dominated**: peak RSS ≈ **244-278 MB regardless of format** (even
  the plain-text path), with a ~150-500 ms cold model load; warm p50 < ~1.3 s / 660
  elements (cross-format timing order not concluded — session-variable). All 23 (doc,format)
  runs were 3-rep deterministic.

## Reproduce

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "unstructured[docx,md]"   # 0.24.1

.venv/bin/python tests/build_fixtures.py   # 1) 4-carrier fixtures + ground_truth.json
.venv/bin/python tests/run_partition.py    # 2) raw element categories + determinism (no metrics)
.venv/bin/python tests/metrics.py          # 3) per-type P/R + confusion + cross-format agreement
.venv/bin/python tests/resource_cost.py    # 4) per-format wall time + peak RSS (isolated subprocess)
.venv/bin/python tests/probe_title_mechanism.py   # 5) isolates verb vs word-count for Title-vs-NarrativeText
```

Requires Python 3.12 + `uv`. Fixtures are local (no network at runtime). Every labeled block
carries a unique sentinel, so recovered/mistyped is exact membership — never guessed. **All
metrics are computed in `metrics.py` from raw element categories vs the labels** — no metric
constant is written by hand (anti-hardcoding).

## What the pack establishes

- **Per-type classification recall by format** (confusion matrix in `metrics.json`).
- **Cross-format consistency**: same content ×4 carriers, per-block agreement + which format
  loses which structure (`cross_format.json`).
- **Mechanism boundaries**: verb-bearing headings claimed by the narrative rule in txt (the
  narrative check precedes the title check; 2×2 word×verb probe), the verb requirement for
  NarrativeText (format-independent), the Markdown blank-line-before-list rule (6→1, isolated).
- **DOCX bullet robustness** across three authoring modes (refutes the historical issue).
- **Resource cost**: ~244-278 MB format-independent memory floor; cold model load; warm
  timing reported as a distribution (not a format race).
- **Determinism**: all 23 (doc,format) runs 3-rep identical.

## Pack contents

- `pretest-information-gain.md` — the gate brief (SERP/issue/source scan, hypotheses,
  matrix, PROCEED verdict; system-dep BLOCKED scoping up front).
- `research-materials.md` — full evidence, per-finding confidence + novelty table, Part-6
  self-check, Gaps.
- `scorecard.md` — provisional dimension scores (80/100), evidence-anchored.
- `metadata-snapshot.md` — versions, absent-dependency table, mechanism constants, exact
  commands, reproducibility.
- `tests/` — `build_fixtures.py`, `run_partition.py`, `metrics.py`, `resource_cost.py`,
  `probe_title_mechanism.py`, and `fixtures/` (`*.html/.md/.txt` + `ground_truth.json`;
  `.docx` regenerated, gitignored).
- `artifacts/raw/` — `partition_raw.json`, `metrics.json`, `cross_format.json`,
  `resource_cost.json`, `probe_title_mechanism.json`.

Evidence phase only: no article, no publishing, no git. All numbers are controlled-fixture
measurements on the four text-carrier formats; PDF/OCR are BLOCKED and unscored.

[#768]: https://github.com/Unstructured-IO/unstructured/issues/768
[#1320]: https://github.com/Unstructured-IO/unstructured/issues/1320
