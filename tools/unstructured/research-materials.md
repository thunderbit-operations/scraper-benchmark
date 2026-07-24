# unstructured — Review Research Materials

Date: 2026-07-24

Status: source material for a future Thunderbit review article. This is **not** a final
blog draft and must not be published as-is.

## Material Boundary

Evidence base for a single-tool review of **`unstructured`** (`Unstructured-IO/unstructured`,
v**0.24.1**), the document partitioning / element-extraction library. It judges **element-
type classification against ground truth and its consistency across web-retrieved document
types**: on fixtures where every block is pre-labeled with its intended element type
(`Title` / `NarrativeText` / `ListItem` / `Table`) and carries a unique sentinel token, it
measures per-type precision/recall (a confusion matrix) per carrier format, **cross-format
consistency** of the *same logical content* rendered as HTML / Markdown / plain-text /
DOCX, the mechanism-tied boundaries where the classifier flips, and per-format resource
cost. It does **not** evaluate OCR, scanned-PDF / image layout, table-structure recovery,
or real-corpus accuracy.

### Scope is bounded by absent system dependencies (recorded, not worked around)

Confirmed absent on this host → the corresponding paths are **BLOCKED and untested**, not
faked:

- **tesseract ❌ / poppler ❌** → every OCR path and every rasterized / scanned-PDF-image
  path (`strategy="hi_res"`, `"ocr_only"`, `partition_image`) is
  `BLOCKED_SYSTEM_DEP(tesseract/poppler)`.
- **electronic-PDF text-layer path** is *also* blocked, for a different reason: in 0.24.1
  importing `partition/pdf.py` pulls `unstructured_inference` at module load — via the
  top-level runtime import `pdf.py` L55 → `pdf_image/pdfminer_processing.py` L11 (`from
  unstructured_inference.config import inference_config`), **not** the `pdf.py` L83-85
  `TYPE_CHECKING` block — *before* strategy dispatch, so even `strategy="fast"` (which only
  needs `pdfminer.six`) will not import without the heavy inference stack (torch/onnx +
  runtime model downloads). Reproduced install chain: `pdfminer` → `pi_heif` → `No module
  named 'unstructured_inference'`.
  `BLOCKED_HEAVY_DEP(unstructured_inference/torch)`. No torch installed; **no PDF number
  is claimed anywhere in this pack.**
- **libmagic ❌** (`magic.Magic()` → "failed to find libmagic") → the auto-sniffing
  `partition()` entry is degraded on this host. The pack drives the **format-specific**
  partitioners (`partition_html/text/md/docx`), the documented way to bypass sniffing.

The four format-specific partitioners **run with no tesseract / poppler / libmagic / torch**
— that credential-free, system-dep-free surface is exactly where element classification
lives, and is the entire scope of this pack.

## Source Snapshot

Point-in-time metadata (see `metadata-snapshot.md`; refresh within 48h before any final
draft):

| Field | Value |
|---|---|
| Repo | [Unstructured-IO/unstructured](https://github.com/Unstructured-IO/unstructured) |
| Version tested | **0.24.1** (`uv pip install "unstructured[docx,md]"` resolved 0.24.1) |
| License | **Apache-2.0** |

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (25F84) arm64 |
| unstructured | **0.24.1** |
| python-docx | **1.2.0** |
| Markdown (Python-Markdown) | **3.10.2** |
| lxml | **6.1.1** |
| spaCy | **3.8.14** (present; heuristics use unstructured's vendored `nlp/tokenize.py`) |
| beautifulsoup4 | **4.15.0** |
| Python | **3.12.13** (uv venv) |
| Absent (→ BLOCKED paths) | **tesseract, poppler, libmagic, torch/unstructured_inference** |
| Fixture generator | [tests/build_fixtures.py](tests/build_fixtures.py) → `tests/fixtures/*.{html,md,txt,docx}` + `ground_truth.json` |
| Extraction runner | [tests/run_partition.py](tests/run_partition.py) → [partition_raw.json](artifacts/raw/partition_raw.json) |
| Metrics | [tests/metrics.py](tests/metrics.py) → [metrics.json](artifacts/raw/metrics.json), [cross_format.json](artifacts/raw/cross_format.json) |
| Resource cost | [tests/resource_cost.py](tests/resource_cost.py) → [resource_cost.json](artifacts/raw/resource_cost.json) |
| Title-mechanism probe | [tests/probe_title_mechanism.py](tests/probe_title_mechanism.py) → [probe_title_mechanism.json](artifacts/raw/probe_title_mechanism.json) |

Fixtures: **9 logical documents**, rendered across up to 4 carrier formats (**23 (doc,
format) partition runs**). The **classification set** — `d1_canonical`, `d2_table`,
`d3_adversarial`, `d4_shortlist_mdblank` — is where the confusion matrix and cross-format
agreement are computed; `d5_docx_*` (bullet-authoring variants) and `d7_large` (canonical
×60, 660 elements) are reported on their own axes so their repeated blocks do not swamp the
aggregate.

Method notes (they affect reproduction):

- **Anti-hardcoding split.** `run_partition.py` dumps only the *raw* element stream
  (`category`, class name, text) + counts + a 3-rep determinism check. **Every metric —
  per-type P/R, the confusion matrix, cross-format agreement — is derived in `metrics.py`**
  from raw `category` vs the labels. No result constant is written by hand (闸门 3).
- **Real prose, not gibberish.** Narrative blocks are genuine English sentences with real
  verbs; titles are short real phrases — so the heuristic classifier is exercised *fairly*
  (a narrative paragraph must actually contain a verb to earn `NarrativeText`). Each block
  embeds **one unique sentinel token**; matching is exact (case-insensitive) sentinel
  membership, never fuzzy.
- **Ground truth is generated with the bytes.** `build_fixtures.py` writes all four
  renderings and `ground_truth.json` together, so labels can never drift from the rendered
  document.
- **`.category` is the measured type** (canonical string: `Title`/`NarrativeText`/
  `ListItem`/`Table`/`UncategorizedText`).
- **Redaction.** `$HOME`→`~` and `$TMPDIR` / `/var/folders` → `<TMP>` in every written JSON
  (verified: artifacts contain no host paths).

## The mechanism (read from installed 0.24.1 source)

Each carrier uses a **different** classification mechanism — the root of every cross-format
divergence below:

- **`partition_text` (.txt): pure heuristic**, no structure. `_text_to_element` order
  (text.py L128-156): `is_bulleted_text` → `is_possible_numbered_list` →
  `is_possible_narrative_text` → `is_possible_title` → else base `Text`
  (`UncategorizedText`). Constants (text_type.py): `title_max_word_length=12`,
  `sentence_min_length=5`, `cap_threshold=0.5`, `non_alpha_threshold=0.5`;
  `is_possible_narrative_text` requires a **verb** (POS `VB*`) when < 2 sentences.
- **`partition_html` (.html): tag-structural** — `h1..h6`→`Title`, `li`→`ListItem`,
  `table`→`Table`; but a `<p>`/free text still runs `is_possible_narrative_text` →
  `NarrativeText` else `UncategorizedText` (parser.py L935).
- **`partition_md` (.md): Markdown→HTML (Python-Markdown)→the HTML path.** Fidelity is
  gated by Python-Markdown's block rules (a list not preceded by a blank line is folded
  into the preceding paragraph). Pipe-tables are enabled (→ `Table`).
- **`partition_docx` (.docx): paragraph-style-name mapping** + numbering/bullet detection
  → `Title`/`ListItem`; body paragraphs fall through to the same text heuristic.

Consequence, confirmed by the data: **`Title`, `ListItem`, and `Table` are recovered from
structure where the carrier provides it; `NarrativeText`-vs-`UncategorizedText` always goes
through the heuristic, in every carrier.**

## Findings

Confidence tags: **[3-rep]** = determinism-verified measurement; **[measured]** = single
computed value from the artifacts; **[mechanism]** = tied to source; **[refuted]** =
predicted-and-falsified.

### FINDING-01 — Per-type classification recall by format (main) [measured][3-rep]

Aggregate recall over the classification set (`metrics.json →
aggregate_by_format_classification_set`):

| Format | Title | NarrativeText | ListItem | Table |
|---|---|---|---|---|
| html | **1.000** (6/6) | 0.857 (6/7) | **1.000** (10/10) | **1.000** (1/1) |
| md | **1.000** (6/6) | 0.857 (6/7) | **1.000** (10/10) | **1.000** (1/1) |
| txt | **0.833** (5/6) | 0.857 (6/7) | **1.000** (10/10) | **0.000** (0/1) |
| docx | **1.000** (6/6) | 0.833 (5/6) | **1.000** (5/5) | **1.000** (1/1) |

(docx n differs because `d4_shortlist` has no DOCX rendering, so docx aggregates over
d1-d3.) Two structural gaps stand out — the `txt` **Title** miss and the `txt` **Table**
zero — both explained by FINDING-02/03.

### FINDING-02 — A verb-bearing heading is claimed by the narrative rule (dispatched before the title rule) in plain text [measured][mechanism]

The single `Title` that `txt` misses is `d3-over`, a heading that happens to contain verbs
("contains", "exceeding"). Outcome by format (`cross_format.json → d3_adversarial`):

| block | html | md | txt | docx |
|---|---|---|---|---|
| verb-bearing heading (intended Title) | `Title` | `Title` | **`NarrativeText`** | `Title` |

**The mechanism is the verb, not the word count.** In `partition_text`, `_text_to_element`
checks `is_possible_narrative_text` (text.py L149 → returns `NarrativeText`) **before**
`is_possible_title` (L155 → `Title`); `is_possible_narrative_text` matches any line that
carries a verb (and clears the cap/non-alpha ratios), so a verb-bearing heading is claimed
as `NarrativeText` and the title rule is never reached. The `title_max_word_length = 12`
cliff lives *inside* `is_possible_title`, which this line never gets to. html/md/docx pin
the same text to `Title` from the `<h1>` tag / Heading style, bypassing the heuristic
ordering entirely.

A 2×2 probe (`tests/probe_title_mechanism.py` → `probe_title_mechanism.json`) isolates
word-count from verb-presence in `partition_text`:

| line | words | has verb | → category | `is_possible_narrative_text` | `is_possible_title` |
|---|---:|:--:|---|:--:|:--:|
| "The team shipped the release" | 5 | yes | **NarrativeText** | True | True |
| "Quarterly regional vendor category summary" | 5 | no | **Title** | False | True |
| the `d3-over` shape | 13 | yes | **NarrativeText** | True | False |
| 13 nouns, no verb | 13 | no | **UncategorizedText** | False | False |

The two **verb** rows are `NarrativeText` at **both** 5 and 13 words — word count is
irrelevant when a verb is present (note the 5-word line is `NarrativeText` even though
`is_possible_title` would say True). The `12`-word boundary only governs the **no-verb**
rows (5 words → `Title`, 13 words → `UncategorizedText`). So the cross-format divergence for
`d3-over` is: **plain text runs the verb-first heuristic and calls a verb-bearing heading
`NarrativeText`; structural carriers assign `Title` from the tag/style.** This is the
"headings mislabeled as text in plain-text ingest" folklore, mechanism-corrected and
quantified.

### FINDING-03 — `Table` exists only where the carrier has a table construct [measured]

`Table` recall is 1.000 for html/md/docx and **0.000 for txt** (`d2_table`). In plain text
the table rows have no construct and are classified `Title` (`cross_format.json → d2_table`:
the table block is `Table` in html/md/docx, `Title` in txt; txt yields 5 elements vs 3).
This is not a defect so much as a format limit — plain text cannot carry a table — but it
is the largest single cross-format structural difference after the Markdown collapse, and
it means a `txt` ingest silently loses every table as mis-typed text.

### FINDING-04 — `NarrativeText` vs `UncategorizedText` is heuristic in EVERY format [measured][mechanism]

A **verbless but real** body sentence (`d3-verbless`: "A comprehensive catalogue of vendor
names, product categories, regional offices and contact records") is classified
`UncategorizedText` in **all four** carriers:

| block | html | md | txt | docx |
|---|---|---|---|---|
| verbless real sentence (intended NarrativeText) | `Uncat.` | `Uncat.` | `Uncat.` | `Uncat.` |
| verb-bearing control | `NarrativeText` | `NarrativeText` | `NarrativeText` | `NarrativeText` |

Because the `<p>`/paragraph body path runs `is_possible_narrative_text` in every carrier,
**structure does not rescue body-text typing** — the verb requirement demotes legitimate
prose that happens to lack a finite verb to the `UncategorizedText` bucket everywhere. This
is the pack's clearest *precision* limitation and it is format-independent (unlike Title,
which structure fixes). (A symbol-heavy line, `d3-nonalpha`, is *correctly* and
consistently `UncategorizedText` across all formats — not scored as a miss.)

### FINDING-05 — Cross-format consistency: clean content agrees 100%; divergence is localized [measured]

Per logical document, fraction of blocks where **all** carriers produce the same outcome /
where **all** match the intended type (`cross_format.json`):

| Doc | formats | all-agree | all-match-intent | element counts |
|---|---|---:|---:|---|
| d1_canonical (clean) | html,md,txt,docx | **1.000** | **1.000** | 11 / 11 / 11 / 11 |
| d2_table | html,md,txt,docx | 0.667 | 0.667 | 3 / 3 / **5** / 3 |
| d3_adversarial | html,md,txt,docx | 0.800 | 0.600 | 5 / 5 / 5 / 5 |
| d4_shortlist (md blank) | md,html,txt | **1.000** | **1.000** | 6 / 6 / 6 |
| d7_large (×60) | html,md,txt,docx | **1.000** | **1.000** | 660 each |

Pairwise agreement makes the pattern explicit: on d2/d3 the **structural formats agree with
each other 1.000** (html~md, html~docx, md~docx) while **`txt` is the outlier** (html~txt
0.8 on d3, 0.667 on d2). On well-formed content the four carriers are interchangeable; the
divergence concentrates in (a) the `txt` heuristic Title cliff, (b) the `txt` table loss,
and (c) — separately — the Markdown lazy-list collapse (FINDING-06).

### FINDING-06 — Markdown lazy lists collapse the whole list into one block [measured][mechanism]

The `#3280` shape — an intro **paragraph** immediately followed by a bullet list with **no
blank line** — folds the entire list into a single `NarrativeText` (`markdown_list_collapse`):

| Markdown variant | elements | ListItem recall |
|---|---:|---:|
| blank line before list (proper) | **6 / 6** | **1.000** |
| no blank line (lazy continuation) | **1 / 6** | **0.000** |

The five identical short items recover perfectly when a blank line precedes the list, and
vanish entirely without it — proving the loss is **Python-Markdown's block rule**, not an
unstructured mis-classification (the blank-line control is the isolation). Because
`partition_md` delegates block parsing to Python-Markdown, any Markdown that omits the
blank line silently loses its list structure. This is the single most destructive
cross-format outcome measured (6→1).

### FINDING-07 — DOCX list detection is robust across authoring modes — the old issue is fixed in 0.24.1 [measured][refuted]

Prediction (from KNOWN-ISSUE [#768]/[#1320]/[#3455]): only the `List Bullet` **style**
yields `ListItem`; `numPr`-only and manual "- " bullets fall through to `NarrativeText`.
**Falsified on 0.24.1** (`docx_bullet_mode_listitem`):

| docx bullet authoring | ListItem recall |
|---|---:|
| `List Bullet` style | **1.000** (5/5) |
| `numPr`-only (no List* style) | **1.000** (5/5) |
| manual "- " text, Normal style | **1.000** (5/5) |

All three authoring modes classify as `ListItem`. The historical "docx bullets →
NarrativeText" complaint does **not** reproduce on this version — a fair, non-cherry-picked
update to the known issue.

### FINDING-08 — Determinism: every run is stable [3-rep]

All **23** (doc, format) partition runs produced an **identical `(category, text)`
sequence across 3 repetitions** (`partition_raw.json → determinism.all_identical` = true
for every entry). The deterministic "header 1"→`NarrativeText` / "header 2"→`Title`
artifact seen in the pretest smoke test (5/5 identical) confirms the heuristics are
stable, not random — the divergences above are reproducible properties, not noise.

### FINDING-09 — Resource cost is model-dominated; memory floor is format-independent [measured]

Isolated subprocess per format on `d7_large` (660 elements, 6 reps; one representative
session in `resource_cost.json`):

| Format | cold 1st call | warm p50 | warm interval | peak RSS |
|---|---:|---:|---:|---:|
| html | 1041 ms | 734 ms | [723, 782] | 275 MB |
| md | 1018 ms | 770 ms | [744, 813] | 278 MB |
| txt | 1450 ms | 1283 ms | [1226, 1354] | 244 MB |
| docx | 1545 ms | 1143 ms | [1052, 1238] | 262 MB |

**Peak RSS sits in a narrow ~244-278 MB band regardless of format** — even the plain-text
heuristic path — i.e. memory is dominated by the spaCy/NLP + library load, not the document
or the parser; this is the robust, session-stable finding. Wall time carries a
**~150-500 ms cold model-load** on the first call and warm-p50 lands under ~1.3 s for 660
elements. **Timing order across formats is deliberately not concluded**: it is a single
session on a host that may run sibling evaluation workers in parallel, and it is not stable
run-to-run (an earlier session had `txt` mid-pack, this one has it slowest), so no
faster/slower verdict is drawn (methodology Part 2 §7). Re-running will reproduce the RSS
band and the sub-1.3 s warm scale, not the exact millisecond order.

## Novelty classification (闸门 1)

| Finding | Class | Evidence / anchor |
|---|---|---|
| Element typing is heuristic + imperfect | **DOCUMENTED** | docs; third-party write-ups |
| Per-format mechanism (tag vs style vs heuristic vs Python-Markdown) | **DOCUMENTED** | installed 0.24.1 source (cited) |
| Heuristic constants (12-word, verb req, 0.5 ratios) | **DOCUMENTED** | `text_type.py` |
| Dispatch order: narrative rule checked before title rule (verb-first) | **DOCUMENTED** | `text.py` L149 < L155 (readable in source) |
| md short-list / list mis-typing | **KNOWN-ISSUE** | [#3280] |
| docx bullets → NarrativeText | **KNOWN-ISSUE (historical)** → **REFUTED on 0.24.1** | [#768]/[#1320]/[#3455]; FINDING-07 |
| Per-type confusion matrix / P-R per format | **EXCLUSIVE** | FINDING-01, no public source labels blocks |
| Quantified cross-format consistency (same content ×4 carriers) | **EXCLUSIVE** | FINDING-05, unmeasured anywhere |
| Verb-bearing headings mis-typed NarrativeText in txt (quantified per-format misfire + 2×2 word/verb boundary demo) | **EXCLUSIVE** | FINDING-02 + probe (mechanism itself is DOCUMENTED; the measured cross-format misfire + isolation are the contribution) |
| Verb requirement demotes verbless prose in ALL formats | **EXCLUSIVE** | FINDING-04, quantified + format-independent |
| md lazy-list collapse quantified (6→1) + blank-line isolation | **EXCLUSIVE** (demonstration of a Python-Markdown rule) | FINDING-06 |
| Peak RSS ~244-278 MB band, format-independent (model-dominated) | **EXCLUSIVE** | FINDING-09 |

Zero-null note for EXCLUSIVE items: SERP (≈20), the official docs, and the issue tracker
(searched for `partition_html`/`partition_md`/`docx`/`ListItem`/`Title` misclassification)
contain qualitative claims and per-input anecdotes but **no labeled-ground-truth confusion
matrix and no same-content cross-format agreement number** — the quantifications above are
the contribution; every *existence* claim is tagged DOCUMENTED / KNOWN-ISSUE.

## Part 6 self-check (worker, pre-audit)

1. **赢家句 vs 自家表.** No "fastest/best" claim is made. The one timing ordering
   (html/md < txt < docx) is explicitly labeled indicative-single-session and **not** a
   verdict (FINDING-09); peak RSS sits in a narrow ~244-278 MB band and is called
   format-independent (model-dominated), not ranked. Recall/agreement numbers each cite the
   exact artifact cell.
2. **Claimed verification has an artifact.** Every number traces to
   `metrics.json` / `cross_format.json` / `resource_cost.json` / `partition_raw.json`; the
   scripts that produce them are in `tests/`. No "I verified" without a file.
3. **Instruments calibrated.** Determinism was checked (3 reps) *before* any single-run
   number was trusted (FINDING-08). RSS is measured in an **isolated subprocess per format**
   so a prior format's load cannot inflate it (Part 2 §6). The verb heuristic was
   calibrated with a known signal — `contains_verb` returns True on a verb sentence and
   False on a verbless one — before FINDING-04 relied on it. **FINDING-02's mechanism was
   not assumed**: a 2×2 word-count×verb probe (`probe_title_mechanism.py`) isolated the
   cause (verb-first dispatch, not the 12-word cliff) — a first draft wrongly credited the
   `title_max_word_length=12` limit, corrected after the probe showed a 5-word verb-bearing
   line is also `NarrativeText`.
4. **Attribution ruled out harness/fixture.** Two early anomalies were traced to the
   **harness, not unstructured**, and fixed: (a) an aggregate-recall crash to ~0.11 caused
   by non-zero-padded rep suffixes (`…r1` ⊂ `…r10`) creating false SPLIT/MERGE matches in
   d7 — fixed with prefix-free zero-padded sentinels; (b) an all-caps heading reported
   DROPPED because the sentinel was written upper-case while matching was case-sensitive —
   fixed with case-insensitive matching. The Markdown collapse (FINDING-06) was likewise
   isolated with a blank-line control to prove it is Python-Markdown, not the tool. The
   symbol-heavy line was **relabeled** to its defensible type so it is not counted as a
   fake miss.
5. **Novelty tags + self-eval-word lint.** Every finding carries a novelty class; the
   docx-bullet prediction is reported as refuted. `grep -iE
   'honest|independent|strongest|trustworthy'` over this file finds only this checklist line
   and the technical term "format-independent" (memory unaffected by carrier) — no
   self-awarded verdict adjectives on findings.

## Gaps / not tested (explicit)

- **PDF (all strategies), OCR, scanned images, `partition_image`, `hi_res`** — BLOCKED
  (tesseract/poppler absent; `partition_pdf` needs `unstructured_inference`/torch). No PDF
  or OCR number appears in this pack.
- **Auto `partition()` sniffing** — BLOCKED (libmagic absent); format-specific partitioners
  used instead.
- **Real-corpus accuracy** — out of scope; all fixtures are controlled synthetic documents.
- **Table *structure* recovery** (cells/rows as data) — only `Table` *presence* is measured,
  not cell-grid fidelity.
- **Chunking / `chunk_by_title`, embeddings, other languages** — out of scope.
- **Timing as a cross-format race** — deliberately not concluded (single session, possible
  sibling-worker contamination).

[#3280]: https://github.com/Unstructured-IO/unstructured/issues/3280
[#768]: https://github.com/Unstructured-IO/unstructured/issues/768
[#1320]: https://github.com/Unstructured-IO/unstructured/issues/1320
[#3455]: https://github.com/Unstructured-IO/unstructured/issues/3455
[#771]: https://github.com/Unstructured-IO/unstructured/issues/771
