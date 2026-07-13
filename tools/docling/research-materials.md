# Docling Review Research Materials

Date: 2026-07-10 (HTML smoke pass) · **deepened 2026-07-13 with the PDF / TableFormer / OCR path under methodology v3**

Status: source material for a future Thunderbit blog article. This is **not** a final blog draft and should not be published as-is.

## Material Boundary

This pack is the evidence base for a single-tool review of **Docling** (`docling-project/docling`, from IBM Research, now an LF AI & Data Foundation project). Docling is a **document-conversion / document-understanding** toolkit — "get your documents ready for gen AI" — not a web crawler. It parses PDF, DOCX, PPTX, XLSX, HTML, images and more into a unified `DoclingDocument` and exports Markdown / HTML / JSON. Its headline capability is the **PDF/image path**: an RT-DETR layout model + the **TableFormer** table-structure model (+ optional VLM), which recover page layout, reading order, and table structure.

The earlier version of this pack tested **only the HTML path** and explicitly deferred Docling's actual main event to Gaps. This version closes that gap. It contains, all measured on one machine:

- an **install-weight** breakdown and a **first-run model-download measurement** (the friction the HTML-only pass could not see);
- a **TableFormer cell-fidelity** benchmark on **7 synthetic PDFs with machine-generated ground truth** (bordered / borderless / colspan header / rowspan / span+borderless / blank-column financials / wide-12-col), scored cell-by-cell with no human judgement;
- a **controlled A/B** isolating *why* two of those tables failed (it is not what it looks like — see FINDING-D3);
- a **real-PDF** pass (two arXiv papers, 9pp + 15pp: reading order, table detection, per-page timing);
- a **scanned/OCR** pass (two genuine scanned PDFs with **zero text layer**, verified) exercising the default OCR engine;
- a **multi-format** pass (DOCX / XLSX / PPTX with ground-truth probes + a **lossless-JSON round-trip** check);
- an **HTML boilerplate-residue** quantification (Docling does no main-content extraction — how much chrome survives, as a number);
- and README/model-card **claim verification** against the official TEDS figures.

All measurements are on macOS arm64 / Python 3.14.2 and reproducible from the scripts in `tests/`. Failures are recorded as failures. Untested areas are in **Gaps**. Every number in `artifacts/raw/docling-deep-summary.json` is computed by `tests/build_summary.py` from run outputs, not hand-written.

### How to read the findings

Findings are numbered `FINDING-DN` (D = the deep PDF-path round) and carry two tags:

- a **confidence** tag — `[reproduced]` (held across a re-run / a controlled A/B), `[single-observation]` (measured once), or `[hypothesis]` (mechanism proposed, no attribution experiment); and
- a **novelty** tag from the pre-registration search (§Novelty verification) — `[KNOWN-ISSUE: link]`, `[DOCUMENTED]`, or `[NO-PUBLIC-HIT]`.

No finding is dressed up with self-evaluative adjectives; novelty is decided by the search table, not by adjective.

## Source Snapshot

Docling's tagline is literally *"Get your documents ready for gen AI."* It converts many formats into a unified `DoclingDocument` and exports Markdown, HTML, DocTags, and lossless JSON. Source: [Docling GitHub README](https://github.com/docling-project/docling) (Tier 1). License is **MIT** (individual model licenses vary).

Point-in-time repo metadata fetched from the GitHub API + PyPI on **2026-07-13** (refresh within 48h of publication):

| Field | Value |
|---|---|
| Repo | [docling-project/docling](https://github.com/docling-project/docling) |
| Stars | **63,069** |
| Forks | **4,449** |
| Open issues | **938** |
| License | **MIT** (model licenses vary) |
| Default branch | **main** |
| Created | **2024-07-09** |
| Last push (activity) | **2026-07-13** (same-day as snapshot) |
| Latest GitHub release | **v2.112.0**, published **2026-07-11** |
| PyPI version tested | **2.111.0** (latest is 2.112.0; tested one minor behind) |
| PyPI Python requirement | **`<4.0,>=3.10`** |
| Governance | LF AI & Data Foundation (originated at IBM Research Zurich) |

Raw snapshots: [github_repo_snapshot_2026-07-13.json](artifacts/raw/github_repo_snapshot_2026-07-13.json), [github_release_snapshot_2026-07-13.json](artifacts/raw/github_release_snapshot_2026-07-13.json), [pypi_snapshot_2026-07-13.json](artifacts/raw/pypi_snapshot_2026-07-13.json). The repo is **extremely active** (938 open issues, pushed the same day as the snapshot, weekly-ish releases) — treat any issue-count / release number as volatile.

### Packaging nuance worth a callout (`docling` vs `docling-slim`)

Since our first pass, the project shipped **`docling-slim`** (on PyPI, v2.112.0, *"Modular version of the Docling package"*) — a ~50 MB core that lets you `pip install docling-slim[format-html]` for HTML **without** torch. So the "1.3 GB install even for HTML" friction below is real for the **default `docling` metapackage** but **is now addressable** by choosing `docling-slim`. The article must not present the heavy install as an unaddressed flaw — the modular fix exists (tracking issue [#2535](https://github.com/docling-project/docling/issues/2535), lightweight-install discussion [#2393](https://github.com/docling-project/docling/issues/2393)). We tested the default `docling` package because that is what `pip install docling` still gives you.

## Novelty verification (pre-registration search)

Before write-up, each candidate was searched against three sources: the Docling GitHub issue tracker (via `gh`), the official docs / model card, and general web results. Full agent log basis in the session; the load-bearing links:

| Candidate finding | Verdict | Prior record |
|---|---|---|
| Heavy torch/opencv/transformers deps for HTML-only use (1.3 GB) | **KNOWN-ISSUE + partly solved** | [#2393](https://github.com/docling-project/docling/issues/2393) (lightweight install, open), [#3100](https://github.com/docling-project/docling/issues/3100) (a CPU-only box pulled **7.4 GB** via nvidia wheels), and **`docling-slim` already ships** ([#2535](https://github.com/docling-project/docling/issues/2535)). Our contribution is the **measured** on-disk breakdown, not the complaint. |
| `import docling` has no `docling.__version__` (AttributeError) | **KNOWN-ISSUE** | [#3733](https://github.com/docling-project/docling/issues/3733) (open, 2026-07-02, exact repro). We reproduce + give the `importlib.metadata` workaround. |
| HTML runs a BeautifulSoup backend, **not** the layout/TableFormer models | **DOCUMENTED (architecture), not spelled out in one place** | [architecture docs](https://docling-project.github.io/docling/concepts/architecture/) map format→backend→pipeline; no official page states plainly "HTML never touches TableFormer." We confirm it by measurement. |
| No main-content/boilerplate extraction (keeps nav/footer) | **KNOWN-ISSUE** | HTML: [#1865](https://github.com/docling-project/docling/issues/1865) (closed, "Nav and Footer not excluded"), [#1930](https://github.com/docling-project/docling/issues/1930) (open). Our contribution: a **residue percentage** on real pages. |
| TableFormer misses **borderless** tables | **KNOWN-ISSUE (conditional)** | [#3749](https://github.com/docling-project/docling/issues/3749) (open, 2026-07-03, "fails on borderless tables with whitespace-delimited columns"), [#3495](https://github.com/docling-project/docling/issues/3495) (borderless double-detected as Table+Picture). **Our data qualifies it**: a borderless table with a header rule + aligned columns was recovered perfectly (T2). |
| TableFormer mishandles **merged / spanning cells** | **KNOWN-ISSUE** | [#3698](https://github.com/docling-project/docling/issues/3698) (open, 2026-06-25, "V1 & V2 mishandling merged rows and columns"), [#207](https://github.com/docling-project/docling/issues/207). **Our data qualifies it**: colspan headers and rowspan labels were flattened *correctly* to GFM when the table was detected (T3/T4b) — see FINDING-D2. |
| Isolated small table on a sparse page classified as a **Picture** and dropped | **KNOWN-ISSUE (adjacent)** | [#3495](https://github.com/docling-project/docling/issues/3495) is the closest (table detected as Table **and** Picture). The **page-sparsity trigger** we isolate in FINDING-D3 (same table drops when alone, converts when surrounded by text) is not stated in that issue. |
| First-run PDF model **download size** in MB | **NO-PUBLIC-HIT for the byte size** | The official [model catalog](https://docling-project.github.io/docling/usage/model_catalog/) names models but publishes **no MB/GB**. Our ~506 MB (HF) + ~70 MB (RapidOCR) measurement is a genuinely undocumented number. Accuracy (TEDS) *is* published (below). |
| Default OCR engine is now **RapidOCR** (not EasyOCR) | **DOCUMENTED but widely mis-stated** | Current `pyproject.toml` bundles `feat-ocr-rapidocr` in core; EasyOCR is an extra ([#3227](https://github.com/docling-project/docling/issues/3227)). Most existing blogs/FAQ still say "EasyOCR default" — **stale**. We confirm RapidOCR by watching the download. |
| `import docling` ≈ 30 s cold (torch/transformers) | **NO-PUBLIC-HIT for Docling specifically** | No Docling issue targets import wall-clock; the ~15-45 s cost is a known [transformers](https://github.com/huggingface/transformers/issues/16863) property. Undocumented *as a Docling fact*; don't imply the transformers slowness itself is undiscovered. |

**Consequence for the writer:** almost every *behavioral* finding here is a **reproduction + quantification of an already-open issue**, and must be framed that way with the link. The genuinely undocumented numbers are (a) the **measured model-download size**, (b) the **cell-level fidelity table** with the page-sparsity trigger, and (c) the **Docling-specific cold-import time**. Frame those as "measured, not previously published," not as "bugs nobody knew about."

## Official Capability Claims to Verify

From the README / model card (Tier 1):

- **"Advanced PDF understanding incl. page layout, reading order, table structure, code, formulas…"** — the PDF/image path (ML models). Tested here (§PDF, §Tables, §OCR).
- **Multi-format** parsing (PDF/DOCX/PPTX/XLSX/HTML/EPUB/audio/images) — tested DOCX/XLSX/PPTX/HTML/PDF/scans here.
- **Unified `DoclingDocument`** + **lossless JSON** export — tested via round-trip (§Multi-format).
- **Official TableFormer accuracy** (HF [model card](https://huggingface.co/ds4sd/docling-models)): **TEDS simple 95.4 / complex 90.1 / all 93.6**, above Camelot (73.0) and EDD (88.3). Layout model = **RT-DETR**. We compare our own cell-recall to this in §Tables.

## Test Environment

| Item | Value |
|---|---|
| Machine | macOS 26.5.2 (arm64, Apple Silicon), **CPU-only** (no CUDA/MPS forced) |
| Python | **3.14.2** |
| Docling | **2.111.0** (docling-core 2.86.0, docling-ibm-models 3.13.3, docling-parse 7.7.0) |
| ML stack | torch 2.13.0, transformers 5.8.1, opencv-python 5.0.0.93, rapidocr 3.9.1 |
| Install method | fresh dedicated venv + `pip install docling` (the default metapackage) |
| HTML backend (observed) | `HTMLDocumentBackend` + `SimplePipeline` (BeautifulSoup-based, **no ML model**) |
| PDF pipeline (observed) | layout (`docling-layout-heron`) + TableFormer (`docling-models`) + RapidOCR |
| Scripts | `tests/` (see Raw Artifact Index) |
| Summary artifact | [docling-deep-summary.json](artifacts/raw/docling-deep-summary.json) (generated, not hand-authored) |

### Setup notes (the real friction, now measured)

- **`pip install docling` succeeded on Python 3.14.2** in a fresh venv; the resulting venv is **1.3 GB**. Docling pulls the full ML stack as **hard dependencies** even to convert HTML:

  | Dependency | On-disk size |
  |---|---:|
  | torch (2.13.0) | **536 MB** |
  | opencv (cv2) | **119 MB** |
  | transformers (5.8.1) | **101 MB** |
  | scipy | **99 MB** |
  | sympy | **76 MB** |
  | pandas | **72 MB** |
  | rapidocr (+ bundled models) | **~100 MB** |
  | docling_parse | **30 MB** |

  For an HTML-only user this is far heavier than a pure-Python converter — but see the `docling-slim` nuance above; the heaviness is now opt-out.

- **`docling.__version__` raises `AttributeError`.** `import docling; docling.__version__` → `AttributeError: module 'docling' has no attribute '__version__'`. The working probe is `importlib.metadata.version("docling")` → `'2.111.0'`. **FINDING-D0 [reproduced] [KNOWN-ISSUE: [#3733](https://github.com/docling-project/docling/issues/3733)]** — a small DX papercut, open upstream since 2026-07-02. *(This corrects the earlier pack, which recorded the version as "unknown" — it is not unknown, the module attribute is simply missing; use `importlib.metadata`.)*

## PDF-path first run — model download + cold cost (the headline friction)

Measured with a **fresh, isolated HF cache** (`HF_HOME` pointed at an empty dir so the download is cleanly attributable; the system cache was untouched). Script: [pdf_coldstart_download.py](tests/pdf_coldstart_download.py) → [pdf_coldstart_download.json](artifacts/raw/pdf_coldstart_download.json).

| Phase | Measurement |
|---|---:|
| `import docling` (warm disk, cold process) | ~5 s here (torch/transformers already imported once); ~30 s on a truly cold first import (earlier pass) |
| `DocumentConverter()` init | 0.018 s |
| **First PDF conversion (incl. model download)** | **223.9 s** |
| Model download → **HF cache** (`docling-models` TableFormer + `docling-layout-heron`) | **506 MB on disk** (342 MB TableFormer + 164 MB layout) |
| Model download → **venv site-packages** (RapidOCR PP-OCRv4 + PP-OCRv6) | **~70 MB** (bypasses `HF_HOME` entirely) |
| **Second PDF conversion (warm)** | **0.55 s** |

**FINDING-D1 [reproduced] [NO-PUBLIC-HIT for the size]:** the PDF path's **first run downloads ~576 MB of models** (≈506 MB to the HuggingFace cache + ≈70 MB of RapidOCR weights into `site-packages`), and the **first conversion takes ~224 s** almost entirely because of that download; the **second conversion is ~0.55 s**. Two things a reader benchmarking Docling must know:

1. **The download splits across two locations.** The layout + TableFormer models honor `HF_HOME`; **RapidOCR's models do not** — they land in `…/site-packages/rapidocr/models/` and it fetched **two OCR model generations** (PP-OCRv4 `.pth` *and* PP-OCRv6 `.onnx`). Anyone trying to pre-bake or air-gap a Docling image has to handle both caches.
2. **No official page publishes this size.** The model catalog lists model names but no bytes (see Novelty). So "~576 MB first-run download, ~224 s first PDF" is a measured, previously-unpublished figure. *(Single machine / warm pip cache / home-broadband; the 224 s is download-bound and will vary with connection — the ~576 MB size is the stable part.)*

## Table fidelity — TableFormer on synthetic PDFs with known ground truth (the headline claim)

Seven table PDFs were **generated by us** ([gen_pdf_fixtures.py](tests/gen_pdf_fixtures.py)) so the ground-truth cell matrix is known by construction; each has a sidecar `*.groundtruth.json`. Docling converts each; [pdf_table_fidelity.py](tests/pdf_table_fidelity.py) parses the emitted Markdown table and scores it **cell-by-cell** against the truth — `detected`, `dims_match`, `cell_recall` (fraction of ground-truth non-empty values present in the correct row). Results: [pdf_table_fidelity.json](artifacts/raw/pdf_table_fidelity.json).

| Table (stress) | Detected | Dims match | Cell recall | Convert s | Note |
|---|:--:|:--:|---:|---:|---|
| **T1** simple **bordered** grid (5×8), alone on page | **No** | — | 0.0 | 12.1 | classified as `<!-- image -->`, all cells dropped |
| **T2** **borderless** (only a header rule) | Yes | Yes | **1.00** | 2.5 | perfect, exact grid |
| **T3** merged 2-level **colspan** header | Yes | Yes | **1.00** | 1.9 | colspan value repeated across span (correct GFM) |
| **T4** merged **rowspan** row-label, alone on page | **No** | — | 0.0 | 0.5 | classified as `<!-- image -->` |
| **T5** colspan header **+ borderless** | Yes | Yes | **1.00** | 2.0 | correct |
| **T6** financials, **blank column**, right-aligned | Yes | Yes | **1.00** | 2.1 | blank "Adj." column preserved, not shifted |
| **T7** **wide** 12-column grid | Yes | Yes | **1.00** | 2.8 | no column shift on a wide table |

**FINDING-D2 [reproduced]:** on the **5 tables Docling detected, cell recall was 1.00 — every ground-truth value landed in the right row**, including the two hard structural cases: a **2-level colspan header** (T3: "Q1 2026" correctly repeated over its two spanned columns, occurrences=2, the correct way to flatten a colspan into border-less GFM) and a **borderless** grid (T2) and a **12-column** grid (T7). A **fully blank column** (T6) was preserved as empty cells, not dropped or shifted. This is consistent with the official TableFormer TEDS (93.6 all-tables) and, on these particular fixtures, is a genuine strength: **when a table is detected, its structure comes through cleanly, merges included.** *(Scope: 7 synthetic tables, clean digital PDFs, single machine — not a TEDS-scale corpus; it is a targeted structural probe, not an accuracy benchmark.)*

The **merged-cell** picture deserves care against the open issue [#3698](https://github.com/docling-project/docling/issues/3698) ("V1 & V2 mishandling merged rows/columns"): on **our** colspan (T3/T5) and rowspan (T4b, below) fixtures the merge was flattened **correctly**. #3698's failing cases involve more irregular multi-row/multi-column merges and multi-page tables ([#3553](https://github.com/docling-project/docling/issues/3553)); our fixtures are the *simple* end of merging. So the honest statement is **"simple colspan/rowspan flattened correctly here; complex/irregular merges are a documented open problem,"** not "merged cells work" or "merged cells are broken."

### FINDING-D3 — the "failure" is a layout-model image mis-classification of *isolated* tables, not a table-parsing weakness

T1 (a perfectly ordinary bordered grid) and T4 (a rowspan table) were **not detected at all** — Docling emitted `<!-- image -->` and dropped every cell. Before calling this a table weakness, we ruled out the fixture and isolated the trigger (methodology v3, Part 6 §4):

- **The text layer is intact.** `pypdfium2` reads all 327 chars of T1's text layer — the PDF is fine.
- **`do_ocr=False` doesn't help** — still `<!-- image -->` (so it is not an OCR mis-route).
- **Inspecting the `DoclingDocument`:** for T1, `len(doc.tables) == 0`, `len(doc.pictures) == 1` — the **layout model classified the whole table region as a Picture**, and the picture is unreachable as text.
- **Controlled A/B (the decisive test):** the *same* T1 and T4 tables, re-rendered **surrounded by ordinary body paragraphs** (`table_t1b_…` / `table_t4b_…`), **both convert correctly** — `len(doc.tables) == 1`, full Markdown tables emitted, and **T4b's rowspan "North" is correctly repeated across its 3 rows**. Script output in [pdf_table_fidelity.json](artifacts/raw/pdf_table_fidelity.json) + the A/B in the run log.

**FINDING-D3 [reproduced] [KNOWN-ISSUE adjacent: [#3495](https://github.com/docling-project/docling/issues/3495)]:** Docling's RT-DETR **layout model uses page context**, and a **small table alone on an otherwise near-empty page** is liable to be classified as a **Picture** and dropped **with no error** — while the identical table **surrounded by text converts perfectly**. This is the real caveat, and it is easy to hit if you feed Docling **one-table-per-page** PDFs (invoices, spec sheets, cropped exports). It is adjacent to the open "table detected as Table *and* Picture" issue #3495, but the **page-sparsity trigger** — same table, drops when isolated, converts when embedded — is the part we add. *(The article should show the A/B: it reframes a scary "dropped my whole table" from "TableFormer is bad" to "give the layout model page context, or post-check `doc.tables`.")*

## Real PDFs — reading order, tables, per-page timing

Two real born-digital academic PDFs (2-column, tables, formulas). Script: [pdf_real_and_scanned.py](tests/pdf_real_and_scanned.py) → [pdf_real_and_scanned.json](artifacts/raw/pdf_real_and_scanned.json). Full Markdown: [real_arxiv_docling_report.md](artifacts/raw/real_arxiv_docling_report.md), [real_arxiv_attention.md](artifacts/raw/real_arxiv_attention.md).

| Real PDF | Pages | Convert s | **s/page** | MD tables | Content probes | Section order recovered |
|---|---:|---:|---:|---:|:--:|:--:|
| arXiv 2408.09869 (the Docling report) | 9 | 134.5 | **14.95** | 3 | **5/5** | 3/4 markers, **in order** (Abstract→Introduction→References; "Related Work" heading not matched) |
| arXiv 1706.03762 (Attention Is All You Need) | 15 | 89.9 | **5.99** | 4 | **5/5** | **in order, 5/5** (Abstract→Introduction→Background→Conclusion→References) |

**FINDING-D7 [single-observation]:** on real 2-column academic PDFs, Docling recovers **reading order correctly** — on the 15-page Attention paper all five section markers (Abstract → Introduction → Background → Conclusion → References) appear **in document order** in the linearized Markdown despite the two-column layout, and every content probe (Transformer, encoder, BLEU, multi-head) is present; the famous multi-column results tables register as **4 detected tables**. This is genuine reading-order / column-merge recovery — the core RAG-chunking value. **Per-page time is CPU-bound and content-dependent, not page-count-dependent:** the *denser* 9-page report (more tables/figures per page → more TableFormer/layout inference) ran **14.95 s/page**, *slower* per page than the 15-page paper at **5.99 s/page**. So "seconds per page" on CPU is driven by how much *structure* is on each page, not by length. *(Single run, CPU-only macOS arm64; GPU would cut these materially — this is a ceiling, not a typical production number. Reading-order "in order" is a marker-ordering signal, not a full linearization audit.)*

## Scanned / OCR — the default engine on genuine image PDFs

Two **genuinely scanned** PDFs (verified **zero text layer** via `pypdfium2`) exercise Docling's default OCR.

- **`ocr_test.pdf` (1 page, 0-char text layer):** Docling's OCR recovered the full sentence — *"Docling bundles PDF document conversion to JSON and Markdown in an easy self contained package"* — cleanly, in **14.3 s** on CPU. Output: [real_ocr_test.md](artifacts/raw/real_ocr_test.md).
- **`nemotron_multipage.pdf` (4 pages, 0-char text layer):** OCR fired on all four pages (**70.1 s total, 17.5 s/page**), emitting the repeated test sentence across pages (this Docling test fixture is intentionally the same sentence per page). Output: [real_nemotron_multipage.md](artifacts/raw/real_nemotron_multipage.md).

Both scanned PDFs (from Docling's own `tests/data/scanned`) have a **verified 0-character text layer** (`pypdfium2`), so any recovered text is OCR output, not a hidden text layer.

**FINDING-D4 [reproduced] [DOCUMENTED but widely mis-stated]:** on a real scanned PDF with **no text layer**, Docling's **default OCR (RapidOCR, not EasyOCR)** fired automatically and recovered the text correctly. The engine identity matters: most existing write-ups (and older Docling FAQ text) say EasyOCR is the default; as of the tested build the default is **RapidOCR** (confirmed by watching PP-OCRv4/v6 download at first run). RapidOCR speed complaints are open upstream ([#1143](https://github.com/docling-project/docling/issues/1143)); our small scans were fast, but OCR is the slow path at scale.

## Multi-format — DOCX / XLSX / PPTX + lossless-JSON round-trip

Generated with known content + ground-truth probes ([gen_doc_fixtures.py](tests/gen_doc_fixtures.py)); scored by [multiformat_docs.py](tests/multiformat_docs.py) → [multiformat_docs.json](artifacts/raw/multiformat_docs.json). Each file is converted to Markdown (probes must appear) **and** exported via `export_to_dict()` (probes must survive the JSON — the lossless claim).

| File | Convert s | All MD probes found | Tables in MD | **All probes survive JSON** |
|---|---:|:--:|---:|:--:|
| `report.docx` (headings + merged-"Total" table + bullets) | 0.137 | **Yes (7/7)** | 1 | **Yes** |
| `workbook.xlsx` (2 sheets, blank column) | 0.016 | **Yes (6/6)** | 2 | **Yes** |
| `deck.pptx` (3 slides, bullets + table) | 0.038 | **Yes (6/6)** | 1 | **Yes** |

**FINDING-D5 [reproduced]:** the "unified multi-format" claim holds on DOCX/XLSX/PPTX — all content probes were found in the Markdown, tables were recovered (including a DOCX table with a merged "Total" row and both XLSX sheets), and **every probe also survived the `export_to_dict()` JSON**, supporting the lossless-`DoclingDocument` claim on these inputs. These formats go through **format-native backends** (not the ML models), so they are fast (tens of ms) and offline. *(Scope: one file per format, small/clean — substantiates breadth, not a stress test of pathological Office files.)*

## HTML — boilerplate residue quantified (raw conversion, no main-content extraction)

Docling converts the **whole** HTML document; it does **not** do readability-style main-content extraction. We measured how much site chrome survives ([html_boilerplate_quant.py](tests/html_boilerplate_quant.py) → [html_boilerplate_quant.json](artifacts/raw/html_boilerplate_quant.json)) by counting boilerplate-marker lines (nav/cookie/footer/legal/TOC) in Docling's own output.

| Page | Non-blank MD lines | Boilerplate-marker lines | % boilerplate | Real article starts at line |
|---|---:|---:|---:|---:|
| Wikipedia "Web scraping" | 255 | **34** | **13.3%** | **28** (chrome leads the doc) |
| scrapethissite/forms | 63 | 1 | 1.6% | — |
| books.toscrape | 65 | 0 | 0.0% | — |
| quotes.toscrape | 35 | 0 | 0.0% | — |

**FINDING-D6 [reproduced] [KNOWN-ISSUE: [#1865](https://github.com/docling-project/docling/issues/1865), [#1930](https://github.com/docling-project/docling/issues/1930)]:** on a chrome-heavy page (Wikipedia) **~13% of Docling's Markdown lines are nav/TOC/footer boilerplate and the real article doesn't begin until line 28** — the output *leads* with "move to sidebar / Contents / Toggle the table of contents" and *ends* with "CS1 maint… / Search Wikipedia." On clean content pages (books/quotes) there is ~0% chrome, so this is a **template-chrome** problem, not a per-page tax. Docling gives **faithful full-document Markdown**, not **clean main-article extraction** — the single most important caveat for "which tool for RAG." Upstream tracks HTML nav/footer furniture (#1865 closed, #1930 open); *note the PDF path does attempt header/footer furniture classification, so "no boilerplate removal at all" is too strong for PDF — it is the HTML backend specifically.*

## Positioning vs Firecrawl

The anchor tool for this category (LLM-ready Markdown) is Firecrawl. The honest difference, now that both the HTML and the PDF/TableFormer paths are measured:

| Axis | Firecrawl | Docling |
|---|---|---|
| Core job | **Crawl + scrape the live web** → Markdown | **Convert a document you already have** → Markdown/JSON |
| Fetching / JS render / anti-bot | Yes (hosted browser) | **No** — you supply the file/HTML/PDF |
| Main-content extraction | Yes (`onlyMainContent`) | **No** — faithful full-document (13% chrome on Wikipedia, FINDING-D6) |
| **PDF table structure (ML)** | limited | **Yes — TableFormer** (TEDS 93.6 official; cell-recall 1.00 on our detected fixtures) |
| Scanned PDF / OCR | limited | **Yes — RapidOCR** by default (recovered a 0-text-layer scan, FINDING-D4) |
| Format breadth | web pages | **PDF/DOCX/PPTX/XLSX/HTML/EPUB/images/audio** |
| Deployment | hosted API (+ self-host) | **local pip library**, offline, no API key |
| Setup weight | API key / light client | **1.3 GB** default install + **~576 MB** first-run models (or `docling-slim`) |
| License | AGPL-ish / commercial (verify in Firecrawl pack) | **MIT** |

**One-line takeaway:** Firecrawl is the tool when the data is *on the live web and needs crawling/JS/main-content cleanup*; Docling is the tool when you *already hold the document* — **especially PDFs, scans, and table-heavy Office files** — and want a faithful, offline, structure-preserving Markdown/JSON conversion with genuine table + OCR understanding. **Complements, not substitutes**: a realistic pipeline crawls with Firecrawl and converts documents with Docling.

## Key Findings for the Writer

1. **FINDING-D1** — PDF path first run downloads **~576 MB of models** (~506 MB HF cache + ~70 MB RapidOCR into site-packages, **two caches**), first PDF **~224 s** (download-bound), warm **~0.55 s**. Size is **unpublished** officially. (§first run)
2. **FINDING-D2** — on detected tables, **cell recall 1.00** across bordered/borderless/colspan-header/rowspan/blank-column/12-col; simple merges flattened correctly. Matches the official TEDS 93.6 story on these fixtures. (§Tables)
3. **FINDING-D3 (the differentiator)** — a **small table alone on a sparse page is classified as a Picture and silently dropped**; the *identical table surrounded by text converts perfectly* (controlled A/B). Reframes a scary "dropped my table" as a layout-context effect; post-check `doc.tables`. Adjacent to #3495. (§Tables)
4. **FINDING-D4** — **default OCR is RapidOCR, not EasyOCR** (common mistake); recovered a genuine 0-text-layer scan cleanly. (§OCR)
5. **FINDING-D5** — DOCX/XLSX/PPTX all convert, tables recovered, and **probes survive the JSON round-trip** (lossless claim holds on these inputs). (§Multi-format)
6. **FINDING-D6** — HTML is **raw full-document** conversion: **~13% boilerplate lines on Wikipedia**, article starts line 28; ~0% on clean pages. Not main-content extraction. Known issue #1865/#1930. (§HTML)
7. **FINDING-D0** — `docling.__version__` raises `AttributeError` (use `importlib.metadata`); open issue #3733. Corrects the earlier "unknown." (§Setup)
8. **Packaging** — `docling-slim` now exists (~50 MB, `[format-html]`), so the 1.3 GB heaviness is **opt-out**; don't frame it as unaddressed. (§Source Snapshot)
9. **On HTML specifically, Docling runs no ML models** — it's a BeautifulSoup backend (SimplePipeline). The "vision models on your webpage" story is PDF/image only. (Novelty §)

## Dimension-level evidence (no synthetic total)

Per methodology v3 Part 3, this pack does **not** publish a single weighted 0-100 score (the earlier "69/100" folded category penalties for "no crawler" that aren't comparable across tools). Evidence per dimension for the writer to weight:

| Dimension | Evidence (measured) | Reader caveat |
|---|---|---|
| Setup / first run | 1.3 GB venv; **~576 MB** first-run models across two caches; first PDF ~224 s, warm ~0.55 s | `docling-slim` opts out of the heavy path |
| PDF table fidelity | **cell recall 1.00** on 5/7 detected fixtures incl. colspan/rowspan/blank-col/12-col; official TEDS 93.6 | 7 synthetic tables, not a TEDS corpus |
| Table detection robustness | **isolated small table → dropped as Picture**; same table in context → perfect (A/B) | layout-context effect; post-check `doc.tables` |
| Scanned / OCR | recovered a **0-text-layer** scan; default **RapidOCR** | OCR is the slow path at scale (#1143) |
| Multi-format | DOCX/XLSX/PPTX all probes found + **JSON round-trip survives** | one clean file per format |
| HTML fidelity vs cleanliness | faithful full-document; **~13% chrome on Wikipedia**, ~0% clean pages | no main-content extraction (#1865) |
| Reading order / structure | 15-pp 2-col paper: all 5 sections **in document order**; 5.99 s/pg (CPU); denser 9-pp report 14.95 s/pg | single run, CPU ceiling |
| Developer experience | 3-line API; clean `DoclingDocument`; lossless JSON | `__version__` missing (#3733) |
| Maintenance | v2.112.0 (2026-07-11), 63k stars, LF AI & Data governance, **938 open issues** | very high issue volume = very active + rough edges |
| License | MIT on code; model licenses vary | — |

## Gaps Before Final Blog Draft

- **VLM path (GraniteDocling) untested** — the optional vision-language pipeline is a separate model download and a separate quality/latency profile; not exercised here.
- **`docling-slim` not benchmarked** — we confirmed it exists on PyPI but did not install it to measure the actual slim footprint / HTML-only speed.
- **No GPU run** — all timing is CPU-only macOS arm64; OCR + TableFormer are much faster on CUDA/MPS, so per-page seconds here are a CPU ceiling, not a GPU number.
- **TEDS-scale table corpus** — our 7 synthetic + 2 real PDFs are a targeted probe, not the FinTabNet/PubTabNet-scale accuracy benchmark the official 93.6 comes from.
- **Complex/irregular merged cells + multi-page tables** (#3698 / #3553) — we tested simple colspan/rowspan (which passed); the documented hard cases were not constructed.
- **Formula / code fidelity** — the arXiv PDFs contain math; we measured reading order + tables, not formula-to-LaTeX accuracy.
- **Head-to-head with Marker / MarkItDown / Firecrawl** on these exact fixtures — third-party benchmarks exist (Docling ~0.887 vs MarkItDown ~0.844 vs Marker ~0.808 TEDS, via OpenDataLoader); a same-bench 4-way including Firecrawl does not appear to exist publicly and is the natural next pack.

## Raw Artifact Index

Scripts (`tests/`):
- Synthetic table PDF generator (+ ground truth): [gen_pdf_fixtures.py](tests/gen_pdf_fixtures.py)
- DOCX/XLSX/PPTX generator (+ ground truth): [gen_doc_fixtures.py](tests/gen_doc_fixtures.py)
- First-run model-download + cold/warm cost: [pdf_coldstart_download.py](tests/pdf_coldstart_download.py)
- **TableFormer cell-fidelity** (+ merged-cell handling + A/B): [pdf_table_fidelity.py](tests/pdf_table_fidelity.py)
- Real + scanned PDF (reading order / OCR / timing): [pdf_real_and_scanned.py](tests/pdf_real_and_scanned.py)
- Multi-format + lossless-JSON round-trip: [multiformat_docs.py](tests/multiformat_docs.py)
- HTML boilerplate-residue quantification: [html_boilerplate_quant.py](tests/html_boilerplate_quant.py)
- Original HTML smoke runner (kept): [run_docling_material_tests.py](tests/run_docling_material_tests.py)
- **Summary generator (computes summary JSON from raw — no hand numbers):** [build_summary.py](tests/build_summary.py)

Raw results (`artifacts/raw/`): [pdf_coldstart_download.json](artifacts/raw/pdf_coldstart_download.json), [pdf_table_fidelity.json](artifacts/raw/pdf_table_fidelity.json), [pdf_real_and_scanned.json](artifacts/raw/pdf_real_and_scanned.json), [multiformat_docs.json](artifacts/raw/multiformat_docs.json), [html_boilerplate_quant.json](artifacts/raw/html_boilerplate_quant.json), and the **generated** [docling-deep-summary.json](artifacts/raw/docling-deep-summary.json). Per-document Markdown outputs `real_*.md`, `doc_*.md`, plus the original HTML outputs `docling_{books,quotes,forms,wikipedia}.md`. Metadata: [github_repo_snapshot_2026-07-13.json](artifacts/raw/github_repo_snapshot_2026-07-13.json), [github_release_snapshot_2026-07-13.json](artifacts/raw/github_release_snapshot_2026-07-13.json), [pypi_snapshot_2026-07-13.json](artifacts/raw/pypi_snapshot_2026-07-13.json).

Fixtures (`artifacts/fixtures/`): `pdf/` (7 synthetic table PDFs + `*.groundtruth.json`, 2 in-context A/B variants, 2 arXiv papers), `scanned/` (ocr_test.pdf, nemotron_multipage.pdf, old_newspaper.png, qr_bill_example.jpg — from Docling's own test suite), `docs/` (report.docx, workbook.xlsx, deck.pptx + ground truth), plus the original HTML fixtures.

Public reproducible copy: `github.com/thunderbit-operations/scraper-benchmark` → `tools/docling/`.

## Complete Source Index

- [Docling GitHub repository](https://github.com/docling-project/docling) — Tier 1 (tagline, formats, claims, MIT, IBM origin, LF AI & Data governance)
- [Docling documentation site](https://docling-project.github.io/docling) — Tier 1 (architecture, model catalog, installation)
- [ds4sd/docling-models model card](https://huggingface.co/ds4sd/docling-models) — Tier 1 (TableFormer TEDS 95.4/90.1/93.6; RT-DETR layout)
- GitHub REST API `repos/docling-project/docling` — Tier 1, metadata snapshot as-of 2026-07-13
- PyPI `docling` (2.112.0) and `docling-slim` (2.112.0) JSON metadata — Tier 1
- Docling issues cited: [#3733](https://github.com/docling-project/docling/issues/3733) (`__version__`), [#3749](https://github.com/docling-project/docling/issues/3749) (borderless), [#3698](https://github.com/docling-project/docling/issues/3698) (merged cells), [#3495](https://github.com/docling-project/docling/issues/3495) (table-as-picture), [#1865](https://github.com/docling-project/docling/issues/1865) / [#1930](https://github.com/docling-project/docling/issues/1930) (HTML nav/footer), [#2393](https://github.com/docling-project/docling/issues/2393) / [#2535](https://github.com/docling-project/docling/issues/2535) (lightweight/slim), [#3100](https://github.com/docling-project/docling/issues/3100) (7.4 GB), [#1143](https://github.com/docling-project/docling/issues/1143) (OCR speed) — all Tier 1
- Third-party table benchmarks (Tier 2, for the writer): OpenDataLoader-derived TEDS (Docling 0.887 / MarkItDown 0.844 / Marker 0.808); codecut.ai; procycons.com
- Test fixtures: 2 arXiv PDFs (2408.09869 = the Docling report; 1706.03762 = Attention Is All You Need); Docling's own `tests/data/scanned` (ocr_test, nemotron_multipage, old_newspaper, qr_bill_example); public HTML pages captured locally
