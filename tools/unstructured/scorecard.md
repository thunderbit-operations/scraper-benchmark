# unstructured — provisional scorecard

**Provisional.** Based only on the completed material tests (see `research-materials.md`).
Not a final benchmark and not a cross-tool ranking. Weights are pack-local and
pre-registered here; scores are evidence-anchored, each citing a run. All numbers are on
controlled synthetic fixtures (`unstructured` 0.24.1, Python 3.12.13, macOS arm64) across
the **HTML / Markdown / plain-text / DOCX** carriers only. **PDF / OCR / hi_res paths are
BLOCKED** (tesseract/poppler absent + `unstructured_inference`/torch) and are **not scored**.

| Dimension | Weight | Score | One-line evidence |
|---|---:|---:|---|
| Setup and first run | 8 | 6 | `uv pip install "unstructured[docx,md]"` clean; but PDF/OCR pull heavy (torch) + system deps, and libmagic-less host disables auto `partition()` |
| Clean-content classification | 12 | 12 | d1 canonical: all 4 carriers produced an identical 11-element stream, 100% of blocks match intent (`cross_format.json`) |
| Title recall | 10 | 8 | 1.000 html/md/docx, **0.833 txt** — a verb-bearing heading is caught by the narrative rule (checked before the title rule) in plain text; tags force `Title` elsewhere (`metrics.json`, `probe_title_mechanism.json`) |
| NarrativeText precision | 10 | 6 | verbless real prose → `UncategorizedText` in **all four** carriers; structure never rescues body-text typing (FINDING-04) |
| ListItem recall | 10 | 10 | 1.000 across all formats **and** all three docx bullet authorings (style/numpr/dash); old #768/#1320 refuted on 0.24.1 |
| Table recovery | 8 | 7 | 1.000 html/md/docx, **0.000 txt** (no table construct → rows become `Title`); a format limit, but a silent loss |
| Cross-format consistency | 12 | 9 | clean content 100% agreement; divergence localized to txt Title cliff + txt table loss + md lazy-list; structural formats agree 1.000 pairwise |
| Markdown robustness | 8 | 5 | lazy-continuation list collapses 6→1 element (ListItem recall 1.000→0.000); recovers fully with a blank line (Python-Markdown rule) |
| Resource cost / footprint | 8 | 6 | ~244-278 MB peak RSS **format-independent** (model-dominated); warm p50 < ~1.3 s / 660 elements; heavy for a "parse text" task |
| Determinism | 6 | 6 | all 23 (doc,format) runs returned identical `(category,text)` sequences across 3 reps |
| System-dep / deployment surface | 8 | 5 | OCR/hi_res/electronic-PDF all BLOCKED (tesseract+poppler+torch); libmagic-less auto-sniff degraded — a real production weight |
| **Total** | **100** | **80** | provisional research-material score only, not a final rating |

Scoring notes:

- **Clean-content classification (12/12):** on a well-formed document (`d1_canonical`) the
  four carriers are interchangeable — identical 11-element output, every `Title` /
  `NarrativeText` / `ListItem` correct. unstructured is unambiguous when the source is
  structured and idiomatic.
- **Title recall (8/10):** docked for the plain-text miss. A heading that contains a verb is
  claimed by `is_possible_narrative_text` — dispatched *before* `is_possible_title` — and so
  becomes `NarrativeText`, but **only in `txt`** (html/md/docx assign `Title` from the
  tag/style). A 2×2 word-count×verb probe confirms the driver is the verb, not the
  12-word limit (a 5-word verb-bearing line is also `NarrativeText`). Not lower because
  structured carriers are perfect and the behavior is exact and predictable.
- **NarrativeText precision (6/10):** the dimension's real limit. `is_possible_narrative_text`
  requires a finite verb, so a legitimate verbless sentence (a list-like enumeration of
  nouns) lands in `UncategorizedText` in **every** carrier — structure does not help here.
  A downstream RAG/index step keyed on `NarrativeText` would silently drop such blocks. Not
  lower because verb-bearing prose is recovered everywhere and the misfire is predictable.
- **ListItem recall (10/10):** full credit — 1.000 across all carriers and, notably, across
  `List Bullet` style, `numPr`-only, and manual "- " docx authorings, refuting the older
  docx-bullet issue on 0.24.1.
- **Table recovery (7/8):** html/md/docx recover `Table`; plain text cannot (no construct)
  and mis-types rows as `Title`. Docked one point because the loss is *silent* (no signal
  that a table was flattened), though it is a genuine format limitation rather than a bug.
- **Cross-format consistency (9/12):** clean content agrees 100% and structural formats
  agree pairwise 1.000; held back because `txt` is a persistent outlier (Title + Table) and
  Markdown carries a catastrophic collapse mode.
- **Markdown robustness (5/8):** the lazy-continuation collapse (6→1) is severe and easy to
  hit in real Markdown; mitigated by the fact that a blank line fully recovers it and the
  root cause is Python-Markdown, not unstructured's classifier — hence mid, not low.
- **Resource cost (6/8):** ~244-278 MB fixed memory floor regardless of format, plus a cold
  model load; heavy relative to a lightweight HTML/text parse, and docked accordingly.
  Timing is reported as a distribution but **not** used to rank formats (single session,
  order not stable run-to-run).
- **System-dep / deployment surface (5/8):** the whole PDF/OCR/hi_res surface is
  unavailable without tesseract + poppler + the torch-based inference stack, and the
  libmagic-less host disables the convenient auto `partition()` entry — a real operational
  cost this pack could only record, not evaluate.
- Scores reflect **element-type classification fidelity and cross-format consistency on
  controlled ground truth** for the four text-carrier formats only; unstructured is **not**
  scored on PDF/OCR (BLOCKED), real-corpus accuracy, or table-structure recovery.
